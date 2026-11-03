"""Turn parsed docket lines into report tables.

Every docket line falls into exactly one bucket, and the counts nest:

  listed      every line on the docket
  ├─ jua        event says JUDGMENT UNDER ADVISEMENT
  ├─ continued  event says CONTINUED (e.g. "CONTINUED BY AGREEMENT")
  └─ cases      everything else: a hearing actually set for that day
     ├─ first_time  the case's first appearance on any docket we've seen
     └─ repeat      the case was on an earlier docket (e.g. reset after a continuance)

"First appearance" is judged from every page scraped, including the lookback days before
start_date (see handler.py), so a case first heard just before the range isn't
miscounted as new.

A "docket" is one judge-day; a "session" is one start time within it. Days scraped with
nothing on them show as 0 in by_date but are left out of averages.
"""
from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from datetime import date
from statistics import mean, median

from docket_parser import Case

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
METRICS = ["listed", "cases", "first_time", "repeat", "jua", "continued"]
STAT_METRICS = ["cases", "first_time"]   # get avg/median/min/max columns in roll-ups


def classify(all_lines: list[Case]) -> list[dict]:
    """Rows with appearance_no and bucket, in docket order. Pass lookback lines too."""
    rows, seen = [], Counter()
    for c in sorted(all_lines, key=lambda c: (c.docket_date, c.session_time, c.seq)):
        seen[c.case_number] += 1
        n = seen[c.case_number]
        bucket = c.event_type if c.event_type != "hearing" else ("first_time" if n == 1 else "repeat")
        rows.append({**c.as_row(), "appearance_no": n, "bucket": bucket})
    return rows


def _counts(row: dict) -> dict[str, int]:
    b = row["bucket"]
    return {"listed": 1, "cases": int(b in ("first_time", "repeat")), "first_time": int(b == "first_time"),
            "repeat": int(b == "repeat"), "jua": int(b == "jua"), "continued": int(b == "continued")}


def _add(acc: dict, key, row):
    for m, v in _counts(row).items():
        acc[key][m] += v


def _rollup(units: list[dict], key_names: list[str], unit: str, sort=None) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for u in units:
        if u["listed"]:
            groups[tuple(u[k] for k in key_names)].append(u)
    out = []
    for g, us in groups.items():
        row = {**dict(zip(key_names, g)), unit: len(us)}
        row.update({f"total_{m}": sum(u[m] for u in us) for m in METRICS})
        for m in STAT_METRICS:
            ns = [u[m] for u in us]
            row.update({f"avg_{m}": round(mean(ns), 2), f"median_{m}": median(ns),
                        f"min_{m}": min(ns), f"max_{m}": max(ns)})
        out.append(row)
    return sorted(out, key=sort or (lambda r: tuple(r[k] for k in key_names)))


def build_reports(lines: list[dict], scraped_days: list[tuple[str, str]]) -> dict[str, list[dict]]:
    """lines: classify() output already trimmed to the report range.
    scraped_days: [(iso_date, judge_id)] for every in-range page, so empty days show as 0."""
    wd = lambda d: date.fromisoformat(d).strftime("%A")
    names = {r["judge_id"]: r["judge_name"] for r in lines}
    per_day = defaultdict(Counter, {k: Counter() for k in scraped_days})
    per_ses = defaultdict(Counter)
    for r in lines:
        _add(per_day, (r["docket_date"], r["judge_id"]), r)
        _add(per_ses, (r["docket_date"], r["session_time"], r["judge_id"]), r)

    by_date = [{"docket_date": d, "weekday": wd(d), "month": d[:7], "judge_id": j,
                "judge_name": names.get(j, ""), **{m: c[m] for m in METRICS},
                "session_times": " ".join(sorted(t for (sd, t, sj) in per_ses if sd == d and sj == j))}
               for (d, j), c in sorted(per_day.items())]
    sessions = [{"docket_date": d, "weekday": wd(d), "month": d[:7], "session_time": t,
                 "judge_id": j, **{m: c[m] for m in METRICS}}
                for (d, t, j), c in sorted(per_ses.items())]

    by_wd = lambda r: WEEKDAYS.index(r["weekday"])
    return {
        "by_date": by_date,
        "sessions": sessions,
        "by_month": _rollup(by_date, ["month"], "dockets"),
        "by_weekday": _rollup(by_date, ["weekday"], "dockets", by_wd),
        "by_time": _rollup(sessions, ["session_time"], "sessions"),
        "by_weekday_time": _rollup(sessions, ["weekday", "session_time"], "sessions",
                                   lambda r: (by_wd(r), r["session_time"])),
        "by_month_time": _rollup(sessions, ["month", "session_time"], "sessions"),
        "cases": lines,
    }


def summary(reports: dict[str, list[dict]]) -> dict:
    days = [r for r in reports["by_date"] if r["listed"]]
    out = {"days_scraped": len(reports["by_date"]), "days_with_dockets": len(days)}
    out.update({f"total_{m}": sum(r[m] for r in reports["by_date"]) for m in METRICS})
    for m in STAT_METRICS:
        out[f"avg_{m}_per_docket_day"] = round(mean(r[m] for r in days), 2) if days else 0
    out["busiest_day"] = max(days, key=lambda r: r["cases"])["docket_date"] if days else None
    return out


def to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
