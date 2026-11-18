"""Collect book titles, prices, ratings and stock status from books.toscrape.com into a CSV.

books.toscrape.com is a practice site built for scraping. The same structure works for a real
catalogue: download a page, read the items out of it, follow the "next" link, pause, repeat.

    python scraper.py --pages 3 --out books.csv
"""

import argparse
import csv
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

START_URL = "https://books.toscrape.com/catalogue/page-1.html"
USER_AGENT = "book-price-scraper/1.0 (practice project)"
COLUMNS = ["title", "price_gbp", "rating", "in_stock", "url"]

# The site writes a rating as a word in the class name: <p class="star-rating Three">
RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def parse_books(html, page_url):
    """Return one dictionary per book on a catalogue page."""
    soup = BeautifulSoup(html, "html.parser")
    books = []
    for item in soup.select("article.product_pod"):
        link = item.select_one("h3 a")
        price_text = item.select_one("p.price_color").get_text(strip=True)
        rating_classes = item.select_one("p.star-rating")["class"]
        stock_text = item.select_one("p.availability").get_text(strip=True)
        books.append(
            {
                # The visible text is cut short ("A Light in the ..."); the title attribute is complete.
                "title": link["title"],
                "price_gbp": float(price_text.lstrip("£")),
                "rating": next(RATING_WORDS[c] for c in rating_classes if c in RATING_WORDS),
                "in_stock": stock_text == "In stock",
                # Links on the page are relative ("a-light.../index.html"), so join them to the page address.
                "url": urljoin(page_url, link["href"]),
            }
        )
    return books


def next_page_url(html, page_url):
    """Return the address of the next catalogue page, or None on the last page."""
    link = BeautifulSoup(html, "html.parser").select_one("li.next a")
    if link is None:
        return None
    return urljoin(page_url, link["href"])


def fetch(session, url, retries=3, backoff=1.0, wait=time.sleep):
    """Download one page and return its raw bytes.

    A server error (5xx) or a dropped connection is tried again, waiting longer each time:
    backoff, then 2 x backoff, and so on. A client error such as 404 is not retried, because
    asking again will not change the answer.
    """
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=15)
            if response.status_code < 500:
                response.raise_for_status()  # raises for 4xx; does nothing for 2xx
                return response.content
            response.raise_for_status()  # 5xx: raise so the retry code below handles it
        except requests.HTTPError as error:
            if error.response.status_code < 500 or attempt == retries:
                raise
        except (requests.ConnectionError, requests.Timeout):
            if attempt == retries:
                raise
        wait(backoff * attempt)


def scrape(start_url, max_pages, delay, download, wait=time.sleep):
    """Follow the "next" links from start_url and return every book found.

    Stops after max_pages pages or when a page has no next link. Pauses `delay` seconds
    between pages so the site is not hammered.
    """
    books = []
    url = start_url
    for page_number in range(1, max_pages + 1):
        html = download(url)
        books.extend(parse_books(html, url))
        url = next_page_url(html, url)
        if url is None or page_number == max_pages:
            break
        wait(delay)
    return books


def write_csv(books, path):
    """Write the books to a CSV file with a header row."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(books)


def main():
    parser = argparse.ArgumentParser(description="Save book prices from books.toscrape.com to a CSV.")
    parser.add_argument("--pages", type=int, default=3, help="how many catalogue pages to read (default 3)")
    parser.add_argument("--out", default="books.csv", help="CSV file to write (default books.csv)")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds to pause between pages (default 1)")
    args = parser.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    def download(url):
        print(f"Reading {url}")
        return fetch(session, url)

    books = scrape(START_URL, args.pages, args.delay, download)
    write_csv(books, args.out)
    print(f"Saved {len(books)} books to {args.out}")


if __name__ == "__main__":
    main()
