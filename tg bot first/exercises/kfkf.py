def sum_elem(n):
    if n < 10:
        return n

    return n % 10 + sum_elem(n // 10)


print(sum_elem(999))
