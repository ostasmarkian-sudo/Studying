import numpy as np

rng = np.random.default_rng(42)
user_id = rng.integers(0, 100, size=1000)
timestamp = rng.integers(0, 100, size=1000)
amount = rng.normal(loc=50, scale=15, size=1000).clip(1, None)

outlier_idx = rng.choice(1000, size=20, replace=False)
amount[outlier_idx] *= rng.uniform(5, 10, size=20)
user_day_matrix = np.zeros((100, 100))
np.add.at(user_day_matrix, (user_id, timestamp), amount)

sums = np.zeros(100)
sums_sq = np.zeros(100)
counts = np.zeros(100)

np.add.at(sums, user_id, amount)
np.add.at(sums_sq, user_id, amount**2)
np.add.at(counts, user_id, 1)

counts_safe = np.where(counts == 0, 1, counts)
means = sums / counts_safe
variances = sums_sq / counts_safe - means**2
stds = np.sqrt(np.maximum(variances, 0))

tx_mean = means[user_id]
tx_std = stds[user_id]
is_anomaly = (tx_std > 0) & (np.abs(amount - tx_mean) > 3 * tx_std)
anomalies = np.column_stack(
    [user_id[is_anomaly], timestamp[is_anomaly], amount[is_anomaly]]
)

daily_totals = user_day_matrix.sum(axis=0)
window = 7
kernel = np.ones(window) / window
rolling_avg = np.convolve(daily_totals, kernel, mode="valid")
volatility = np.where(means > 0, stds / means, 0)
top5_idx = np.argsort(volatility)[::-1][:5]

print("matrix user x day:", user_day_matrix.shape)
print("Count anomaly:", is_anomaly.sum())
print(anomalies[:5])
print("rolling_avg", rolling_avg[:5].round(2))
for uid in top5_idx:
    print(f"user {uid}: volatility={volatility[uid]:.2f}")
