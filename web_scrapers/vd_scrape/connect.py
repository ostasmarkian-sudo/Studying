from playwright.async_api import async_playwright
import asyncio


async def connect():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    page = await browser.new_page(java_script_enabled=True)
    return playwright, browser, page


if __name__ == "__main__":
    connect()
