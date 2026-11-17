# Lessons across 5 slate(s)

**Too early to act on:** 5 of 20 slates so far. Numbers are shown for interest only.

- 3 slate(s) skipped because their projections were rebuilt after the fact (2026-11-07, 2026-11-09, 2026-11-10); lessons use pre-lock projections only.
- Ceilings: 12.9% of players beat their ceiling (target 10%); 83.4% landed inside floor–ceiling (target 80%).
- Smash rate is 16.0% overall; highest for salary $8K+ (29.3%, 58 players).
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
| under $4K | 220 | 17.7% | 79.5% |
| $4-6K | 250 | 10.8% | 84.4% |
| $6-8K | 122 | 10.7% | 86.1% |
| $8K+ | 57 | 8.8% | 87.7% |

Targets: about 10% over ceiling, 80% inside floor–ceiling.

## Smash rate by minutes bump

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 1 min | 749 | 15.2% | 0.95x |
| 1-4 min | 68 | 25.0% | 1.56x |

Average smash rate 16.0%. * = small sample.

## Smash rate by team implied total

|  | Players | Smash | vs avg |
|---|---|---|---|
| under 110 | 196 | 12.2% | 0.76x |
| 110-116 | 346 | 15.9% | 0.99x |
| 116-122 | 236 | 19.5% | 1.22x |
| 122+ | 39 | 15.4% | 0.96x |

Average smash rate 16.0%. * = small sample.

## Smash rate by salary

|  | Players | Smash | vs avg |
|---|---|---|---|
| under $4K | 361 | 9.1% | 0.57x |
| $4-6K | 271 | 18.8% | 1.17x |
| $6-8K | 127 | 23.6% | 1.47x |
| $8K+ | 58 | 29.3% | 1.83x |

Average smash rate 16.0%. * = small sample.

## Smash rate by position

|  | Players | Smash | vs avg |
|---|---|---|---|
| C | 152 | 14.5% | 0.9x |
| PF | 145 | 12.4% | 0.77x |
| PG | 218 | 16.1% | 1.0x |
| SF | 154 | 13.6% | 0.85x |
| SG | 148 | 23.6% | 1.47x |

Average smash rate 16.0%. * = small sample.

## Lineup make-up

|  | Lineups | Stars | Values | 3+ one game | From top total |
|---|---|---|---|---|---|
| Best possible | 5 | 0.8 | 2.0 | 60.0% | 0.0% |
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
