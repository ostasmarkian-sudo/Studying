import ddddocr
from curl_cffi import requests
import asyncio
ocr = ddddocr.DdddOcr(show_ad=False)
s = requests.Session(impersonate="chrome")
async def captcha():
    