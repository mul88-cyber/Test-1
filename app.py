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

# Top Net Buy
st.header("🧲 Top Saham Net Buy Asing")
now = df["Date"].max()
periode = st.selectbox("Pilih periode", ["All Time", "3 Bulan Terakhir", "1 Bulan Terakhir"])
df_filtered = df.copy()
if periode == "3 Bulan Terakhir":
    df_filtered = df[df["Date"] >= now - timedelta(days=90)]
elif periode == "1 Bulan Terakhir":
    df_filtered = df[df["Date"] >= now - timedelta(days=30)]

top_buy = df_filtered.groupby("Stock Code").agg({
    "Company Name": "first",
    "Net Foreign": "sum",
    "Volume": "sum",
    "Close": "last"
}).reset_index().sort_values(by="Net Foreign", ascending=False).head(10)

st.dataframe(top_buy.style.format({"Net Foreign": ",.0f", "Volume": ",.0f", "Close": ",.0f"}))
fig1 = px.bar(top_buy, x="Stock Code", y="Net Foreign", title=f"Top Net Foreign Buy - {periode}")
st.plotly_chart(fig1, use_container_width=True)

# Deteksi Akumulasi
st.header("🔍 Deteksi Akumulasi (Volume Naik, Harga Sideways)")
df["Price Change %"] = (df["Close"] - df["Open Price"]) / df["Open Price"] * 100
akumulasi = df[(df["Volume"] > df["Volume"].rolling(5).mean()) & (df["Price Change %"].abs() < 2)]
akumulasi_top = akumulasi.groupby("Stock Code").agg({
    "Volume": "mean",
    "Price Change %": "mean",
    "Net Foreign": "sum"
}).reset_index().sort_values(by="Volume", ascending=False).head(10)

st.dataframe(akumulasi_top.style.format({"Volume": ",.0f", "Price Change %": ".2f", "Net Foreign": ",.0f"}))
fig_aku = px.bar(akumulasi_top, x="Stock Code", y="Volume", title="Top 10 Saham Akumulasi - Volume Tinggi, Harga Sideways")
st.plotly_chart(fig_aku, use_container_width=True)

# Foreign Flow
st.header("🌍 Foreign Flow Harian per Saham")
selected_ff = st.selectbox("Pilih saham", df["Stock Code"].unique())
if pd.api.types.is_datetime64_any_dtype(df["Date"]):
    unique_months = sorted(df["Date"].dt.to_period("M").dropna().unique(), reverse=True)
    if unique_months:
        selected_month = st.selectbox("Pilih bulan", [str(m) for m in unique_months])
        month_df = df[(df["Stock Code"] == selected_ff) & (df["Date"].dt.to_period("M") == pd.Period(selected_month))]
        fig_ff = px.line(month_df.sort_values("Date"), x="Date", y="Net Foreign", title=f"Foreign Flow - {selected_ff} ({selected_month})", markers=True)
        st.plotly_chart(fig_ff, use_container_width=True)
    else:
        st.warning("Data tanggal tidak tersedia atau tidak valid.")

# VWAP & RSI
st.header("📈 VWAP & RSI")
selected_stock = st.selectbox("Pilih saham", df["Stock Code"].unique(), key="vwap")
vwap_data = df[df["Stock Code"] == selected_stock].copy().reset_index(drop=True)
fig_vwap = px.line(vwap_data, x="Date", y=["Close", "VWAP"], title=f"{selected_stock} - Harga vs VWAP")
st.plotly_chart(fig_vwap, use_container_width=True)
fig_rsi = px.line(vwap_data, x="Date", y="RSI", title=f"{selected_stock} - RSI 14 Hari")
st.plotly_chart(fig_rsi, use_container_width=True)

# Watchlist
st.header("⭐ Watchlist Saham")
watchlist = st.multiselect("Pilih saham", df["Stock Code"].unique())
if watchlist:
    filtered_watchlist = df[df["Stock Code"].isin(watchlist)]
    st.dataframe(filtered_watchlist[["Date", "Stock Code", "Close", "Volume", "Net Foreign", "VWAP", "RSI"]]
                 .sort_values(by="Date", ascending=False)
                 .style.format({"Close": ",.0f", "Volume": ",.0f", "Net Foreign": ",.0f", "VWAP": ",.0f", "RSI": ".1f"}))

