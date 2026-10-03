# Daily to Monthly Stock Pipeline

A modular **Pandas** pipeline that turns 2 years of daily stock prices for 10 tickers into monthly summaries with technical indicators, then saves one CSV file per ticker.

**Tools:** Python and Pandas only. No third-party technical analysis libraries. The only other imports are from Python's standard library (`pathlib`, `math`).

---

## Overview

| | |
|---|---|
| **Input** | One CSV with daily `date, volume, open, high, low, close, adjclose, ticker` |
| **Output** | 10 files named `result_{SYMBOL}.csv`, each with 24 monthly rows |
| **Tickers** | AAPL, AMD, AMZN, AVGO, CSCO, MSFT, NFLX, PEP, TMUS, TSLA |
| **Period** | January 2018 to December 2019 |

**In one sentence:** about 500 daily rows per stock become 24 monthly rows per stock, with indicators added as extra columns.

### About the dataset

Checked on the provided dataset before building the pipeline:
- 5,030 rows in total, which is 503 trading days for each of the 10 tickers.
- Every ticker covers 24 calendar months, from Jan 2018 to Dec 2019.
- No duplicate `(ticker, date)` rows.
- Rows are not in date order, so the pipeline sorts them first.

---

## Project Structure

```
.
├── data/
│   └── stock_data.csv        # input dataset
├── output/
│   └── result_{SYMBOL}.csv   # 10 output files
├── main.py                   # pipeline script
├── requirements.txt          # pandas
└── README.md
```

## How to Run

1. Download the dataset from https://github.com/sandeep-tt/tt-intern-dataset. The file there is named `output_file.csv`. Save it as `data/stock_data.csv`.
2. Install and run:

```bash
pip install -r requirements.txt
python main.py
```

Pandas 2.2 or newer is needed, because the month-end alias `"ME"` is used for resampling. A successful run ends with `All saved output files validated successfully.`

---

## How It Works

| Step | Function | What it does |
|---|---|---|
| 1 | `load_data` | Reads the master CSV |
| 2 | `validate_input`, `validate_duplicates` | Checks columns, the 10 tickers, and duplicate rows |
| 3 | `clean_data` | Converts dates and sorts by ticker and date |
| 4 | `aggregate_monthly` | Daily to monthly Open, High, Low, Close |
| 5 | `sma_seeded_ema` | Calculates the EMA, starting from the SMA |
| 6 | `calculate_indicators` | Adds SMA, EMA, Donchian, Bollinger and Z-score columns |
| 7 | `validate_monthly_output` | Checks 24 rows, sorted dates, unique months, correct ticker |
| 8 | `process_all_tickers` | Splits the data per ticker with `groupby` and runs steps 4 to 7 |
| 9 | `save_results` | Writes one CSV per ticker |
| 10 | `validate_saved_files` | Reads the saved files back and checks them |

Calculation functions (steps 4 to 6) are kept separate from file-writing functions (steps 9 and 10), as the assignment asks.

---

## Methodology

### Monthly Open, High, Low, Close

Daily data is resampled to calendar months with `resample("ME")` and `.agg()`:

| Column | Rule | Meaning |
|---|---|---|
| `open` | `first` | Open price on the **first trading day** of the month |
| `high` | `max` | Highest high during the month |
| `low` | `min` | Lowest low during the month |
| `close` | `last` | Close price on the **last trading day** of the month |

Open and Close are snapshots of a single day, not averages.

### Indicators

All indicators use the **monthly close**, except Donchian, which uses monthly high and low.

| Indicator | Columns | How it is calculated |
|---|---|---|
| Simple Moving Average | `SMA_10`, `SMA_20` | `close.rolling(n).mean()` |
| Exponential Moving Average | `EMA_10`, `EMA_20` | `sma_seeded_ema` (see below) |
| Donchian Channels | `Donchian_High_20`, `Donchian_Low_20` | `high.rolling(20).max()` and `low.rolling(20).min()` |
| Bollinger Bands | `BB_Middle_20`, `BB_Upper_20`, `BB_Lower_20` | 20-month mean, plus and minus 2 standard deviations |
| Z-score | `Z_Score_20` | `(close - 20-month mean) / 20-month std` |

### EMA

The EMA follows the formula in the assignment reference:

1. **Multiplier:** `2 / (N + 1)`
2. **First value:** the SMA of the first N closes, as the reference suggests.
3. **Every value after that:** `multiplier × current close + (1 − multiplier) × previous EMA`. This is the same as the reference's `(current − previous EMA) × multiplier + previous EMA`.

The EMA is the one calculation done with a plain loop instead of a built-in Pandas function. Each EMA value depends on the one before it, so the loop follows the formula step by step. It runs over only 24 monthly values per ticker.

The code also checks that, on the first row where both exist, the EMA equals the SMA. If it doesn't, the pipeline stops.

### Output columns

Every `result_{SYMBOL}.csv` has these columns, in this order:

```
date, open, high, low, close,
SMA_10, SMA_20, EMA_10, EMA_20,
Donchian_High_20, Donchian_Low_20,
BB_Middle_20, BB_Upper_20, BB_Lower_20,
Z_Score_20, ticker
```

---

## Validation

The pipeline stops with a clear error message if any check fails.

| When | What is checked |
|---|---|
| Before processing | All required columns exist. All 10 tickers are present, and no others. No duplicate `(ticker, date)` rows. |
| During calculation | EMA seeds match the SMA. Each ticker has exactly 24 rows, unique months, sorted dates, and the right ticker value. |
| After saving | Exactly the 10 expected files exist. Each has 24 rows, the exact column order, one ticker, and sorted unique dates. |

---

## Assumptions

1. **Months:** Calendar months, labelled with the month-end date. Open and Close come from the first and last trading day that exists in the data for that month.
2. **Indicator input:** SMA, EMA, Bollinger Bands and Z-score use the monthly **close**, as the assignment says. Donchian uses monthly **high** and **low**, as in the given formula.
3. **Window size:** The assignment gives no window for Donchian, Bollinger or Z-score, so I used **20 months**, matching the longest moving average. Bollinger Bands use **k = 2**.
4. **Standard deviation:** Pandas' default rolling standard deviation (sample, `ddof=1`) is used, following the formula in the assignment.
5. **EMA start:** The first EMA value is the SMA of the first N closes, as the reference suggests.
6. **Empty cells at the start:** An indicator can't be calculated until enough months exist, so the early rows are left empty (`NaN`). They are not filled in or dropped, which keeps all 24 rows in every file.

   | Indicator | Empty rows at the start |
   |---|---|
   | `SMA_10`, `EMA_10` | first 9 |
   | `SMA_20`, `EMA_20`, Donchian, Bollinger, Z-score | first 19 |

7. **Unused columns:** `volume` and `adjclose` are not needed in the output, so they are not carried forward.
8. **Strict checks:** If a ticker is missing or unexpected, or a ticker doesn't give exactly 24 months, the pipeline stops instead of continuing with bad data.

---

## Requirements Checklist

- [x] Daily to monthly resampling with correct first / last / max / min logic
- [x] SMA 10 and 20, EMA 10 and 20 (EMA starts from the SMA, as in the reference)
- [x] Donchian Channels, Bollinger Bands and Z-score as separate columns
- [x] 10 files named `result_{SYMBOL}.csv`, 24 rows each
- [x] Modular functions, with calculation separate from file writing
- [x] Pandas only, no third-party technical analysis libraries
- [x] Checks before processing, during calculation and after saving
- [x] Assumptions documented