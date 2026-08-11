from bs4 import BeautifulSoup
import time
from playwright.sync_api import sync_playwright


def run_playwright():
    with sync_playwright() as playwright:
        with playwright.chromium.launch(headless=False) as browser:
            page = browser.new_page(java_script_enabled=True)
            page.goto("https://ksd.ua/books/khudozni", wait_until="load")
            page.wait_for_timeout(2000)
            page.wait_for_selector(
                "input[placeholder='Пошук в КСД']:visible", timeout=5000
            )
            search = page.locator("input[placeholder='Пошук в КСД']:visible")

            if search:
                search.fill("Все про")
                time.sleep(1)
                page.keyboard.press("Enter")
                page.wait_for_timeout(50)
            sort_menu = page.get_by_role("combobox")
            sort_menu.click()
            page.get_by_role("option", name="Від нових до старих").click()
            page.wait_for_timeout(50)
            page.get_by_role("link", name="Всі книги", exact=True).click()
            page.wait_for_timeout(10)
            page.get_by_role("button", name="Зменшити каталог").click()
            page.wait_for_timeout(10)
            page.get_by_role("button", name="Авторизуватись").click()
            page.close()


run_playwright()
