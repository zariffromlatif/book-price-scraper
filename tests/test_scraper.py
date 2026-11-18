"""Tests for scraper.py. None of them touches the network.

The two HTML files in tests/fixtures are real pages saved from books.toscrape.com
(the first and the last page of the catalogue).
"""

import csv
from pathlib import Path

import pytest
import requests

import scraper

FIXTURES = Path(__file__).parent / "fixtures"
PAGE_1_URL = "https://books.toscrape.com/catalogue/page-1.html"
PAGE_50_URL = "https://books.toscrape.com/catalogue/page-50.html"


def page(name):
    return (FIXTURES / name).read_bytes()


# --- reading books out of a page -------------------------------------------


def test_a_catalogue_page_gives_twenty_books():
    books = scraper.parse_books(page("page1.html"), PAGE_1_URL)

    assert len(books) == 20


def test_first_book_has_full_title_price_rating_stock_and_link():
    first = scraper.parse_books(page("page1.html"), PAGE_1_URL)[0]

    assert first == {
        "title": "A Light in the Attic",  # the page shows it cut short: "A Light in the ..."
        "price_gbp": 51.77,
        "rating": 3,
        "in_stock": True,
        "url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
    }


# --- finding the next page -------------------------------------------------


def test_next_page_link_is_turned_into_a_full_address():
    assert (
        scraper.next_page_url(page("page1.html"), PAGE_1_URL)
        == "https://books.toscrape.com/catalogue/page-2.html"
    )


def test_last_page_has_no_next_page():
    assert scraper.next_page_url(page("page50.html"), PAGE_50_URL) is None


# --- downloading a page, with retries --------------------------------------


class FakeResponse:
    def __init__(self, status_code, content=b""):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)


class FakeSession:
    """Stands in for requests.Session: hands out the prepared answers in order."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0

    def get(self, url, timeout):
        self.calls += 1
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def no_wait(seconds):
    pass


def test_fetch_tries_again_after_a_server_error():
    session = FakeSession(
        [FakeResponse(503), requests.ConnectionError("dropped"), FakeResponse(200, b"ok")]
    )

    content = scraper.fetch(session, PAGE_1_URL, retries=3, wait=no_wait)

    assert content == b"ok"
    assert session.calls == 3


def test_fetch_gives_up_after_the_allowed_number_of_tries():
    session = FakeSession([FakeResponse(503)] * 3)

    with pytest.raises(requests.HTTPError):
        scraper.fetch(session, PAGE_1_URL, retries=3, wait=no_wait)

    assert session.calls == 3


def test_fetch_does_not_retry_a_missing_page():
    session = FakeSession([FakeResponse(404), FakeResponse(200, b"ok")])

    with pytest.raises(requests.HTTPError):
        scraper.fetch(session, PAGE_1_URL, retries=3, wait=no_wait)

    assert session.calls == 1


def test_fetch_waits_longer_before_each_new_try():
    waits = []
    session = FakeSession([FakeResponse(503), FakeResponse(503), FakeResponse(200, b"ok")])

    scraper.fetch(session, PAGE_1_URL, retries=3, backoff=1.0, wait=waits.append)

    assert waits == [1.0, 2.0]


# --- walking through the pages ---------------------------------------------


def test_scrape_stops_at_the_page_limit_and_pauses_between_pages():
    pauses = []
    downloaded = []

    def download(url):
        downloaded.append(url)
        return page("page1.html")  # every page says "next", so only the limit stops it

    books = scraper.scrape(
        PAGE_1_URL, max_pages=2, delay=1.5, download=download, wait=pauses.append
    )

    assert len(downloaded) == 2
    assert len(books) == 40
    assert pauses == [1.5]  # one pause between two pages, none after the last


def test_scrape_stops_when_there_is_no_next_page():
    books = scraper.scrape(
        PAGE_50_URL,
        max_pages=10,
        delay=0,
        download=lambda url: page("page50.html"),
        wait=no_wait,
    )

    assert len(books) == 20


# --- writing the CSV -------------------------------------------------------


def test_csv_has_a_header_and_one_row_per_book(tmp_path):
    books = scraper.parse_books(page("page1.html"), PAGE_1_URL)
    out = tmp_path / "books.csv"

    scraper.write_csv(books, out)

    with out.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 20
    assert list(rows[0]) == ["title", "price_gbp", "rating", "in_stock", "url"]
    assert rows[0]["title"] == "A Light in the Attic"
    assert rows[0]["price_gbp"] == "51.77"
