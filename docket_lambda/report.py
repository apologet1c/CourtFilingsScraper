"""Aggregate parsed docket entries into the eviction-docket reports.

"People on a docket" is reported two ways, because the question is ambiguous:
  * cases       - docket lines (one per case called)
  * defendants  - named defendants on those cases (a case with 2 tenants counts 2)
Plaintiffs are carried too in case you need total parties.

A "session" is one judge + date + start time (e.g. Tue 11/3 2:00 PM). A "docket day"
is one judge + date across all of its sessions.
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from statistics import mean, median

from docket_parser import DocketEntry

WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

ENTRY_FIELDS = ["db", "judge_id", "judge_name", "docket_date", "month", "weekday", "session_time",
                "session_dt", "seq", "case_number", "case_type", "casemasterid", "assigned_to",
                "event_code", "event", "n_plaintiffs", "n_defendants", "plaintiffs", "defendants",
                "is_fed"]


def _session_rows(entries: list[DocketEntry]) -> list[dict]:
    groups: dict[tuple, list[DocketEntry]] = defaultdict(list)
    for e in entries:
        groups[(e.judge_id, e.docket_date, e.session_time)].append(e)
    rows = []
    for (jid, d, t), es in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        f = es[0]
        rows.append({
            "docket_date": d, "month": f.month, "weekday": f.weekday, "session_time": t,
            "judge_id": jid, "judge_name": f.judge_name,
            "cases": len(es),
            "defendants": sum(e.n_defendants for e in es),
            "plaintiffs": sum(len(e.plaintiffs) for e in es),
        })
    return rows


def _docket_day_rows(sessions: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for s in sessions:
        groups[(s["judge_id"], s["docket_date"])].append(s)
    rows = []
    for (jid, d), ss in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        f = ss[0]
        rows.append({
            "docket_date": d, "month": f["month"], "weekday": f["weekday"],
            "judge_id": jid, "judge_name": f["judge_name"],
            "sessions": len(ss), "session_times": " ".join(s["session_time"] for s in ss),
            "cases": sum(s["cases"] for s in ss),
            "defendants": sum(s["defendants"] for s in ss),
            "plaintiffs": sum(s["plaintiffs"] for s in ss),
        })
    return rows


def _rollup(rows: list[dict], keys: list[str], unit: str, order=None) -> list[dict]:
    """Group session/day rows by `keys`; report totals plus per-docket avg/median/max."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[tuple(r[k] for k in keys)].append(r)
    out = []
    for k, rs in groups.items():
        cases = [r["cases"] for r in rs]
        defs = [r["defendants"] for r in rs]
        row = dict(zip(keys, k))
        row.update({
            unit: len(rs),
            "total_cases": sum(cases),
            "total_defendants": sum(defs),
            f"avg_cases_per_{unit[:-1]}": round(mean(cases), 2),
            f"median_cases_per_{unit[:-1]}": median(cases),
            f"max_cases_per_{unit[:-1]}": max(cases),
            f"avg_defendants_per_{unit[:-1]}": round(mean(defs), 2),
            f"median_defendants_per_{unit[:-1]}": median(defs),
            f"max_defendants_per_{unit[:-1]}": max(defs),
        })
        out.append(row)
    sort_key = order or (lambda r: tuple(r[k] for k in keys))
    return sorted(out, key=sort_key)


def build_reports(entries: list[DocketEntry], fed_flags: dict[str, bool] | None = None) -> dict[str, list[dict]]:
    entry_rows = []
    for e in entries:
        r = e.as_row()
        r["is_fed"] = "" if fed_flags is None else fed_flags.get(e.casemasterid, "")
        entry_rows.append(r)

    sessions = _session_rows(entries)
    days = _docket_day_rows(sessions)
    wd = lambda r: (WEEKDAY_ORDER.index(r["weekday"]),)
    wdt = lambda r: (WEEKDAY_ORDER.index(r["weekday"]), r["session_time"])
    return {
        "entries": entry_rows,
        "sessions": sessions,                       # answer: people per docket (per time slot)
        "docket_days": days,                        # answer: people per docket (per judge-day)
        "by_date": _rollup(sessions, ["docket_date", "weekday"], "sessions"),
        "by_month": _rollup(sessions, ["month"], "sessions"),
        "by_weekday": _rollup(sessions, ["weekday"], "sessions", order=wd),
        "by_time": _rollup(sessions, ["session_time"], "sessions"),
        "by_weekday_time": _rollup(sessions, ["weekday", "session_time"], "sessions", order=wdt),
        "by_month_days": _rollup(days, ["month"], "docket_days"),
        "by_weekday_days": _rollup(days, ["weekday"], "docket_days", order=wd),
    }


def to_csv(rows: list[dict], fields: list[str] | None = None) -> str:
    buf = io.StringIO()
    if not rows:
        return ""
    w = csv.DictWriter(buf, fieldnames=fields or list(rows[0].keys()), extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def summary(reports: dict[str, list[dict]]) -> dict:
    s, d = reports["sessions"], reports["docket_days"]
    return {
        "sessions": len(s),
        "docket_days": len(d),
        "total_cases": sum(r["cases"] for r in s),
        "total_defendants": sum(r["defendants"] for r in s),
        "avg_cases_per_session": round(mean([r["cases"] for r in s]), 2) if s else 0,
        "avg_defendants_per_session": round(mean([r["defendants"] for r in s]), 2) if s else 0,
        "first_date": s[0]["docket_date"] if s else None,
        "last_date": s[-1]["docket_date"] if s else None,
    }
