# 0an readout: F1, F2 and F5 against the three explanations

Share is re-tests over slots used. Each change is the arm minus its concurrent control (F0 for Gemini and
DeepSeek, Panel A0 for Opus), paired by seed, with its 95% interval. The label is the registered one.

| explanation tested | arm | Opus | Gemini | DeepSeek |
|---|---|---|---|---|
| losing track of what was measured | F1 ledger | +4.4 [+2.6, +6.2]: no effect | -0.9 [-2.1, +0.2]: no effect | +0.8 [+0.1, +1.6]: no effect |
| not producing new candidates | F2 menu | -19.7 [-23.3, -16.0]: reduces | -26.2 [-27.9, -24.5]: reduces | -31.4 [-33.5, -29.4]: reduces |
| missing knowledge of the structure | F5 structure | -4.7 [-7.8, -1.5]: no effect | -0.5 [-1.8, +0.8]: no effect | +1.5 [+0.8, +2.2]: no effect |

Joint reading per model (registered rule of 0an.3):

- Opus: F2 works and F5 does not: the bottleneck is producing candidates; F1 does not work.
- Gemini: F2 works and F5 does not: the bottleneck is producing candidates; F1 does not work.
- DeepSeek: F2 works and F5 does not: the bottleneck is producing candidates; F1 does not work.

## Final pick, split by seed into exploration and selection

Pick change = exploration part (change in the best true value measured) minus selection part (change in
best measured minus nominated). The pick label is the registered one, with its band.

| arm | model | pairs | pick change | label | exploration part | selection part | readings of the nominated candidate (control) | nominated the highest mean (control) |
|---|---|---|---|---|---|---|---|---|
| F1 ledger | Opus | 60 | -0.126 [-0.211, -0.036] | pick falls (descriptive) | -0.185 [-0.252, -0.117] | -0.059 [-0.107, -0.016] | 21.1 (16.5) | 75% (53%) |
| F1 ledger | Gemini | 120 | -0.190 [-0.271, -0.113] | pick falls | -0.176 [-0.246, -0.107] | +0.015 [-0.010, +0.038] | 39.7 (39.3) | 91% (92%) |
| F1 ledger | DeepSeek | 120 | +0.011 [-0.032, +0.058] | no change beyond delta | +0.005 [-0.034, +0.047] | -0.006 [-0.033, +0.022] | 19.0 (18.4) | 77% (71%) |
| F2 menu | Opus | 30 | +0.098 [-0.066, +0.268] | no change beyond delta (descriptive) | +0.184 [+0.030, +0.336] | +0.087 [-0.001, +0.182] | 13.1 (16.2) | 60% (47%) |
| F2 menu | Gemini | 120 | +0.035 [-0.035, +0.106] | no change beyond delta | +0.169 [+0.106, +0.234] | +0.134 [+0.096, +0.173] | 11.4 (39.3) | 64% (92%) |
| F2 menu | DeepSeek | 120 | -0.011 [-0.098, +0.076] | no change beyond delta | +0.084 [+0.008, +0.162] | +0.095 [+0.053, +0.140] | 11.1 (18.4) | 53% (71%) |
| F5 structure | Opus | 30 | -0.020 [-0.157, +0.138] | no change beyond delta (descriptive) | -0.070 [-0.202, +0.071] | -0.051 [-0.106, +0.000] | 17.1 (16.2) | 73% (47%) |
| F5 structure | Gemini | 120 | +0.016 [-0.009, +0.045] | no change beyond delta | +0.018 [-0.007, +0.044] | +0.002 [-0.018, +0.020] | 38.5 (39.3) | 89% (92%) |
| F5 structure | DeepSeek | 120 | -0.128 [-0.190, -0.066] | pick falls | -0.114 [-0.171, -0.056] | +0.014 [-0.015, +0.044] | 18.7 (18.4) | 75% (71%) |

## Exploration and lost slots

| arm | model | distinct (control) | rejected per new name, % (control) | lost slots: non-viable, rounds |
|---|---|---|---|---|
| F1 ledger | Opus | 9.0 (11.3) | 75.8 (70.6) | 1.93, 0.00 |
| F1 ledger | Gemini | 3.4 (3.0) | 89.9 (90.1) | 0.46, 0.03 |
| F1 ledger | DeepSeek | 4.7 (4.9) | 80.5 (78.7) | 0.03, 0.00 |
| F2 menu | Opus | 17.7 (11.2) | 74.5 (70.7) | 5.47, 0.00 |
| F2 menu | Gemini | 14.5 (3.0) | 75.1 (90.1) | 3.02, 0.03 |
| F2 menu | DeepSeek | 17.7 (4.9) | 74.8 (78.7) | 3.86, 0.00 |
| F5 structure | Opus | 12.8 (11.2) | 74.5 (70.7) | 2.90, 0.00 |
| F5 structure | Gemini | 3.3 (3.0) | 93.3 (90.1) | 0.41, 0.00 |
| F5 structure | DeepSeek | 4.3 (4.9) | 84.0 (78.7) | 0.07, 0.00 |

## F2: the menu in the panel

| model | new names taken from the list | viable, from the list | viable, its own |
|---|---|---|---|
| claude-opus-4.7 | 1717 of 1980 (87%) | 30.7% (1717) | 40.7% (263) |
| deepseek-chat-v3.1 | 7512 of 7719 (97%) | 30.7% (7512) | 70.0% (207) |
| gemini-2.5-flash | 5057 of 5912 (86%) | 30.6% (5057) | 48.9% (855) |

## F2: list names against the agent's own (scripts/menu_check_0an.py)

New names exclude the starting candidate. "Earlier list" names were shown on an earlier list but not the
current one. Intervals resample whole campaigns. The baseline is the same definition with no list.

| model | list: viable (names) | earlier list | own | own minus list | own minus list, matched on rounds | no list: F0 | no list: A0 Blind |
|---|---|---|---|---|---|---|---|
| claude-opus-4.7 | 30.5% [27.7, 33.2] (1712) | 41.0% [27.3, 57.1] (39) | 38.7% [31.6, 46.1] (217) | +8.2 [+0.7, +15.9] | +10.8 [-0.6, +23.3] | none | 34.9% [32.9, 36.9] (2088) |
| deepseek-chat-v3.1 | 30.7% [28.9, 32.4] (7507) | 45.2% [28.0, 62.5] (31) | 45.8% [36.3, 56.2] (83) | +15.1 [+5.0, +26.2] | +15.6 [+5.3, +28.6] | 45.2% [43.2, 47.1] (1128) | 53.3% [49.7, 56.7] (531) |
| gemini-2.5-flash | 30.6% [29.1, 32.3] (5054) | 38.8% [31.7, 45.3] (209) | 40.2% [35.0, 45.2] (515) | +9.6 [+4.0, +14.9] | +10.0 [+4.8, +15.5] | 16.9% [14.6, 19.4] (1554) | 17.2% [13.7, 21.0] (766) |
