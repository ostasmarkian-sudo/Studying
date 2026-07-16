import requests
import statistics
numbers = []
url = "https://www.random.org/integers/?num=1&min=1&max=100&col=1&base=10&format=plain&rnd=new"
for i in range(10):
    data = requests.get(url).text
    numbers.append(int(data))
print(numbers)
print(statistics.mean(numbers))


