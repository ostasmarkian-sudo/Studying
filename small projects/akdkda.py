from playwright.sync_api import sync_playwright


def show_response(response):
    request_type = response.request.resource_type

    if request_type in ("fetch", "xhr"):
        print(response.status, response.url)


with sync_playwright() as playwright:
    with playwright.chromium.launch(headless=False) as browser:
        page = browser.new_page()

        page.goto("https://ksd.ua/", wait_until="domcontentloaded")

        page.on("response", show_response)
        page.locator("//input[@id='_R_19h8qelb_']").click()
        main_placeholder = page.locator("//input[@id='_r_0_']")
        main_placeholder.click()
        page.wait_for_timeout(5000)
