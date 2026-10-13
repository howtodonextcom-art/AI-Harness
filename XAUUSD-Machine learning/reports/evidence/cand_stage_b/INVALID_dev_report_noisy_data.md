# Candidate evaluation, window DEV
spec sha256 `f9bb929e6dda0c49...` | code `130277dae0` | 8.00 years | 549025 M5 bars | 4069 ARMED setups of the control (episodes)

## 1. Structural reachability (no outcome)
| variant | changes | episodes | per year | reachability = episodes / armed setups |
|---|---|---|---|---|
| CTRL | - | 7 | 0.880 | 0.002 |
| A_C1 | C1 | 8 | 1.000 | 0.002 |
| A_C2 | C2 | 69 | 8.620 | 0.017 |
| A_C3a | C3a | 10 | 1.250 | 0.002 |
| A_C3b | C3b | 14 | 1.750 | 0.003 |
| B_C1C2 | C1+C2 | 126 | 15.750 | 0.031 |
| B_C2C3a | C2+C3a | 77 | 9.620 | 0.019 |
| CORE | C1+C2+C3a+C3b | 248 | 31.000 | 0.061 |
| LOO_noC1 | C2+C3a+C3b | 145 | 18.120 | 0.036 |
| LOO_noC2 | C1+C3a+C3b | 24 | 3.000 | 0.006 |
| LOO_noC3a | C1+C2+C3b | 213 | 26.620 | 0.052 |
| LOO_noC3b | C1+C2+C3a | 159 | 19.880 | 0.039 |
| X_C7 | C7 | 17 | 2.120 | 0.004 |
| X_CORE_C7 | C1+C2+C3a+C3b+C7 | 470 | 58.750 | 0.116 |

## 2. Episode frequency and 3. Executed PAPER trades
| variant | episodes | attempted | refused by governor | unresolved | executed | per year | BUY | SELL |
|---|---|---|---|---|---|---|---|---|
| CTRL | 7 | 7 | {"RISK_LIMIT": 1} | 0 | 6 | 0.750 | 3 | 3 |
| A_C1 | 8 | 8 | {} | 0 | 8 | 1.000 | 4 | 4 |
| A_C2 | 69 | 69 | {"RISK_LIMIT": 2} | 0 | 67 | 8.380 | 35 | 32 |
| A_C3a | 10 | 10 | {"RISK_LIMIT": 1} | 0 | 9 | 1.120 | 6 | 3 |
| A_C3b | 14 | 14 | {"RISK_LIMIT": 1} | 0 | 13 | 1.620 | 7 | 6 |
| B_C1C2 | 126 | 126 | {"RISK_LIMIT": 6} | 0 | 120 | 15.000 | 60 | 60 |
| B_C2C3a | 77 | 77 | {"RISK_LIMIT": 2} | 0 | 75 | 9.380 | 39 | 36 |
| CORE | 248 | 248 | {"COOLDOWN": 1, "RISK_LIMIT": 18} | 0 | 229 | 28.620 | 117 | 112 |
| LOO_noC1 | 145 | 145 | {"RISK_LIMIT": 4} | 0 | 141 | 17.620 | 74 | 67 |
| LOO_noC2 | 24 | 24 | {"RISK_LIMIT": 1} | 0 | 23 | 2.880 | 13 | 10 |
| LOO_noC3a | 213 | 213 | {"COOLDOWN": 1, "RISK_LIMIT": 14} | 0 | 198 | 24.750 | 102 | 96 |
| LOO_noC3b | 159 | 159 | {"RISK_LIMIT": 9} | 0 | 150 | 18.750 | 74 | 76 |
| X_C7 | 17 | 17 | {} | 0 | 17 | 2.120 | 7 | 10 |
| X_CORE_C7 | 470 | 470 | {"RISK_LIMIT": 60, "COOLDOWN": 3} | 0 | 407 | 50.880 | 199 | 208 |

