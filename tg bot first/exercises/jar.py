
class Jar:
    def __init__(self, capacity):
        self._size = 0
        self._capacity = capacity
    def __str__(self):
        return "🍪" * self._size
    def deposit(self,n):
        if self._size + n > self._capacity or self._size + n < 0 or n < 0:
            raise ValueError("jar is full")
        self._size += n
    def withdraw (self,n):
        if self._size - n < 0 or n < 0:
            raise ValueError("jar is full")
        self._size -= n
    @property
    def capacity(self):
        return self._capacity 
    @property
    def size(self):
        return self._size
        
        
jar1 = Jar(12)
jar1.deposit(12)
jar1.withdraw(5)
print(jar1)
print(jar1.capacity)
print(jar1.size)