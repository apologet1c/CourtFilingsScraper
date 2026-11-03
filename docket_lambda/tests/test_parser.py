"""Run: python -m unittest discover -s docket_lambda/tests"""
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from docket_parser import parse_docket, is_complete, scheduled_date  # noqa: E402
from report import build_reports, summary  # noqa: E402
import handler  # noqa: E402


def entry(n, case, cid):
    return f"""
<TABLE class=clspg WIDTH=100% BORDER=0 CELLSPACING=0 CELLPADDING=0><TR>
 <TD VALIGN=TOP width=5%><B><FONT FACE=ARIAL SIZE=4><B>{n}&nbsp;</B></TD>
 <TD VALIGN=TOP COLSPAN=2><FONT FACE=ARIAL SIZE=3><B>
 <A HREF="GetCaseInformation.asp?submitted=true&db=Tulsa&casemasterid={cid}" target="_blank">{case}</A></B></FONT>
 <BR><FONT FACE=ARIAL SIZE=1 COLOR=RED>HEARING - ATTY/PL (HEA)</FONT><BR></TD></TR></TABLE>"""


def page(d, sessions):
    html = (f"<B>Docket for Judge Jane Doe - Tulsa County</B></FONT><HR></FONT>"
            f"<FONT FACE=ARIAL SIZE=2>All Events Scheduled on {d:%m/%d/%Y}.</TD>")
    n = 0
    for t, k in sessions:
        html += f"<FONT FACE=ARIAL SIZE=3><B>{d:%A, %B} {d.day}, {d.year} at {t}</B></FONT><HR>"
        for _ in range(k):
            n += 1
            html += entry(n, f"SC-{d.year}-{n}", str(n))
    return html + "<BR><!--End Transmission--><HR>"


MON, TUE = date(2026, 3, 2), date(2026, 3, 3)


class Tests(unittest.TestCase):
    def test_parse(self):
        html = page(MON, [("9:00 AM", 2), ("1:30 PM", 3)])
        cs = parse_docket(html, "1058")
        self.assertEqual(len(cs), 5)
        self.assertEqual((cs[0].session_time, cs[-1].session_time), ("09:00", "13:30"))
        self.assertEqual((cs[0].weekday, cs[0].judge_name),
                         ("Monday", "Jane Doe"))
        self.assertTrue(is_complete(html))
        self.assertEqual(scheduled_date(html), MON)

    def test_reports(self):
        cs = parse_docket(page(MON, [("9:00 AM", 2), ("1:30 PM", 3)]), "1058")
        cs += parse_docket(page(TUE, [("9:00 AM", 4)]), "1058")
        r = build_reports(cs, [(MON.isoformat(), "1058"), (TUE.isoformat(), "1058"), ("2026-03-04", "1058")])
        self.assertEqual([x["cases"] for x in r["by_date"]], [5, 4, 0])     # empty day shown as 0
        self.assertEqual(r["by_month"][0]["avg_cases_per_docket"], 4.5)     # ...but not averaged in
        self.assertEqual([(x["session_time"], x["total_cases"]) for x in r["by_time"]],
                         [("09:00", 6), ("13:30", 3)])
        self.assertEqual(summary(r)["total_cases"], 9)

    def test_plan_judge_windows(self):
        ev = {"start_date": "2026-06-29", "end_date": "2026-07-03",
              "judges": [{"id": "1", "to": "2026-06-30"}, {"id": "2", "from": "2026-07-01"}]}
        self.assertEqual([(j, d.day) for j, d in handler.plan(ev)],
                         [("1", 29), ("1", 30), ("2", 1), ("2", 2), ("2", 3)])
        ev = {"start_date": "2026-07-03", "end_date": "2026-07-06", "judge": "9"}   # Fri..Mon
        self.assertEqual([d.day for _, d in handler.plan(ev)], [3, 6])


if __name__ == "__main__":
    unittest.main()
