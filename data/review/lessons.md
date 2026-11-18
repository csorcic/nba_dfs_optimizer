# Lessons across 6 slate(s)

**Too early to act on:** 6 of 20 slates so far. Numbers are shown for interest only.

- 3 slate(s) skipped because their projections were rebuilt after the fact (2026-11-07, 2026-11-09, 2026-11-10); lessons use pre-lock projections only.
- Ceilings: 12.8% of players beat their ceiling (target 10%); 83.4% landed inside floor–ceiling (target 80%).
- Smash rate is 15.3% overall; highest for salary $8K+ (25.0%, 68 players).
- Ownership estimate misses real %Drafted by 3.97 points on average (bias +0.0) over 3 slate(s).

## Recommended changes

### Consider a 3-player game stack in GPPs

100.0% of winning lineups had 3+ players from one game (3 lineups). Your GPP default doesn't require a stack.

- Before: stack_min_players 0
- After: stack_min_players 3
- Setting: `optimizer.stack_min_players`

## Ceiling calibration by salary

| Salary | Players | Over ceiling | Inside range |
|---|---|---|---|
| under $4K | 253 | 17.0% | 80.2% |
| $4-6K | 293 | 11.3% | 84.0% |
| $6-8K | 139 | 10.8% | 84.9% |
| $8K+ | 66 | 7.6% | 89.4% |

Targets: about 10% over ceiling, 80% inside floor–ceiling.

## Smash rate by minutes bump

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 1 min | 827 | 14.3% | 0.93x |
| 1-4 min | 118 | 22.0% | 1.44x |
| 4 min+ | 9 | 22.2% | 1.45x * |

Average smash rate 15.3%. * = small sample.

## Smash rate by team implied total

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 110 | 265 | 12.5% | 0.81x |
| 110-116 | 399 | 15.0% | 0.98x |
| 116-122 | 251 | 18.7% | 1.22x |
| 122+ | 39 | 15.4% | 1.01x |

Average smash rate 15.3%. * = small sample.

## Smash rate by salary

|  | Players | Smash | vs avg |
|---|---|---|---|
| under $4K | 425 | 8.2% | 0.54x |
| $4-6K | 316 | 18.7% | 1.22x |
| $6-8K | 145 | 24.1% | 1.58x |
| $8K+ | 68 | 25.0% | 1.63x |

Average smash rate 15.3%. * = small sample.

## Smash rate by position

|  | Players | Smash | vs avg |
|---|---|---|---|
| C | 179 | 14.0% | 0.91x |
| PF | 170 | 12.4% | 0.81x |
| PG | 257 | 15.6% | 1.02x |
| SF | 178 | 12.4% | 0.81x |
| SG | 170 | 22.4% | 1.46x |

Average smash rate 15.3%. * = small sample.

## Lineup make-up

|  | Lineups | Stars | Values | 3+ one game | From top total |
|---|---|---|---|---|---|
| Best possible | 6 | 0.67 | 1.67 | 66.7% | 16.7% |
| Contest winners | 3 | 1.0 | 1.33 | 100.0% | 0.0% |

Your GPP stack default: off.

## Ownership estimate vs real

| Salary | Players | Avg miss | Bias |
|---|---|---|---|
| under $4K | 216 | 1.39 | -0.41 |
| $4-6K | 170 | 4.66 | -2.08 |
| $6-8K | 81 | 5.49 | +0.32 |
| $8K+ | 38 | 12.3 | +10.93 |

Bias + means we guessed too high.

_Recommendations only. Nothing in config/settings.yaml is changed until Chris approves it._
