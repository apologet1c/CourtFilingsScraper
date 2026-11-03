"""Thin OSCN HTTP client (stdlib urllib). Credentials come from env vars; nothing is hard-coded.

Auth: your OSCN access key is attached one of two ways, depending on how it was issued:
  OSCN_KEY + OSCN_KEY_HEADER=<Header-Name>   -> sent as a request header
  OSCN_KEY + OSCN_KEY_PARAM=<param>          -> appended as a query-string parameter
Set OSCN_COOKIE too if your access is cookie-based.
"""
from __future__ import annotations

import os
import time
import urllib.parse
import urllib.request
from datetime import date

BASE = "https://www.oscn.net/applications/oscn/"


class CaptchaError(RuntimeError):
    pass


def docket_url(judge_id: str, day: date, db: str = "Tulsa") -> str:
    # Matches the known-good form; StartDate is M/D/YY.
    params = {
        "report": "WebJudicialDocketJudgeAll",
        "errorcheck": "true",
        "db": db,
        "Judge": str(judge_id),
        "database": "",
        "StartDate": f"{day.month}/{day.day}/{day:%y}",
        "GeneralNumber": "1",
        "generalnumber1": "1",
        "GeneralCheck": "on",
    }
    return BASE + "report.asp?" + urllib.parse.urlencode(params)


def case_url(casemasterid: str, db: str = "Tulsa") -> str:
    return BASE + "GetCaseInformation.asp?" + urllib.parse.urlencode(
        {"submitted": "true", "db": db, "casemasterid": casemasterid})


class OSCNClient:
    def __init__(self):
        self.key = os.environ.get("OSCN_KEY", "")
        self.key_header = os.environ.get("OSCN_KEY_HEADER", "")
        self.key_param = os.environ.get("OSCN_KEY_PARAM", "")
        self.cookie = os.environ.get("OSCN_COOKIE", "")
        self.user_agent = os.environ.get("USER_AGENT", "CourtFilingsScraper/1.0")
        self.delay = float(os.environ.get("REQUEST_DELAY_SECONDS", "1.0"))
        self.timeout = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "30"))
        self.retries = int(os.environ.get("REQUEST_RETRIES", "3"))
        self._last = 0.0

    def _prepare(self, url: str) -> urllib.request.Request:
        if self.key and self.key_param:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode({self.key_param: self.key})
        headers = {"User-Agent": self.user_agent}
        if self.key and self.key_header:
            headers[self.key_header] = self.key
        if self.cookie:
            headers["Cookie"] = self.cookie
        return urllib.request.Request(url, headers=headers)

    def get(self, url: str) -> str:
        last_err: Exception | None = None
        for attempt in range(self.retries):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            try:
                with urllib.request.urlopen(self._prepare(url), timeout=self.timeout) as r:
                    self._last = time.monotonic()
                    text = r.read().decode("ISO-8859-1")  # OSCN declares ISO-8859-1
                if "captcha" in text.lower():
                    raise CaptchaError(f"CAPTCHA returned for {url} - check OSCN key config")
                return text
            except CaptchaError:
                raise
            except Exception as e:  # network / 5xx: back off and retry
                last_err = e
                self._last = time.monotonic()
                time.sleep(2 ** attempt * 2)
        raise RuntimeError(f"GET failed after {self.retries} tries: {url}: {last_err}")
