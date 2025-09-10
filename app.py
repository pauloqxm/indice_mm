import streamlit as st
import pandas as pd

# Carregar dados
@st.cache_data
def load_data():
    return pd.read_csv("bacia_banabuiu.csv")

df = load_data()

st.title("🌧️ Cálculo do Índice de Intensidade da Precipitação (INT)")

# Converter data se existir
if "date" in df.columns:
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["ano"] = df["date"].dt.year
else:
    st.error("A planilha precisa ter uma coluna chamada 'date'.")
    st.stop()

if "precip" not in df.columns:
    st.error("A planilha precisa ter uma coluna chamada 'precip'.")
    st.stop()

# ==============================
# Cálculos
# ==============================

# Soma da precipitação
soma_precip = df["precip"].sum()

# Dias úmidos (>= 1mm)
dias_umedos = (df["precip"] >= 1).sum()

# Precipitação média por dia úmido
media_umedo = soma_precip / dias_umedos if dias_umedos > 0 else 0

# Média anual da precipitação
media_anual = df.groupby("ano")["precip"].sum().mean()

# Intensidade da Precipitação (INT)
INT = media_umedo / media_anual if media_anual > 0 else 0

# ==============================
# Exibir resultados
# ==============================
st.metric("🌧️ Soma da precipitação", f"{soma_precip:.2f} mm")
st.metric("📅 Dias úmidos", dias_umedos)
st.metric("💧 Precipitação média por dia úmido", f"{media_umedo:.2f} mm/dia")
st.metric("📊 Média anual da precipitação", f"{media_anual:.2f} mm")
st.metric("⚡ Intensidade da Precipitação (INT)", f"{INT:.3f}")
