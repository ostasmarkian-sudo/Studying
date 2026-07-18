import requests


def get_quote():
    url = "https://api.frankfurter.dev/v2/currencies"
    data = requests.get(url).json()
    result = {}
    for item in data:
        result[item["iso_code"]] = item["name"]

    return result


curen = get_quote()
for code, name in curen.items():
    print(f"{code} - {name}")
