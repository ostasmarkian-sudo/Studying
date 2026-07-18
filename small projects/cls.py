import re
f = input("print a numbers: ")
numbers = list(map(int, re.split(r"[,\s]+", f)))
used = numbers.copy()

for x in range(len(numbers) - 1):
    for i in range(x+1,len(numbers)):
        if numbers[x] ^ numbers[i] == 0:
            if numbers[x] in used:
                used.remove(numbers[x])
            if numbers[i] in used:
                used.remove(numbers[i])
print(used)