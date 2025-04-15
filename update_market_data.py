import os
from datetime import datetime, date
import pandas as pd
import yfinance as yf

# Existing list: Nifty 50 symbols
nifty_50_symbols = [
    "ADANIENT.NS", "ADANIPORTS.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS",
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "BPCL.NS", "BHARTIARTL.NS", "BRITANNIA.NS",
    "CIPLA.NS", "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS", "EICHERMOT.NS",
    "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS",
    "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS", "INDUSINDBK.NS",
    "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LTIM.NS", "LT.NS",
    "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS", "ONGC.NS",
    "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS", "SUNPHARMA.NS",
    "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TECHM.NS",
    "TITAN.NS", "UPL.NS", "ULTRACEMCO.NS", "WIPRO.NS"
]

# New list: Two commodity tickers.
commodity_symbols = [
    "GOLDBEES.NS",  # Gold ETF
    "SILVERBEE.NS"   # Silver ETF
]

# New list: Five top currency tickers (for conversion rates to INR).
currency_symbols = [
    "USDINR=X",     # US Dollar to INR
    "EURINR=X",     # Euro to INR
    "GBPINR=X",     # British Pound to INR
    "JPYINR=X",     # Japanese Yen to INR
    "AUDINR=X"      # Australian Dollar to INR
]

# Combine all tickers for a single data download
all_tickers = nifty_50_symbols + commodity_symbols + currency_symbols

def update_market_data():
    csv_file = "market_data.csv"
    # Check if file was already updated today and has valid data
    if os.path.exists(csv_file):
        mod_time = datetime.fromtimestamp(os.path.getmtime(csv_file)).date()
        if mod_time == date.today():
            try:
                df_check = pd.read_csv(csv_file)
                if not df_check.empty:
                    print(":white_check_mark: Market data CSV is already up to date.")
                    return
                else:
                    print(":warning: File is empty. Will re-fetch data.")
            except Exception as e:
                print(f":warning: Error reading CSV. Will re-fetch data: {e}")
        else:
            print(":arrows_counterclockwise: File is outdated. Will fetch new data.")
    else:
        print(":open_file_folder: No file found. Will fetch fresh data.")

    # Proceed to fetch and save fresh data
    print(":inbox_tray: Downloading fresh market data for Nifty 50, commodities, and currencies...")
    try:
        data = yf.download(
            tickers=all_tickers,
            period="1d",
            interval="1d",
            group_by='ticker',
            auto_adjust=True,
            threads=True
        )
    except Exception as e:
        print(":x: Failed to download market data:", e)
        return

    # Flatten the data for each symbol
    data_rows = []
    for symbol in all_tickers:
        try:
            # If the data was downloaded for a symbol, extract first (and only) row.
            row = data[symbol].iloc[0]
            data_rows.append({
                "Symbol": symbol,
                "Open": row["Open"],
                "High": row["High"],
                "Low": row["Low"],
                "Close": row["Close"],
                "Volume": row["Volume"],
                "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        except Exception as e:
            print(f":x: {symbol} failed: {e}")
    
    df = pd.DataFrame(data_rows)
    if df.empty:
        print(":warning: No data fetched. File will not be overwritten.")
    else:
        df.to_csv(csv_file, index=False)
        print(f":white_check_mark: Market data saved to {csv_file}")

if __name__ == "__main__":
    update_market_data()
