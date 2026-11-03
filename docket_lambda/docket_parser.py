"""Parse an OSCN "WebJudicialDocketJudgeAll" docket page into structured rows.

Stdlib only so the Lambda deploys without layers.

Page shape (as of Nov 2026):
  * Header: "Docket for Judge <NAME> - <County> County" / "All Events Scheduled on MM/DD/YYYY."
  * One or more session headers: "<Weekday>, <Month> <D>, <YYYY> at <H:MM AM|PM>"
  * Under each session, one <TABLE class=clspg> per entry with the case number link,
    "Case Assigned to: ...", a red event line ending in "(CODE)", and a caption
    "<P1>, Plaintiff, and <P2>, Plaintiff, v. <D1>, Defendant, and <D2>, Defendant."
  * Footer: "<!--End Transmission-->" (used to confirm a complete download).
"""
from __future__ import annotations

import html as htmllib
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime

JUDGE_RE = re.compile(r"Docket for Judge\s+(.*?)\s+-\s+(\w[\w ]*?)\s+County", re.I)
SCHEDULED_RE = re.compile(r"All Events Scheduled on\s+(\d{1,2}/\d{1,2}/\d{4})", re.I)
SESSION_RE = re.compile(
    r"<B>\s*((?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}\s+at\s+\d{1,2}:\d{2}\s*[AP]M)\s*</B>",
    re.I,
)
ENTRY_SPLIT_RE = re.compile(r"<TABLE\s+class=clspg\b", re.I)
CASE_RE = re.compile(
    r'casemasterid=(\d+)[^>]*>\s*([A-Z]{1,3}-\d{4}-\d+[A-Z]?)\s*</A>', re.I
)
ASSIGNED_RE = re.compile(r"Case Assigned to:\s*([^<]*)", re.I)
EVENT_RE = re.compile(r"COLOR=RED>\s*([^<]*)</FONT>", re.I)
EVENT_CODE_RE = re.compile(r"\(([A-Z0-9]{2,6})\)\s*$")
CAPTION_RE = re.compile(r'width=45%>\s*<FONT[^>]*>\s*<B>(.*?)</B>', re.I | re.S)
END_MARKER = "<!--End Transmission-->"


@dataclass
class DocketEntry:
    db: str
    judge_id: str
    judge_name: str
    docket_date: str          # YYYY-MM-DD
    session_dt: str           # ISO datetime of the session header
    session_time: str         # HH:MM (24h)
    weekday: str
    month: str                # YYYY-MM
    seq: int                  # line number on the docket
    case_number: str
    case_type: str            # SC, CJ, CS, ...
    casemasterid: str
    assigned_to: str
    event: str
    event_code: str
    plaintiffs: list[str] = field(default_factory=list)
    defendants: list[str] = field(default_factory=list)

    @property
    def n_defendants(self) -> int:
        return len(self.defendants)

    def as_row(self) -> dict:
        d = asdict(self)
        d["n_plaintiffs"] = len(self.plaintiffs)
        d["n_defendants"] = len(self.defendants)
        d["plaintiffs"] = " | ".join(self.plaintiffs)
        d["defendants"] = " | ".join(self.defendants)
        return d


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = htmllib.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def split_caption(caption: str) -> tuple[list[str], list[str]]:
    """'A, Plaintiff, and B, Plaintiff, v. C, Defendant, and D, Defendant.' -> ([A,B],[C,D])."""
    caption = _clean(caption)
    parts = re.split(r",?\s+v\.\s+", caption, maxsplit=1)
    def names(chunk: str, role: str) -> list[str]:
        out = []
        for piece in re.split(rf",\s*{role}\b[.,]?", chunk, flags=re.I):
            piece = re.sub(r"^\s*and\s+", "", piece.strip(" ,."), flags=re.I).strip(" ,.")
            if piece:
                out.append(piece)
        return out
    pls = names(parts[0], "Plaintiff")
    dfs = names(parts[1], "Defendant") if len(parts) > 1 else []
    return pls, dfs


def scheduled_date(html: str):
    m = SCHEDULED_RE.search(html)
    return datetime.strptime(m.group(1), "%m/%d/%Y").date() if m else None


def is_complete(html: str) -> bool:
    return END_MARKER.lower() in html.lower()


def looks_like_captcha(html: str) -> bool:
    return "captcha" in html.lower()


def parse_docket(html: str, judge_id: str = "", db: str = "") -> list[DocketEntry]:
    judge_name, county = "", db
    m = JUDGE_RE.search(html)
    if m:
        judge_name, county = _clean(m.group(1)), m.group(2).strip()
    db = db or county
    docket_date = ""
    m = SCHEDULED_RE.search(html)
    if m:
        docket_date = datetime.strptime(m.group(1), "%m/%d/%Y").date().isoformat()

    entries: list[DocketEntry] = []
    # Walk session headers; each session owns the text up to the next header.
    sessions = list(SESSION_RE.finditer(html))
    for i, s in enumerate(sessions):
        dt = datetime.strptime(re.sub(r"\s+", " ", s.group(1)), "%A, %B %d, %Y at %I:%M %p")
        end = sessions[i + 1].start() if i + 1 < len(sessions) else len(html)
        block = html[s.end():end]
        for chunk in ENTRY_SPLIT_RE.split(block)[1:]:
            cm = CASE_RE.search(chunk)
            if not cm:
                continue
            seq_m = re.search(r"SIZE=4><B>(\d+)", chunk, re.I)
            ev = EVENT_RE.search(chunk)
            event = _clean(ev.group(1)) if ev else ""
            code_m = EVENT_CODE_RE.search(event)
            cap = CAPTION_RE.search(chunk)
            pls, dfs = split_caption(cap.group(1)) if cap else ([], [])
            asg = ASSIGNED_RE.search(chunk)
            entries.append(DocketEntry(
                db=db,
                judge_id=str(judge_id),
                judge_name=judge_name,
                docket_date=docket_date or dt.date().isoformat(),
                session_dt=dt.isoformat(timespec="minutes"),
                session_time=dt.strftime("%H:%M"),
                weekday=dt.strftime("%A"),
                month=dt.strftime("%Y-%m"),
                seq=int(seq_m.group(1)) if seq_m else 0,
                case_number=cm.group(2),
                case_type=cm.group(2).split("-")[0],
                casemasterid=cm.group(1),
                assigned_to=_clean(asg.group(1)) if asg else "",
                event=event,
                event_code=code_m.group(1) if code_m else "",
                plaintiffs=pls,
                defendants=dfs,
            ))
    return entries


if __name__ == "__main__":  # quick local check: python docket_parser.py docket.htm
    import json, sys
    rows = [e.as_row() for e in parse_docket(open(sys.argv[1], encoding="ISO-8859-1").read())]
    print(json.dumps(rows[:3], indent=2))
    print(f"{len(rows)} entries")
