from playwright.sync_api import sync_playwright
import sys

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
                page.mouse.wheel(0, 700)
                pag.click()
                print(x)

        elif sys.argv[2]:
            number = int(sys.argv[2])
            for i in range(number):
                book = all_books.nth(i)
                print(book.inner_text())
                print(book.get_attribute("href"))
        page.wait_for_timeout(500)
