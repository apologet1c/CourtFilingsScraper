"""One-shot OSCN eviction docket scraper: date range in -> raw HTML in S3 + case-count reports out.

Event:
{
  "start_date": "2023-01-01",
  "end_date":   "2023-12-31",
  "judge": "1058",                      # one judge for the whole range, OR:
  "judges": [                           # judge ids by date window (inclusive; open-ended ok)
    {"id": "1001", "from": "2023-01-01", "to": "2023-06-30"},
    {"id": "1058", "from": "2023-07-01"}
  ],
  "report_name": "2023",                # optional; default "<start>_<end>"
  "overwrite": false,                   # optional; re-download pages already saved
  "weekdays_only": true                 # optional
}

Env: S3_BUCKET, OSCN_KEY, OSCN_KEY_HEADER (header name the key goes in),
     OSCN_DB=Tulsa, REQUEST_DELAY_SECONDS=1.0, USER_AGENT.
     Leave S3_BUCKET unset to write to ./out instead (handy for a local run:
     `python handler.py event.json`).

Pages already saved are skipped, so if a run dies, just run the same event again.
If Lambda is about to time out, it re-invokes itself with an "offset" to keep going,
then builds the report on the last leg.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from docket_parser import parse_docket, is_complete, scheduled_date
from report import build_reports, summary, to_csv

log = logging.getLogger()
log.setLevel(logging.INFO)

BUCKET = os.environ.get("S3_BUCKET", "")
LOCAL_DIR = Path(os.environ.get("LOCAL_OUT_DIR", "out"))
DB = os.environ.get("OSCN_DB", "Tulsa")
DELAY = float(os.environ.get("REQUEST_DELAY_SECONDS", "1.0"))
TIME_RESERVE_MS = 60_000
MAX_CHAIN = 50


# ------------------------------------------------------------------ storage (S3 or local)

if BUCKET:
    import boto3
    from botocore.exceptions import ClientError
    _s3 = boto3.client("s3")

    def save(key: str, body: str, content_type: str = "text/html") -> None:
        _s3.put_object(Bucket=BUCKET, Key=key, Body=body.encode("utf-8"), ContentType=content_type)

    def load(key: str) -> str | None:
        try:
            return _s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode("utf-8")
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise

    def exists(key: str) -> bool:
        try:
            _s3.head_object(Bucket=BUCKET, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise
else:
    def save(key: str, body: str, content_type: str = "") -> None:
        p = LOCAL_DIR / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")

    def load(key: str) -> str | None:
        p = LOCAL_DIR / key
        return p.read_text(encoding="utf-8") if p.exists() else None

    def exists(key: str) -> bool:
        return (LOCAL_DIR / key).exists()


def page_key(judge: str, day: date) -> str:
    return f"raw/{DB}/judge={judge}/{day:%Y}/{day.isoformat()}.html"


# ------------------------------------------------------------------ OSCN

def docket_url(judge: str, day: date) -> str:
    return "https://www.oscn.net/applications/oscn/report.asp?" + urllib.parse.urlencode({
        "report": "WebJudicialDocketJudgeAll", "errorcheck": "true", "db": DB, "Judge": judge,
        "database": "", "StartDate": f"{day.month}/{day.day}/{day:%y}",
        "GeneralNumber": "1", "generalnumber1": "1", "GeneralCheck": "on",
    })


def fetch(url: str, tries: int = 3) -> str:
    headers = {"User-Agent": os.environ.get("USER_AGENT", "CourtFilingsScraper/1.0")}
    if os.environ.get("OSCN_KEY"):
        headers[os.environ["OSCN_KEY_HEADER"]] = os.environ["OSCN_KEY"]
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                html = r.read().decode("ISO-8859-1")  # OSCN serves ISO-8859-1
            if "captcha" in html.lower():
                raise PermissionError("OSCN returned a CAPTCHA; check OSCN_KEY / OSCN_KEY_HEADER")
            return html
        except PermissionError:
            raise
        except Exception as e:
            if attempt == tries - 1:
                raise
            log.warning("retrying %s: %s", url, e)
            time.sleep(5 * (attempt + 1))


# ------------------------------------------------------------------ plan

def plan(event: dict) -> list[tuple[str, date]]:
    """Every (judge_id, day) to fetch, in date order."""
    start, end = date.fromisoformat(event["start_date"]), date.fromisoformat(event["end_date"])
    if "judges" in event:
        windows = [(str(j["id"]),
                    date.fromisoformat(j.get("from") or event["start_date"]),
                    date.fromisoformat(j.get("to") or event["end_date"])) for j in event["judges"]]
    elif "judge" in event:
        windows = [(str(event["judge"]), start, end)]
    else:
        raise ValueError('event needs "judge" or "judges"')
    weekdays_only = event.get("weekdays_only", True)
    out, d = [], start
    while d <= end:
        if not weekdays_only or d.weekday() < 5:
            out += [(j, d) for j, a, b in windows if a <= d <= b]
        d += timedelta(days=1)
    if not out:
        raise ValueError("no judge covers any day in the range; check the judges windows")
    return out


# ------------------------------------------------------------------ steps

def scrape(pairs, event, context) -> int | None:
    """Fetch missing pages. Returns the offset to resume from if time ran out, else None."""
    for i in range(int(event.get("offset", 0)), len(pairs)):
        if context and context.get_remaining_time_in_millis() < TIME_RESERVE_MS:
            return i
        judge, day = pairs[i]
        key = page_key(judge, day)
        if not event.get("overwrite") and exists(key):
            continue
        url = docket_url(judge, day)
        time.sleep(DELAY)
        try:
            html = fetch(url)
        except PermissionError:
            raise
        except Exception as e:
            log.error("giving up on %s %s: %s", judge, day, e)
            continue
        got = scheduled_date(html)
        if not is_complete(html) or (got and got != day):
            log.error("bad page for %s %s (complete=%s, date=%s); not saved", judge, day, is_complete(html), got)
            continue
        save(key, html)
        log.info("%d/%d saved %s", i + 1, len(pairs), key)
    return None


def make_report(pairs, event) -> dict:
    cases, scraped, missing = [], [], []
    for judge, day in pairs:
        html = load(page_key(judge, day))
        if html is None:
            missing.append(f"{day.isoformat()} judge {judge}")
            continue
        scraped.append((day.isoformat(), judge))
        cases += parse_docket(html, judge)

    reports = build_reports(cases, scraped)
    name = event.get("report_name") or f"{event['start_date']}_{event['end_date']}"
    base = f"reports/{DB}/{name}"
    for table, rows in reports.items():
        save(f"{base}/{table}.csv", to_csv(rows), "text/csv")
    result = {**summary(reports), "missing_pages": missing,
              "output": f"s3://{BUCKET}/{base}/" if BUCKET else str(LOCAL_DIR / base),
              "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    save(f"{base}/summary.json", json.dumps(result, indent=2), "application/json")
    return result


def lambda_handler(event, context=None):
    pairs = plan(event)
    resume_at = scrape(pairs, event, context)
    if resume_at is not None:
        depth = event.get("chain_depth", 0) + 1
        if depth > MAX_CHAIN:
            raise RuntimeError(f"chain limit hit; rerun the same event to continue (offset {resume_at})")
        import boto3
        boto3.client("lambda").invoke(
            FunctionName=context.invoked_function_arn, InvocationType="Event",
            Payload=json.dumps({**event, "offset": resume_at, "chain_depth": depth}).encode())
        return {"status": "continuing", "offset": resume_at, "of": len(pairs)}
    return make_report(pairs, event)


if __name__ == "__main__":  # local run: python handler.py event.json
    import sys
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(lambda_handler(json.load(open(sys.argv[1]))), indent=2))