## 4. Expectancy after costs (R per trade) and 5. Statistical uncertainty
| variant | N | months | E | lower 97.5% | upper 97.5% | status | reason |
|---|---|---|---|---|---|---|---|
| CTRL | 6 | 5 | -0.599 | -1.032 | 0.514 | INCONCLUSIVE | N=6, months=5 below N_min=30/12 |
| A_C1 | 8 | 6 | 0.049 | -1.028 | 1.274 | INCONCLUSIVE | N=8, months=6 below N_min=30/12 |
| A_C2 | 67 | 42 | 0.240 | -0.107 | 0.607 | INCONCLUSIVE | bounds [-0.107, 0.607]R, N=67 (N_req(0.20R)=663) |
| A_C3a | 9 | 5 | -0.443 | -1.029 | 0.273 | INCONCLUSIVE | N=9, months=5 below N_min=30/12 |
| A_C3b | 13 | 11 | 0.099 | -0.631 | 1.090 | INCONCLUSIVE | N=13, months=11 below N_min=30/12 |
| B_C1C2 | 120 | 61 | 0.681 | 0.390 | 0.974 | INCONCLUSIVE | bounds [0.390, 0.974]R, N=120 (N_req(0.20R)=663) |
| B_C2C3a | 75 | 43 | 0.221 | -0.105 | 0.576 | INCONCLUSIVE | bounds [-0.105, 0.576]R, N=75 (N_req(0.20R)=663) |
| CORE | 229 | 77 | 0.680 | 0.462 | 0.912 | INCONCLUSIVE | bounds [0.462, 0.912]R, N=229 (N_req(0.20R)=663) |
| LOO_noC1 | 141 | 64 | 0.472 | 0.221 | 0.736 | INCONCLUSIVE | bounds [0.221, 0.736]R, N=141 (N_req(0.20R)=663) |
| LOO_noC2 | 23 | 15 | 0.370 | -0.188 | 1.157 | INCONCLUSIVE | N=23, months=15 below N_min=30/12 |
| LOO_noC3a | 198 | 74 | 0.752 | 0.528 | 0.972 | INCONCLUSIVE | bounds [0.528, 0.972]R, N=198 (N_req(0.20R)=663) |
| LOO_noC3b | 150 | 66 | 0.599 | 0.340 | 0.869 | INCONCLUSIVE | bounds [0.340, 0.869]R, N=150 (N_req(0.20R)=663) |
| X_C7 | 17 | 12 | -0.518 | -1.024 | -0.033 | INCONCLUSIVE | N=17, months=12 below N_min=30/12 |
| X_CORE_C7 | 407 | 89 | 0.271 | 0.110 | 0.443 | INCONCLUSIVE | bounds [0.110, 0.443]R, N=407 (N_req(0.20R)=663) |

Power (design): {"sd": 1.5, "deff": 1.5, "n_min": 30, "n_required": {"0.3": 295, "0.2": 663, "0.15": 1178, "0.1": 2649}}

Cost decomposition per executed trade (R): price path (already contains the spread mechanics and slippage), swap, planned spread, planned slippage
| variant | mean price R | mean swap R | planned spread R | planned slippage R | win rate | false positives |
|---|---|---|---|---|---|---|
| CTRL | -0.596 | -0.003 | 0.022 | 0.021 | 0.167 | 0.000 |
| A_C1 | 0.051 | -0.002 | 0.028 | 0.017 | 0.375 | 0.000 |
| A_C2 | 0.270 | -0.030 | 0.101 | 0.018 | 0.433 | 0.030 |
| A_C3a | -0.441 | -0.002 | 0.015 | 0.023 | 0.222 | 0.000 |
| A_C3b | 0.105 | -0.006 | 0.025 | 0.014 | 0.385 | 0.000 |
| B_C1C2 | 0.699 | -0.018 | 0.100 | 0.015 | 0.575 | 0.042 |
| B_C2C3a | 0.248 | -0.027 | 0.098 | 0.018 | 0.427 | 0.027 |
| CORE | 0.693 | -0.013 | 0.097 | 0.014 | 0.572 | 0.044 |
| LOO_noC1 | 0.488 | -0.016 | 0.097 | 0.015 | 0.504 | 0.043 |
| LOO_noC2 | 0.373 | -0.003 | 0.023 | 0.013 | 0.478 | 0.043 |
| LOO_noC3a | 0.766 | -0.014 | 0.098 | 0.013 | 0.596 | 0.040 |
| LOO_noC3b | 0.613 | -0.014 | 0.099 | 0.016 | 0.547 | 0.040 |
| X_C7 | -0.500 | -0.018 | 0.037 | 0.018 | 0.176 | 0.059 |
| X_CORE_C7 | 0.290 | -0.018 | 0.096 | 0.015 | 0.437 | 0.071 |

