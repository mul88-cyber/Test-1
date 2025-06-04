import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="Dashboard Big Player IDX", layout="wide")

@st.cache_data
def load_data():
    FILE_ID = "1Pw_3C6EJvzEYsVHagbu7tL5szit6kitl"
    CSV_URL = f"https://drive.google.com/uc?id={FILE_ID}"
    try:
        df = pd.read_csv(CSV_URL)
    except Exception as e:
        st.error(f"Gagal mengunduh data dari Google Drive: {e}")
        st.stop()

    for col in df.columns:
        if col.strip().lower() == "last trading date":
            df.rename(columns={col: "Date"}, inplace=True)
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
            break

    if df["Date"].isna().all():
        st.error("Semua nilai tanggal tidak valid. Periksa format 'Last Trading Date' di sumber.")
        st.stop()

    sector_url = "https://docs.google.com/spreadsheets/d/1wk5lkVqAMgFdcYBUKXqdIS2Rx3cX8pFgxSiXgeqEMjs/export?format=csv"
    try:
        sector_df = pd.read_csv(sector_url)
    except Exception as e:
        st.error(f"Gagal mengunduh data sektor: {e}")
        st.stop()

    sector_df.columns = sector_df.columns.str.strip()
    if len(sector_df.columns) >= 2:
        sector_df.rename(columns={sector_df.columns[1]: "Sector"}, inplace=True)
        df = pd.merge(df, sector_df, left_on="Stock Code", right_on="Kode Saham", how="left")
        df.drop(columns=["Kode Saham"], inplace=True, errors='ignore')

    required_cols = ["Stock Code", "Close", "Volume", "Foreign Buy", "Foreign Sell"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        st.error(f"Dataset kekurangan kolom penting: {missing_cols}")
        st.stop()

    return df

df = load_data()

# Indikator
try:
    df["Net Foreign"] = df["Foreign Buy"] - df["Foreign Sell"]
    df["Typical Price"] = (df["High"] + df["Low"] + df["Close"]) / 3
    df["VWAP"] = (df["Typical Price"] * df["Volume"]).cumsum() / df["Volume"].cumsum()
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))
except Exception as e:
    st.warning(f"Indikator tidak dapat dihitung sepenuhnya: {e}")

st.title(":chart_with_upwards_trend: Dashboard Analisa Big Player (Bandarmologi)")

# ... (semua fitur sebelumnya tetap sama) ...

# --- ⏰ Filter Tanggal & Saham (Data Mentah) ---
st.header("⏰ Filter Tanggal & Saham (Data Mentah)")
selected_symbols = st.multiselect("Filter saham", df["Stock Code"].unique())
start_date, end_date = st.date_input("Rentang tanggal", [df["Date"].min(), df["Date"].max()])
filtered = df.copy()
if selected_symbols:
    filtered = filtered[filtered["Stock Code"].isin(selected_symbols)]
filtered = filtered[(filtered["Date"] >= pd.to_datetime(start_date)) & (filtered["Date"] <= pd.to_datetime(end_date))]

cols_show = [
    "Date", "Stock Code", "Previous", "Open Price", "High", "Low", "Close",
    "Change", "Change %", "Volume", "Frequency", "Foreign Sell", "Foreign Buy", "Net Foreign"
]
cols_final = [col for col in cols_show if col in filtered.columns]
data_to_show = filtered[cols_final].sort_values(by="Date", ascending=False)

if len(data_to_show) * len(data_to_show.columns) < 262144:
    st.dataframe(data_to_show.style.format({
        "Volume": ",.0f", "Frequency": ",.0f", "Foreign Sell": ",.0f",
        "Foreign Buy": ",.0f", "Net Foreign": ",.0f", "Previous": ",.0f",
        "Open Price": ",.0f", "High": ",.0f", "Low": ",.0f", "Close": ",.0f",
        "Change": ",.0f", "Change %": ".2f%"
    }), use_container_width=True)
else:
    st.warning("Dataset terlalu besar, ditampilkan tanpa format angka.")
    st.dataframe(data_to_show, use_container_width=True)
