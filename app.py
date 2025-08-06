
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# Carregar dados
df = pd.read_csv("indice_mm.csv", sep=";", decimal=",")

# Processar datas
if 'data' in df.columns:
    df['data'] = pd.to_datetime(df['data'], errors='coerce')
    df = df.dropna(subset=['data'])
    df = df.sort_values('data')
else:
    st.error("Coluna 'data' não encontrada.")
    st.stop()

df.rename(columns={df.columns[1]: 'Precipitacao'}, inplace=True)
df['Ano'] = df['data'].dt.year
df['Mes'] = df['data'].dt.month
df['Dia Úmido'] = df['Precipitacao'] >= 1
df['Dia Seco'] = df['Precipitacao'] < 1

# Períodos secos consecutivos
df['Seco_Grupo'] = (df['Dia Seco'] != df['Dia Seco'].shift()).cumsum()
periodos_secos = df[df['Dia Seco']].groupby('Seco_Grupo').size()
qtd_periodos_secos = len(periodos_secos)

# Filtros interativos
anos_disponiveis = df['Ano'].dropna().unique()
ano_selecionado = st.selectbox("Selecione o ano", sorted(anos_disponiveis, reverse=True))
df_ano = df[df['Ano'] == ano_selecionado]

data_min = df_ano['data'].min().to_pydatetime()
data_max = df_ano['data'].max().to_pydatetime()
data_range = st.slider("Selecione o período",
                       min_value=data_min,
                       max_value=data_max,
                       value=(data_min, data_max),
                       format="DD/MM/YYYY")
df_filtrado = df_ano[(df_ano['data'] >= data_range[0]) & (df_ano['data'] <= data_range[1])]

# Título
st.title("Dashboard Interativo de Chuvas")

# Métricas
col1, col2, col3, col4 = st.columns(4)
col1.metric("Precipitação Total (mm)", round(df_filtrado['Precipitacao'].sum(), 1))
col2.metric("Dias Úmidos (≥1 mm)", int(df_filtrado['Dia Úmido'].sum()))
col3.metric("Dias Secos (<1 mm)", int(df_filtrado['Dia Seco'].sum()))
col4.metric("Períodos de Dias Secos", qtd_periodos_secos)

# Gráfico interativo de precipitação
st.subheader("Precipitação Diária")
fig1 = px.line(df_filtrado, x='data', y='Precipitacao',
               labels={'data': 'Data', 'Precipitacao': 'Precipitação (mm)'},
               title="Precipitação ao Longo do Tempo")
st.plotly_chart(fig1, use_container_width=True)

# Gráfico interativo de períodos secos
st.subheader("Distribuição dos Períodos Secos")
if not periodos_secos.empty:
    fig2 = px.histogram(periodos_secos, nbins=20,
                        labels={'value': 'Duração dos Períodos (dias)', 'count': 'Frequência'},
                        title="Períodos Secos Consecutivos")
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("Nenhum período seco identificado.")
