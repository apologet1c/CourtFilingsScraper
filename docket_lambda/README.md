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
Raw pages are saved to `raw/{db}/judge={id}/{yyyy}/{yyyy-mm-dd}.html`. Reports go to `reports/{db}/{report_name}/`:

| csv | contents |
|---|---|
| `by_date.csv` | **cases on each day** (includes 0-case days) plus that day's time slots |
| `sessions.csv` | cases at each date + time slot |
| `by_month`, `by_weekday` | dockets, total cases, avg/median/min/max cases per docket day |
| `by_time`, `by_weekday_time`, `by_month_time` | the same stats, per time slot |
| `cases.csv` | every case line, for your own pivots |
| `summary.json` | totals, plus any days whose page couldn't be fetched (`missing_pages`) |

**JUAs are split out.** A line whose event reads "JUDGMENT UNDER ADVISEMENT" (or "JUA") is not
counted in `cases`. It goes in a separate `jua` / `total_jua` column, and all averages are
over `cases` only. `cases.csv` keeps every line, with an `is_jua` flag.

Days with 0 cases (holidays) still appear in `by_date.csv`, but they are left out of the averages.

A page is not saved, and the day shows up in `missing_pages`, if:
- it's missing OSCN's `<!--End Transmission-->` footer, or
- it's dated differently than requested.

A CAPTCHA response stops the run.

## Test
```bash
python -m unittest discover -s docket_lambda/tests
```
