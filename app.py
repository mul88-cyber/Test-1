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

st.title(":chart_with_upwards_trend: Dashboard Analisa Big Player (Bandarmologi)")

# --- Top Net Buy ---
st.header("🧲 Top Saham Net Buy Asing")
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

st.dataframe(top_buy.style.format({"Net Foreign": "{:,.0f}", "Volume": "{:,.0f}", "Close": "{:,.0f}"}))
fig1 = px.bar(top_buy, x="Stock Code", y="Net Foreign", title=f"Top Net Foreign Buy - {periode}")
st.plotly_chart(fig1, use_container_width=True)

# --- Deteksi Akumulasi ---
st.header("🔍 Deteksi Akumulasi (Volume Naik, Harga Sideways)")
df["Price Change %"] = (df["Close"] - df["Open Price"]) / df["Open Price"] * 100
akumulasi = df[(df["Volume"] > df["Volume"].rolling(5).mean()) & (df["Price Change %"].abs() < 2)]
akumulasi_top = (
    akumulasi.groupby("Stock Code")
    .agg({"Volume": "mean", "Price Change %": "mean", "Net Foreign": "sum"})
    .reset_index()
    .sort_values(by="Volume", ascending=False)
    .head(10)
)
st.dataframe(akumulasi_top.style.format({"Volume": "{:,.0f}", "Price Change %": "{:.2f}", "Net Foreign": "{:,.0f}"}))
fig_aku = px.bar(akumulasi_top, x="Stock Code", y="Volume", title="Top 10 Saham Akumulasi - Rata2 Volume Tinggi, Harga Sideways")
st.plotly_chart(fig_aku, use_container_width=True)

# --- Foreign Flow per Saham (Bulanan) ---
st.header("🌍 Foreign Flow Harian per Saham")
selected_ff = st.selectbox("Pilih saham untuk melihat foreign flow harian", df["Stock Code"].unique())
unique_months = df["Date"].dt.to_period("M").unique().sort_values(ascending=False)
selected_month = st.selectbox("Pilih bulan", unique_months.astype(str))
month_df = df[(df["Stock Code"] == selected_ff) & (df["Date"].dt.to_period("M") == pd.Period(selected_month))]
fig_ff = px.line(month_df.sort_values("Date"), x="Date", y="Net Foreign", title=f"Foreign Flow Harian - {selected_ff} ({selected_month})", markers=True)
st.plotly_chart(fig_ff, use_container_width=True)

# --- VWAP & RSI ---
st.header("📈 VWAP & RSI")
selected_stock = st.selectbox("Pilih saham untuk lihat VWAP & RSI", df["Stock Code"].unique(), key="vwap")
vwap_data = df[df["Stock Code"] == selected_stock].copy().reset_index(drop=True)
fig_vwap = px.line(vwap_data, x="Date", y=["Close", "VWAP"], labels={"value": "Harga", "Date": "Tanggal"}, title=f"{selected_stock} - Harga vs VWAP")
st.plotly_chart(fig_vwap, use_container_width=True)
fig_rsi = px.line(vwap_data, x="Date", y="RSI", labels={"value": "RSI", "Date": "Tanggal"}, title=f"{selected_stock} - RSI 14 Hari")
st.plotly_chart(fig_rsi, use_container_width=True)

# --- Watchlist ---
st.header("⭐ Watchlist Saham")
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

# --- Heatmap Volume Spike ---
st.header("🔥 Heatmap Volume Spike (vs Rata-rata)")
avg_volume_per_stock = df.groupby("Stock Code")["Volume"].mean().reset_index()
avg_volume_per_stock.columns = ["Stock Code", "Avg Volume"]
df_spike = pd.merge(df, avg_volume_per_stock, on="Stock Code")
df_spike["Volume Spike Ratio"] = df_spike["Volume"] / df_spike["Avg Volume"]
spike_top = df_spike.sort_values(by="Volume Spike Ratio", ascending=False).dropna().head(20)
fig_spike = px.density_heatmap(spike_top, x="Stock Code", y="Volume Spike Ratio", z="Volume", color_continuous_scale="Inferno", title="Top 20 Saham dengan Volume Spike")
st.plotly_chart(fig_spike, use_container_width=True)

