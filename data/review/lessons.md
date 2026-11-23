# Lessons across 11 slate(s)

**Too early to act on:** 11 of 20 slates so far. Numbers are shown for interest only.

- 3 slate(s) skipped because their projections were rebuilt after the fact (2026-11-07, 2026-11-09, 2026-11-10); lessons use pre-lock projections only.
- Ceilings: 11.9% of players beat their ceiling (target 10%); 84.5% landed inside floor–ceiling (target 80%).
- Smash rate is 14.2% overall; highest for salary $6-8K (21.4%, 266 players).
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
| under $4K | 475 | 15.6% | 81.9% |
| $4-6K | 520 | 10.6% | 85.0% |
| $6-8K | 256 | 9.8% | 85.9% |
| $8K+ | 111 | 7.2% | 90.1% |

Targets: about 10% over ceiling, 80% inside floor–ceiling.

## Smash rate by minutes bump

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 1 min | 1398 | 13.3% | 0.94x |
| 1-4 min | 297 | 17.8% | 1.26x |
| 4 min+ | 22 | 18.2% | 1.28x * |

Average smash rate 14.2%. * = small sample.

## Smash rate by team implied total

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 110 | 485 | 11.1% | 0.79x |
| 110-116 | 709 | 14.8% | 1.05x |
| 116-122 | 440 | 16.4% | 1.16x |
| 122+ | 83 | 14.5% | 1.02x |

Average smash rate 14.2%. * = small sample.

## Smash rate by salary

|  | Players | Smash | vs avg |
|---|---|---|---|
| under $4K | 782 | 7.2% | 0.51x |
| $4-6K | 549 | 19.3% | 1.36x |
| $6-8K | 266 | 21.4% | 1.51x |
| $8K+ | 120 | 20.0% | 1.41x |

Average smash rate 14.2%. * = small sample.

## Smash rate by position

|  | Players | Smash | vs avg |
|---|---|---|---|
| C | 329 | 14.0% | 0.99x |
| PF | 302 | 11.6% | 0.82x |
| PG | 459 | 15.3% | 1.08x |
| SF | 325 | 11.1% | 0.78x |
| SG | 302 | 18.5% | 1.31x |

Average smash rate 14.2%. * = small sample.

## Lineup make-up

|  | Lineups | Stars | Values | 3+ one game | From top total |
|---|---|---|---|---|---|
| Best possible | 11 | 0.73 | 1.82 | 72.7% | 27.3% |
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
