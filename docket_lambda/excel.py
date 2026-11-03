"""Excel report: heatmaps + summary, all driven by formulas over the raw Cases sheet.

Sheets
  Heatmaps  - pick a metric (first_time, cases, ...) and average/total from dropdowns;
              grids: time slot x weekday, month x weekday, and a calendar (month x day).
  Summary   - totals and per-docket averages for each metric, plus run settings.
  By Date   - one row per judge-day; counts are COUNTIFS over Cases.
  Sessions  - one row per judge-day-time; counts are COUNTIFS over Cases.
  Cases     - every docket line (static data). Edit/delete rows here and everything recalculates.
"""
from __future__ import annotations

import io
from datetime import date, time

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter as col
from openpyxl.worksheet.datavalidation import DataValidation

from report import METRICS, WEEKDAYS

BOLD = Font(bold=True)
HDR_FILL = PatternFill("solid", fgColor="DDE4EE")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
HEAT = ColorScaleRule(start_type="min", start_color="FFFFFF",
                      mid_type="percentile", mid_value=50, mid_color="F8CBAD",
                      end_type="max", end_color="C00000")
METRIC_HELP = {
    "listed": "every line on the docket",
    "cases": "hearings set that day (listed minus JUA and continued)",
    "first_time": "cases appearing for the first time (subset of cases)",
    "repeat": "cases seen on an earlier docket (subset of cases)",
    "jua": "judgment under advisement lines",
    "continued": "continued lines (e.g. by agreement)",
}


def _typed(k: str, v):
    """Real dates/times/numbers, so COUNTIFS never has to guess whether "2026-03" is text or a date."""
    if k == "docket_date":
        return date.fromisoformat(v)
    if k == "month":
        return date(int(v[:4]), int(v[5:7]), 1)
    if k == "session_time":
        return time(int(v[:2]), int(v[3:5]))
    if k == "judge_id" and str(v).isdigit():
        return int(v)
    return v


FORMATS = {"docket_date": "yyyy-mm-dd", "month": "mmm yyyy", "session_time": "h:mm AM/PM"}


def _append(ws, keys, row):
    ws.append([_typed(k, row[k]) for k in keys])
    for j, k in enumerate(keys, 1):
        if k in FORMATS:
            ws.cell(ws.max_row, j).number_format = FORMATS[k]


def _header(ws, headers):
    ws.append(headers)
    for c in ws[1]:
        c.font, c.fill = BOLD, HDR_FILL
    ws.freeze_panes = "A2"


def _widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[col(i)].width = w


