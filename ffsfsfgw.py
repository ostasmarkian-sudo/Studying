from playwright.sync_api import sync_playwright
import sys

clas = "MuiButtonBase-root MuiPaginationItem-root MuiPaginationItem-sizeLarge MuiPaginationItem-text MuiPaginationItem-circular MuiPaginationItem-page mui-1izv2jb"
if len(sys.argv) < 2:
    sys.exit("Немає ім'я")
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
            page_number = page.locator(f"//a[class={clas}]")
            ...
        elif sys.argv[2]:
            number = int(sys.argv[2])
        for i in range(number):
            book = all_books.nth(i)
            print(book.inner_text())
            print(book.get_attribute("href"))
        page.wait_for_timeout(5000)
