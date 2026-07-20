import json
import requests
import time

start = time.perf_counter()
with open(
    r"C:\Users\marki\Documents\Studying Projects\small projects\sites.txt",
    "r",
) as f:
    reader = f.read().splitlines()
    for site in reader:
        try:
            req = requests.get(site, timeout=5)
            req.raise_for_status()
        except requests.exceptions.Timeout:
            print("The Server isn'tresponding")
        except requests.exceptions.ConnectionError:
            print("don't have connect")
        except requests.exceptions.HTTPError as error:
            print(f"{site} — HTTP-помилка: {error}")
        else:
            elapsed = time.perf_counter() - start
            print(f"{site}")
            print(req.status_code)
            print(f"Час запиту: {elapsed:.3f} сек")
