from playwright.sync_api import sync_playwright
import sys
import math

if len(sys.argv) < 3:
    sys.exit("Вкажи назву книги та кількість або all")

with sync_playwright() as playwright:
    with playwright.chromium.launch(headless=False) as browser:
        page = browser.new_page(java_script_enabled=True)
        page.goto("https://ksd.ua/", wait_until="load")
        page.locator("//input[@id='_R_19h8qelb_']").click()
        search = page.locator("//input[@id='_r_0_']")
        search.fill(sys.argv[1])
        search.click()
        search.press("Enter")
        all_books = page.locator(
            "//a[@class='ui-catalog-card--variant-default mui-1i20r6w-ui-catalog-card']"
        )
        all_books.first.wait_for(state="visible", timeout=10_000)
        if sys.argv[2] == "all":
            x = 1
            books = all_books
            while all_books.count() == 20:
                x += 1
                pag = page.locator(f"//a[@aria-label='Go to page {x}']")
                all_books = page.locator(
                    "//a[@class='ui-catalog-card--variant-default mui-1i20r6w-ui-catalog-card']"
                )
                for i in range(all_books.count()):
                    book = all_books.nth(i)
                    print(book.inner_text())
                    print(book.get_attribute("href"))
                pag.scroll_into_view_if_needed()
                pag.click()
        else:
            number = int(sys.argv[2])
            pages = math.ceil(number / 20)

            for pager in range(1, pages + 1):
                books_to_take = min(number, 20)

                for i in range(books_to_take):
                    book = all_books.nth(i)
                    print(book.inner_text())
                    print(book.get_attribute("href"))

                number -= books_to_take

                if pager < pages:
                    next_page = pager + 1
                    pag = page.locator(f"//a[@aria-label='Go to page {next_page}']")

                    pag.scroll_into_view_if_needed()
                    pag.click()
                    page.wait_for_timeout(1000)
