# Lessons across 13 slate(s)

**Too early to act on:** 13 of 20 slates so far. Numbers are shown for interest only.

- 3 slate(s) skipped because their projections were rebuilt after the fact (2026-11-07, 2026-11-09, 2026-11-10); lessons use pre-lock projections only.
- Ceilings: 11.8% of players beat their ceiling (target 10%); 84.6% landed inside floor–ceiling (target 80%).
- Smash rate is 14.2% overall; highest for salary $6-8K (22.0%, 286 players).
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
| under $4K | 526 | 15.4% | 81.7% |
| $4-6K | 557 | 10.4% | 85.5% |
| $6-8K | 275 | 9.8% | 86.2% |
| $8K+ | 120 | 7.5% | 89.2% |

Targets: about 10% over ceiling, 80% inside floor–ceiling.

## Smash rate by minutes bump

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 1 min | 1514 | 13.5% | 0.95x |
| 1-4 min | 321 | 17.4% | 1.23x |
| 4 min+ | 22 | 18.2% | 1.28x * |

Average smash rate 14.2%. * = small sample.

## Smash rate by team implied total

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 110 | 552 | 11.4% | 0.8x |
| 110-116 | 737 | 15.1% | 1.06x |
| 116-122 | 485 | 16.1% | 1.13x |
| 122+ | 83 | 14.5% | 1.02x |

Average smash rate 14.2%. * = small sample.

## Smash rate by salary

|  | Players | Smash | vs avg |
|---|---|---|---|
| under $4K | 854 | 7.3% | 0.51x |
| $4-6K | 586 | 19.3% | 1.36x |
| $6-8K | 286 | 22.0% | 1.55x |
| $8K+ | 131 | 19.8% | 1.4x |

Average smash rate 14.2%. * = small sample.

## Smash rate by position

|  | Players | Smash | vs avg |
|---|---|---|---|
| C | 356 | 14.0% | 0.99x |
| PF | 327 | 12.2% | 0.86x |
| PG | 494 | 14.6% | 1.03x |
| SF | 353 | 11.6% | 0.82x |
| SG | 327 | 18.7% | 1.31x |

Average smash rate 14.2%. * = small sample.

## Lineup make-up

|  | Lineups | Stars | Values | 3+ one game | From top total |
|---|---|---|---|---|---|
| Best possible | 13 | 0.77 | 1.92 | 76.9% | 25.0% |
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
