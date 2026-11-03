"""Parse an OSCN "WebJudicialDocketJudgeAll" docket page into one row per case.

Page shape (as of Nov 2026):
  * "Docket for Judge <NAME> - <County> County" / "All Events Scheduled on MM/DD/YYYY."
  * Session headers: "<Weekday>, <Month> <D>, <YYYY> at <H:MM AM|PM>"
  * Under each header, one <TABLE class=clspg> per case, linking GetCaseInformation.asp
  * Footer "<!--End Transmission-->" marks a complete page.
"""
from __future__ import annotations

import html as htmllib
import re
from dataclasses import dataclass, asdict
from datetime import date, datetime

JUDGE_RE = re.compile(r"Docket for Judge\s+(.*?)\s+-\s+\w[\w ]*?\s+County", re.I)
SCHEDULED_RE = re.compile(r"All Events Scheduled on\s+(\d{1,2}/\d{1,2}/\d{4})", re.I)
SESSION_RE = re.compile(
    r"<B>\s*((?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}"
    r"\s+at\s+\d{1,2}:\d{2}\s*[AP]M)\s*</B>", re.I)
ENTRY_SPLIT_RE = re.compile(r"<TABLE\s+class=clspg\b", re.I)
CASE_RE = re.compile(r"casemasterid=(\d+)[^>]*>\s*([A-Z]{1,3}-\d{4}-\d+[A-Z]?)\s*</A>", re.I)
EVENT_RE = re.compile(r"COLOR=RED>\s*([^<]*)</FONT>", re.I)
END_MARKER = "<!--end transmission-->"
# Event text OSCN prints when a case is back on the docket after judgment was taken under advisement.
JUA_RE = re.compile(r"JUDGMENT\s+UNDER\s+ADVISEMENT|\bJUA\b", re.I)


@dataclass
class Case:
    judge_id: str
    judge_name: str
    docket_date: str   # YYYY-MM-DD
    month: str         # YYYY-MM
    weekday: str
    session_time: str  # HH:MM, 24h
    case_number: str
    casemasterid: str
    event: str
    is_jua: bool = False   # judgment under advisement: counted separately, not in "cases"

    def as_row(self) -> dict:
        return asdict(self)


def _clean(s: str) -> str:
    s = htmllib.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def scheduled_date(html: str) -> date | None:
    m = SCHEDULED_RE.search(html)
    return datetime.strptime(m.group(1), "%m/%d/%Y").date() if m else None


def is_complete(html: str) -> bool:
    return END_MARKER in html.lower()


def parse_docket(html: str, judge_id: str = "") -> list[Case]:
    m = JUDGE_RE.search(html)
    judge_name = _clean(m.group(1)) if m else ""
    cases: list[Case] = []
    sessions = list(SESSION_RE.finditer(html))
    for i, s in enumerate(sessions):
        dt = datetime.strptime(re.sub(r"\s+", " ", s.group(1)), "%A, %B %d, %Y at %I:%M %p")
        block = html[s.end(): sessions[i + 1].start() if i + 1 < len(sessions) else len(html)]
        for chunk in ENTRY_SPLIT_RE.split(block)[1:]:
            cm = CASE_RE.search(chunk)
            if not cm:
                continue
            ev = EVENT_RE.search(chunk)
            event = _clean(ev.group(1)) if ev else ""
            cases.append(Case(
                judge_id=str(judge_id), judge_name=judge_name,
                docket_date=dt.date().isoformat(), month=dt.strftime("%Y-%m"),
                weekday=dt.strftime("%A"), session_time=dt.strftime("%H:%M"),
                case_number=cm.group(2), casemasterid=cm.group(1),
                event=event, is_jua=bool(JUA_RE.search(event)),
            ))
    return cases


if __name__ == "__main__":  # python docket_parser.py saved_docket.htm
    import sys
    rows = parse_docket(open(sys.argv[1], encoding="ISO-8859-1").read())
    for r in rows[:5]:
        print(r)
    print(f"{len(rows)} cases")
