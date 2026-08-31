# Python Learning Projects

Backend and automation projects written while learning Python — web scraping,
async I/O, PostgreSQL, and API integrations. The repository is a learning log:
it goes from small language exercises to a scraper that reverse-engineers a
distributor's internal search API.

Python 3.14 · PostgreSQL · asyncio

## Repository layout

```
web_scrapers/
  digikey_scrape/     API-level scraper for the DigiKey catalog  (main project)
  avnet_scrape/       same approach applied to Avnet             (early WIP)
  scraper.py          Playwright practice: search + sort + filters on ksd.ua
  ffsfsfgw.py         CLI book scraper with pagination (ksd.ua)
website monitoring/   async uptime checker writing history to PostgreSQL
tg bots/bots/         currency converter and image watermark bots
small projects/       exercises: regex, CSV, requests, pytest, FastAPI, Pillow
```

---

## DigiKey scraper

`web_scrapers/digikey_scrape/`

An asynchronous scraper for the DigiKey electronic-component catalog. Instead of
parsing rendered HTML, it drives the site's own JSON search API.

**How it works**

1. `get_url()` opens the category tree, scrolls it to force lazy-loading, and
   collects every leaf-category link.
2. For each category, `open_w()` opens the listing page with a `response`
   listener attached. Clicking **Apply All** triggers the site's request to
   `/products/api/v5/filter-page/{id}`, and the listener captures three things
   from it: the JSON payload, the total product count, and the locale headers
   (`site`, `lang`, `x-currency`) the site sends.
3. The `s=` query parameter of that request is an **lz-string compressed JSON
   page state**. The scraper decompresses it, rewrites the pagination fields
   (`p` = page number, `pp` = 100 items per page), recompresses it, and builds a
   URL for every remaining page.
4. Those requests are issued with `page.evaluate()` — the `fetch` runs **inside
   the page context** with `credentials: "include"`, so cookies, session state,
   and the browser's TLS fingerprint all apply automatically. No session
   replication needed.
5. Results flow through an `asyncio.Queue` pipeline: `filter_data()` flattens
   each record into a `Product` dataclass, and `data_recording()` upserts it
   into PostgreSQL with `ON CONFLICT (product_id) DO UPDATE`, so re-runs refresh
   prices and stock instead of duplicating rows.

**Why this approach:** one request returns 100 structured products, versus
rendering and parsing a page per batch. It is faster, and it does not break
every time the site's CSS classes change.

**Stack:** patchright (stealth Playwright fork), persistent browser context,
`lzstring`, `asyncio.TaskGroup`, psycopg 3.

**Status:** the pagination and decoding logic works. The pipeline does not yet
run end-to-end on Windows — see [Known issues](#known-issues).

### Avnet scraper

`web_scrapers/avnet_scrape/` — the same idea against Avnet, which encodes its
filter state as **base64 JSON** rather than lz-string. Currently only builds
category URLs; early work in progress.

---

## Website monitoring

`website monitoring/`

Tracks availability of a list of websites and stores the history in PostgreSQL
(`websites` and `checks` tables).

- `database.py` — synchronous operations: add a site (with URL validation via a
  named-group regex and a duplicate check), print check history, delete a site
  and its checks.
- `monitoring.py` — the async checker. Fetches the latest known status for every
  site in one `DISTINCT ON` query, then runs all HTTP requests concurrently
  inside an `asyncio.TaskGroup`, bounded by a `Semaphore(50)`. Records status
  code, response time, availability, and a truncated error message. Timeouts and
  the `aiohttp` error hierarchy are handled separately.
- `main.py` — argparse CLI plus APScheduler for periodic runs, and a Telegram
  bot for status-change notifications. **Incomplete.**

**Stack:** `asyncio`, `aiohttp`, psycopg 3, APScheduler, pyTelegramBotAPI.

---

## Telegram bots

`tg bots/bots/`

- **`currency_bot.py`** — converts between currencies using live rates from the
  Frankfurter API.
- **`watermark_bot.py`** — takes an image and returns it with a tiled text
  watermark drawn via Pillow.

**Stack:** pyTelegramBotAPI, `requests`, Pillow.

---

## Small projects

`small projects/` — focused exercises:

| File | What it does |
| --- | --- |
| `numb3rs.py`, `test_numb3rs.py` | IPv4 validator with a pytest suite |
| `main.py` | parses an nginx-style access log with a named-group regex |
| `filter.py` | filters log lines by field (date, level, user, reason) |
| `ksd_scrape.py`, `ksd_check_prise.py` | requests + BeautifulSoup scraper writing books to PostgreSQL |
| `asyns.py` | minimal `asyncio.TaskGroup` example |
| `list.py` | builds an animated GIF from images (Pillow) |
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
pip install patchright psycopg[binary,pool] lzstring aiohttp apscheduler pyTelegramBotAPI requests beautifulsoup4 pillow fastapi
```

```bash
patchright install chromium
```

Configuration and secrets live in local `config.py` files and environment
variables, both git-ignored. The scrapers use a persistent browser profile
directory (also ignored) so the login and cookie state survives between runs.

---

## Known issues

**The DigiKey pipeline cannot run in a single process on Windows.** Two
dependencies want incompatible asyncio event loops:

- Playwright/patchright launches the browser as a **subprocess**, and asyncio
  subprocess support on Windows exists only in `ProactorEventLoop`.
- psycopg's async connections wait on sockets through `loop.add_reader()` /
  `add_writer()`, which `ProactorEventLoop` does not implement — that is why
  psycopg documents `WindowsSelectorEventLoopPolicy` for async use.

Selecting either loop breaks the other half of the pipeline. The fix is to stop
using async psycopg here and run the blocking driver in a worker thread
(`asyncio.to_thread`), leaving the default Proactor loop to the browser. Not yet
applied. On Linux and macOS the question does not arise.

---

## Author

[ostasmarkian-sudo](https://github.com/ostasmarkian-sudo)