def build_workbook(reports: dict[str, list[dict]], event: dict) -> bytes:
    wb = Workbook()
    heat = wb.active
    heat.title = "Heatmaps"
    summ = wb.create_sheet("Summary")
    bd = wb.create_sheet("By Date")
    ses = wb.create_sheet("Sessions")
    cs = wb.create_sheet("Cases")

    # ---------------- Cases (raw)
    case_cols = ["docket_date", "weekday", "month", "session_time", "judge_id", "judge_name",
                 "case_number", "bucket", "appearance_no", "event_type", "event", "casemasterid"]
    _header(cs, case_cols)
    for r in reports["cases"]:
        _append(cs, case_cols, r)
    nc = max(cs.max_row, 2)
    C = {k: f"Cases!${col(i)}$2:${col(i)}${nc}" for i, k in enumerate(case_cols, 1)}
    cs.auto_filter.ref = f"A1:{col(len(case_cols))}{nc}"
    _widths(cs, [11, 10, 8, 7, 7, 16, 15, 11, 9, 10, 60, 11])

    def countifs(criteria: list[tuple[str, str]], metric: str) -> str:
        crit = ",".join(f"{C[k]},{v}" for k, v in criteria)
        if metric == "listed":
            return f"=COUNTIFS({crit})"
        if metric == "cases":
            return f'=COUNTIFS({crit},{C["bucket"]},"first_time")+COUNTIFS({crit},{C["bucket"]},"repeat")'
        return f'=COUNTIFS({crit},{C["bucket"]},"{metric}")'

    # ---------------- By Date
    bd_cols = ["docket_date", "weekday", "month", "judge_id", "judge_name"] + METRICS
    _header(bd, bd_cols)
    for i, r in enumerate(reports["by_date"], 2):
        _append(bd, bd_cols[:5], r)
        for j, m in enumerate(METRICS, 6):
            bd.cell(i, j, countifs([("docket_date", f"$A{i}"), ("judge_id", f"$D{i}")], m))
    nb = max(bd.max_row, 2)
    _widths(bd, [11, 10, 8, 8, 16] + [10] * len(METRICS))
    bd.auto_filter.ref = f"A1:{col(len(bd_cols))}{nb}"

    # ---------------- Sessions
    ses_cols = ["docket_date", "weekday", "month", "session_time", "judge_id"] + METRICS
    _header(ses, ses_cols)
    for i, r in enumerate(reports["sessions"], 2):
        _append(ses, ses_cols[:5], r)
        for j, m in enumerate(METRICS, 6):
            ses.cell(i, j, countifs([("docket_date", f"$A{i}"), ("session_time", f"$D{i}"),
                                     ("judge_id", f"$E{i}")], m))
    ns = max(ses.max_row, 2)
    _widths(ses, [11, 10, 8, 8, 8] + [10] * len(METRICS))
    ses.auto_filter.ref = f"A1:{col(len(ses_cols))}{ns}"

    m0, m1 = col(6), col(5 + len(METRICS))   # metric columns F..K in both By Date and Sessions

    def pick(sheet: str, n: int) -> str:
        """Column of the metric chosen in Heatmaps!$B$2."""
        return f"INDEX('{sheet}'!${m0}$2:${m1}${n},0,MATCH(Heatmaps!$B$2,'{sheet}'!${m0}$1:${m1}$1,0))"

    def rng(sheet, c, n):
        return f"'{sheet}'!${c}$2:${c}${n}"

    # ---------------- Heatmaps
    heat["A1"] = "Eviction docket heatmaps"
    heat["A1"].font = Font(bold=True, size=14)
    heat["A2"], heat["B2"] = "Metric", "first_time"
    heat["A3"], heat["B3"] = "Show", "average"
    for c in ("B2", "B3"):
        heat[c].fill, heat[c].font = INPUT_FILL, BOLD
    heat["C2"] = '=IFERROR(VLOOKUP(B2,Summary!$A$4:$B$9,2,FALSE),"")'
    heat["C3"] = '=IF(B3="average","average per session (grid 1) / per docket day (grid 2)","total")'
    dv_m = DataValidation(type="list", formula1='"' + ",".join(METRICS) + '"', allow_blank=False)
    dv_s = DataValidation(type="list", formula1='"average,total"', allow_blank=False)
    heat.add_data_validation(dv_m)
    heat.add_data_validation(dv_s)
    dv_m.add("B2")
    dv_s.add("B3")

    days_present = [d for d in WEEKDAYS if any(r["weekday"] == d for r in reports["by_date"])] or WEEKDAYS[:5]
    times = [_typed("session_time", t) for t in sorted({r["session_time"] for r in reports["sessions"]})]
    month_starts = [_typed("month", m) for m in sorted({r["month"] for r in reports["by_date"]})]

    def grid(top: int, title: str, row_labels, row_fmt, cols, formula, num_fmt="0.0") -> int:
        heat.cell(top, 1, title).font = BOLD
        hdr = top + 1
        for j, c in enumerate(cols, 2):
            cell = heat.cell(hdr, j, c)
            cell.font, cell.fill, cell.alignment = BOLD, HDR_FILL, Alignment(horizontal="center")
        for i, lab in enumerate(row_labels, hdr + 1):
            cell = heat.cell(i, 1, lab)
            cell.font, cell.fill = BOLD, HDR_FILL
            if row_fmt:
                cell.number_format = row_fmt
            for j in range(2, len(cols) + 2):
                v = heat.cell(i, j, formula(f"$A{i}", f"{col(j)}${hdr}"))
                v.number_format = num_fmt
                v.alignment = Alignment(horizontal="center")
        last = hdr + max(len(row_labels), 1)
        if row_labels:
            heat.conditional_formatting.add(f"B{hdr + 1}:{col(len(cols) + 1)}{last}", HEAT)
        return last + 2

    # Grid 1: time slot x weekday, per session
    S = lambda c: rng("Sessions", c, ns)
    top = grid(5, "Time slot x weekday (per session)", times, "h:mm AM/PM", days_present,
               lambda r, c: (f'=IFERROR(IF($B$3="total",SUMIFS({pick("Sessions", ns)},{S("B")},{c},{S("D")},{r}),'
                             f'AVERAGEIFS({pick("Sessions", ns)},{S("B")},{c},{S("D")},{r})),"")'))

    # Grid 2: month x weekday, per docket day (days with nothing listed are left out of averages)
    B = lambda c: rng("By Date", c, nb)
    top = grid(top, "Month x weekday (per docket day)", month_starts, "mmm yyyy", days_present,
               lambda r, c: (f'=IFERROR(IF($B$3="total",SUMIFS({pick("By Date", nb)},{B("B")},{c},{B("C")},{r}),'
                             f'AVERAGEIFS({pick("By Date", nb)},{B("B")},{c},{B("C")},{r},{B("F")},">0")),"")'))

    # Grid 3: calendar, month x day-of-month (blank = not scraped / no such date)
    grid(top, "Calendar (metric per day; blank = weekend/holiday/not scraped)", month_starts, "mmm yyyy",
         list(range(1, 32)),
         lambda r, c: (f'=IF(DAY(DATE(YEAR({r}),MONTH({r}),{c}))<>{c},"",'
                       f'IF(COUNTIFS({B("A")},DATE(YEAR({r}),MONTH({r}),{c}))=0,"",'
                       f'SUMIFS({pick("By Date", nb)},{B("A")},DATE(YEAR({r}),MONTH({r}),{c}))))'),
         num_fmt="0")
    _widths(heat, [12] + [10] * 7)
    for j in range(9, 33):
        heat.column_dimensions[col(j)].width = 5

    # ---------------- Summary
    summ["A1"] = "Summary"
    summ["A1"].font = Font(bold=True, size=14)
    for j, h in enumerate(["metric", "meaning", "total", "avg per docket day", "max per docket day"], 1):
        c = summ.cell(3, j, h)
        c.font, c.fill = BOLD, HDR_FILL
    for i, m in enumerate(METRICS, 4):
        mc = col(6 + METRICS.index(m))
        summ.cell(i, 1, m).font = BOLD
        summ.cell(i, 2, METRIC_HELP[m])
        summ.cell(i, 3, f"=SUM({B(mc)})")
        summ.cell(i, 4, f'=IFERROR(AVERAGEIFS({B(mc)},{B("F")},">0"),"")').number_format = "0.0"
        summ.cell(i, 5, f"=MAX({B(mc)})")
    r = 4 + len(METRICS) + 1
    summ.cell(r, 1, "Docket days with anything listed").font = BOLD
    summ.cell(r, 3, f'=COUNTIF({B("F")},">0")')
    r += 2
    summ.cell(r, 1, "Run settings").font = BOLD
    for k in ("start_date", "end_date", "judge", "judges", "lookback_days", "skip_dates", "include_dates"):
        if k in event:
            r += 1
            summ.cell(r, 1, k)
            summ.cell(r, 2, str(event[k]))
    _widths(summ, [32, 58, 10, 18, 18])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
