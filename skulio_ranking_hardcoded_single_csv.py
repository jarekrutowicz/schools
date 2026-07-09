#!/usr/bin/env python3
import csv
import time
from time import sleep

import requests

LOCATIONS = [
    {"type": "city", "name": "Gdańsk", "teryt_code": None, "voivodeship": "POMORSKIE"},
    {"type": "city", "name": "Gdynia", "teryt_code": None, "voivodeship": "POMORSKIE"},
]

YEARS = range(2019, 2026)
SUBJECTS = [None, "mathematics"]

EXAM_TYPE = "e8"
API_URL = "https://skulio.pl/api/v1/rankings"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json",
}
TIMEOUT = 20
OUTPUT_FILE = "skulio_ranking_gdansk_gdynia_2019_2025_all.csv"

CSV_FIELDS = [
    "year",
    "subject",
    "position",
    "school_id",
    "school_name",
    "slug",
    "city",
    "voivodeship",
    "score",
    "voivodeship_position",
    "voivodeship_total",
    "is_public",
]


def fetch_city_ranking(city, voivodeship, year, subject):
    matched = []
    page = 1
    while True:
        params = {
            "city": city,
            "voivodeship": voivodeship,
            "year": year,
            "exam_type": EXAM_TYPE,
            "page": page,
        }
        if subject:
            params["subject"] = subject

        resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("items", [])
        page_matches = [i for i in items if i.get("city") == city]
        matched.extend(page_matches)

        page_size = data.get("page_size", 50)
        label = subject if subject else "overall"
        print(f"    [{city} | {year} | {label}] page {page}: {len(page_matches)} matching / {len(items)} total")

        if len(items) < page_size:
            break
        page += 1
        sleep(10)
    return matched


def fetch_combo(year, subject):
    all_items = []
    for loc in LOCATIONS:
        city = loc["name"]
        voivodeship = loc["voivodeship"]
        all_items.extend(fetch_city_ranking(city, voivodeship, year, subject))

    seen = set()
    unique = []
    for item in all_items:
        sid = item.get("school_id")
        if sid not in seen:
            seen.add(sid)
            unique.append(item)

    unique.sort(key=lambda x: x.get("score") or 0, reverse=True)
    subject_label = subject if subject else "overall"
    for idx, item in enumerate(unique, 1):
        item["position"] = idx
        item["year"] = year
        item["subject"] = subject_label

    return unique


def write_csv(rows, output_path):
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    all_rows = []

    print(f"Locations: {', '.join(l['name'] for l in LOCATIONS)}")
    print(f"Years: {YEARS.start}-{YEARS.stop - 1}")
    print(f"Subjects: {[s if s else 'overall' for s in SUBJECTS]}\n")

    for subject in SUBJECTS:
        label = subject if subject else "overall"
        print(f"##### SUBJECT: {label} #####\n")

        for year in YEARS:
            print(f"=== Year {year} ({label}) ===")
            rows = fetch_combo(year, subject)
            all_rows.extend(rows)

            gdansk_count = sum(1 for i in rows if i["city"] == "Gdańsk")
            gdynia_count = sum(1 for i in rows if i["city"] == "Gdynia")
            print(f"  -> Appended {len(rows)} rows (Gdańsk: {gdansk_count}, Gdynia: {gdynia_count})\n")

            time.sleep(10)

    write_csv(all_rows, OUTPUT_FILE)
    print(f"Saved {len(all_rows)} rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
