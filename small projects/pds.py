import pandas as pd

frame = pd.DataFrame(
    {"Bob": ["I liked it.", "It was awful."], "Sue": ["Pretty good.", "Bland."]},
    index=["Product A", "Product B"],
)
reviews = pd.read_csv(
    "C:/Users/marki/Documents/Studying Projects/small projects/students.csv",
    index_col=0,
)

review_score_mean = reviews.score.mean()
without_ = reviews.score.fillna(review_score_mean)
score_diff = without_.map(lambda p: p - review_score_mean)
s = reviews.apply(lambda row: row["score"] - row["age"], axis=1)


def level(x):
    match True:
        case _ if x > 0:
            return "above average"
        case _ if x < 0:
            return "below average"
        case _:
            return "average"


d = score_diff.apply(level)
s = d + " - " + round(score_diff, 2).astype(str)
print(s)
