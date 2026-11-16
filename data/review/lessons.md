# Lessons across 4 slate(s)

**Too early to act on:** 4 of 20 slates so far. Numbers are shown for interest only.

- 3 slate(s) skipped because their projections were rebuilt after the fact (2026-11-07, 2026-11-09, 2026-11-10); lessons use pre-lock projections only.
- Ceilings: 12.5% of players beat their ceiling (target 10%); 83.8% landed inside floor–ceiling (target 80%).
- Smash rate is 16.0% overall; highest for salary $8K+ (28.9%, 45 players).
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
| under $4K | 160 | 16.2% | 81.2% |
| $4-6K | 196 | 10.7% | 84.2% |
| $6-8K | 88 | 10.2% | 85.2% |
| $8K+ | 44 | 11.4% | 88.6% |

Targets: about 10% over ceiling, 80% inside floor–ceiling.

## Smash rate by minutes bump

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 1 min | 590 | 15.6% | 0.97x |
| 1-4 min | 35 | 22.9% | 1.43x |

Average smash rate 16.0%. * = small sample.

## Smash rate by team implied total

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 110 | 183 | 12.0% | 0.75x |
| 110-116 | 219 | 17.4% | 1.08x |
| 116-122 | 196 | 18.4% | 1.15x |
| 122+ | 27 | 14.8% | 0.93x * |

Average smash rate 16.0%. * = small sample.

## Smash rate by salary

|  | Players | Smash | vs avg |
|---|---|---|---|
| under $4K | 276 | 10.1% | 0.63x |
| $4-6K | 212 | 18.4% | 1.15x |
| $6-8K | 92 | 21.7% | 1.36x |
| $8K+ | 45 | 28.9% | 1.81x |

Average smash rate 16.0%. * = small sample.

## Smash rate by position

|  | Players | Smash | vs avg |
|---|---|---|---|
| C | 112 | 15.2% | 0.95x |
| PF | 116 | 12.1% | 0.75x |
| PG | 166 | 16.3% | 1.02x |
| SF | 115 | 13.0% | 0.82x |
| SG | 116 | 23.3% | 1.45x |

Average smash rate 16.0%. * = small sample.

## Lineup make-up

|  | Lineups | Stars | Values | 3+ one game | From top total |
|---|---|---|---|---|---|
| Best possible | 4 | 1.0 | 2.0 | 75.0% | 0.0% |
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
