
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Dashboard de Precipitação", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_csv("indice_mm.csv", sep=";", decimal=",")
    
    if 'data' in df.columns:
        df['data'] = pd.to_datetime(df['data'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['data'])
        df = df.sort_values('data')
    else:
        st.error("Coluna 'data' não encontrada no arquivo.")
        st.stop()

    precip_col = df.columns[1]
    df['Precipitacao'] = pd.to_numeric(df[precip_col].astype(str).str.replace(',', '.'), errors='coerce')
    df = df.dropna(subset=['Precipitacao'])

    df['Ano'] = df['data'].dt.year
    df['Mes'] = df['data'].dt.month
    df['Mes_Nome'] = df['data'].dt.month_name()
    df['Dia_do_Ano'] = df['data'].dt.dayofyear
    df['Dia Úmido'] = df['Precipitacao'] >= 1
    df['Dia Seco'] = df['Precipitacao'] < 1

    return df

df = load_data()

st.sidebar.header("Filtros Básicos")

mes_selecionado = st.sidebar.selectbox(
    "Selecione o mês", 
    options=['Todos'] + sorted(df['Mes'].unique()),
    format_func=lambda x: 'Todos' if x == 'Todos' else datetime(1900, x, 1).strftime('%B')
)

anos_disponiveis = sorted(df['Ano'].unique())
ano_min, ano_max = st.slider(
    "Selecione o intervalo de anos:",
    min_value=min(anos_disponiveis),
    max_value=max(anos_disponiveis),
    value=(min(anos_disponiveis), max(anos_disponiveis)),
    step=1
)

df_filtrado_ano = df[(df['Ano'] >= ano_min) & (df['Ano'] <= ano_max)]
if mes_selecionado != 'Todos':
    df_filtrado_ano = df_filtrado_ano[df_filtrado_ano['Mes'] == mes_selecionado]

st.subheader("Refinar Período")
if len(df_filtrado_ano) > 0:
    data_min = df_filtrado_ano['data'].min().to_pydatetime()
    data_max = df_filtrado_ano['data'].max().to_pydatetime()
    data_range = st.slider(
        "Selecione o período específico:",
        min_value=data_min,
        max_value=data_max,
        value=(data_min, data_max),
        format="DD/MM/YYYY"
    )

    df_filtrado = df_filtrado_ano[
        (df_filtrado_ano['data'] >= data_range[0]) & 
        (df_filtrado_ano['data'] <= data_range[1])
    ]
else:
    df_filtrado = pd.DataFrame()
    st.warning("Nenhum dado disponível para os filtros selecionados")

if len(df_filtrado) > 0:
    df_filtrado['Seco_Grupo'] = (df_filtrado['Dia Seco'] != df_filtrado['Dia Seco'].shift()).cumsum()
    periodos_secos = df_filtrado[df_filtrado['Dia Seco']].groupby('Seco_Grupo').size()
    qtd_periodos_secos = len(periodos_secos)
else:
    qtd_periodos_secos = 0

titulo = f"Análise de Precipitação ({ano_min}-{ano_max})"
if mes_selecionado != 'Todos':
    nome_mes = datetime(1900, mes_selecionado, 1).strftime('%B')
    titulo += f" - {nome_mes}"
st.title(titulo)

if len(df_filtrado) > 0:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Precipitação Total (mm)", f"{round(df_filtrado['Precipitacao'].sum(), 1)} mm")
    col2.metric("Dias Úmidos (≥1 mm)", f"{int(df_filtrado['Dia Úmido'].sum())} dias")
    col3.metric("Dias Secos (<1 mm)", f"{int(df_filtrado['Dia Seco'].sum())} dias")
    col4.metric("Períodos Secos", f"{qtd_periodos_secos} períodos")
else:
    st.warning("Nenhum dado disponível para os filtros selecionados")

if len(df_filtrado) > 0:
    tab1, tab2, tab3, tab4 = st.tabs([
        "Precipitação Diária", 
        "Análise Mensal", 
        "Períodos Secos", 
        "Média Anual por Dia"
    ])

    with tab1:
        st.subheader("Precipitação Diária")
        fig1 = px.bar(df_filtrado, x='data', y='Precipitacao',
                     labels={'data': 'Data', 'Precipitacao': 'Precipitação (mm)'},
                     color='Precipitacao',
                     color_continuous_scale='Blues')
        st.plotly_chart(fig1, use_container_width=True)

    with tab2:
        st.subheader("Análise Mensal")
        mensal = df_filtrado.groupby(['Ano', 'Mes', 'Mes_Nome']).agg({
            'Precipitacao': 'sum',
            'Dia Úmido': 'sum',
            'Dia Seco': 'sum'
        }).reset_index().sort_values(['Ano', 'Mes'])

        fig2 = px.bar(mensal, x='Mes_Nome', y='Precipitacao',
                     labels={'Mes_Nome': 'Mês', 'Precipitacao': 'Precipitação Total (mm)'},
                     color='Ano',
                     barmode='group',
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

    with tab4:
        st.subheader("Média de Precipitação por Dia do Ano")
        media_diaria = df_filtrado.copy()
        media_diaria['Dia_Ano'] = media_diaria['data'].dt.dayofyear
        media_diaria = media_diaria.groupby('Dia_Ano')['Precipitacao'].mean().reset_index()
        fig4 = px.line(media_diaria, x='Dia_Ano', y='Precipitacao',
                       labels={'Dia_Ano': 'Dia do Ano', 'Precipitacao': 'Precipitação Média (mm)'},
                       title="Média Anual de Precipitação por Dia do Ano")
        st.plotly_chart(fig4, use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown("**Definições:**")
st.sidebar.markdown("- **Dia Úmido:** Precipitação ≥ 1 mm")
st.sidebar.markdown("- **Dia Seco:** Precipitação < 1 mm")
st.sidebar.markdown("- **Período Seco:** Sequência consecutiva de dias secos")
