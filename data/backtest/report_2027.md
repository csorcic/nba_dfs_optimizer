# Backtest 2026-27

28 days, 2026-10-21 to 2026-11-18. Error = projection minus actual DK points (positive bias = we projected too high).

| Group | Players | MAE | Bias | Baseline MAE | Minutes MAE | Inside floor-ceiling | Over ceiling |
|---|---|---|---|---|---|---|---|
| **All** | 4856 | 7.47 | +0.39 | 7.82 | 4.76 | 85% | 9% |
| Salary under $4K | 477 | 5.96 | -1.27 | 6.04 | 5.36 | 83% | 12% |
| Salary $4K-$6K | 525 | 7.68 | +0.34 | 7.81 | 4.71 | 87% | 7% |
| Salary $6K-$8K | 254 | 8.42 | +1.12 | 8.55 | 4.21 | 89% | 6% |
| Salary $8K+ | 118 | 10.34 | -0.84 | 10.15 | 3.91 | 89% | 7% |
| Projected under 15 pts | 1519 | 5.95 | -1.70 | 6.10 | 5.39 | 80% | 16% |
| Projected 15-25 pts | 1621 | 7.53 | +1.54 | 7.78 | 4.86 | 86% | 6% |
| Projected 25-35 pts | 1008 | 8.34 | +1.29 | 9.07 | 4.32 | 88% | 5% |
| Projected 35+ pts | 708 | 9.37 | +0.93 | 9.86 | 3.82 | 88% | 5% |
| Games with a Vegas line | 4856 | 7.47 | +0.39 | 7.82 | 4.76 | 85% | 9% |

Baseline = player's season average DK points to date (what a naive projection would say).
Inside floor-ceiling should be about 80% and over ceiling about 10% if the spread is right.
