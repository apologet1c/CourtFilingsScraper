# OSCN eviction docket Lambda

Answers *"how many people were on each eviction docket in 2026?"*: it pulls each judge's daily
OSCN docket page, keeps the raw HTML in S3, and writes CSV reports by **date, month, weekday,
and time slot**.

Stdlib + boto3 only (both ship with the Lambda Python runtime), so there's nothing to package.

## Files
| file | role |
|---|---|
| `handler.py` | Lambda entry; `scrape` / `classify` / `report` / `all` actions, self-continues past the 15-min limit |
| `oscn_client.py` | URL builder (matches the `WebJudicialDocketJudgeAll` link), throttled GET, key injection |
| `docket_parser.py` | Parses a docket page into one row per case line |
| `report.py` | Aggregations + CSV |
| `storage.py` | S3 key layout |
| `template.yaml` | SAM template (Lambda, IAM, nightly schedule) |

## Run it
```json
{"action": "all", "judges": ["1058"], "start_date": "2026-01-01", "end_date": "2026-12-31", "report_name": "2026"}
```
- `scrape` – downloads `raw/dockets/{db}/judge={id}/YYYY/MM/YYYY-MM-DD.html`. Pages already in S3
  are skipped (except the last `REFRESH_RECENT_DAYS`, which can still change), so reruns are cheap.
  Pages missing OSCN's `<!--End Transmission-->` footer, or dated differently than requested,
  are not saved. A CAPTCHA aborts the run.
- `report` – parses everything in range from S3 and writes to `reports/dockets/{db}/{report_name}/`.
- `all` – scrape, then report.
- `classify` *(optional)* – fetches each case page once into `raw/cases/` so `"fed_only": true`
  can drop non-eviction small-claims cases (see below).

When time runs low the function re-invokes itself with an `offset` cursor (`MAX_CHAIN_DEPTH`
caps the chain). At ~1 s/request, one judge-year (~250 weekdays) is one invocation.

## Reports
"People" is reported two ways: **cases** (docket lines) and **defendants** (named on the
caption — two tenants on one case counts 2). Plaintiffs are carried too.

| csv | grain |
|---|---|
| `sessions.csv` | **one row per docket**: judge × date × start time |
| `docket_days.csv` | judge × date (all time slots combined) |
| `by_date`, `by_month`, `by_weekday`, `by_time`, `by_weekday_time` | roll-ups of sessions: count, totals, avg / median / max per session |
| `by_month_days`, `by_weekday_days` | same, per judge-day |
| `entries.csv` | every case line, for ad-hoc pivots |
| `summary.json` | headline totals |

## Config (env)
`S3_BUCKET`, `JUDGE_IDS`, `OSCN_DB` (Tulsa), `CASE_TYPES` (SC), `WEEKDAYS_ONLY` (true),
`REQUEST_DELAY_SECONDS` (1.0), `REFRESH_RECENT_DAYS` (3), `TIME_RESERVE_SECONDS` (60),
`FED_ONLY` (false), `FED_REGEX`, `OSCN_KEY` + `OSCN_KEY_HEADER` **or** `OSCN_KEY_PARAM`, `OSCN_COOKIE`,
`USER_AGENT`. Prefer Secrets Manager / encrypted env for `OSCN_KEY`.

## Caveats
- The docket page doesn't label case type beyond the `SC-` prefix, so small-claims money cases
  heard by the same judge are counted unless you run `classify` + `fed_only`.
- Every event on the docket counts (including "JUDGMENT UNDER ADVISEMENT" / "CONTINUED" lines);
  filter on `event` in `entries.csv` if you only want first appearances.

## Test
```bash
python -m unittest discover -s docket_lambda/tests
```
