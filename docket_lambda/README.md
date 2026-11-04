# OSCN eviction docket counter

Give it a date range and the judge id(s). It saves every daily docket page to S3, then
writes CSVs showing how many cases were on each docket, broken out by date, month,
weekday and time slot.

## Run
Invoke the Lambda once per range:
```json
{"start_date": "2026-01-01", "end_date": "2026-12-31", "judge": "1058", "report_name": "2026"}
```
When the judge changes partway through, give each judge a date window (`from`/`to` are inclusive; leave either off to mean the range's start or end):
```json
{"start_date": "2023-01-01", "end_date": "2023-12-31", "report_name": "2023",
 "judges": [{"id": "1001", "to": "2023-06-30"}, {"id": "1058", "from": "2023-07-01"}]}
```
Optional settings: `"overwrite": true` re-downloads pages, and `"weekdays_only": false` includes weekends.

### Days that aren't fetched
OSCN is only hit on days court could be open. For example, 2026 takes **251 requests, not 365**.
- **Weekends** are skipped.
- **Oklahoma legal holidays** are skipped (`holidays.py`): New Year's Day, MLK Day, Presidents' Day,
  Memorial Day, Independence Day, Labor Day, Veterans Day, Thanksgiving, the day after Thanksgiving, and Christmas.
  A fixed-date holiday on a Saturday is observed the Friday before; on a Sunday, the Monday after.
- **Christmas Eve is fetched on purpose**, because how it's observed changes with the governor's order each
  year. The list is kept conservative: a wrongly skipped day loses data, while a wrongly fetched one costs a single request.
- `"skip_dates": [...]` adds closures (weather, Christmas Eve if you know it).
  `"include_dates": [...]` forces a fetch on a date that would otherwise be skipped.
  `"skip_holidays": false` turns holiday skipping off.
- `summary.json` lists every holiday that was skipped (`skipped_holidays`), so you can check it.

- Pages already saved are skipped, so if a run dies, invoke the same event again.
- If a range takes longer than 15 minutes, the function re-invokes itself and finishes the report on the last leg.
- At 1 request/sec, one year (~250 weekdays) takes about 4–5 minutes.

To run locally without Lambda or S3, leave `S3_BUCKET` unset. The output goes to `./out/`:
```bash
OSCN_KEY=... OSCN_KEY_HEADER=... python handler.py event.json
```

## Environment variables
| var | |
|---|---|
| `S3_BUCKET` | where pages and reports go |
| `OSCN_KEY` | your key |
| `OSCN_KEY_HEADER` | name of the header the key is sent in |
| `OSCN_DB` | default `Tulsa` |
| `REQUEST_DELAY_SECONDS` | default `1.0` |

## Output
Raw pages are saved to `raw/{db}/judge={id}/{yyyy}/{yyyy-mm-dd}.html`. Reports go to `reports/{db}/{report_name}/`.

### What gets counted
Every docket line goes in exactly one bucket:

```
listed        every line on the docket
├─ jua          event says JUDGMENT UNDER ADVISEMENT
├─ continued    event says CONTINUED (e.g. "CONTINUED BY AGREEMENT")
└─ cases        everything else: hearings actually set that day
   ├─ first_time  the case's first appearance on any docket scraped
   └─ repeat      the case was on an earlier docket
```

To count **only first-time appearances**, use `first_time`.

"Earlier" includes the **lookback** window: `lookback_days` (default 30) scrapes the days before
`start_date`. Those days are used only to tell first-time cases from repeats and are never counted in the report.
With the default, a 1-year run costs about 21 extra requests.

### `report.xlsx`
| sheet | |
|---|---|
| **Heatmaps** | Dropdowns pick the metric (`first_time`, `cases`, `jua`, ...) and average vs. total. There are three color-scaled grids: time slot × weekday (per session), month × weekday (per docket day), and a calendar (month × day). |
| **Summary** | Total, average and max per docket day for each metric, plus the run settings. |
| **By Date** / **Sessions** | One row per judge-day / judge-day-time slot. The counts are `COUNTIFS` formulas over Cases. |
| **Cases** | Every docket line: bucket, appearance number, event text. |

Every number in the workbook is a formula over **Cases**, so if you delete or relabel a row there,
the heatmaps and summary recalculate.

### CSVs (same numbers, for scripts)
| csv | contents |
|---|---|
| `by_date.csv` | each metric on each day (includes 0-case days) plus that day's time slots |
| `sessions.csv` | each metric at each date + time slot |
| `by_month`, `by_weekday` | totals per metric; avg/median/min/max of `cases` and `first_time` per docket day |
| `by_time`, `by_weekday_time`, `by_month_time` | the same stats, per time slot |
| `cases.csv` | every line with `bucket` and `appearance_no` |
| `summary.json` | totals, `skipped_holidays`, `missing_pages` |

Days with nothing on the docket still appear in `by_date`, but they are left out of the averages.

A page is not saved, and the day shows up in `missing_pages`, if:
- it's missing OSCN's `<!--End Transmission-->` footer, or
- it's dated differently than requested.

A CAPTCHA response stops the run.

## Deploy
`openpyxl` (in `requirements.txt`) is the one dependency. `sam build && sam deploy --guided` bundles it.
To run locally, `pip install openpyxl` first.

## Test
```bash
python -m unittest discover -s docket_lambda/tests
```
