# Python Learning Projects

Backend and automation projects written while learning Python — web scraping,
async I/O, PostgreSQL, and API integrations. The repository is a learning log.

Python 3.14 · PostgreSQL · asyncio

---

## Repository layout

```
web_scrapers/
  digikey_scrape/       API-level scraper for the DigiKey catalog   (main project)
    main.py               pipeline entry point
    playwright_.py        browser session, category tree, page requests
    filter.py             record -> Product dataclass
    db.py, test.py        PostgreSQL upserts / scratch checks
  avnet_scrape/         same approach applied to Avnet              (WIP)
    scraper.py, db.py, schema.sql
  stex24_scraper/       stex24.com — catalogue and stock
    scraper.py, db.py, schema.sql
  automation24_scrape/  automation24.com — article list
    scraper.py, db.py, schema.sql
  reichelt_scraper/     reichelt.de                                 (WIP)
    scraper.py
  scraper.py            Playwright practice: search + sort + filters on ksd.ua
  ffsfsfgw.py           CLI book scraper with pagination (ksd.ua)
  akdkda.py             Playwright response-listener experiment (ksd.ua)
  postgrewithpandas.py  pandas + SQLAlchemy reads over the scraped databases

vihicle monitoring/
  auto_ria/
    scraper.py          auto.ria.com listings
    urls.npy

website monitoring/     async uptime checker writing history to PostgreSQL
  database.py           add a site, print check history, delete a site and its checks
  monitoring.py         the async checker
  main.py               argparse CLI, APScheduler, Telegram notifications  (incomplete)

tg bots/bots/           currency converter and image watermark bots
  currency_bot.py, watermark_bot.py, bot.py

small projects/         exercises: regex, CSV, requests, pytest, FastAPI, Pillow, NumPy

cars.jsonl, cars.npy    scraped data kept at the repo root
```

---

## Small projects

| File | What it does |
| --- | --- |
| `numb3rs.py`, `test_numb3rs.py` | IPv4 validator with a pytest suite |
| `main.py` | parses an nginx-style access log with a named-group regex |
| `filter.py` | filters log lines by field (date, level, user, reason) |
| `ksd_scrape.py`, `ksd_check_prise.py` | requests + BeautifulSoup scraper writing books to PostgreSQL |
| `asyns.py` | minimal `asyncio.TaskGroup` example |
| `list.py` | builds an animated GIF from images (Pillow) |
| `numpyy.py` | NumPy practice |
| `path.py` | maze solver |
| `response.py`, `request-check.py` | HTTP request experiments |

---

## Setup

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install patchright psycopg[binary,pool] lzstring aiohttp httpx curl_cffi apscheduler pyTelegramBotAPI requests beautifulsoup4 pillow fastapi numpy pandas sqlalchemy matplotlib
```

```bash
patchright install chromium
```

Configuration and secrets live in local `config.py` files and environment
variables, both git-ignored. The scrapers use a persistent browser profile
directory (also ignored) so the login and cookie state survives between runs.

---

## Author

[ostasmarkian-sudo](https://github.com/ostasmarkian-sudo)
