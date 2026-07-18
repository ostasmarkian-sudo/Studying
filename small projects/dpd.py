import csv
import sys
if len(sys.argv) < 3:
     sys.exit("Too few command-line arguments")
elif len(sys.argv) > 3:
    sys.exit("Too many command-line arguments")
with open (sys.argv[1],"r",) as f:
        with open (sys.argv[2],"w") as r:
            reader = csv.DictReader(f)
            writer = csv.DictWriter(r, fieldnames=["first", "last", "house"])
            writer.writeheader()
            print("Writer created")
            for text in reader:
                last,first = text['name'].split(",")
                house = text['house']
                writer.writerow({
                "first": first,
                "last": last,
                "house": house 
                })