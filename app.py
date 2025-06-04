import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="Dashboard Big Player IDX", layout="wide")

@st.cache_data
def load_data():
    FILE_ID = "1Pw_3C6EJvzEYsVHagbu7tL5szit6kitl"
    CSV_URL = f"https://drive.google.com/uc?id={FILE_ID}"
    df = pd.read_csv(CSV_URL)

    for col in df.columns:
        if col.strip().lower() == "last trading date":
            df.rename(columns={col: "Date"}, inplace=True)
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
            break

    # Load sector mapping from Google Sheets
    sector_url = "https://docs.google.com/spreadsheets/d/1wk5lkVqAMgFdcYBUKXqdIS2Rx3cX8pFgxSiXgeqEMjs/export?format=csv"
    sector_df = pd.read_csv(sector_url)
    sector_df.columns = sector_df.columns.str.strip()
    sector_df.rename(columns={sector_df.columns[1]: "Sector"}, inplace=True)
    df = pd.merge(df, sector_df, left_on="Stock Code", right_on="Kode Saham", how="left")
    df.drop(columns=["Kode Saham"], inplace=True)
    return df

df = load_data()

# Hitung indikator
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

st.title("📊 Dashboard Analisa Big Player (Bandarmologi)")

# Top Net Buy
st.subheader("🧠 Top Saham Net Buy Asing")
if "Date" in df.columns:
    now = df["Date"].max()
    options = ["All Time", "3 Bulan Terakhir", "1 Bulan Terakhir"]
    periode = st.selectbox("Pilih periode", options)
    if periode == "3 Bulan Terakhir":
        df_filtered = df[df["Date"] >= now - timedelta(days=90)]
    elif periode == "1 Bulan Terakhir":
        df_filtered = df[df["Date"] >= now - timedelta(days=30)]
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

    st.dataframe(top_buy.style.format({
        "Net Foreign": "{:,.0f}", "Volume": "{:,.0f}", "Close": "{:,.0f}"
    }))
    fig1 = px.bar(top_buy, x="Stock Code", y="Net Foreign", title=f"Top Net Foreign Buy - {periode}")
    st.plotly_chart(fig1, use_container_width=True)
else:
    st.warning("Data tidak memiliki kolom Date untuk difilter.")

# Deteksi Akumulasi
st.subheader("🔍 Deteksi Akumulasi (Volume Naik, Harga Sideways)")
df["Price Change %"] = (df["Close"] - df["Open Price"]) / df["Open Price"] * 100
accumulated = df[(df["Volume"] > df["Volume"].median()) & (df["Price Change %"].abs() < 2)]
st.dataframe(accumulated[["Date", "Stock Code", "Volume", "Close", "Price Change %"]].sort_values(by="Volume", ascending=False).head(10).style.format({"Volume": "{:,.0f}", "Close": "{:,.0f}"}))

# Transaksi Non Reguler
st.subheader("📦 Saham dengan Transaksi Non-Regular")
non_reg = df[df["Non Regular Volume"] > 0]
st.dataframe(non_reg[["Date", "Stock Code", "Non Regular Volume", "Non Regular Value"]].sort_values(by="Non Regular Value", ascending=False).head(10).style.format({"Non Regular Volume": "{:,.0f}", "Non Regular Value": "{:,.0f}"}))

# VWAP & RSI
st.subheader("📈 VWAP Chart (Harga vs VWAP)")
selected_stock = st.selectbox("Pilih saham untuk lihat VWAP & RSI", df["Stock Code"].unique())
vwap_data = df[df["Stock Code"] == selected_stock].copy().reset_index(drop=True)
fig_vwap = px.line(vwap_data, x="Date", y=["Close", "VWAP"], labels={"value": "Harga", "Date": "Tanggal"}, title=f"{selected_stock} - Harga vs VWAP")
st.plotly_chart(fig_vwap, use_container_width=True)

st.subheader("📉 RSI (Relative Strength Index)")
fig_rsi = px.line(vwap_data, x="Date", y="RSI", labels={"value": "RSI", "Date": "Tanggal"}, title=f"{selected_stock} - RSI 14 Hari")
st.plotly_chart(fig_rsi, use_container_width=True)

# Watchlist
st.subheader("⭐ Watchlist Saham")
watchlist = st.multiselect("Pilih saham yang ingin dimonitor", df["Stock Code"].unique())
if watchlist:
    filtered_watchlist = df[df["Stock Code"].isin(watchlist)]
    st.dataframe(filtered_watchlist[["Date", "Stock Code", "Close", "Volume", "Net Foreign", "VWAP", "RSI"]].sort_values(by="Date", ascending=False).style.format({
        "Close": "{:,.0f}", "Volume": "{:,.0f}", "Net Foreign": "{:,.0f}", "VWAP": "{:,.0f}", "RSI": "{:,.1f}"
    }))
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

# Heatmap per Sektor
st.subheader("🌍 Heatmap Berdasarkan Sektor")
sector_summary = df.groupby("Sector").agg({
    "Net Foreign": "sum",
    "Volume": "sum"
}).reset_index().sort_values(by="Net Foreign", ascending=False)
fig_sector = px.treemap(sector_summary, path=["Sector"], values="Net Foreign", color="Volume", title="Net Foreign per Sektor (Warna = Volume)", color_continuous_scale="Viridis")
st.plotly_chart(fig_sector, use_container_width=True)

# Foreign Flow
st.subheader("🌍 Foreign Flow (Aliran Dana Asing)")
if "Date" in df.columns:
    date_range = st.date_input("Pilih rentang tanggal untuk foreign flow", [df["Date"].min(), df["Date"].max()])
    if len(date_range) == 2:
        start_date, end_date = date_range
        flow_df = df[(df["Date"] >= pd.to_datetime(start_date)) & (df["Date"] <= pd.to_datetime(end_date))]

        top_foreign = (
            flow_df.groupby("Stock Code")["Net Foreign"]
            .sum().reset_index().sort_values(by="Net Foreign", ascending=False).head(10)
        )
        st.dataframe(top_foreign.style.format({"Net Foreign": "{:,.0f}"}))

        fig_flow = px.bar(top_foreign, x="Stock Code", y="Net Foreign",
                          title="Top 10 Aliran Dana Asing (Net Foreign)", color="Net Foreign")
        st.plotly_chart(fig_flow, use_container_width=True)
else:
    st.warning("Data tidak memiliki kolom Date untuk foreign flow.")

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
