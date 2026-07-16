import sys
import csv
from tabulate import tabulate

if len(sys.argv) > 2:
    sys.exit("Too many command-line arguments")
elif len(sys.argv) < 2:
    sys.exit("Too few command-line arguments")
else:
    try:
        menu = sys.argv[1]
        if not menu.endswith(".csv"):
            sys.exit("incorrect")
        with open(menu, "r") as f:
            reader = csv.reader(f)
            data = list(reader)
        header = data[0]
        rows = data[1:]
        print(tabulate(rows, header, tablefmt="grid"))
    except FileNotFoundError:
        sys.exit("File does not exist")
