def main():
    tools("NEWS","STOP")
def tools(*text):
    low = map(str.lower,text)
    print(*low,sep=" ")

if __name__ == "__main__":
    main()