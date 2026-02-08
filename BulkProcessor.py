import os
import re
import csv
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed

current_directory = os.getcwd()
directory = os.path.join(current_directory, "Small Claims", "SC-23FEDs")

# File path for the output CSV
output_csv = os.path.join(directory, 'cases.csv')

# ---------------------------------------------------------------------------
# Pre-compiled regex patterns for field extraction
# (avoids recompiling on every file)
# ---------------------------------------------------------------------------
_RE_PLAINTIFF = re.compile(r'(?<=td valign="center" width="50%">)(.*)(?=,)')
_RE_DEFENDANT = re.compile(r'v.<br />[\r\n]+([^\r\n]+)(.*)(?=,)')
_RE_MONEY_PLUS = re.compile(r'(?<=AMOUNT IN DEBT OF )(.*)(?= \+)')
_RE_MONEY_POSS = re.compile(r'(?<=AMOUNT IN DEBT OF)(.*)(?= POSS)')
_RE_MONEY_CLEAN = re.compile(r'[^\d.]+')
_RE_MONEY_DOTS = re.compile(r'^\.*')
_RE_FILED = re.compile(r'Filed:\s+(\d{2}/\d{2}/\d{4})')
_RE_CLOSED = re.compile(r'Closed:\s+(\d{2}/\d{2}/\d{4})')
_RE_BARCODE = re.compile(r'(&bc=\d+&fmt=tif)')
_RE_ATTY = re.compile(r'(?<=<td valign="top" width="50%">)(.*)(?=,&nbsp;)')

# ---------------------------------------------------------------------------
# Boolean patterns – simple case-insensitive substring checks via str.lower()
# are ~5-10x faster than individual re.search() calls on each file.
# ---------------------------------------------------------------------------
_SIMPLE_PATTERNS = (
    'answer',                       # 1  → Answer
    'transferred',                  # 2  → Transfer
    'under advisement',             # 3  → JUA
    'execution instruction form',   # 4  → ExecutionFiled
    'execution returned',           # 5  → ExecutionReturns
    'journal entry of judgment',    # 6  → JEs
    'voluntary dismissal',          # 7  → VoluntaryDismissal
    'dismissed by court',           # 8  → CourtDismissal
    'dismissed',                    # 9  → Dismissed
    'motion to vacate',             # 10 → MTV
    'jury trial',                   # 11 → Trial
    'pers serv',                    # 12 → PersonalService
    'served - post',                # 13 → ConstructiveService
    'by serving',                   # 14 → OccupantService
)

# Complex patterns that genuinely require regex (optional groups / lookahead)
_RE_DEF_NOT_APPEAR = re.compile(r'DEFENDANT(S)? APPEARED NOT', re.IGNORECASE)
_RE_DEF_APPEAR = re.compile(r'DEFENDANT(S)?(?: \w+){0,3} APPEARED(?! NOT)', re.IGNORECASE)

CSV_HEADER = [
    'Docket Number', 'Plaintiff', 'Defendant', 'Docket Links', 'Petition', 'Document2',
    'Filed', 'Closed', 'Rent',
    'Answer', 'Transfer', 'JUA', 'ExecutionFiled', 'ExecutionReturns', 'JEs',
    'VoluntaryDismissal', 'CourtDismissal', 'Dismissed', 'MTV', 'Trial',
    'PersonalService', 'ConstructiveService', 'OccupantService', 'Served',
    'DefNoAppear', 'DefAppear', 'Unserved', 'Atty1', 'Atty2', 'Atty3'
]


