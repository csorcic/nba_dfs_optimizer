# Lessons across 3 slate(s)

**Too early to act on:** 3 of 20 slates so far. Numbers are shown for interest only.

- 3 slate(s) skipped because their projections were rebuilt after the fact (2026-11-07, 2026-11-09, 2026-11-10); lessons use pre-lock projections only.
- Ceilings: 12.8% of players beat their ceiling (target 10%); 83.2% landed inside floor–ceiling (target 80%).
- Smash rate is 15.8% overall; highest for salary $8K+ (33.3%, 33 players).
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
| under $4K | 114 | 14.0% | 82.5% |
| $4-6K | 159 | 11.3% | 83.0% |
| $6-8K | 69 | 13.0% | 84.1% |
| $8K+ | 32 | 15.6% | 84.4% |

Targets: about 10% over ceiling, 80% inside floor–ceiling.

## Smash rate by minutes bump

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 1 min | 459 | 15.9% | 1.0x |
| 1-4 min | 27 | 14.8% | 0.94x * |

Average smash rate 15.8%. * = small sample.

## Smash rate by team implied total

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 110 | 129 | 10.9% | 0.68x |
| 110-116 | 175 | 16.0% | 1.01x |
| 116-122 | 155 | 20.0% | 1.26x |
| 122+ | 27 | 14.8% | 0.94x * |

Average smash rate 15.8%. * = small sample.

## Smash rate by salary

|  | Players | Smash | vs avg |
|---|---|---|---|
| under $4K | 212 | 7.5% | 0.48x |
| $4-6K | 169 | 18.9% | 1.2x |
| $6-8K | 72 | 25.0% | 1.58x |
| $8K+ | 33 | 33.3% | 2.1x |

Average smash rate 15.8%. * = small sample.

## Smash rate by position

|  | Players | Smash | vs avg |
|---|---|---|---|
| C | 89 | 16.9% | 1.06x |
| PF | 90 | 11.1% | 0.7x |
| PG | 130 | 15.4% | 0.97x |
| SF | 89 | 14.6% | 0.92x |
| SG | 88 | 21.6% | 1.36x |

Average smash rate 15.8%. * = small sample.

## Lineup make-up

|  | Lineups | Stars | Values | 3+ one game | From top total |
|---|---|---|---|---|---|
| Best possible | 3 | 1.0 | 1.67 | 66.7% | 0.0% |
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