## 6. Safety violations
| variant | signals | net_rr<1.5 | stop>3ATR | risk!=0.25 | cost_R>cap | spike | on SHOCK bar | gap through stop | ambiguous bars | horizon exits | MDD R | worst month R | caps hold |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CTRL | 13 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 5.130 | -2.070 | True |
| A_C1 | 24 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 4.110 | -2.070 | True |
| A_C2 | 125 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 0 | 8.490 | -2.410 | True |
| A_C3a | 17 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 5.520 | -2.070 | True |
| A_C3b | 25 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 7.210 | -3.100 | True |
| B_C1C2 | 286 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 3 | 0 | 8.140 | -3.080 | True |
| B_C2C3a | 134 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 0 | 9.250 | -3.060 | True |
| CORE | 621 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 7 | 0 | 10.170 | -3.150 | True |
| LOO_noC1 | 339 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 5 | 0 | 10.220 | -3.090 | True |
| LOO_noC2 | 57 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 5.490 | -2.030 | True |
| LOO_noC3a | 563 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 7 | 0 | 9.140 | -2.410 | True |
| LOO_noC3b | 336 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 3 | 0 | 9.170 | -3.080 | True |
| X_C7 | 23 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 12.780 | -3.100 | True |
| X_CORE_C7 | 940 | 0 | 0 | 0 | 0 | 0 | 0 | 9 | 10 | 0 | 25.880 | -10.240 | False |

## 7. Candidate versus control (incremental trades: present in the variant, absent in its parent)
| variant | parent | N | E | lower | upper | status | reason |
|---|---|---|---|---|---|---|---|
| A_C1 | CTRL | 2 | 1.995 | 1.995 | 1.995 | INCONCLUSIVE | N=2, months=1 below N_min=30/12 |
| A_C2 | CTRL | 62 | 0.301 | -0.058 | 0.683 | INCONCLUSIVE | bounds [-0.058, 0.683]R, N=62 (N_req(0.20R)=663) |
| A_C3a | CTRL | 3 | -0.129 | -0.129 | -0.129 | INCONCLUSIVE | N=3, months=1 below N_min=30/12 |
| A_C3b | CTRL | 7 | 0.698 | -0.589 | 1.565 | INCONCLUSIVE | N=7, months=7 below N_min=30/12 |
| B_C1C2 | A_C2 | 57 | 1.133 | 0.724 | 1.504 | INCONCLUSIVE | bounds [0.724, 1.504]R, N=57 (N_req(0.20R)=663) |
| B_C2C3a | A_C2 | 8 | 0.064 | -0.689 | 0.983 | INCONCLUSIVE | N=8, months=6 below N_min=30/12 |
| LOO_noC1 | B_C2C3a | 79 | 0.728 | 0.365 | 1.098 | INCONCLUSIVE | bounds [0.365, 1.098]R, N=79 (N_req(0.20R)=663) |
| X_C7 | CTRL | 12 | -0.556 | -1.038 | -0.046 | INCONCLUSIVE | N=12, months=10 below N_min=30/12 |
| X_CORE_C7 | CORE | 312 | 0.184 | -0.010 | 0.389 | INCONCLUSIVE | bounds [-0.010, 0.389]R, N=312 (N_req(0.20R)=663) |
| CORE | LOO_noC1 | 94 | 0.914 | 0.596 | 1.220 | INCONCLUSIVE | bounds [0.596, 1.220]R, N=94 (N_req(0.20R)=663) |
| CORE | LOO_noC2 | 208 | 0.712 | 0.489 | 0.942 | INCONCLUSIVE | bounds [0.489, 0.942]R, N=208 (N_req(0.20R)=663) |
| CORE | LOO_noC3a | 31 | 0.218 | -0.245 | 0.747 | INCONCLUSIVE | bounds [-0.245, 0.747]R, N=31 (N_req(0.20R)=663) |
| CORE | LOO_noC3b | 99 | 0.760 | 0.436 | 1.085 | INCONCLUSIVE | bounds [0.436, 1.085]R, N=99 (N_req(0.20R)=663) |

