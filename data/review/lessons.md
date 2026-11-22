# Lessons across 10 slate(s)

**Too early to act on:** 10 of 20 slates so far. Numbers are shown for interest only.

- 3 slate(s) skipped because their projections were rebuilt after the fact (2026-11-07, 2026-11-09, 2026-11-10); lessons use pre-lock projections only.
- Ceilings: 12.3% of players beat their ceiling (target 10%); 84.0% landed inside floor–ceiling (target 80%).
- Smash rate is 14.5% overall; highest for salary $6-8K (21.7%, 249 players).
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
| under $4K | 428 | 16.8% | 80.8% |
| $4-6K | 483 | 10.6% | 84.7% |
| $6-8K | 239 | 10.0% | 85.8% |
| $8K+ | 100 | 7.0% | 90.0% |

Targets: about 10% over ceiling, 80% inside floor–ceiling.

## Smash rate by minutes bump

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 1 min | 1287 | 13.8% | 0.95x |
| 1-4 min | 271 | 17.3% | 1.2x |
| 4 min+ | 22 | 18.2% | 1.25x * |

Average smash rate 14.5%. * = small sample.

## Smash rate by team implied total

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 110 | 430 | 12.3% | 0.85x |
| 110-116 | 642 | 15.0% | 1.03x |
| 116-122 | 440 | 16.4% | 1.13x |
| 122+ | 68 | 11.8% | 0.81x |

Average smash rate 14.5%. * = small sample.

## Smash rate by salary

|  | Players | Smash | vs avg |
|---|---|---|---|
| under $4K | 712 | 7.6% | 0.52x |
| $4-6K | 511 | 19.6% | 1.35x |
| $6-8K | 249 | 21.7% | 1.5x |
| $8K+ | 108 | 19.4% | 1.34x |

Average smash rate 14.5%. * = small sample.

## Smash rate by position

|  | Players | Smash | vs avg |
|---|---|---|---|
| C | 298 | 14.4% | 1.0x |
| PF | 279 | 11.8% | 0.82x |
| PG | 426 | 15.5% | 1.07x |
| SF | 301 | 12.0% | 0.83x |
| SG | 276 | 18.5% | 1.27x |

Average smash rate 14.5%. * = small sample.

## Lineup make-up

|  | Lineups | Stars | Values | 3+ one game | From top total |
|---|---|---|---|---|---|
| Best possible | 10 | 0.7 | 1.7 | 70.0% | 20.0% |
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
