import re 
import csv
from pathlib import Path

country = {}
country_file = Path(__file__).resolve().parents[1] / "data" / "country.csv"
with country_file.open("r", encoding="utf-8") as file:
    reader = csv.reader(file)
    next(reader)
    for code, name in reader:
        country[code] = name
def get_country(code):
    return country.get(code)
text = input("write the text: ")
pattern = r"^(\+?\d{1,3}) ?\-?([0-9\-\s.]{9,14})$"
result = re.search(pattern , text)
if result:
    d = result.group(1)
    a = get_country(d)
    print(f"{a} = {d}")
    print(result.group(2))
else:
    print("incorrect")
