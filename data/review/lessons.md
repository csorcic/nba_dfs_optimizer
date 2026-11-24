# Lessons across 12 slate(s)

**Too early to act on:** 12 of 20 slates so far. Numbers are shown for interest only.

- 3 slate(s) skipped because their projections were rebuilt after the fact (2026-11-07, 2026-11-09, 2026-11-10); lessons use pre-lock projections only.
- Ceilings: 12.1% of players beat their ceiling (target 10%); 84.3% landed inside floor–ceiling (target 80%).
- Smash rate is 14.2% overall; highest for salary $6-8K (21.5%, 275 players).
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
| under $4K | 495 | 16.0% | 81.4% |
| $4-6K | 535 | 10.7% | 85.0% |
| $6-8K | 264 | 9.8% | 86.0% |
| $8K+ | 114 | 7.0% | 89.5% |

Targets: about 10% over ceiling, 80% inside floor–ceiling.

## Smash rate by minutes bump

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 1 min | 1431 | 13.4% | 0.94x |
| 1-4 min | 321 | 17.4% | 1.23x |
| 4 min+ | 22 | 18.2% | 1.28x * |

Average smash rate 14.2%. * = small sample.

## Smash rate by team implied total

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 110 | 512 | 11.1% | 0.78x |
| 110-116 | 709 | 14.8% | 1.04x |
| 116-122 | 470 | 16.6% | 1.17x |
| 122+ | 83 | 14.5% | 1.02x |

Average smash rate 14.2%. * = small sample.

## Smash rate by salary

|  | Players | Smash | vs avg |
|---|---|---|---|
| under $4K | 811 | 7.3% | 0.51x |
| $4-6K | 564 | 19.5% | 1.37x |
| $6-8K | 275 | 21.5% | 1.51x |
| $8K+ | 124 | 19.4% | 1.36x |

Average smash rate 14.2%. * = small sample.

## Smash rate by position

|  | Players | Smash | vs avg |
|---|---|---|---|
| C | 339 | 14.2% | 1.0x |
| PF | 313 | 11.5% | 0.81x |
| PG | 473 | 15.0% | 1.06x |
| SF | 340 | 11.5% | 0.81x |
| SG | 309 | 18.8% | 1.32x |

Average smash rate 14.2%. * = small sample.

## Lineup make-up

|  | Lineups | Stars | Values | 3+ one game | From top total |
|---|---|---|---|---|---|
| Best possible | 12 | 0.75 | 1.92 | 75.0% | 27.3% |
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
