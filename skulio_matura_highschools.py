#!/usr/bin/env python3
"""Download Gdańsk and Gdynia high-school matura rankings into four CSVs.

The API returns the complete Pomeranian ranking even when ``city`` is supplied,
so the script fetches every page and keeps only the two requested cities.
"""

import csv
import time
from pathlib import Path

import requests


LOCATIONS = {"Gdańsk", "Gdynia"}
YEARS = range(2019, 2027)
SUBJECTS = {
    "overall": None,
    "mathematics": "mathematics",
    "biology": "biology",
    "chemistry": "chemistry",
}
EXAM_TYPE = "matura"
LEVEL = "rozszerzony"
API_URL = "https://skulio.pl/api/v1/rankings"
OUTPUT_TEMPLATE = "skulio_matura_gdansk_gdynia_{subject}_2019_2026.csv"
AVAILABLE_FROM_API = range(2021, 2027)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json",
}
TIMEOUT = 30
CSV_FIELDS = [
    "year", "subject", "level", "position", "school_id", "school_name",
    "slug", "city", "voivodeship", "score", "voivodeship_position",
    "voivodeship_total", "is_public",
]


def fetch_ranking(year, subject):
    if year not in AVAILABLE_FROM_API:
        return []

    rows = []
    page = 1
    while True:
        params = {
            "voivodeship": "POMORSKIE",
            "year": year,
            "exam_type": EXAM_TYPE,
            "level": LEVEL,
            "page": page,
        }
        if subject:
            params["subject"] = subject

        response = requests.get(API_URL, params=params, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items", [])
        rows.extend(item for item in items if item.get("city") in LOCATIONS)
        print(f"  {year} / {subject or 'overall'} / page {page}: "
              f"{len(items)} returned, {len(rows)} target rows")

        page_size = payload.get("page_size", 50)
        if len(items) < page_size:
            break
        page += 1
        time.sleep(1)
    return rows


def prepare_rows(rows, year, subject):
    unique = {}
    for row in rows:
        unique[row.get("school_id")] = row
    ordered = sorted(unique.values(), key=lambda row: row.get("score") or 0, reverse=True)
    for position, row in enumerate(ordered, 1):
        row["year"] = year
        row["subject"] = subject or "overall"
        row["level"] = LEVEL
        row["position"] = position
    return ordered


def write_csv(rows, subject):
    output = Path(OUTPUT_TEMPLATE.format(subject=subject))
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} rows to {output}")


def main():
    for label, subject in SUBJECTS.items():
        all_rows = []
        print(f"\n##### {label} #####")
        for year in YEARS:
            all_rows.extend(prepare_rows(fetch_ranking(year, subject), year, subject))
        write_csv(all_rows, label)


if __name__ == "__main__":
    main()
