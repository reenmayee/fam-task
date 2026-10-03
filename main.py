import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = "data/stock_data.csv"
OUTPUT_DIR = "output"

EXPECTED_TICKERS = {
    "AAPL", "AMD", "AMZN", "AVGO", "CSCO",
    "MSFT", "NFLX", "PEP", "TMUS", "TSLA"
}

EXPECTED_COLUMNS = {
    "date", "volume", "open", "high",
    "low", "close", "adjclose", "ticker"
}


# ============================================================
# 1. LOAD DATA
# ============================================================

def load_data(filepath):
    df = pd.read_csv(filepath)

    print(f"Loaded {len(df)} rows.")

    return df


# ============================================================
# 2. VALIDATE INPUT DATA
# ============================================================

def validate_input(df):

    # Check required columns
    actual_columns = set(df.columns)

    missing_columns = EXPECTED_COLUMNS - actual_columns

    if missing_columns:
        raise ValueError(
            f"Missing columns: {missing_columns}"
        )

    # Check tickers
    actual_tickers = set(df["ticker"].unique())

    missing_tickers = EXPECTED_TICKERS - actual_tickers

    if missing_tickers:
        raise ValueError(
            f"Missing tickers: {missing_tickers}"
        )

    unexpected_tickers = actual_tickers - EXPECTED_TICKERS

    if unexpected_tickers:
        raise ValueError(
            f"Unexpected tickers: {unexpected_tickers}"
        )

    print("Input validation passed.")


# ============================================================
# 3. CLEAN DATA
# ============================================================

def clean_data(df):

    # Convert date column to datetime
    df["date"] = pd.to_datetime(df["date"])

    # Sort by ticker and date
    df = df.sort_values(
        ["ticker", "date"]
    ).reset_index(drop=True)

    return df


# ============================================================
# 4. CHECK DUPLICATES
# ============================================================

def validate_duplicates(df):

    duplicate_count = df.duplicated(
        subset=["ticker", "date"]
    ).sum()

    if duplicate_count > 0:
        raise ValueError(
            f"Found {duplicate_count} duplicate records."
        )

    print("Duplicate check passed.")


# ============================================================
# 5. MONTHLY OHLC AGGREGATION
# ============================================================

def aggregate_monthly(ticker_df):

    ticker_df = ticker_df.set_index("date")

    monthly = ticker_df.resample("ME").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last"
    })

    return monthly.reset_index()


# ============================================================
# 6. CALCULATE TECHNICAL INDICATORS
# ============================================================


def sma_seeded_ema(close, span):
    """
    Calculate EMA using the SMA of the first `span` values
    as the initial EMA seed.
    """

    alpha = 2 / (span + 1)

    ema = pd.Series(float("nan"), index=close.index)

    # First EMA value is the SMA of the first `span` closes
    seed_index = close.index[span - 1]
    ema.loc[seed_index] = close.iloc[:span].mean()

    # Recursive EMA calculation after the seed
    for i in range(span, len(close)):
        current_index = close.index[i]
        previous_index = close.index[i - 1]

        ema.loc[current_index] = (
            alpha * close.loc[current_index]
            + (1 - alpha) * ema.loc[previous_index]
        )

    return ema


def calculate_indicators(monthly):

    close = monthly["close"]

    # --------------------------------------------------------
    # Simple Moving Average
    # --------------------------------------------------------

    monthly["SMA_10"] = (
        close.rolling(10).mean()
    )

    monthly["SMA_20"] = (
        close.rolling(20).mean()
    )

    # --------------------------------------------------------
    # Exponential Moving Average
    # --------------------------------------------------------

    monthly["EMA_10"] = sma_seeded_ema(close, 10)
    monthly["EMA_20"] = sma_seeded_ema(close, 20)

    # Validate EMA seeds
    if not np.isclose(
        monthly["EMA_10"].iloc[9],
        monthly["SMA_10"].iloc[9]
    ):    
        raise ValueError("EMA_10 seed validation failed.")

    if not np.isclose(
        monthly["EMA_20"].iloc[19],
        monthly["SMA_20"].iloc[19]
    ):
        raise ValueError("EMA_20 seed validation failed.")

    # --------------------------------------------------------
    # Donchian Channels
    # 20-month rolling window
    # --------------------------------------------------------

    monthly["Donchian_High_20"] = (
        monthly["high"]
        .rolling(20)
        .max()
    )

    monthly["Donchian_Low_20"] = (
        monthly["low"]
        .rolling(20)
        .min()
    )

    # --------------------------------------------------------
    # Bollinger Bands
    # 20-month window
    # k = 2
    # --------------------------------------------------------

    rolling_mean = (
        close.rolling(20).mean()
    )

    rolling_std = (
        close.rolling(20).std()
    )

    monthly["BB_Middle_20"] = rolling_mean

    monthly["BB_Upper_20"] = (
        rolling_mean + 2 * rolling_std
    )

    monthly["BB_Lower_20"] = (
        rolling_mean - 2 * rolling_std
    )

    # --------------------------------------------------------
    # Z-Score
    # --------------------------------------------------------

    monthly["Z_Score_20"] = (
        (close - rolling_mean)
        / rolling_std
    )

    return monthly


