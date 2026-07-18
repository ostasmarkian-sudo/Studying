import re
def main():
    ip = input("IPv4 Address: ").strip()
    print(ip)
    print(validate(ip))

def validate(ip):
   patern = (r"^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$")
   match = re.search(patern,ip)
   return bool(match)
if __name__ == "__main__":
    main()