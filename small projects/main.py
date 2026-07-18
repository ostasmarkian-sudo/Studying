import re
with open ("text.txt","r") as f:
    text = f.read()
pattern = r"(?P<ip>(25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)\.(с5[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|\d)\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]\d|[0-9]))[ -]{5}\[(?P<date>(\d{2})\/(\w{1,4})\/(\d{4}:\d{2}:\d{2}:\d{2}\s(\+\d{1,4})))\]\s\"(?P<method>[A-Za-z]{1,9})\s(?P<path>\S+)\s(?P<protocol>(HTTP\/1\.0|HTTP\/1\.1|HTTP\/2|HTTP\/3|HTTPS))\"\s(?P<status>[1-5]\d{2})\s(?P<size>\d+)"
with open ("clearlog.txt","w") as file:
    for match in re.finditer(pattern,text):
        file.write (f"""
           ip: {match.group("ip")}
           date: {match.group("date")}
           method:{match.group("method")}
           path: {match.group("path")}
           protocol: {match.group("protocol")}
           status: {match.group("status")}
           size: {match.group("size")}
           """)