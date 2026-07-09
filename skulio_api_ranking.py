#!/usr/bin/env python3
"""
Skulio.pl school ranking fetcher — hardcoded to Gdańsk + Gdynia,
looping over years 2019-2025 AND over two subject modes:
  1. Original/overall endpoint (no subject param)
  2. &subject=mathematics

Locations are hardcoded from this URL pattern:
https://skulio.pl/ranking?locations=[{"type":"city","name":"Gdańsk","teryt_code":null,"voivodeship":"POMORSKIE"},{"type":"city","name":"Gdynia","teryt_code":null,"voivodeship":"POMORSKIE"}]&year=2025

Second endpoint variant (with subject):
https://skulio.pl/ranking?locations=[...]&year=2025&subject=mathematics

Note: Skulio's /ranking page ignores the `locations` query parameter
server-side. This script instead calls the underlying JSON API directly:

    https://skulio.pl/api/v1/rankings?city=<city>&voivodeship=<voivodeship>&year=<year>&exam_type=e8[&subject=mathematics]

which filters correctly by city+voivodeship (and subject). Since that
endpoint returns the WHOLE voivodeship ranking (paginated), we page
through all results and keep only rows matching Gdańsk or Gdynia.

For each (year, subject) combination, a separate CSV file is written:
  - overall:      skulio_ranking_gdansk_gdynia_2023.csv
  - mathematics:  skulio_ranking_gdansk_gdynia_mathematics_2023.csv

Usage:
    python skulio_ranking_hardcoded.py
"""

import csv
import time
from time import sleep

import requests

LOCATIONS = [
    {"type": "city", "name": "Gdańsk", "teryt_code": None, "voivodeship": "POMORSKIE"},
    {"type": "city", "name": "Gdynia", "teryt_code": None, "voivodeship": "POMORSKIE"},
]

YEARS = range(2019, 2027)  # 2019 through 2025 inclusive
SUBJECTS = [None, "mathematics"]  # None -> original endpoint (overall)

EXAM_TYPE = "e8"
API_URL = "https://skulio.pl/api/v1/rankings"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json",
}
TIMEOUT = 20

CSV_FIELDS = [
    "position", "school_id", "school_name", "slug", "city",
    "voivodeship", "score", "voivodeship_position",
    "voivodeship_total", "is_public",
]

OUTPUT_TEMPLATE_OVERALL = "skulio_ranking_gdansk_gdynia_{year}.csv"
OUTPUT_TEMPLATE_SUBJECT = "skulio_ranking_gdansk_gdynia_{subject}_{year}.csv"


def fetch_city_ranking(city, voivodeship, year, subject):
    matched = []
    page = 1
    while True:
        params = {
            "city": city, "voivodeship": voivodeship, "year": year,
            "exam_type": EXAM_TYPE, "page": page,
        }
        if subject:
            params["subject"] = subject

        resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=TIMEOUT)
        sleep(5)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("items", [])
        page_matches = [i for i in items if i.get("city") == city]
        matched.extend(page_matches)

        page_size = data.get("page_size", 50)
        print(f"    [{city}] page {page}: {len(page_matches)} matching / {len(items)} total")

        if len(items) < page_size:
            break
        page += 1

    return matched


def fetch_combo(year, subject):
    all_items = []
    for loc in LOCATIONS:
        city, voivodeship = loc["name"], loc["voivodeship"]
        label = subject if subject else "overall"
        print(f"  Fetching {city} ({voivodeship}) for year {year}, subject={label}...")
        all_items.extend(fetch_city_ranking(city, voivodeship, year, subject))

    seen, unique = set(), []
    for item in all_items:
        sid = item.get("school_id")
        if sid not in seen:
            seen.add(sid)
            unique.append(item)

    unique.sort(key=lambda x: x.get("score") or 0, reverse=True)
    for idx, item in enumerate(unique, 1):
        item["position"] = idx

    return unique


def write_csv(schools, output_path):
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(schools)


def main():
    print(f"Locations: {', '.join(l['name'] for l in LOCATIONS)}")
    print(f"Years: {YEARS.start}-{YEARS.stop - 1}")
    print(f"Subjects: {[s if s else 'overall' for s in SUBJECTS]}\n")

    for subject in SUBJECTS:
        label = subject if subject else "overall"
        print(f"##### SUBJECT: {label} #####\n")

        for year in YEARS:
            print(f"=== Year {year} ({label}) ===")
            schools = fetch_combo(year, subject)

            output_path = (OUTPUT_TEMPLATE_SUBJECT.format(subject=subject, year=year)
                           if subject else OUTPUT_TEMPLATE_OVERALL.format(year=year))
            write_csv(schools, output_path)

            gdansk_count = sum(1 for i in schools if i["city"] == "Gdańsk")
            gdynia_count = sum(1 for i in schools if i["city"] == "Gdynia")
            print(f"  -> Saved {len(schools)} schools to {output_path} "
                  f"(Gdańsk: {gdansk_count}, Gdynia: {gdynia_count})\n")

            time.sleep(30)

    print("All years and subjects processed.")


if __name__ == "__main__":
    main()