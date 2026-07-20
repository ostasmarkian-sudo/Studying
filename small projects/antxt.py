from collections import Counter
import re
import sys


def filt(log_name):
    with open(log_name) as f:
        reader2 = f.read()
        reader1 = reader2.lower()
        reader = re.sub(r"[.,]", "", reader1).split(" ")
        return reader


co = filt(r"C:\Users\marki\Documents\Studying Projects\small projects\text.txt")
count = Counter(co)
print(count)
print(sum(count.values()))
print(count.most_common(5))
print(max(count, key=len))
