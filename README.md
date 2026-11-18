# Book price scraper

A small Python scraper that collects book titles, prices, ratings and stock status from
[books.toscrape.com](https://books.toscrape.com) and saves them to a CSV file.

books.toscrape.com is a practice site built for scraping. The structure here is the one I use for a real
catalogue: download a page, read the items, follow the "next" link, pause, repeat.

## Run it

```
pip install -r requirements.txt
python scraper.py --pages 3 --out books.csv
```

| Option | Meaning | Default |
|---|---|---|
| `--pages` | How many catalogue pages to read (20 books each, 50 pages exist) | 3 |
| `--out` | CSV file to write | books.csv |
| `--delay` | Seconds to pause between pages | 1 |

## What you get

`sample-output.csv` is a real run of two pages (40 books).

| title | price_gbp | rating | in_stock | url |
|---|---|---|---|---|
| A Light in the Attic | 51.77 | 3 | True | https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html |
| Tipping the Velvet | 53.74 | 1 | True | https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html |

## How it behaves

- **Clean values.** Prices are numbers (51.77, not "£51.77"), ratings are 1 to 5 (the site writes them as
  words), titles are complete (the page cuts long ones short), and links are full addresses.
- **Polite.** One request at a time, a pause between pages, and a User-Agent that says what it is.
- **Retries.** A server error or a dropped connection is tried up to three times, waiting longer each time.
  A missing page (404) is not retried.
- **Stops by itself** at the page limit or on the last page.

## Tests

```
python -m pytest
```

11 tests, none of which touches the network. They read two real pages saved in `tests/fixtures` and cover
reading books from a page, finding the next page, retrying, stopping, and the CSV format.

## Limits

It reads the catalogue pages only, so it does not collect the description or stock count shown on each
book's own page. It does not handle sites that need a login or that build their pages with JavaScript.
