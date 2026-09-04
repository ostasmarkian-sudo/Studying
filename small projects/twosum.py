import numpy as np

array = np.random.randint(0, 11, size=6)
print(array)
twosum = int(input("Enter a number"))
for i in range(len(array)):
    for j in range(i + 1, len(array)):
        if array[i] + array[j] == twosum:
            print(f"[{i}][{j}]")
