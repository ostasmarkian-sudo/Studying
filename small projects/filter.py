import re
import sys
import time
pattern = r"^(?P<data>(\d{4}\-\d{2}\-\d{2})\s(?P<time>\d{2}\:\d{2}\:\d{2})\s(?P<mark>INFO|ERROR|WARNING)(?:\sUSER\s(?P<name>[A-Z][a-z]{1,25}))?\s(?P<reason>.+)(\n)?)$"

def search(func):
    x = 0
    func_f = re.search(r"^(data|time|mark|name|reason|all)$",func, re.IGNORECASE)
    if func_f is None:
        print("Неправильний фільтр")
        return
    if func_f:
        func_f = func_f.group().lower()
    
    with open("logs.txt","r") as f:
        for line in f:
            x += 1
            filter = re.search(pattern , line , re.IGNORECASE)
            if filter == None:
                sys.exit(f"перевірте рядок {x}")
            match func_f:
                case "data":
                    print(filter.group("data"))
                case "time":
                    print(filter.group("time"))
                case "mark":
                     print(filter.group("mark"))
                case "name":
                    print(filter.group("name"))
                case "reason":
                    print(filter.group("reason"))
def trigered():
    with open("logs.txt","r") as f:
        f.seek(0,2)
        while True:
            line = f.readline()
            
            if not line:
                time.sleep(0.2)
                continue
            print(repr(line))
            match = re.search(pattern , line , re.IGNORECASE)
            if match == None:
                sys.exit(f"перевірте рядок {line}")
                
trigered()