# --- Heatmap per Sektor ---
st.header("🌐 Heatmap Berdasarkan Sektor")
sector_summary = df.groupby("Sector").agg({"Net Foreign": "sum", "Volume": "sum"}).reset_index().sort_values(by="Net Foreign", ascending=False)
fig_sector = px.treemap(sector_summary, path=["Sector"], values="Net Foreign", color="Volume", title="Net Foreign per Sektor (Warna = Volume)", color_continuous_scale="Viridis")
st.plotly_chart(fig_sector, use_container_width=True)

# --- Filter Tanggal Data Mentah + Filter Saham + Kolom Khusus ---
st.header("⏰ Filter Tanggal Data Mentah")
unique_symbols = df["Stock Code"].unique()
selected_symbols = st.multiselect("Pilih saham", unique_symbols)
min_date, max_date = df["Date"].min(), df["Date"].max()
start_date, end_date = st.date_input("Pilih rentang tanggal", [min_date, max_date], min_value=min_date, max_value=max_date)

filtered = df.copy()
if selected_symbols:
    filtered = filtered[filtered["Stock Code"].isin(selected_symbols)]
if start_date and end_date:
    filtered = filtered[(filtered["Date"] >= pd.to_datetime(start_date)) & (filtered["Date"] <= pd.to_datetime(end_date))]

cols_to_show = [
    "Date", "Stock Code", "Previous", "Open Price", "High", "Low", "Close",
    "Change", "Change %", "Volume", "Frequency", "Foreign Sell", "Foreign Buy", "Net Foreign"
]
cols_final = [col for col in cols_to_show if col in filtered.columns]
st.dataframe(filtered[cols_final].sort_values(by="Date", ascending=False).style.format({
    "Volume": "{:,.0f}", "Frequency": "{:,.0f}", "Foreign Sell": "{:,.0f}",
    "Foreign Buy": "{:,.0f}", "Net Foreign": "{:,.0f}", "Previous": "{:,.0f}",
    "Open Price": "{:,.0f}", "High": "{:,.0f}", "Low": "{:,.0f}", "Close": "{:,.0f}",
    "Change": "{:,.0f}", "Change %": "{:.2f}%"
}))
[[AKAN DISISIPKAN FITUR BARU DI BAWAH HEADER YANG ADA]]

# --- 📢 Alert Harian ---
st.header("📢 Alert Harian (Volume, Net Foreign, Harga)")
latest_date = df["Date"].max()
latest_df = df[df["Date"] == latest_date]
alerts = latest_df[(latest_df["Volume"] > latest_df["Volume"].median() * 2) |
                   (latest_df["Net Foreign"].abs() > latest_df["Net Foreign"].median() * 2) |
                   (latest_df["Change %"].abs() > 5)]

st.dataframe(alerts[["Date", "Stock Code", "Volume", "Net Foreign", "Change %"]].sort_values(by="Net Foreign", ascending=False).style.format({
    "Volume": "{:,.0f}", "Net Foreign": "{:,.0f}", "Change %": "{:.2f}%"
}))

# --- 🔁 Integrasi Multi Hari (5 Hari Terakhir) ---
st.header("🔁 Integrasi Multi Hari (5 Hari Terakhir)")
cutoff = df["Date"].max() - timedelta(days=5)
multi_df = df[df["Date"] >= cutoff]
summary_multi = (
    multi_df.groupby("Stock Code")
    .agg({
        "Net Foreign": "mean",
        "Volume": "mean",
        "Close": ["first", "last"]
    })
    .reset_index()
)
summary_multi.columns = ["Stock Code", "Net Foreign Avg", "Volume Avg", "Close First", "Close Last"]
summary_multi["Change 5D %"] = (summary_multi["Close Last"] - summary_multi["Close First"]) / summary_multi["Close First"] * 100
summary_multi = summary_multi.sort_values(by="Net Foreign Avg", ascending=False).head(10)

st.dataframe(summary_multi.style.format({
    "Net Foreign Avg": "{:,.0f}", "Volume Avg": "{:,.0f}", "Change 5D %": "{:.2f}%"
}))
