import os
import re
import shutil
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_file(file_path, target_folder, pattern):
    try:
        # Read file content (ignore encoding errors)
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        # If the pattern matches, move the file to the target folder
        if re.search(pattern, content, re.IGNORECASE):
            shutil.move(file_path, os.path.join(target_folder, os.path.basename(file_path)))
            return True
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
    return False

def main():
    parser = argparse.ArgumentParser(
        description="Classify docket HTML files and move forcible entry and detainer cases."
    )
    parser.add_argument("file_path", help="Folder containing docket HTML files")
    parser.add_argument("target_folder", help="Folder to move forcible entry and detainer cases")
    parser.add_argument("--pattern", default=r"forcible\s+entry",
                        help="Regex pattern to identify forcible entry and detainer cases")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker threads")
    args = parser.parse_args()

    # Create target folder if it doesn't exist
    if not os.path.exists(args.target_folder):
        os.makedirs(args.target_folder)

    # List all HTML files in the input folder
    files = [os.path.join(args.file_path, f)
             for f in os.listdir(args.file_path)
             if f.lower().endswith('.html')]

    total = len(files)
    moved_count = 0

    # Process files concurrently using a ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_file, file, args.target_folder, args.pattern): file for file in files}
        for future in as_completed(futures):
            if future.result():
                moved_count += 1

    print(f"Processed {total} files. Moved {moved_count} forcible entry and detainer cases.")

import sys
sys.argv = ['notebook', 'SC-24Tulsa', 'SC-24Tulsa/FEDs', '--pattern', r"forcible\s+entry", '--workers', '8']

main()
