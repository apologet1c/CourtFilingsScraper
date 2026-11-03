"""AWS Lambda entry point: scrape OSCN eviction dockets to S3 and build reports.

Event (all fields optional; env vars give defaults):
{
  "action": "scrape" | "classify" | "report" | "all",   # default "all" = scrape, then report
  "db": "Tulsa",
  "judges": ["1058"],                  # OSCN Judge= ids for the eviction dockets
  "start_date": "2026-01-01",
  "end_date": "2026-12-31",            # default: today (or Dec 31 for future-looking runs)
  "weekdays_only": true,
  "overwrite": false,                  # re-download pages already in S3
  "case_types": ["SC"],                # docket lines to keep in the report
  "fed_only": false,                   # report only cases verified as FED via "classify"
  "report_name": "2026"                # report folder under REPORT_PREFIX/{db}/
}

Long ranges are split across invocations: when the remaining time drops below
TIME_RESERVE_SECONDS the function re-invokes itself asynchronously with an "offset"
cursor. Pages already in S3 are skipped, so re-running is idempotent and safe.
"""
from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import boto3

import storage
from oscn_client import OSCNClient, CaptchaError, docket_url, case_url
from docket_parser import parse_docket, is_complete, scheduled_date
from report import build_reports, to_csv, summary, ENTRY_FIELDS

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

TIME_RESERVE_MS = int(os.environ.get("TIME_RESERVE_SECONDS", "60")) * 1000
MAX_CHAIN = int(os.environ.get("MAX_CHAIN_DEPTH", "100"))
REFRESH_RECENT_DAYS = int(os.environ.get("REFRESH_RECENT_DAYS", "3"))
FED_RE = re.compile(os.environ.get("FED_REGEX", r"FORCIBLE\s+ENTRY|\bF\.?E\.?D\.?\b|EVICTION"), re.I)


# ---------------------------------------------------------------- config

def _cfg(event: dict) -> dict:
    today = date.today()
    judges = event.get("judges") or [j.strip() for j in os.environ.get("JUDGE_IDS", "").split(",") if j.strip()]
    if not judges:
        raise ValueError("No judges configured: pass event.judges or set JUDGE_IDS")
    start = date.fromisoformat(event.get("start_date") or os.environ.get("START_DATE", f"{today.year}-01-01"))
    end = date.fromisoformat(event.get("end_date") or os.environ.get("END_DATE", today.isoformat()))
    return {
        "action": event.get("action", "all"),
        "db": event.get("db") or os.environ.get("OSCN_DB", "Tulsa"),
        "judges": [str(j) for j in judges],
        "start": start,
        "end": end,
        "weekdays_only": event.get("weekdays_only", os.environ.get("WEEKDAYS_ONLY", "true").lower() == "true"),
        "overwrite": bool(event.get("overwrite", False)),
        "case_types": [c.upper() for c in (event.get("case_types")
                       or os.environ.get("CASE_TYPES", "SC").split(","))],
        "fed_only": bool(event.get("fed_only", os.environ.get("FED_ONLY", "false").lower() == "true")),
        "report_name": event.get("report_name") or f"{start.isoformat()}_{end.isoformat()}",
    }


def _days(start: date, end: date, weekdays_only: bool):
    d = start
    while d <= end:
        if not weekdays_only or d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def _pairs(cfg) -> list[tuple[str, date]]:
    return [(j, d) for d in _days(cfg["start"], cfg["end"], cfg["weekdays_only"]) for j in cfg["judges"]]


def _continue(event: dict, context, **updates) -> dict:
    """Re-invoke this function asynchronously with an updated cursor."""
    depth = int(event.get("chain_depth", 0)) + 1
    if depth > MAX_CHAIN:
        raise RuntimeError(f"MAX_CHAIN_DEPTH ({MAX_CHAIN}) exceeded; resume manually with {updates}")
    nxt = {**event, **updates, "chain_depth": depth}
    boto3.client("lambda").invoke(FunctionName=context.invoked_function_arn,
                                  InvocationType="Event", Payload=json.dumps(nxt).encode())
    log.info("continuing in new invocation: %s", updates)
    return {"status": "continued", **updates}


def _out_of_time(context) -> bool:
    return context is not None and context.get_remaining_time_in_millis() < TIME_RESERVE_MS


# ---------------------------------------------------------------- actions

