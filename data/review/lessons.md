# Lessons across 7 slate(s)

**Too early to act on:** 7 of 20 slates so far. Numbers are shown for interest only.

- 3 slate(s) skipped because their projections were rebuilt after the fact (2026-11-07, 2026-11-09, 2026-11-10); lessons use pre-lock projections only.
- Ceilings: 12.8% of players beat their ceiling (target 10%); 83.6% landed inside floor–ceiling (target 80%).
- Smash rate is 14.8% overall; highest for salary $8K+ (24.1%, 83 players).
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
| under $4K | 330 | 17.3% | 80.3% |
| $4-6K | 367 | 11.2% | 84.2% |
| $6-8K | 181 | 9.9% | 86.2% |
| $8K+ | 78 | 7.7% | 88.5% |

Targets: about 10% over ceiling, 80% inside floor–ceiling.

## Smash rate by minutes bump

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 1 min | 1020 | 13.8% | 0.93x |
| 1-4 min | 165 | 21.2% | 1.43x |
| 4 min+ | 15 | 13.3% | 0.9x * |

Average smash rate 14.8%. * = small sample.

## Smash rate by team implied total

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 110 | 279 | 12.5% | 0.85x |
| 110-116 | 534 | 15.0% | 1.01x |
| 116-122 | 333 | 16.8% | 1.13x |
| 122+ | 54 | 13.0% | 0.87x |

Average smash rate 14.8%. * = small sample.

## Smash rate by salary

|  | Players | Smash | vs avg |
|---|---|---|---|
| under $4K | 537 | 8.0% | 0.54x |
| $4-6K | 392 | 18.6% | 1.26x |
| $6-8K | 188 | 22.3% | 1.51x |
| $8K+ | 83 | 24.1% | 1.62x |

Average smash rate 14.8%. * = small sample.

## Smash rate by position

|  | Players | Smash | vs avg |
|---|---|---|---|
| C | 222 | 13.1% | 0.88x |
| PF | 213 | 12.7% | 0.85x |
| PG | 322 | 15.8% | 1.07x |
| SF | 227 | 11.9% | 0.8x |
| SG | 216 | 20.4% | 1.37x |

Average smash rate 14.8%. * = small sample.

## Lineup make-up

|  | Lineups | Stars | Values | 3+ one game | From top total |
|---|---|---|---|---|---|
| Best possible | 7 | 0.71 | 1.71 | 71.4% | 14.3% |
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
