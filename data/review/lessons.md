# Lessons across 14 slate(s)

**Too early to act on:** 14 of 20 slates so far. Numbers are shown for interest only.

- 3 slate(s) skipped because their projections were rebuilt after the fact (2026-11-07, 2026-11-09, 2026-11-10); lessons use pre-lock projections only.
- Ceilings: 11.8% of players beat their ceiling (target 10%); 84.6% landed inside floor–ceiling (target 80%).
- Smash rate is 14.1% overall; highest for salary $6-8K (21.5%, 311 players).
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
| under $4K | 567 | 15.3% | 81.5% |
| $4-6K | 610 | 10.5% | 85.4% |
| $6-8K | 300 | 9.3% | 87.0% |
| $8K+ | 129 | 7.8% | 88.4% |

Targets: about 10% over ceiling, 80% inside floor–ceiling.

## Smash rate by minutes bump

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 1 min | 1643 | 13.3% | 0.95x |
| 1-4 min | 357 | 17.4% | 1.23x |
| 4 min+ | 22 | 18.2% | 1.29x * |

Average smash rate 14.1%. * = small sample.

## Smash rate by team implied total

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 110 | 594 | 10.8% | 0.76x |
| 110-116 | 816 | 15.3% | 1.09x |
| 116-122 | 529 | 15.9% | 1.13x |
| 122+ | 83 | 14.5% | 1.03x |

Average smash rate 14.1%. * = small sample.

## Smash rate by salary

|  | Players | Smash | vs avg |
|---|---|---|---|
| under $4K | 932 | 7.2% | 0.51x |
| $4-6K | 639 | 19.4% | 1.38x |
| $6-8K | 311 | 21.5% | 1.53x |
| $8K+ | 140 | 19.3% | 1.37x |

Average smash rate 14.1%. * = small sample.

## Smash rate by position

|  | Players | Smash | vs avg |
|---|---|---|---|
| C | 390 | 13.6% | 0.96x |
| PF | 351 | 12.8% | 0.91x |
| PG | 538 | 14.3% | 1.02x |
| SF | 386 | 11.7% | 0.83x |
| SG | 357 | 18.2% | 1.29x |

Average smash rate 14.1%. * = small sample.

## Lineup make-up

|  | Lineups | Stars | Values | 3+ one game | From top total |
|---|---|---|---|---|---|
| Best possible | 14 | 0.79 | 1.86 | 71.4% | 23.1% |
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
