from playwright.async_api import async_playwright
import asyncio


async def handle_response(response):
    resource_type = response.request.resource_type

    if resource_type not in {"fetch", "xhr"}:
        return
    if "productlistshort_ajx.aspx" not in response.url:
        return
    html = await response.text()
    print("URL:", response.url)
    return html


async def open_w():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)

        page = await browser.new_page(n)

        page.on("response", handle_response)
        await page.goto(
            "https://edshop.edsystem.eu/",
            wait_until="load",
        )
        await page.locator("//a[@data-nav-id='11']").hover()
        submenu = page.locator("a.aside-nav_link[data-nav-id='115'")
        await submenu.wait_for(state="visible", timeout=5000)
        await submenu.click()
        await page.get_by_role("link", name="Show catalogue").click()
        await page.wait_for_timeout(1000)
        next_page = page.locator("//a[@id='pag_top_next']")
        numbers = await page.locator("a.pager_item").all_inner_texts()
        page_count = int(numbers[-2])
        for i in range(2, page_count + 1):
            await next_page.click()
            await page.wait_for_timeout(1000)
        await page.wait_for_timeout(10000)
        await browser.close()


async def main():
    await asyncio.gather(
        open_w(),
    )


asyncio.run(main())
