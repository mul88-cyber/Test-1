import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Dashboard Big Player IDX", layout="wide")

# Optimasi: cache data besar
@st.cache_data
def load_data():
    FILE_ID = "1Pw_3C6EJvzEYsVHagbu7tL5szit6kitl"
    CSV_URL = f"https://drive.google.com/uc?id={FILE_ID}"
    df = pd.read_csv(CSV_URL)

    # Format tanggal fleksibel
    for col in df.columns:
        if col.strip().lower() == "last trading date":
            df.rename(columns={col: "Date"}, inplace=True)
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
            break

    return df.copy()

df = load_data()

# Hitung Net Foreign
df["Net Foreign"] = df["Foreign Buy"] - df["Foreign Sell"]

# Hitung VWAP
df["Typical Price"] = (df["High"] + df["Low"] + df["Close"]) / 3
df["VWAP"] = (df["Typical Price"] * df["Volume"]).cumsum() / df["Volume"].cumsum()

# Hitung RSI
delta = df["Close"].diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)
avg_gain = gain.rolling(window=14).mean()
avg_loss = loss.rolling(window=14).mean()
rs = avg_gain / avg_loss
df["RSI"] = 100 - (100 / (1 + rs))

st.title("📊 Dashboard Analisa Big Player (Bandarmologi)")

# Top Net Buy - Periode
st.subheader("🧠 Top Saham Net Buy Asing")
if "Date" in df.columns:
    now = df["Date"].max()
    options = ["All Time", "3 Bulan Terakhir", "1 Bulan Terakhir"]
    periode = st.selectbox("Pilih periode", options)
    if periode == "3 Bulan Terakhir":
        start_date = now - timedelta(days=90)
        df_filtered = df[df["Date"] >= start_date]
    elif periode == "1 Bulan Terakhir":
        start_date = now - timedelta(days=30)
        df_filtered = df[df["Date"] >= start_date]
    else:
        df_filtered = df.copy()

    top_buy = (
        df_filtered.groupby("Stock Code")
        .agg({
            "Company Name": "first",
            "Net Foreign": "sum",
            "Volume": "sum",
            "Close": "last"
        })
        .reset_index()
        .sort_values(by="Net Foreign", ascending=False)
        .head(10)
    )

    st.dataframe(top_buy)
    fig1 = px.bar(top_buy, x="Stock Code", y="Net Foreign", title=f"Top Net Foreign Buy - {periode}")
    st.plotly_chart(fig1, use_container_width=True)
else:
    st.warning("Data tidak memiliki kolom Date untuk difilter.")

# Filter Akumulasi
st.subheader("🔍 Deteksi Akumulasi (Volume Naik, Harga Sideways)")
df["Price Change %"] = (df["Close"] - df["Open Price"]) / df["Open Price"] * 100
accumulated = df[(df["Volume"] > df["Volume"].median()) & (df["Price Change %"].abs() < 2)]
st.dataframe(accumulated[["Stock Code", "Volume", "Close", "Price Change %"]].sort_values(by="Volume", ascending=False).head(10))

# Transaksi Non Reguler
st.subheader("📦 Saham dengan Transaksi Non-Regular")
non_reg = df[df["Non Regular Volume"] > 0]
st.dataframe(non_reg[["Stock Code", "Non Regular Volume", "Non Regular Value"]].sort_values(by="Non Regular Value", ascending=False).head(10))

# VWAP & RSI
st.subheader("📈 VWAP Chart (Harga vs VWAP)")
selected_stock = st.selectbox("Pilih saham untuk lihat VWAP & RSI", df["Stock Code"].unique())
vwap_data = df[df["Stock Code"] == selected_stock].copy().reset_index(drop=True)
fig_vwap = px.line(vwap_data, y=["Close", "VWAP"], labels={"value": "Harga", "index": "Hari ke-"}, title=f"{selected_stock} - Harga vs VWAP")
st.plotly_chart(fig_vwap, use_container_width=True)

st.subheader("📉 RSI (Relative Strength Index)")
fig_rsi = px.line(vwap_data, y="RSI", labels={"value": "RSI", "index": "Hari ke-"}, title=f"{selected_stock} - RSI 14 Hari")
st.plotly_chart(fig_rsi, use_container_width=True)

# Watchlist
st.subheader("⭐ Watchlist Saham")
watchlist = st.multiselect("Pilih saham yang ingin dimonitor", df["Stock Code"].unique())
if watchlist:
    filtered_watchlist = df[df["Stock Code"].isin(watchlist)]
    st.dataframe(filtered_watchlist[["Stock Code", "Close", "Volume", "Net Foreign", "VWAP", "RSI"]].sort_values(by="Net Foreign", ascending=False))
    csv = filtered_watchlist.to_csv(index=False).encode('utf-8')
    st.download_button("📂 Download Watchlist sebagai CSV", data=csv, file_name="watchlist.csv", mime="text/csv")
else:
    st.info("Pilih minimal satu saham untuk menampilkan watchlist.")

# Heatmap Volume Spike
st.subheader("🔥 Heatmap Volume Spike (Volume vs Rata-rata)")
avg_volume_per_stock = df.groupby("Stock Code")["Volume"].mean().reset_index()
avg_volume_per_stock.columns = ["Stock Code", "Avg Volume"]
df_spike = pd.merge(df, avg_volume_per_stock, on="Stock Code")
df_spike["Volume Spike Ratio"] = df_spike["Volume"] / df_spike["Avg Volume"]
spike_top = df_spike.sort_values(by="Volume Spike Ratio", ascending=False).dropna().head(20)
fig_spike = px.density_heatmap(spike_top, x="Stock Code", y="Volume Spike Ratio", z="Volume", color_continuous_scale="Inferno", title="Top 20 Saham dengan Volume Spike")
st.plotly_chart(fig_spike, use_container_width=True)

# Filter Tanggal
st.subheader("⏰ Filter Tanggal")
if "Date" in df.columns:
    min_date, max_date = df["Date"].min(), df["Date"].max()
    start_date, end_date = st.date_input("Pilih rentang tanggal", [min_date, max_date], min_value=min_date, max_value=max_date)
    if start_date and end_date:
        df_filtered = df[(df["Date"] >= pd.to_datetime(start_date)) & (df["Date"] <= pd.to_datetime(end_date))]
        st.dataframe(df_filtered.head(50))
    else:
        st.warning("Rentang tanggal tidak valid.")
else:
    st.warning("Kolom 'Date' tidak ditemukan di data.")

# Candlestick Chart
st.subheader("📉 Grafik Candlestick")
selected_candle = st.selectbox("Pilih saham untuk candlestick", df["Stock Code"].unique(), key="candle")
candle_data = df[df["Stock Code"] == selected_candle].copy()
if not candle_data.empty:
    fig_candle = go.Figure(data=[go.Candlestick(
        x=candle_data.index,
        open=candle_data["Open Price"],
        high=candle_data["High"],
        low=candle_data["Low"],
        close=candle_data["Close"]
    )])
    fig_candle.update_layout(title=f"Candlestick Chart: {selected_candle}", xaxis_title="Index", yaxis_title="Harga")
    st.plotly_chart(fig_candle, use_container_width=True)
else:
    st.warning("Data tidak ditemukan.")
