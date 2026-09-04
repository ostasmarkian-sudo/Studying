import numpy as np

alphabet = "qwerty"
rng = np.random.default_rng()

text = "".join(rng.choice(list(alphabet), size=10))


def length_of_longest_substring(s: str) -> int:
    last_seen = {}
    start = 0
    best = 0

    for i, ch in enumerate(s):
        if ch in last_seen and last_seen[ch] >= start:
            start = last_seen[ch] + 1
        last_seen[ch] = i
        best = max(best, i - start + 1)
    print(best)


length_of_longest_substring(text)
