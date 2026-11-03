"""Run: python -m unittest discover -s docket_lambda/tests"""
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from docket_parser import parse_docket, is_complete, scheduled_date  # noqa: E402
from report import build_reports, classify, summary  # noqa: E402
import handler  # noqa: E402


def entry(n, case, cid, event="HEARING - ATTY/PL (HEA)"):
    return f"""
<TABLE class=clspg WIDTH=100% BORDER=0 CELLSPACING=0 CELLPADDING=0><TR>
 <TD VALIGN=TOP width=5%><B><FONT FACE=ARIAL SIZE=4><B>{n}&nbsp;</B></TD>
 <TD VALIGN=TOP COLSPAN=2><FONT FACE=ARIAL SIZE=3><B>
 <A HREF="GetCaseInformation.asp?submitted=true&db=Tulsa&casemasterid={cid}" target="_blank">{case}</A></B></FONT>
 <BR><FONT FACE=ARIAL SIZE=1 COLOR=RED>{event}</FONT><BR></TD></TR></TABLE>"""


def page(d, sessions, jua=0, cont=0):
    html = (f"<B>Docket for Judge Jane Doe - Tulsa County</B></FONT><HR></FONT>"
            f"<FONT FACE=ARIAL SIZE=2>All Events Scheduled on {d:%m/%d/%Y}.</TD>")
    n = 0
    for t, k in sessions:
        html += f"<FONT FACE=ARIAL SIZE=3><B>{d:%A, %B} {d.day}, {d.year} at {t}</B></FONT><HR>"
        for _ in range(k):
            n += 1
            html += entry(n, f"SC-{d.year}-{n}", str(n))
    for _ in range(jua):
        n += 1
        html += entry(n, f"SC-{d.year}-{n}", str(n), "HEARING - JUDGMENT UNDER ADVISEMENT. - ATTY/PL (HEA)")
    for _ in range(cont):
        n += 1
        html += entry(n, f"SC-{d.year}-{n}", str(n), "HEARING - CONTINUED BY AGREEMENT. - ATTY/PL (HEA)")
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
        r = build_reports(classify(cs), [(MON.isoformat(), "1058"), (TUE.isoformat(), "1058"), ("2026-03-04", "1058")])
        self.assertEqual([x["cases"] for x in r["by_date"]], [5, 4, 0])     # empty day shown as 0
        self.assertEqual(r["by_month"][0]["avg_cases"], 4.5)                # ...but not averaged in
        self.assertEqual([(x["session_time"], x["total_cases"]) for x in r["by_time"]],
                         [("09:00", 6), ("13:30", 3)])
        # page() reuses case numbers SC-2026-1.. each day, so Tuesday's 4 are all repeats
        self.assertEqual([(x["first_time"], x["repeat"]) for x in r["by_date"][:2]], [(5, 0), (0, 4)])
        self.assertEqual(summary(r)["total_cases"], 9)

    def test_jua_and_continued_split_out(self):
        cs = parse_docket(page(MON, [("9:00 AM", 3)], jua=2, cont=1), "1058")
        self.assertEqual([c.event_type for c in cs], ["hearing"] * 3 + ["jua"] * 2 + ["continued"])
        r = build_reports(classify(cs), [(MON.isoformat(), "1058")])
        d = r["by_date"][0]
        self.assertEqual((d["listed"], d["cases"], d["first_time"], d["jua"], d["continued"]), (6, 3, 3, 2, 1))
        self.assertEqual((r["by_month"][0]["total_cases"], r["by_month"][0]["total_jua"],
                          r["by_month"][0]["total_continued"], r["by_month"][0]["avg_cases"]), (3, 2, 1, 3))
        self.assertEqual((summary(r)["total_cases"], summary(r)["total_continued"]), (3, 1))

    def test_workbook_builds(self):
        import excel
        r = build_reports(classify(parse_docket(page(MON, [("9:00 AM", 2)]), "1058")), [(MON.isoformat(), "1058")])
        self.assertTrue(excel.build_workbook(r, {"start_date": "2026-03-02"}).startswith(b"PK"))

    def test_plan_judge_windows(self):
        ev = {"start_date": "2026-06-15", "end_date": "2026-06-19", "lookback_days": 0,
              "judges": [{"id": "1", "to": "2026-06-16"}, {"id": "2", "from": "2026-06-17"}]}
        self.assertEqual([(j, d.day) for j, d in handler.plan(ev)],
                         [("1", 15), ("1", 16), ("2", 17), ("2", 18), ("2", 19)])
        ev = {"start_date": "2026-06-12", "end_date": "2026-06-15", "judge": "9", "lookback_days": 0}   # Fri..Mon
        self.assertEqual([d.day for _, d in handler.plan(ev)], [12, 15])

    def test_holidays_skipped(self):
        ev = {"start_date": "2026-11-23", "end_date": "2026-11-30", "judge": "9", "lookback_days": 0}   # Thanksgiving week
        self.assertEqual([d.day for _, d in handler.plan(ev)], [23, 24, 25, 30])
        ev["include_dates"], ev["skip_dates"] = ["2026-11-27"], ["2026-11-24"]
        self.assertEqual([d.day for _, d in handler.plan(ev)], [23, 25, 27, 30])
        ev = {"start_date": "2021-12-20", "end_date": "2021-12-31", "judge": "9", "lookback_days": 0}   # Sat Xmas, Sat New Year
        days = [d.day for _, d in handler.plan(ev)]
        self.assertNotIn(24, days)
        self.assertNotIn(31, days)
        self.assertIn(27, days)
        self.assertEqual(len(handler.plan({"start_date": "2026-01-01", "end_date": "2026-12-31",
                                           "judge": "9", "lookback_days": 0})), 261 - 10)

    def test_lookback_marks_earlier_cases_as_repeats(self):
        ev = {"start_date": "2026-03-03", "end_date": "2026-03-03", "judge": "9", "lookback_days": 1}
        self.assertEqual([d.day for _, d in handler.plan(ev)], [2, 3])
        lines = parse_docket(page(MON, [("9:00 AM", 2)]), "9") + parse_docket(page(TUE, [("9:00 AM", 3)]), "9")
        rows = [r for r in classify(lines) if r["docket_date"] >= "2026-03-03"]
        self.assertEqual([r["bucket"] for r in rows], ["repeat", "repeat", "first_time"])


if __name__ == "__main__":
    unittest.main()