def scrape(cfg, event, context) -> dict:
    client = OSCNClient()
    pairs = _pairs(cfg)
    offset = int(event.get("offset", 0))
    stats = {"fetched": 0, "skipped": 0, "incomplete": 0, "errors": 0}
    recent_cutoff = date.today() - timedelta(days=REFRESH_RECENT_DAYS)

    for i in range(offset, len(pairs)):
        if _out_of_time(context):
            return {"next_offset": i, "total": len(pairs), **stats}
        judge, day = pairs[i]
        key = storage.docket_key(cfg["db"], judge, day)
        # Dockets on/after the cutoff can still change, so always re-pull those.
        if not cfg["overwrite"] and day < recent_cutoff and storage.exists(key):
            stats["skipped"] += 1
            continue
        url = docket_url(judge, day, cfg["db"])
        try:
            html = client.get(url)
        except CaptchaError:
            raise  # stop the whole run; credentials are wrong
        except Exception as e:
            log.error("fetch failed %s: %s", url, e)
            stats["errors"] += 1
            continue
        if not is_complete(html):
            log.warning("incomplete page (no End Transmission marker), not saved: %s", url)
            stats["incomplete"] += 1
            continue
        got = scheduled_date(html)
        if got and got != day:
            log.warning("asked for %s, OSCN returned %s; not saved: %s", day, got, url)
            stats["incomplete"] += 1
            continue
        storage.put_text(key, html, metadata={
            "source-url": url, "judge-id": judge, "docket-date": day.isoformat(),
            "fetched-at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "entries": str(len(parse_docket(html, judge, cfg["db"]))),
        })
        stats["fetched"] += 1
    return {"next_offset": None, "total": len(pairs), **stats}


def _load_entries(cfg) -> list:
    keys = []
    for judge, day in _pairs(cfg):
        keys.append((judge, storage.docket_key(cfg["db"], judge, day)))

    def load(jk):
        judge, key = jk
        html = storage.get_text_or_none(key)
        return parse_docket(html, judge, cfg["db"]) if html else []

    with ThreadPoolExecutor(max_workers=16) as ex:
        entries = [e for es in ex.map(load, keys) for e in es]
    seen, out = set(), []
    for e in entries:  # guard against the same docket line appearing in two stored pages
        k = (e.judge_id, e.session_dt, e.case_number, e.event)
        if e.case_type in cfg["case_types"] and k not in seen:
            seen.add(k)
            out.append(e)
    return out


def classify(cfg, event, context) -> dict:
    """Fetch each case page once (cached in S3) so the report can keep only true FEDs."""
    client = OSCNClient()
    ids = sorted({e.casemasterid for e in _load_entries(cfg)})
    offset = int(event.get("offset", 0))
    fetched = 0
    for i in range(offset, len(ids)):
        if _out_of_time(context):
            return {"next_offset": i, "total": len(ids), "fetched": fetched}
        key = storage.case_key(cfg["db"], ids[i])
        if storage.exists(key) and not cfg["overwrite"]:
            continue
        html = client.get(case_url(ids[i], cfg["db"]))
        got = scheduled_date(html)
        if got and got != day:
            log.warning("asked for %s, OSCN returned %s; not saved: %s", day, got, url)
            stats["incomplete"] += 1
            continue
        storage.put_text(key, html, metadata={"casemasterid": ids[i]})
        fetched += 1
    return {"next_offset": None, "total": len(ids), "fetched": fetched}


def _fed_flags(cfg, entries) -> dict[str, bool]:
    def flag(cid):
        html = storage.get_text_or_none(storage.case_key(cfg["db"], cid))
        return cid, (bool(FED_RE.search(html)) if html is not None else None)  # None = not classified
    with ThreadPoolExecutor(max_workers=16) as ex:
        return dict(ex.map(flag, sorted({e.casemasterid for e in entries})))


def report(cfg, event, context) -> dict:
    entries = _load_entries(cfg)
    flags = None
    if cfg["fed_only"]:
        flags = _fed_flags(cfg, entries)
        missing = sum(1 for v in flags.values() if v is None)
        if missing:
            log.warning("%d cases not yet classified; run action=classify first", missing)
        entries = [e for e in entries if flags.get(e.casemasterid)]

    reports = build_reports(entries, flags)
    base = f"{storage.REPORT_PREFIX}/{cfg['db']}/{cfg['report_name']}"
    for name, rows in reports.items():
        storage.put_text(f"{base}/{name}.csv",
                         to_csv(rows, ENTRY_FIELDS if name == "entries" else None),
                         content_type="text/csv; charset=utf-8")
    summ = {**summary(reports), "config": {k: str(v) for k, v in cfg.items()}}
    storage.put_text(f"{base}/summary.json", json.dumps(summ, indent=2),
                     content_type="application/json; charset=utf-8")
    return {"report_prefix": f"s3://{storage.BUCKET}/{base}/", **summ}


# ---------------------------------------------------------------- entry

def lambda_handler(event, context):
    event = event or {}
    cfg = _cfg(event)
    action = cfg["action"]
    log.info("action=%s db=%s judges=%s %s..%s offset=%s", action, cfg["db"], cfg["judges"],
             cfg["start"], cfg["end"], event.get("offset", 0))

    if action in ("scrape", "all", "classify"):
        fn = classify if action == "classify" else scrape
        res = fn(cfg, event, context)
        if res["next_offset"] is not None:
            return _continue(event, context, offset=res["next_offset"])
        log.info("%s complete: %s", action, res)
        if action != "all":
            return res
    if action in ("report", "all"):
        return report(cfg, event, context)
    raise ValueError(f"unknown action {action!r}")
