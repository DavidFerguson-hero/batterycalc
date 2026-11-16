# Accuracy check (task 3.1)

How close is the **estimate route** (yearly use plus our typical pattern of use) to the answer from a home's **real half-hourly smart meter data**?

## Method
- **Data:** Low Carbon London smart meter trial, 2013 (UK Power Networks, via [4TU.ResearchData](https://data.4tu.nl/datasets/fbbe775b-48d8-469f-a39b-b64488bfd6fd), CC BY 4.0). One full calendar year of half-hourly readings for 4,443 London homes on standard tariffs. The data stays outside this repo; only the anonymised summary figures below are kept.
- **Sample:** 61 homes with at least 99% of readings present, spread evenly from the 5th to the 95th centile of yearly use (about 1,200 to 8,200 kWh).
- **Comparison:** each home goes through `POST /api/v2/assess` twice, with the same flat starting tariff (28.16p/kWh, 53p/day):
  - the **upload route**, using its real readings
  - the **estimate route**, given only its real yearly total
- **What it tests:** our assumed pattern of use through the day and the year, *not* how well we guess yearly use from a home's details. The trial recorded no property details.
- **Re-run:** `cd api && python scripts/accuracy_check.py --lcl /path/to/LCL_2013.csv --homes 61 --markdown`

## Result

| | Before (hand-drawn day, identical days) | After (measured day, varied days) |
|---|---|---|
| Year-1 saving of a 10 kWh battery, median gap (estimate vs real) | **+8%** (estimate too high) | **+1%** |
| Median size of that gap | 8% | 5% |
| Within ±10% | 34 of 61 | **47 of 61** |
| Within ±20% | 54 of 61 | **57 of 61** |
| Payback, median gap | 1.4 years too soon | 0.1 years |
| Payback within 2 years | 38 of 61 | **52 of 61** |
| Same verdict | 51 of 61 (every miss too hopeful) | **54 of 61** (4 too hopeful, 3 too cautious, all close calls) |
| Same recommended size | 49 of 61 | 49 of 61 |

### What was wrong and what changed (`api/engine/profile_estimator.py`)
1. **Daily shape.** The hand-drawn day put 8% of use before 06:00 and 23% in the 16:00–19:00 peak. Measured across 3,765 trial homes, the real figures are 15% and 17%. The estimate now uses the measured average day.
2. **Every day was the same.** Real homes' daily totals vary by about 25% around the month's average. A battery can't store all of a busy day's peak, or fill usefully on a quiet one. The estimate now varies each day by a fixed pseudo-random factor with that spread, keeping each month's total.
3. **Seasons.** The gas-heated monthly factors are now the measured ones; they were already close. The electric-heating factors are unchanged, because the trial had too few electrically heated homes to measure them.

### Limits
- These are London homes in 2013 on standard tariffs, with no electric cars, heat pumps or solar panels. Today's homes may use electricity differently (more working from home, LED lighting).
- The trial has no property type, so flats and houses now share one daily shape.
- The estimate route also has to guess yearly use when someone doesn't know it. This check doesn't cover that; a real home with known details is needed (David's house is next).

## After: all 61 homes
| Home | kWh/yr | Size real/est | Tariff same? | Yr-1 saving real/est | Payback real/est (yrs) | Verdict real/est | 10 kWh saving real/est | Gap |
|---|---|---|---|---|---|---|---|---|
| L01 | 3,869 | 10 / 10 | yes | £658 / £690 | 11.2 / 10.7 | not_yet / not_yet | £658 / £690 | +5% |
| L02 | 5,423 | 15 / 15 | yes | £1,040 / £993 | 8.4 / 8.7 | borderline / borderline | £817 / £758 | -7% |
| L03 | 3,628 | 10 / 10 | yes | £673 / £663 | 10.9 / 11.1 | not_yet / not_yet | £673 / £663 | -2% |
| L04 | 2,885 | 10 / 7.5 | yes | £485 / £516 | 14.9 / 12.3 | not_yet / not_yet | £485 / £557 | +15% |
| L05 | 4,576 | 10 / 10 | yes | £780 / £741 | 8.1 / 8.5 | borderline / borderline | £780 / £741 | -5% |
| L06 | 4,946 | 15 / 13.5 | yes | £950 / £901 | 10.3 / 10.3 | not_yet / not_yet | £755 / £753 | -0% |
| L07 | 1,338 | 5 / 5 | yes | £272 / £260 | never / never | not_yet / not_yet | £274 / £262 | -4% |
| L08 | 2,449 | 7.5 / 7.5 | yes | £440 / £462 | 14.3 / 13.7 | not_yet / not_yet | £490 / £478 | -2% |
| L09 | 2,167 | 5 / 5 | yes | £349 / £364 | never / 14.7 | not_yet / not_yet | £409 / £424 | +4% |
| L10 | 7,632 | 20 / 20 | yes | £1,119 / £1,369 | 10.4 / 7.8 | not_yet / borderline | £574 / £709 | +24% |
| L11 | 2,105 | 5 / 5 | yes | £308 / £360 | never / 14.8 | not_yet / not_yet | £354 / £412 | +16% |
| L12 | 2,628 | 7.5 / 7.5 | yes | £504 / £486 | 12.6 / 13.0 | not_yet / not_yet | £534 / £511 | -4% |
| L13 | 1,774 | 5 / 5 | yes | £310 / £327 | never / never | not_yet / not_yet | £347 / £347 | +0% |
| L14 | 2,707 | 7.5 / 7.5 | yes | £429 / £496 | 14.6 / 12.8 | not_yet / not_yet | £478 / £526 | +10% |
| L15 | 8,188 | 20 / 20 | yes | £1,312 / £1,423 | 8.1 / 7.5 | borderline / borderline | £789 / £690 | -12% |
| L16 | 3,426 | 7.5 / 10 | yes | £592 / £638 | 10.8 / 11.5 | not_yet / not_yet | £643 / £638 | -1% |
| L17 | 2,766 | 10 / 7.5 | yes | £506 / £503 | 14.3 / 12.6 | not_yet / not_yet | £506 / £536 | +6% |
| L18 | 2,394 | 7.5 / 7.5 | yes | £447 / £454 | 14.1 / 13.9 | not_yet / not_yet | £466 / £468 | +0% |
| L19 | 1,388 | 5 / 5 | yes | £290 / £269 | never / never | not_yet / not_yet | £291 / £272 | -6% |
| L20 | 2,042 | 5 / 5 | yes | £346 / £355 | never / never | not_yet / not_yet | £399 / £400 | +0% |
| L21 | 1,458 | 5 / 5 | yes | £282 / £281 | never / never | not_yet / not_yet | £289 / £285 | -1% |
| L22 | 3,986 | 10 / 10 | yes | £614 / £702 | 11.9 / 10.5 | not_yet / not_yet | £614 / £702 | +14% |
| L23 | 1,970 | 5 / 5 | yes | £345 / £349 | never / never | not_yet / not_yet | £394 / £386 | -2% |
| L24 | 4,456 | 10 / 10 | yes | £729 / £735 | 10.1 / 10.0 | not_yet / not_yet | £729 / £735 | +1% |
| L25 | 2,565 | 7.5 / 7.5 | yes | £433 / £478 | 14.5 / 13.2 | not_yet / not_yet | £490 / £500 | +2% |
| L26 | 4,693 | 10 / 10 | yes | £764 / £746 | 8.2 / 8.4 | borderline / borderline | £764 / £746 | -2% |
| L27 | 3,326 | 10 / 10 | yes | £638 / £625 | 11.5 / 11.7 | not_yet / not_yet | £638 / £625 | -2% |
| L28 | 2,272 | 7.5 / 7.5 | yes | £434 / £436 | 14.5 / 14.4 | not_yet / not_yet | £449 / £444 | -1% |
| L29 | 5,253 | 15 / 15 | yes | £856 / £972 | 11.3 / 10.1 | not_yet / not_yet | £633 / £757 | +20% |
| L30 | 3,521 | 10 / 10 | yes | £576 / £650 | 12.6 / 11.3 | not_yet / not_yet | £576 / £650 | +13% |
| L31 | 3,172 | 10 / 7.5 | yes | £571 / £541 | 12.8 / 11.8 | not_yet / not_yet | £571 / £603 | +6% |
| L32 | 1,894 | 5 / 5 | yes | £318 / £341 | never / never | not_yet / not_yet | £348 / £371 | +7% |
| L33 | 2,989 | 7.5 / 7.5 | yes | £527 / £526 | 12.1 / 12.1 | not_yet / not_yet | £565 / £574 | +2% |
| L34 | 3,244 | 10 / 10 | yes | £556 / £613 | 13.1 / 11.9 | not_yet / not_yet | £556 / £613 | +10% |
| L35 | 5,803 | 15 / 15 | yes | £1,050 / £1,035 | 8.3 / 8.4 | borderline / borderline | £800 / £756 | -5% |
| L36 | 4,257 | 10 / 10 | yes | £690 / £724 | 10.7 / 10.2 | not_yet / not_yet | £690 / £724 | +5% |
| L37 | 4,179 | 10 / 10 | yes | £754 / £718 | 8.3 / 10.3 | borderline / not_yet | £754 / £718 | -5% |
| L38 | 6,769 | 20 / 20 | yes | £1,102 / £1,265 | 10.6 / 8.4 | not_yet / borderline | £630 / £735 | +17% |
| L39 | 5,114 | 15 / 15 | yes | £981 / £954 | 8.8 / 10.2 | borderline / not_yet | £748 / £756 | +1% |
| L40 | 4,068 | 10 / 10 | yes | £645 / £709 | 11.4 / 10.4 | not_yet / not_yet | £645 / £709 | +10% |
| L41 | 6,277 | 15 / 15 | yes | £1,005 / £1,078 | 8.6 / 8.1 | borderline / borderline | £662 / £748 | +13% |
| L42 | 2,818 | 7.5 / 7.5 | yes | £530 / £508 | 12.0 / 12.5 | not_yet / not_yet | £571 / £546 | -4% |
| L43 | 3,695 | 10 / 10 | yes | £611 / £671 | 12.0 / 10.9 | not_yet / not_yet | £611 / £671 | +10% |
| L44 | 6,494 | 20 / 20 | yes | £1,080 / £1,228 | 10.8 / 8.6 | not_yet / borderline | £581 / £743 | +28% |
| L45 | 4,813 | 10 / 13.5 | yes | £767 / £885 | 8.2 / 10.5 | borderline / not_yet | £767 / £749 | -2% |
| L46 | 1,524 | 5 / 5 | yes | £280 / £292 | never / never | not_yet / not_yet | £289 / £298 | +3% |
| L47 | 1,588 | 5 / 5 | yes | £310 / £302 | never / never | not_yet / not_yet | £321 / £311 | -3% |
| L48 | 4,358 | 20 / 10 | yes | £798 / £730 | 14.4 / 10.1 | not_yet / not_yet | £503 / £730 | +45% |
| L49 | 2,510 | 7.5 / 7.5 | yes | £451 / £471 | 14.0 / 13.4 | not_yet / not_yet | £483 / £490 | +1% |
| L50 | 3,777 | 10 / 10 | yes | £711 / £680 | 10.4 / 10.8 | not_yet / not_yet | £711 / £680 | -4% |
| L51 | 2,324 | 7.5 / 7.5 | yes | £427 / £444 | 14.7 / 14.2 | not_yet / not_yet | £475 / £454 | -4% |
| L52 | 2,215 | 7.5 / 5 | yes | £440 / £367 | 14.3 / 14.6 | not_yet / not_yet | £443 / £433 | -2% |
| L53 | 3,096 | 10 / 7.5 | yes | £549 / £536 | 13.2 / 11.9 | not_yet / not_yet | £549 / £591 | +8% |
| L54 | 1,655 | 5 / 5 | yes | £315 / £311 | never / never | not_yet / not_yet | £319 / £324 | +2% |
| L55 | 1,267 | 5 / 5 | yes | £243 / £247 | never / never | not_yet / not_yet | £271 / £248 | -9% |
| L56 | 7,112 | 20 / 20 | yes | £1,188 / £1,309 | 8.9 / 8.1 | borderline / borderline | £615 / £725 | +18% |
| L57 | 1,714 | 5 / 5 | yes | £275 / £319 | never / never | not_yet / not_yet | £308 / £336 | +9% |
| L58 | 1,837 | 5 / 5 | yes | £313 / £334 | never / never | not_yet / not_yet | £356 / £360 | +1% |
| L59 | 6,010 | 20 / 15 | yes | £1,211 / £1,055 | 8.8 / 8.2 | borderline / borderline | £689 / £753 | +9% |
| L60 | 5,599 | 20 / 15 | yes | £1,042 / £1,013 | 11.2 / 8.6 | not_yet / borderline | £627 / £758 | +21% |
| L61 | 3,039 | 10 / 7.5 | yes | £591 / £531 | 12.4 / 12.0 | not_yet / not_yet | £591 / £583 | -1% |
