
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Dashboard de Precipitação", layout="wide")

# Carregar e processar dados
@st.cache_data
def load_data():
    # Carrega os dados substituindo vírgulas por pontos nos decimais
    df = pd.read_csv("indice_mm.csv", sep=";", decimal=",")
    
    # Processamento de datas
    if 'data' in df.columns:
        df['data'] = pd.to_datetime(df['data'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['data'])
        df = df.sort_values('data')
    else:
        st.error("Coluna 'data' não encontrada no arquivo.")
        st.stop()

    # Garantir que a coluna de precipitação está numérica
    precip_col = df.columns[1]
    df['Precipitacao'] = pd.to_numeric(
        df[precip_col].astype(str).str.replace(',', '.'), 
        errors='coerce'
    )
    df = df.dropna(subset=['Precipitacao'])
    
    # Extrair ano e mês
    df['Ano'] = df['data'].dt.year
    df['Mes'] = df['data'].dt.month
    df['Mes_Nome'] = df['data'].dt.month_name()
    df['Dia_do_Ano'] = df['data'].dt.dayofyear

    # Classificar dias
    df['Dia Úmido'] = df['Precipitacao'] >= 1
    df['Dia Seco'] = df['Precipitacao'] < 1

    return df

df = load_data()

# Sidebar com filtros
st.sidebar.header("Filtros")

# Filtro de ano na sidebar
anos_disponiveis = sorted(df['Ano'].unique(), reverse=True)
ano_selecionado = st.sidebar.selectbox("Selecione o ano", anos_disponiveis)

# Filtro de mês na sidebar (apenas para o ano selecionado)
meses_disponiveis = sorted(df[df['Ano'] == ano_selecionado]['Mes'].unique())
mes_selecionado = st.sidebar.selectbox(
    "Selecione o mês", 
    options=['Todos'] + meses_disponiveis,
    format_func=lambda x: 'Todos' if x == 'Todos' else datetime(1900, x, 1).strftime('%B')
)

# Aplicar filtros
df_filtrado = df[df['Ano'] == ano_selecionado]
if mes_selecionado != 'Todos':
    df_filtrado = df_filtrado[df_filtrado['Mes'] == mes_selecionado]

# Contador de registros na sidebar
st.sidebar.markdown(f"**Registros carregados:** {len(df_filtrado)} dia{'s' if len(df_filtrado) != 1 else ''}")

# Calcular períodos secos
df_filtrado['Seco_Grupo'] = (df_filtrado['Dia Seco'] != df_filtrado['Dia Seco'].shift()).cumsum()
periodos_secos = df_filtrado[df_filtrado['Dia Seco']].groupby('Seco_Grupo').size()
qtd_periodos_secos = len(periodos_secos)

# Layout principal
titulo = f"Análise de Precipitação - {ano_selecionado}"
if mes_selecionado != 'Todos':
    nome_mes = datetime(1900, mes_selecionado, 1).strftime('%B')
    titulo += f" - {nome_mes}"
st.title(titulo)

# Métricas
col1, col2, col3, col4 = st.columns(4)
col1.metric("Precipitação Total (mm)", f"{round(df_filtrado['Precipitacao'].sum(), 1)} mm")
col2.metric("Dias Úmidos (≥1 mm)", f"{int(df_filtrado['Dia Úmido'].sum())} dias")
col3.metric("Dias Secos (<1 mm)", f"{int(df_filtrado['Dia Seco'].sum())} dias")
col4.metric("Períodos Secos", f"{qtd_periodos_secos} períodos")

# Gráficos
tab1, tab2, tab3 = st.tabs(["Precipitação Diária", "Análise Mensal", "Períodos Secos"])

with tab1:
    st.subheader("Precipitação Diária")
    fig1 = px.bar(df_filtrado, x='data', y='Precipitacao',
                 labels={'data': 'Data', 'Precipitacao': 'Precipitação (mm)'},
                 color='Precipitacao',
                 color_continuous_scale='Blues')
    st.plotly_chart(fig1, use_container_width=True)

with tab2:
    st.subheader("Análise Mensal")
    mensal = df_filtrado.groupby(['Mes', 'Mes_Nome']).agg({
        'Precipitacao': 'sum',
        'Dia Úmido': 'sum',
        'Dia Seco': 'sum'
    }).reset_index().sort_values('Mes')

    fig2 = px.bar(mensal, x='Mes_Nome', y='Precipitacao',
                 labels={'Mes_Nome': 'Mês', 'Precipitacao': 'Precipitação Total (mm)'},
                 text='Precipitacao')
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.subheader("Distribuição dos Períodos Secos")
    if not periodos_secos.empty:
        fig3 = px.histogram(periodos_secos, nbins=20,
                          labels={'value': 'Duração (dias)', 'count': 'Quantidade'},
                          title="Distribuição de Períodos Secos Consecutivos")
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Nenhum período seco identificado no período selecionado.")

# Informações adicionais
st.sidebar.markdown("---")
st.sidebar.markdown("**Definições:**")
st.sidebar.markdown("- **Dia Úmido:** Precipitação ≥ 1 mm")
st.sidebar.markdown("- **Dia Seco:** Precipitação < 1 mm")
st.sidebar.markdown("- **Período Seco:** Sequência consecutiva de dias secos")