## 8. Preregistered selection rule and INCONCLUSIVE findings
| change | S structural | V safety | O not refuted | caps | statuses | enters | flag |
|---|---|---|---|---|---|---|---|
| C1 | True | True | True | True | INCONCLUSIVE, INCONCLUSIVE, INCONCLUSIVE | True | owner priority |
| C2 | True | True | True | True | INCONCLUSIVE, INCONCLUSIVE, INCONCLUSIVE | True | owner priority |
| C3a | True | True | True | True | INCONCLUSIVE, INCONCLUSIVE, INCONCLUSIVE | True | research, flagged |
| C3b | True | True | True | True | INCONCLUSIVE, INCONCLUSIVE, INCONCLUSIVE | True | research, flagged |

Included changes: ['C1', 'C2', 'C3a', 'C3b']; frozen candidate: **CORE**; no candidate: False

Trades/E by year
| variant | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 |
|---|---|---|---|---|---|---|---|---|
| CTRL | 1/1.537 | 1/-1.020 | 1/-1.019 | 2/-1.036 | 0/- | 0/- | 0/- | 1/-1.021 |
| A_C1 | 1/1.537 | 1/-1.020 | 1/-1.019 | 2/-1.036 | 0/- | 2/1.995 | 0/- | 1/-1.021 |
| A_C2 | 3/0.842 | 7/0.699 | 13/-0.093 | 3/-0.028 | 5/0.126 | 11/0.826 | 10/-0.122 | 15/0.096 |
| A_C3a | 1/1.537 | 4/-0.352 | 1/-1.019 | 2/-1.036 | 0/- | 0/- | 0/- | 1/-1.021 |
| A_C3b | 3/-0.175 | 1/-1.020 | 1/-1.019 | 3/-1.035 | 0/- | 2/1.996 | 1/1.993 | 2/0.486 |
| B_C1C2 | 6/0.417 | 12/0.730 | 17/0.043 | 5/0.779 | 13/1.274 | 20/1.350 | 17/0.367 | 30/0.536 |
| B_C2C3a | 3/0.842 | 10/0.451 | 15/-0.217 | 3/-0.028 | 5/0.126 | 12/0.672 | 10/-0.122 | 17/0.318 |
| CORE | 18/0.104 | 20/0.617 | 38/0.160 | 16/1.029 | 15/1.189 | 51/0.849 | 30/0.970 | 41/0.700 |
| LOO_noC1 | 8/0.056 | 11/0.591 | 27/0.097 | 9/0.628 | 8/0.487 | 34/0.633 | 17/0.748 | 27/0.491 |
| LOO_noC2 | 4/-0.386 | 4/-0.348 | 2/0.310 | 4/-0.277 | 0/- | 6/1.495 | 1/1.993 | 2/0.486 |
| LOO_noC3a | 15/0.127 | 13/0.827 | 30/0.275 | 16/1.029 | 15/1.189 | 44/1.016 | 27/0.968 | 38/0.602 |
| LOO_noC3b | 9/0.275 | 19/0.544 | 25/-0.057 | 5/0.779 | 13/1.274 | 25/1.116 | 20/0.459 | 34/0.613 |
| X_C7 | 3/0.984 | 1/-1.020 | 8/-0.698 | 4/-1.028 | 0/- | 0/- | 0/- | 1/-1.033 |
| X_CORE_C7 | 56/0.176 | 64/-0.184 | 83/0.199 | 22/0.055 | 21/0.687 | 59/0.731 | 44/0.528 | 58/0.239 |
