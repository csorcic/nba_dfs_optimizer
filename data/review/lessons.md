# Lessons across 8 slate(s)

**Too early to act on:** 8 of 20 slates so far. Numbers are shown for interest only.

- 3 slate(s) skipped because their projections were rebuilt after the fact (2026-11-07, 2026-11-09, 2026-11-10); lessons use pre-lock projections only.
- Ceilings: 12.8% of players beat their ceiling (target 10%); 83.6% landed inside floor–ceiling (target 80%).
- Smash rate is 14.7% overall; highest for salary $8K+ (21.7%, 92 players).
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
| under $4K | 362 | 17.1% | 80.7% |
| $4-6K | 402 | 11.7% | 83.8% |
| $6-8K | 195 | 9.7% | 86.2% |
| $8K+ | 85 | 7.1% | 89.4% |

Targets: about 10% over ceiling, 80% inside floor–ceiling.

## Smash rate by minutes bump

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 1 min | 1088 | 13.5% | 0.92x |
| 1-4 min | 208 | 21.2% | 1.44x |
| 4 min+ | 15 | 13.3% | 0.91x * |

Average smash rate 14.7%. * = small sample.

## Smash rate by team implied total

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 110 | 335 | 11.3% | 0.77x |
| 110-116 | 563 | 15.3% | 1.04x |
| 116-122 | 359 | 17.3% | 1.17x |
| 122+ | 54 | 13.0% | 0.88x |

Average smash rate 14.7%. * = small sample.

## Smash rate by salary

|  | Players | Smash | vs avg |
|---|---|---|---|
| under $4K | 590 | 7.5% | 0.51x |
| $4-6K | 427 | 20.1% | 1.37x |
| $6-8K | 202 | 21.3% | 1.45x |
| $8K+ | 92 | 21.7% | 1.48x |

Average smash rate 14.7%. * = small sample.

## Smash rate by position

|  | Players | Smash | vs avg |
|---|---|---|---|
| C | 244 | 13.1% | 0.89x |
| PF | 230 | 11.7% | 0.8x |
| PG | 356 | 15.7% | 1.07x |
| SF | 249 | 12.9% | 0.87x |
| SG | 232 | 19.8% | 1.35x |

Average smash rate 14.7%. * = small sample.

## Lineup make-up

|  | Lineups | Stars | Values | 3+ one game | From top total |
|---|---|---|---|---|---|
| Best possible | 8 | 0.75 | 1.62 | 75.0% | 25.0% |
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
