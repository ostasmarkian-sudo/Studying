# Python Learning Projects

A collection of Python projects and exercises created while learning backend
development, automation, web scraping, databases, and asynchronous
programming. This repository documents my progress from small language
exercises to more practical applications.

## Projects

### Website Monitoring System

Located in `website monitoring/`.

An application for monitoring website availability. It checks saved URLs,
records response status and timing data in PostgreSQL, and is designed to send
Telegram notifications when a website changes its availability status.

**Main concepts:** `asyncio`, `aiohttp`, PostgreSQL, `psycopg`, HTTP requests,
Telegram Bot API, error handling, and scheduled monitoring.

### DigiKey Web Scraper

Located in `web_scrapers/vd_scrape/`.

An asynchronous scraper for collecting product information from the DigiKey
catalog. It uses a browser automation workflow to capture product data,
normalizes the collected records, and stores them in PostgreSQL.

**Main concepts:** Patchright/Playwright, asynchronous queues, browser
automation, data filtering, pagination, JSON processing, and PostgreSQL.

**Current limitation:** the scraper currently runs reliably on Linux and macOS.
On Windows, Patchright conflicts with PostgreSQL-related subprocess
handling, which prevents the full scraper pipeline from starting correctly.

### Telegram Bots

Located in `tg bots/`.

This folder contains two Telegram bot projects:

- **Currency bot** — converts between currencies using exchange-rate data from
  the Frankfurter API.
- **Watermark bot** — receives an image, applies a repeated text watermark,
  and returns the processed image to the user.

**Main concepts:** Telegram Bot API, REST APIs, environment variables, Pillow,
image processing, and user input handling.

### Small Python Projects

Located in `small projects/`.

A set of focused exercises and experiments used to practise Python basics and
backend-related tools. Topics include classes, functions, regular expressions,
CSV files, HTTP requests, testing, FastAPI, and PostgreSQL.

Examples include a phone-number validator with tests, CSV processing scripts,
simple web scrapers, and FastAPI experiments.

### Asyncio Example

`asyns.py` is a compact example of concurrent task execution with
`asyncio.TaskGroup`.

## Technologies

- Python
- asyncio and aiohttp
- PostgreSQL and psycopg
- Patchright / Playwright
- Telegram Bot API and pyTelegramBotAPI
- FastAPI
- Requests and Beautiful Soup
- Pillow

## Repository Status

This is an educational repository. The projects are actively used for learning,
experimentation, and gradual improvement rather than as production-ready
applications.

## Author

[ostasmarkian-sudo](https://github.com/ostasmarkian-sudo)
