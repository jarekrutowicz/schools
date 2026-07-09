#!/usr/bin/env python3
"""
Generic Skulio.pl ranking page parser.

Fetches a Skulio ranking URL (any combination of query parameters such as
locations, year, exam_type, subject, etc.), extracts the ranking data
embedded in the page's __NUXT_DATA__ SSR payload, and writes it to CSV.

The page structure (Nuxt SSR flat-array data format) is assumed stable;
only the query-string arguments change between runs.

Usage:
    python skulio_ranking_parser.py --url "https://skulio.pl/ranking?year=2025&exam_type=e8" --output ranking.csv

    # Or with a locations filter (URL-encode it yourself, or pass raw and
    # requests/urllib will handle it):
    python skulio_ranking_parser.py \
        --url 'https://skulio.pl/ranking?locations=[{"type":"city","name":"Gdańsk","teryt_code":null,"voivodeship":"POMORSKIE"},{"type":"city","name":"Gdynia","teryt_code":null,"voivodeship":"POMORSKIE"}]&year=2025' \
        --output gdansk_gdynia_2025.csv
"""

import argparse
import csv
import json
import re
import sys

import requests

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
}

CSV_FIELDS = [
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


def fetch_html(url: str, timeout: int = 30) -> str:
    """Download the ranking page HTML."""
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def extract_nuxt_data(html: str) -> list:
    """
    Extract and parse the __NUXT_DATA__ JSON payload embedded in the page.

    Nuxt serializes server-rendered state as a flat JSON array where
    objects/arrays reference other elements by index (a form of
    de-duplication / pointer compression). We return this raw array;
    callers must resolve references themselves.
    """
    match = re.search(
        r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        raise ValueError(
            "Could not find __NUXT_DATA__ script tag in the page. "
            "The page structure may have changed, or the request was "
            "blocked/redirected."
        )
    return json.loads(match.group(1))


def resolve(raw: list, val):
    """Dereference a Nuxt pointer: ints (except bools) index into `raw`."""
    if isinstance(val, int) and not isinstance(val, bool) and 0 <= val < len(raw):
        return raw[val]
    return val


def parse_ranking_items(raw: list) -> list[dict]:
    """
    Walk the resolved Nuxt payload to find the ranking-initial data block
    and return a list of school dicts.
    """
    # raw[1] is the top-level {"data": <idx>, "state": <idx>, ...} map
    root = raw[1]
    state_container = resolve(raw, root.get("data"))  # -> ["ShallowReactive", <idx>]
    if isinstance(state_container, list) and len(state_container) == 2:
        state = resolve(raw, state_container[1])
    else:
        state = state_container

    ranking_initial = resolve(raw, state.get("ranking-initial"))
    data_block = resolve(raw, ranking_initial.get("data"))

    items_idx = data_block.get("items")
    item_index_list = resolve(raw, items_idx)

    schools = []
    for idx in item_index_list:
        ref = resolve(raw, idx)
        if not isinstance(ref, dict):
            continue
        row = {field: resolve(raw, val) for field, val in ref.items()}
        schools.append(row)
    return schools


def write_csv(schools: list[dict], output_path: str) -> None:
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(schools)


def main():
    import json


import urllib.parse

year = '2026'
timeout = 30

locations = [
    {"type": "city", "name": "Gdańsk", "teryt_code": None, "voivodeship": "POMORSKIE"},
    {"type": "city", "name": "Gdynia", "teryt_code": None, "voivodeship": "POMORSKIE"}
]

params = {
    "locations": json.dumps(locations, ensure_ascii=False),
    "year": year
}
# params["subject"] = "mathematics"  # optional

query_string = urllib.parse.urlencode(params)
url = f"https://skulio.pl/ranking?{query_string}"
output = 'mean' + year

print(f"Fetching: {url}")
html = fetch_html(url, timeout=timeout)

print("Extracting __NUXT_DATA__ payload...")
raw = extract_nuxt_data(html)

print("Parsing ranking items...")
schools = parse_ranking_items(raw)

if not schools:
    print("Warning: no schools found. The page structure may have "
          "changed, or the query returned zero results.", file=sys.stderr)

write_csv(schools, output)
print(f"Saved {len(schools)} rows to: {output}")

if schools:
    print("\nFirst 5 rows:")
    for s in schools[:5]:
        print(f"  {s.get('position')}. {s.get('school_name', '')[:55]} "
              f"| {s.get('city')} | score: {s.get('score')}")

if __name__ == "__main__":
    main()