# Volume Spike Heatmap
st.header("🔥 Heatmap Volume Spike")
avg_volume = df.groupby("Stock Code")["Volume"].mean().reset_index(name="Avg Volume")
df_spike = pd.merge(df, avg_volume, on="Stock Code")
df_spike["Volume Spike Ratio"] = df_spike["Volume"] / df_spike["Avg Volume"]
spike_top = df_spike.sort_values(by="Volume Spike Ratio", ascending=False).dropna().head(20)
fig_spike = px.density_heatmap(spike_top, x="Stock Code", y="Volume Spike Ratio", z="Volume", color_continuous_scale="Inferno")
st.plotly_chart(fig_spike, use_container_width=True)

# Heatmap per Sektor
st.header("🌐 Heatmap Berdasarkan Sektor")
if "Sector" in df.columns:
    sector_summary = df.groupby("Sector").agg({"Net Foreign": "sum", "Volume": "sum"}).reset_index()
    fig_sector = px.treemap(sector_summary, path=["Sector"], values="Net Foreign", color="Volume", color_continuous_scale="Viridis")
    st.plotly_chart(fig_sector, use_container_width=True)
else:
    st.warning("Kolom 'Sector' tidak ditemukan dalam data.")

# Filter Mentah
st.header("⏰ Filter Tanggal & Saham (Data Mentah)")
selected_symbols = st.multiselect("Filter saham", df["Stock Code"].unique())
start_date, end_date = st.date_input("Rentang tanggal", [df["Date"].min(), df["Date"].max()])
filtered = df.copy()
if selected_symbols:
    filtered = filtered[filtered["Stock Code"].isin(selected_symbols)]
filtered = filtered[(filtered["Date"] >= pd.to_datetime(start_date)) & (filtered["Date"] <= pd.to_datetime(end_date))]
cols_show = ["Date", "Stock Code", "Previous", "Open Price", "High", "Low", "Close", "Change", "Change %", "Volume", "Frequency", "Foreign Sell", "Foreign Buy", "Net Foreign"]
st.dataframe(filtered[[col for col in cols_show if col in filtered.columns]]
    .sort_values(by="Date", ascending=False).style.format({
    "Volume": ",.0f", "Frequency": ",.0f", "Foreign Sell": ",.0f", "Foreign Buy": ",.0f",
    "Net Foreign": ",.0f", "Previous": ",.0f", "Open Price": ",.0f", "High": ",.0f",
    "Low": ",.0f", "Close": ",.0f", "Change": ",.0f", "Change %": ".2f%"}))

# Alert Harian
st.header("📢 Alert Harian")
latest_df = df[df["Date"] == df["Date"].max()]
alerts = latest_df[(latest_df["Volume"] > latest_df["Volume"].median()*2) |
                   (latest_df["Net Foreign"].abs() > latest_df["Net Foreign"].median()*2) |
                   (latest_df["Change %"].abs() > 5)]
st.dataframe(alerts[["Date", "Stock Code", "Volume", "Net Foreign", "Change %"]]
             .sort_values(by="Net Foreign", ascending=False).style.format({
    "Volume": ",.0f", "Net Foreign": ",.0f", "Change %": ".2f%"}))

# Integrasi Multi Hari
st.header("🔁 Integrasi Multi Hari (5 Hari Terakhir)")
cutoff = df["Date"].max() - timedelta(days=5)
multi_df = df[df["Date"] >= cutoff]
summary_multi = multi_df.groupby("Stock Code").agg({
    "Net Foreign": "mean",
    "Volume": "mean",
    "Close": ["first", "last"]
}).reset_index()
summary_multi.columns = ["Stock Code", "Net Foreign Avg", "Volume Avg", "Close First", "Close Last"]
summary_multi["Change 5D %"] = (summary_multi["Close Last"] - summary_multi["Close First"]) / summary_multi["Close First"] * 100
summary_multi = summary_multi.sort_values(by="Net Foreign Avg", ascending=False).head(10)
st.dataframe(summary_multi.style.format({
    "Net Foreign Avg": ",.0f", "Volume Avg": ",.0f", "Change 5D %": ".2f%"
}))
