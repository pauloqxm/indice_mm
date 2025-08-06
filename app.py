
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Carregando os dados
df = pd.read_csv("indice_mm.csv")

# Verifica se há uma coluna de data
if 'data' in df.columns:
    df['data'] = pd.to_datetime(df['data'], errors='coerce')
    df = df.dropna(subset=['data'])
    df = df.sort_values('data')
else:
    st.error("Coluna 'data' não encontrada.")
    st.stop()

# Renomeia a coluna de precipitação para facilitar
df.rename(columns={df.columns[1]: 'Precipitacao'}, inplace=True)

# Define variáveis principais
df['Dia Úmido'] = df['Precipitacao'] >= 1
df['Dia Seco'] = df['Precipitacao'] < 1

# Calcula os períodos secos consecutivos
df['Seco_Grupo'] = (df['Dia Seco'] != df['Dia Seco'].shift()).cumsum()
periodos_secos = df[df['Dia Seco']].groupby('Seco_Grupo').size()
qtd_periodos_secos = len(periodos_secos)
media_dias_secos = periodos_secos.mean() if qtd_periodos_secos > 0 else 0

# Título
st.title("Dashboard de Chuvas")

# Métricas principais
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total de Precipitação (mm)", round(df['Precipitacao'].sum(), 1))
col2.metric("Dias Úmidos (≥1 mm)", int(df['Dia Úmido'].sum()))
col3.metric("Dias Secos (<1 mm)", int(df['Dia Seco'].sum()))
col4.metric("Períodos de Dias Secos", qtd_periodos_secos)

# Gráfico de linha da precipitação
st.subheader("Precipitação Diária")
fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(df['data'], df['Precipitacao'], label='Precipitação (mm)', color='blue')
ax.set_ylabel('mm')
ax.set_xlabel('data')
ax.set_title('Histórico de Precipitação')
ax.grid(True)
st.pyplot(fig)

# Histograma dos períodos secos
st.subheader("Distribuição dos Períodos Secos")
if not periodos_secos.empty:
    fig2, ax2 = plt.subplots()
    ax2.hist(periodos_secos, bins=range(1, periodos_secos.max()+2), edgecolor='black')
    ax2.set_xlabel('Duração dos Períodos Secos (dias)')
    ax2.set_ylabel('Frequência')
    ax2.set_title('Períodos Secos Consecutivos')
    st.pyplot(fig2)
else:
    st.info("Nenhum período seco identificado.")