def _extract_fields(html):
    """Extract structured fields from a single case HTML page."""
    try:
        plaintiff = _RE_PLAINTIFF.findall(html)
        defendant = _RE_DEFENDANT.findall(html)

        plaintiff = plaintiff[0] if plaintiff else '.'
        defendant = defendant[0] if defendant else '.'

        money = _RE_MONEY_PLUS.findall(html)
        if not money:
            money = _RE_MONEY_POSS.findall(html)
        money = money[0] if money else '.'

        # Clean the money string
        money = _RE_MONEY_CLEAN.sub('', money)
        money = _RE_MONEY_DOTS.sub('', money)

        filing_date_match = _RE_FILED.search(html)
        closed_date_match = _RE_CLOSED.search(html)
        filed = filing_date_match.group(1) if filing_date_match else ""
        closed = closed_date_match.group(1) if closed_date_match else ""

        barcodelinks = _RE_BARCODE.findall(html)
        barcodelinks = [e.replace("amp;", "") for e in barcodelinks]
        barcodelinks = ["https://www.oscn.net/dockets/GetDocument.aspx?ct=tulsa" + e for e in barcodelinks]

        atty = _RE_ATTY.findall(html)

        # what if we don't find any documents?
        if len(barcodelinks) == 0:
            petition = "NONE"
            cares = "NONE"
        # what if we find one document?
        elif len(barcodelinks) == 1:
            petition = barcodelinks[0]
            cares = "NONE"
        # what if we find 2+ documents?
        else:
            petition = barcodelinks[0]
            cares = barcodelinks[1]

        petition = "=HYPERLINK(\"" + petition + "\", \"Petition\")"
        cares = "=HYPERLINK(\"" + cares + "\", \"NTQ\")"

        atty1 = atty[0] if len(atty) > 0 else ""
        atty2 = atty[1] if len(atty) > 1 else ""
        atty3 = atty[2] if len(atty) > 2 else ""

        return plaintiff, defendant, petition, cares, filed, closed, money, atty1, atty2, atty3

    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None, None, None, None, None, None, None, None, None


def process_file(filepath):
    """Process a single HTML file and return a complete CSV row.

    Designed to run in a worker process – all state is either passed in
    or lives in module-level pre-compiled constants.
    """
    filename = os.path.basename(filepath)

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract structured fields
    plaintiff, defendant, petition, cares, filed, closed, money, atty1, atty2, atty3 = _extract_fields(content)

    # One .lower() call, then fast O(n) substring checks for 14 simple patterns
    content_lower = content.lower()
    simple_results = [p in content_lower for p in _SIMPLE_PATTERNS]

    # Complex regex patterns (need optional groups / negative lookahead)
    has_def_not_appear = _RE_DEF_NOT_APPEAR.search(content) is not None
    has_def_appear = _RE_DEF_APPEAR.search(content) is not None
    has_unserved = 'unserved' in content_lower
    has_served = 'served' in content_lower

    # Build case identifiers
    case_number = filename.split('.')[0]
    docketnum = "SC-23-" + str(case_number)
    docketlink = "=HYPERLINK(\"https://www.oscn.net/dockets/GetCaseInformation.aspx?db=tulsa&number=" + docketnum + "\", \"Docket\")"

    # Column order matches the original: has_1-14, has_18(Served), has_15, has_16, has_17
    return [
        docketnum, plaintiff, defendant, docketlink, petition, cares,
        filed, closed, money,
        *simple_results,       # 14 booleans: patterns 1-14
        has_served,            # pattern 18 → 'Served'
        has_def_not_appear,    # pattern 15 → 'DefNoAppear'
        has_def_appear,        # pattern 16 → 'DefAppear'
        has_unserved,          # pattern 17 → 'Unserved'
        atty1, atty2, atty3
    ]


if __name__ == '__main__':
    html_files = glob.glob(os.path.join(directory, '*.html'))
    total = len(html_files)
    print(f"Processing {total} files...")

    # Process files concurrently using threads (avoids Windows process-spawn crashes)
    rows = []
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(process_file, f): f for f in html_files}
        for future in as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as e:
                print(f"Error processing {futures[future]}: {e}")

    # Sort by docket number for consistent, reproducible output
    rows.sort(key=lambda r: r[0])

    # Batch-write all rows at once (one I/O call instead of thousands)
    with open(output_csv, 'w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)

    print(f"Data exported to {output_csv} ({len(rows)} cases)")
