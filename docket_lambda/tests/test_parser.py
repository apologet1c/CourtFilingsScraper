"""Run: python -m unittest discover -s docket_lambda/tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from docket_parser import parse_docket, split_caption, is_complete, scheduled_date  # noqa: E402
from report import build_reports  # noqa: E402


def entry(n, case, cid, caption, event="HEARING - ATTY/PL (HEA)"):
    return f"""
<TABLE class=clspg WIDTH=100% BORDER=0 CELLSPACING=0 CELLPADDING=0>	 <TR>
	 <TD VALIGN=TOP width=5%><B><FONT FACE=ARIAL SIZE=4><B>{n}&nbsp;</B></TD>
	 <TD VALIGN=TOP COLSPAN=2><FONT FACE=ARIAL SIZE=3><B>
	 <A HREF="GetCaseInformation.asp?submitted=true&db=Tulsa&casemasterid={cid}" target="_blank">{case}</A></B></FONT>
&nbsp; <FONT FACE=ARIAL SIZE=1>Case Assigned to: Small Claims Judge
	 <BR><FONT FACE=ARIAL SIZE=1 COLOR=RED>{event}</FONT><BR>
	 </TD>
	 <TD VALIGN=TOP  width=45%><FONT FACE=ARIAL SIZE=1><B>
	 {caption}</B></FONT>
	 </TD></TR></TABLE>"""


FIXTURE = (
    "<TD><FONT FACE=ARIAL SIZE=4><B>Docket for Judge Jane Doe - Tulsa County</B></FONT><HR></FONT>"
    "<FONT FACE=ARIAL SIZE=2>All Events Scheduled on 03/02/2026.</TD>"
    "<HR><FONT FACE=ARIAL SIZE=3><B>Monday, March 2, 2026 at 9:00 AM</B></FONT><HR>"
    + entry(1, "SC-2026-1", "10", "ACME APTS, LLC,           Plaintiff, v. JOHN ROE,           Defendant.")
    + entry(2, "CJ-2026-9", "11", "A,           Plaintiff, v. B,           Defendant.", "STATUS (STC)")
    + "<P class=clspg2>&nbsp;</P><FONT FACE=ARIAL SIZE=3><B>Monday, March 2, 2026 at 1:30 PM</B></FONT><HR>"
    + entry(3, "SC-2026-2", "12", "X LLC DBA,           Plaintiff, and X APTS,           Plaintiff, v. "
            "AMY POE,           Defendant, and BOB POE,           Defendant, and ALL OCCUPANTS,           Defendant.")
    + "<BR><!--End Transmission--><HR>"
)


class ParserTests(unittest.TestCase):
    def test_parse(self):
        es = parse_docket(FIXTURE, judge_id="1058")
        self.assertEqual([e.case_number for e in es], ["SC-2026-1", "CJ-2026-9", "SC-2026-2"])
        self.assertEqual(es[0].judge_name, "Jane Doe")
        self.assertEqual(es[0].db, "Tulsa")
        self.assertEqual((es[0].session_time, es[2].session_time), ("09:00", "13:30"))
        self.assertEqual(es[0].weekday, "Monday")
        self.assertEqual(es[1].event_code, "STC")
        self.assertEqual(es[2].defendants, ["AMY POE", "BOB POE", "ALL OCCUPANTS"])
        self.assertEqual(es[2].plaintiffs, ["X LLC DBA", "X APTS"])
        self.assertTrue(is_complete(FIXTURE))
        self.assertEqual(str(scheduled_date(FIXTURE)), "2026-03-02")

    def test_caption_comma_in_name(self):
        p, d = split_caption("Lafortune Tower, Llc,    Plaintiff, v. Jane Q,    Defendant.")
        self.assertEqual((p, d), (["Lafortune Tower, Llc"], ["Jane Q"]))

    def test_reports(self):
        es = [e for e in parse_docket(FIXTURE, "1058") if e.case_type == "SC"]
        r = build_reports(es)
        self.assertEqual([(s["session_time"], s["cases"], s["defendants"]) for s in r["sessions"]],
                         [("09:00", 1, 1), ("13:30", 1, 3)])
        self.assertEqual(r["docket_days"][0]["defendants"], 4)
        self.assertEqual(r["by_weekday"][0]["max_defendants_per_session"], 3)


if __name__ == "__main__":
    unittest.main()
