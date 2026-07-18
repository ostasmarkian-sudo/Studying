# Studying

A collection of small Python projects and exercises created while I learn programming.

This repository is used for practice, experiments, and tracking my progress. The projects are educational and may change as I learn new concepts and improve the code.

## Repository contents

### `small projects`

Small Python exercises covering topics such as:

- working with files and CSV data;
- regular expressions and log parsing;
- functions, classes, lists, and data processing;
- simple scripts created while learning Python fundamentals.

### `tg bots`

Telegram bot experiments built with `pyTelegramBotAPI`:

- a currency conversion bot that receives exchange-rate data from the Frankfurter API;
- a watermark bot that adds repeated text to uploaded images using Pillow.

### `sqlite`

Experiments with SQLite databases, SQL queries, and Python database integration.

### `layout-control`

A work-in-progress Python application for detecting text typed with the wrong keyboard layout and converting it between English and Ukrainian layouts.

## Technologies

- Python 3
- SQLite
- pyTelegramBotAPI
- Pillow
- Requests
- Keyboard

## Getting started

Clone the repository:

```bash
git clone https://github.com/ostasmarkian-sudo/Studying.git
cd Studying
```

Create and activate a virtual environment on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the Telegram bot dependencies:

```powershell
pip install -r "tg bots\requirements.txt"
```

For the keyboard-layout project, install the additional dependency:

```powershell
pip install keyboard
```

## Running the Telegram bots

Bot tokens are read from environment variables and must not be committed to the repository.

Currency bot:

```powershell
$env:TELEGRAM_CURRENCY_BOT_TOKEN="your-token"
python "tg bots\bots\currency_bot.py"
```

Watermark bot:

```powershell
$env:TELEGRAM_WATERMARK_BOT_TOKEN="your-token"
python "tg bots\bots\watermark_bot.py"
```

## Project status

This is an educational repository, not a production-ready application. Some files are experiments, and some projects are still in development.

## Goals

- practise writing clear and maintainable Python code;
- learn how to work with APIs, Telegram bots, images, files, and databases;
- add tests and improve project structure;
- document progress through Git commits.

## Author

[ostasmarkian-sudo](https://github.com/ostasmarkian-sudo)
