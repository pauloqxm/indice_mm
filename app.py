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

# Seleção de modo (único ou múltiplos anos)
modo_selecao = st.sidebar.radio(
    "Seleção de anos:",
    options=['Ano único', 'Múltiplos anos'],
    index=0
)

anos_disponiveis = sorted(df['Ano'].unique(), reverse=True)

if modo_selecao == 'Ano único':
    ano_selecionado = st.sidebar.selectbox("Selecione o ano", anos_disponiveis)
    anos_selecionados = [ano_selecionado]
else:
    anos_selecionados = st.sidebar.multiselect(
        "Selecione os anos", 
        options=anos_disponiveis,
        default=[anos_disponiveis[0]]
    )

# Filtro de mês (apenas quando um único ano estiver selecionado)
if len(anos_selecionados) == 1:
    meses_disponiveis = sorted(df[df['Ano'] == anos_selecionados[0]]['Mes'].unique())
    mes_selecionado = st.sidebar.selectbox(
        "Selecione o mês", 
        options=['Todos'] + meses_disponiveis,
        format_func=lambda x: 'Todos' if x == 'Todos' else datetime(1900, x, 1).strftime('%B')
    )
else:
    mes_selecionado = 'Todos'

# Aplicar filtros iniciais
df_filtrado_ano = df[df['Ano'].isin(anos_selecionados)]
if mes_selecionado != 'Todos':
    df_filtrado_ano = df_filtrado_ano[df_filtrado_ano['Mes'] == mes_selecionado]

# Contador interativo de registros
st.sidebar.markdown(f"**Registros carregados:** {len(df_filtrado_ano)} dia{'s' if len(df_filtrado_ano) != 1 else ''}")

# Seleção de período com slider de data (após filtros iniciais)
if len(df_filtrado_ano) > 0:
    data_min = df_filtrado_ano['data'].min().to_pydatetime()
    data_max = df_filtrado_ano['data'].max().to_pydatetime()
    data_range = st.sidebar.slider(
        "Selecione o período específico",
        min_value=data_min,
        max_value=data_max,
        value=(data_min, data_max),
        format="DD/MM/YYYY"
    )

    # Aplicar filtro de período
    df_filtrado = df_filtrado_ano[
        (df_filtrado_ano['data'] >= data_range[0]) & 
        (df_filtrado_ano['data'] <= data_range[1])
    ]
else:
    df_filtrado = pd.DataFrame()
    st.sidebar.warning("Nenhum dado disponível para os filtros selecionados")

# Atualizar contador após filtro de período
if len(df_filtrado_ano) > 0:
    st.sidebar.markdown(f"**Período selecionado:** {len(df_filtrado)} dia{'s' if len(df_filtrado) != 1 else ''}")

# Calcular períodos secos (apenas para o período filtrado)
if len(df_filtrado) > 0:
    df_filtrado['Seco_Grupo'] = (df_filtrado['Dia Seco'] != df_filtrado['Dia Seco'].shift()).cumsum()
    periodos_secos = df_filtrado[df_filtrado['Dia Seco']].groupby('Seco_Grupo').size()
    qtd_periodos_secos = len(periodos_secos)
else:
    qtd_periodos_secos = 0

# Layout principal
if len(anos_selecionados) == 1:
    titulo = f"Análise de Precipitação - {anos_selecionados[0]}"
    if mes_selecionado != 'Todos':
        nome_mes = datetime(1900, mes_selecionado, 1).strftime('%B')
        titulo += f" - {nome_mes}"
else:
    anos_str = ", ".join(map(str, sorted(anos_selecionados)))
    titulo = f"Análise de Precipitação - Anos: {anos_str}"
    
st.title(titulo)

# Métricas
if len(df_filtrado) > 0:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Precipitação Total (mm)", f"{round(df_filtrado['Precipitacao'].sum(), 1)} mm")
    col2.metric("Dias Úmidos (≥1 mm)", f"{int(df_filtrado['Dia Úmido'].sum())} dias")
    col3.metric("Dias Secos (<1 mm)", f"{int(df_filtrado['Dia Seco'].sum())} dias")
    col4.metric("Períodos Secos", f"{qtd_periodos_secos} períodos")
else:
    st.warning("Nenhum dado disponível para os filtros selecionados")

# Gráficos
if len(df_filtrado) > 0:
    tab1, tab2, tab3 = st.tabs(["Precipitação Diária", "Análise Mensal", "Períodos Secos"])

    with tab1:
        st.subheader("Precipitação Diária")
        fig1 = px.bar(df_filtrado, x='data', y='Precipitacao',
                     labels={'data': 'Data', 'Precipitacao': 'Precipitação (mm)'},
                     color='Precipitacao',
                     color_continuous_scale='Blues')
        
        # Adicionar linha de média se múltiplos anos
        if len(anos_selecionados) > 1:
            media = df_filtrado.groupby(df_filtrado['data'].dt.dayofyear)['Precipitacao'].mean().reset_index()
            fig1.add_scatter(x=df_filtrado['data'].unique(), y=media['Precipitacao'],
                           mode='lines', name='Média', line=dict(color='red', width=2))
        
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
        
        # Adicionar comparação se múltiplos anos
        if len(anos_selecionados) > 1:
            fig2.update_layout(barmode='group')
        
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
