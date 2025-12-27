"""Bulk downloader for OSCN criminal misdemeanor (CM) cases.

This script fetches docket HTML for CM cases using the URL pattern:
```
https://www.oscn.net/dockets/GetCaseInformation.aspx?db=<county>&number=CM-<year>-<case_number>
```

The script improves on the small-claims bulk downloader by letting you choose
the county, year, case-number range, output directory, padding width, and
throttling settings. It also rotates user agents and retries when a captcha or
short response is detected.
"""

from __future__ import annotations

import argparse
import sys
import time
from itertools import cycle
from pathlib import Path
from typing import Iterable, Iterator

import requests


DEFAULT_USER_AGENT = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/58.0.3029.110 Safari/537.3"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

MINIMUM_HTML_BYTES = 3000


def build_case_identifier(year: int, case_number: int, pad_width: int) -> str:
    """Return the CM case identifier with optional zero padding."""

    padded_number = str(case_number).zfill(pad_width) if pad_width > 0 else str(case_number)
    return f"CM-{year}-{padded_number}"


def build_case_url(county: str, case_identifier: str) -> str:
    """Create the docket URL for a CM case."""

    return f"https://www.oscn.net/dockets/GetCaseInformation.aspx?db={county}&number={case_identifier}"


def ensure_output_directory(path: Path) -> None:
    """Create the output directory if it does not exist."""

    path.mkdir(parents=True, exist_ok=True)


def detect_captcha_or_short_response(content: bytes) -> bool:
    """Heuristically detect captchas or empty responses."""

    return len(content) < MINIMUM_HTML_BYTES or b"captcha" in content.lower()


def download_case(
    session: requests.Session,
    url: str,
    user_agent_cycle: Iterator[dict[str, str]],
    timeout: int,
    max_retries: int,
    wait_on_captcha: bool,
    sleep_between_attempts: float,
) -> bytes | None:
    """Download a single case page, retrying if the response looks invalid."""

    for attempt in range(1, max_retries + 1):
        session.headers.update(next(user_agent_cycle))
        response = session.get(url, timeout=timeout)
        content = response.content

        if not detect_captcha_or_short_response(content):
            return content

        message = (
            f"Attempt {attempt}/{max_retries}: Captcha or short response detected at {url}."
        )
        print(message)

        if wait_on_captcha:
            input(
                "Open the URL in a browser, solve any captcha, then press Enter to retry..."
            )

        if attempt < max_retries:
            time.sleep(sleep_between_attempts)

    return None


def build_user_agents(custom_user_agent: str | None) -> tuple[dict[str, str], ...]:
    """Return a single header dictionary in a tuple for cycling."""

    if custom_user_agent:
        return (
            {
                "User-Agent": custom_user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
        )

    return (DEFAULT_USER_AGENT,)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bulk download OSCN CM docket pages.")
    parser.add_argument("--county", required=True, help="County slug used by OSCN (e.g., tulsa, oklahoma).")
    parser.add_argument("--year", type=int, default=2025, help="Case year, e.g., 2025.")
    parser.add_argument("--start", type=int, required=True, help="Starting case number (inclusive).")
    parser.add_argument("--end", type=int, required=True, help="Ending case number (inclusive).")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("downloads") / "cm",
        help="Where to save downloaded HTML files.",
    )
    parser.add_argument(
        "--pad-width",
        type=int,
        default=6,
        help="Zero-pad case numbers to this width (use 0 for no padding).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Seconds to sleep between successful requests (0 to disable).",
    )
    parser.add_argument(
        "--sleep-on-retry",
        type=float,
        default=2.0,
        help="Seconds to sleep between retry attempts when responses look invalid.",
    )
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds.")
    parser.add_argument(
        "--max-retries", type=int, default=3, help="Number of attempts before giving up on a case."
    )
    parser.add_argument(
        "--wait-on-captcha",
        action="store_true",
        help=(
            "Pause and prompt when a captcha or short response is detected instead of immediately retrying."
        ),
    )
    parser.add_argument(
        "--user-agent",
        help=(
            "Override the default rotating user agents with a single custom one (e.g., include your bypass key)."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.start > args.end:
        print("Start number must be less than or equal to end number.")
        return 1

    ensure_output_directory(args.output_dir)

    case_numbers = range(args.start, args.end + 1)
    total = args.end - args.start + 1
    user_agents = cycle(build_user_agents(args.user_agent))

    with requests.Session() as session:
        for idx, case_number in enumerate(case_numbers, start=1):
            case_id = build_case_identifier(args.year, case_number, args.pad_width)
            url = build_case_url(args.county, case_id)

            content = download_case(
                session=session,
                url=url,
                user_agent_cycle=user_agents,
                timeout=args.timeout,
                max_retries=args.max_retries,
                wait_on_captcha=args.wait_on_captcha,
                sleep_between_attempts=args.sleep_on_retry,
            )

            if content is None:
                print(f"Skipping {case_id}: maximum retries reached.")
                continue

            output_path = args.output_dir / f"{case_id}.html"
            output_path.write_bytes(content)
            print(f"[{idx}/{total}] Saved {output_path}")

            if args.sleep > 0:
                time.sleep(args.sleep)

    return 0


if __name__ == "__main__":
    sys.exit(main())
