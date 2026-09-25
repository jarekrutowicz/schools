#!/usr/bin/env python3
"""Pobiera laureatów i finalistów OMJ z Gdańska, Gdyni i Sopotu.

Uruchomienie:
    python matematyka_konkurs.py

Wynik jest zapisywany do ``matematyka_konkurs.csv`` w katalogu skryptu.
"""

import csv
import html
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


BASE_URL = "https://omj.edu.pl/{}"
EDITIONS = (
    "xxi", "xx", "xix", "xviii", "xvii", "xvi", "xv", "xiv", "xiii",
    "xii", "xi", "x", "ix", "viii", "vii", "vi", "v", "iv", "iii",
    "ii", "i",
)
URL_ALIASES = {
    "xv": ("laureacifinalisci-xv", "wyroznieni-xv", "laureaci-xv"),
    "xiv": ("laureacifinalisci-xiv", "laureaci-xiv"),
    "xiii": ("laureacifinalisci-xiii", "laureaci-xiii"),
    "xii": ("laureacifinalisci-xii", "laureaci-xii"),
    "xi": ("laureacifinalisci-xi", "laureaci-xi"),
    "x": ("laureacifinalisci-x", "laureaci-x"),
    "ix": ("laureacifinalisci-ix", "laureaci-ix"),
    "viii": ("laureacifinalisci-viii", "laureaci-viii"),
    "vii": ("laureacifinalisci-vii", "laureaci-vii"),
    "vi": ("laureacifinalisci-vi", "laureaci-vi"),
    "v": ("laureacifinalisci-v", "laureaci-v"),
    "iv": ("laureacifinalisci-iv", "laureaci-iv"),
    "iii": ("laureacifinalisci-iii", "laureaci-iii"),
    "ii": ("laureacifinalisci-ii", "laureaci-ii"),
    "i": ("laureacifinalisci-i", "laureaci-i"),
}
TARGET_CITIES = {"Gdańsk", "Gdynia", "Sopot"}
OUTPUT = Path(__file__).with_name("matematyka_konkurs.csv")
FIELDS = [
    "edycja", "rok", "status", "stopien", "nazwisko", "imie", "klasa",
    "szkola", "miejscowosc", "zrodlo",
]


def clean(value):
    value = html.unescape(value).replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


class TableParser(HTMLParser):
    """Wyciąga wiersze tabel oraz nagłówki sekcji z HTML strony OMJ."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.current_row = None
        self.current_cell = None
        self.headings = []
        self.heading_level = None
        self.heading_text = []
        self.label_tag = None
        self.label_text = []
        self.last_section = ""

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.heading_level = int(tag[1])
            self.heading_text = []
        elif tag in {"strong", "b", "caption"}:
            self.label_tag = tag
            self.label_text = []
        elif tag == "tr":
            self.current_row = []
        elif tag in {"td", "th"} and self.current_row is not None:
            self.current_cell = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            heading = clean("".join(self.heading_text))
            if heading:
                self.headings.append(heading)
                if re.search(r"laureaci|finaliści", heading, re.I):
                    self.last_section = heading
            self.heading_level = None
            self.heading_text = []
        elif tag == self.label_tag:
            label = clean("".join(self.label_text))
            if re.search(r"laureaci|finaliści|finaliści", label, re.I):
                self.last_section = label
            self.label_tag = None
            self.label_text = []
        elif tag in {"td", "th"} and self.current_cell is not None:
            self.current_row.append(clean("".join(self.current_cell)))
            self.current_cell = None
        elif tag == "tr" and self.current_row is not None:
            if self.current_row:
                self.rows.append((self.last_section, self.current_row))
            self.current_row = None

    def handle_data(self, data):
        if self.current_cell is not None:
            self.current_cell.append(data)
        elif self.heading_level is not None:
            self.heading_text.append(data)
        elif self.label_tag is not None:
            self.label_text.append(data)


def fetch(url):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")


def fetch_edition(edition):
    candidates = URL_ALIASES.get(edition, (f"laureacifinalisci-{edition}",))
    last_error = None
    for slug in candidates:
        url = BASE_URL.format(slug)
        try:
            return url, fetch(url)
        except Exception as error:
            last_error = error
    raise last_error


def parse_page(edition, source_url, content):
    parser = TableParser()
    parser.feed(content)
    result = []
    current_headers = None
    for section, cells in parser.rows:
        normalized = [clean(cell).lower() for cell in cells]
        if "nazwisko" in normalized and "miejscowość" in normalized:
            current_headers = normalized
            continue
        if not current_headers or len(cells) < len(current_headers):
            continue
        values = dict(zip(current_headers, cells))
        city = clean(values.get("miejscowość", ""))
        if city not in TARGET_CITIES:
            continue
        status = "Finalista" if re.search(r"finali", section, re.I) else "Laureat"
        degree_match = re.search(r"([IVX]+)\s*stopnia", section, re.I)
        result.append({
            "edycja": edition.upper(),
            "rok": edition_year(edition, content),
            "status": status,
            "stopien": degree_match.group(1).upper() if degree_match else "",
            "nazwisko": values.get("nazwisko", ""),
            "imie": values.get("imię", values.get("imie", "")),
            "klasa": values.get("klasa", ""),
            "szkola": values.get("szkoła", values.get("szkola", "")),
            "miejscowosc": city,
            "zrodlo": source_url,
        })
    return result


def edition_year(edition, content):
    match = re.search(r"\((\d{4})/(\d{2,4})\)", content)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    return ""


def main():
    all_rows = []
    for number, edition in enumerate(EDITIONS, 1):
        url = BASE_URL.format(f"laureacifinalisci-{edition}")
        try:
            url, content = fetch_edition(edition)
            rows = parse_page(edition, url, content)
            all_rows.extend(rows)
            print(f"[{number:02}/{len(EDITIONS)}] {edition.upper()}: {len(rows)} wyników")
        except Exception as error:
            print(f"BŁĄD {edition.upper()} ({url}): {error}", file=sys.stderr)
        time.sleep(0.2)

    all_rows.sort(key=lambda row: (row["edycja"], row["miejscowosc"], row["nazwisko"], row["imie"]))
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Zapisano {len(all_rows)} rekordów do {OUTPUT}")


if __name__ == "__main__":
    main()
