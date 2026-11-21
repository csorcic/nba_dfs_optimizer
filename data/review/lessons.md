# Lessons across 9 slate(s)

**Too early to act on:** 9 of 20 slates so far. Numbers are shown for interest only.

- 3 slate(s) skipped because their projections were rebuilt after the fact (2026-11-07, 2026-11-09, 2026-11-10); lessons use pre-lock projections only.
- Ceilings: 12.5% of players beat their ceiling (target 10%); 83.8% landed inside floor–ceiling (target 80%).
- Smash rate is 14.6% overall; highest for salary $6-8K (21.9%, 233 players).
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
| under $4K | 398 | 16.6% | 81.2% |
| $4-6K | 450 | 11.3% | 83.8% |
| $6-8K | 225 | 10.2% | 85.8% |
| $8K+ | 93 | 6.5% | 90.3% |

Targets: about 10% over ceiling, 80% inside floor–ceiling.

## Smash rate by minutes bump

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 1 min | 1199 | 13.6% | 0.93x |
| 1-4 min | 250 | 18.8% | 1.29x |
| 4 min+ | 20 | 20.0% | 1.37x * |

Average smash rate 14.6%. * = small sample.

## Smash rate by team implied total

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 110 | 389 | 11.3% | 0.78x |
| 110-116 | 614 | 15.5% | 1.06x |
| 116-122 | 412 | 16.5% | 1.13x |
| 122+ | 54 | 13.0% | 0.89x |

Average smash rate 14.6%. * = small sample.

## Smash rate by salary

|  | Players | Smash | vs avg |
|---|---|---|---|
| under $4K | 659 | 7.1% | 0.49x |
| $4-6K | 477 | 20.1% | 1.38x |
| $6-8K | 233 | 21.9% | 1.5x |
| $8K+ | 100 | 20.0% | 1.37x |

Average smash rate 14.6%. * = small sample.

## Smash rate by position

|  | Players | Smash | vs avg |
|---|---|---|---|
| C | 274 | 13.1% | 0.9x |
| PF | 258 | 11.6% | 0.8x |
| PG | 397 | 15.6% | 1.07x |
| SF | 278 | 12.9% | 0.89x |
| SG | 262 | 19.1% | 1.31x |

Average smash rate 14.6%. * = small sample.

## Lineup make-up

|  | Lineups | Stars | Values | 3+ one game | From top total |
|---|---|---|---|---|---|
| Best possible | 9 | 0.67 | 1.56 | 66.7% | 22.2% |
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