# ============================================================
# 7. VALIDATE MONTHLY OUTPUT
# ============================================================

def validate_monthly_output(df, ticker):

    # Exactly 24 months
    if len(df) != 24:
        raise ValueError(
            f"{ticker}: expected 24 monthly rows, "
            f"got {len(df)}"
        )

    # No duplicate months
    if df["date"].duplicated().any():
        raise ValueError(
            f"{ticker}: duplicate months found."
        )

    # Dates must be sorted
    if not df["date"].is_monotonic_increasing:
        raise ValueError(
            f"{ticker}: dates are not sorted."
        )

    # Only one ticker should exist
    if (
        df["ticker"].nunique() != 1
        or df["ticker"].iloc[0] != ticker
    ):
        raise ValueError(
            f"{ticker}: ticker validation failed."
        )

    print(
        f"{ticker}: output validation passed."
    )


# ============================================================
# 8. PROCESS ALL TICKERS
# ============================================================

def process_all_tickers(df):

    results = {}

    for ticker, ticker_df in df.groupby("ticker"):

        print(f"\nProcessing {ticker}...")

        # Monthly OHLC
        monthly = aggregate_monthly(
            ticker_df.copy()
        )

        # Technical indicators
        monthly = calculate_indicators(
            monthly
        )

        # Add ticker column
        monthly["ticker"] = ticker

        # Validate result
        validate_monthly_output(
            monthly,
            ticker
        )

        results[ticker] = monthly

    return results


# ============================================================
# 9. SAVE RESULTS
# ============================================================

def save_results(results, output_dir=OUTPUT_DIR):

    output_path = Path(output_dir)

    # Create output directory if it doesn't exist
    output_path.mkdir(
        parents=True,
        exist_ok=True
    )

    for ticker, result_df in results.items():

        file_path = (
            output_path
            / f"result_{ticker}.csv"
        )

        result_df.to_csv(
            file_path,
            index=False
        )

        print(
            f"Saved: {file_path}"
        )

# ============================================================
# 10. VALIDATE SAVED CSV FILES
# ============================================================

def validate_saved_files(output_dir="output"):

    output_path = Path(output_dir)

    expected_files = {
        f"result_{ticker}.csv"
        for ticker in EXPECTED_TICKERS
    }

    actual_files = {
        file.name
        for file in output_path.glob("result_*.csv")
    }

    # Check exactly 10 expected files
    if actual_files != expected_files:
        raise ValueError(
            f"Output files mismatch.\n"
            f"Expected: {expected_files}\n"
            f"Found: {actual_files}"
        )

    required_columns = [
        "date", "open", "high", "low", "close",
        "SMA_10", "SMA_20",
        "EMA_10", "EMA_20",
        "Donchian_High_20", "Donchian_Low_20",
        "BB_Middle_20", "BB_Upper_20", "BB_Lower_20",
        "Z_Score_20", "ticker"
    ]

    # Validate every saved CSV
    for ticker in sorted(EXPECTED_TICKERS):

        file_path = output_path / f"result_{ticker}.csv"

        result = pd.read_csv(file_path)

        # Check 24 monthly rows
        if len(result) != 24:
            raise ValueError(
                f"{ticker}: expected 24 rows, got {len(result)}"
            )

        # Check exact column structure
        if list(result.columns) != required_columns:
            raise ValueError(
                f"{ticker}: output columns do not match expected schema."
            )

        # Check ticker
        if result["ticker"].nunique() != 1:
            raise ValueError(
                f"{ticker}: multiple tickers found."
            )

        if result["ticker"].iloc[0] != ticker:
            raise ValueError(
                f"{ticker}: incorrect ticker value."
            )

        # Check dates
        result["date"] = pd.to_datetime(result["date"])

        if not result["date"].is_monotonic_increasing:
            raise ValueError(
                f"{ticker}: dates are not sorted."
            )

        if result["date"].duplicated().any():
            raise ValueError(
                f"{ticker}: duplicate dates found."
            )

        print(
            f"{ticker}: saved file validation passed."
        )

    print(
        "\nAll saved output files validated successfully."
    )


# ============================================================
# 11. MAIN PIPELINE
# ============================================================

def main():

    # Load
    df = load_data(INPUT_FILE)

    # Validate input
    validate_input(df)

    # Clean
    df = clean_data(df)

    # Check duplicates
    validate_duplicates(df)

    # Process all tickers
    results = process_all_tickers(df)

    # Save CSV files
    save_results(results)

    # Validate saved CSV files
    validate_saved_files()

    print(
        "\nAll tickers processed successfully."
    )

    # Final shape check
    print("\nFinal output shapes:")

    for ticker, result in results.items():

        print(
            f"{ticker}: {result.shape}"
        )


# ============================================================
# RUN PROGRAM
# ============================================================

if __name__ == "__main__":
    main()