"""Turn parsed cases into the report tables (counts of cases only).

"cases" excludes JUA lines (judgment under advisement); those are counted on their own
in a "jua" column so the two never mix. Every per-docket stat is on "cases".

A "docket" here is one judge-day. A "session" is one start time within that day
(e.g. Tue 11/3 at 2:00 PM). Days that were scraped but had no cases appear in
by_date.csv with 0 and are left out of the averages so holidays don't drag them down.
"""
from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from statistics import mean, median

from docket_parser import Case

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _rollup(counts: dict[tuple, int], jua: dict[tuple, int], key_names: list[str], key_fn, unit: str,
            sort=None) -> list[dict]:
    """counts: {(date, ...): n_cases} -> grouped by key_fn(k) with totals and per-unit stats."""
    groups: dict[tuple, list[int]] = defaultdict(list)
    jua_tot: Counter = Counter()
    for k, n in counts.items():
        if n:
            groups[key_fn(k)].append(n)
    for k, n in jua.items():
        jua_tot[key_fn(k)] += n
    rows = [{**dict(zip(key_names, g)), unit: len(ns), "total_cases": sum(ns), "total_jua": jua_tot[g],
             f"avg_cases_per_{unit[:-1]}": round(mean(ns), 2),
             f"median_cases_per_{unit[:-1]}": median(ns),
             f"min_cases_per_{unit[:-1]}": min(ns),
             f"max_cases_per_{unit[:-1]}": max(ns)}
            for g, ns in groups.items()]
    return sorted(rows, key=sort or (lambda r: tuple(r[k] for k in key_names)))


def build_reports(cases: list[Case], scraped_days: list[tuple[str, str]]) -> dict[str, list[dict]]:
    """scraped_days: [(iso_date, judge_id)] for every page fetched, so empty days show as 0."""
    from datetime import date
    wd = lambda d: date.fromisoformat(d).strftime("%A")

    per_day = Counter({(d, j): 0 for d, j in scraped_days})
    per_session, jua_day, jua_session = Counter(), Counter(), Counter()
    names = {}
    for c in cases:
        day_k, ses_k = (c.docket_date, c.judge_id), (c.docket_date, c.session_time, c.judge_id)
        if c.is_jua:
            jua_day[day_k] += 1
            jua_session[ses_k] += 1
            per_session.setdefault(ses_k, 0)   # keep the slot listed even if it's all JUAs
        else:
            per_day[day_k] += 1
            per_session[ses_k] += 1
        names[c.judge_id] = c.judge_name

    by_date = [{"docket_date": d, "weekday": wd(d), "month": d[:7], "judge_id": j,
                "judge_name": names.get(j, ""), "cases": n, "jua": jua_day[(d, j)],
                "session_times": " ".join(sorted(t for (sd, t, sj) in per_session if sd == d and sj == j))}
               for (d, j), n in sorted(per_day.items())]
    sessions = [{"docket_date": d, "weekday": wd(d), "month": d[:7], "session_time": t,
                 "judge_id": j, "cases": n, "jua": jua_session[(d, t, j)]}
                for (d, t, j), n in sorted(per_session.items())]

    by_wd = lambda r: WEEKDAYS.index(r["weekday"])
    return {
        "by_date": by_date,                                     # cases on each day
        "sessions": sessions,                                   # cases at each date + time
        "by_month": _rollup(per_day, jua_day, ["month"], lambda k: (k[0][:7],), "dockets"),
        "by_weekday": _rollup(per_day, jua_day, ["weekday"], lambda k: (wd(k[0]),), "dockets", by_wd),
        "by_time": _rollup(per_session, jua_session, ["session_time"], lambda k: (k[1],), "sessions"),
        "by_weekday_time": _rollup(per_session, jua_session, ["weekday", "session_time"],
                                   lambda k: (wd(k[0]), k[1]), "sessions",
                                   lambda r: (by_wd(r), r["session_time"])),
        "by_month_time": _rollup(per_session, jua_session, ["month", "session_time"],
                                 lambda k: (k[0][:7], k[1]), "sessions"),
        "cases": [c.as_row() for c in cases],
    }


def summary(reports: dict[str, list[dict]]) -> dict:
    days = [r for r in reports["by_date"] if r["cases"]]
    n = [r["cases"] for r in days]
    return {
        "days_scraped": len(reports["by_date"]),
        "days_with_cases": len(days),
        "total_cases": sum(n),
        "total_jua": sum(r["jua"] for r in reports["by_date"]),
        "avg_cases_per_docket_day": round(mean(n), 2) if n else 0,
        "busiest_day": max(days, key=lambda r: r["cases"])["docket_date"] if days else None,
    }


def to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
