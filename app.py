import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="HY-INT e DSL", layout="wide")

# -------------------------
# Leitura e preparo dos dados
# -------------------------
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "date" not in df.columns or "precip" not in df.columns:
        raise ValueError("A planilha precisa ter as colunas 'date' e 'precip'.")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    # Garante tipo numérico para precip
    df["precip"] = pd.to_numeric(df["precip"], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)

df = load_data("bacia_banabuiu.csv")
df["year"] = df["date"].dt.year

st.title("🌧️ HY-INT e DSL (Duration of Dry Days)")
st.caption("Entrada: colunas 'date' (diária) e 'precip' (mm). Dia úmido: precip ≥ 1 mm.")

# -------------------------
# Parâmetros
# -------------------------
with st.sidebar:
    st.header("Parâmetros")
    limiar_umido = st.number_input("Limiar de dia úmido (mm)", value=1.0, step=0.1)
    # Sugestão de baseline com 30 anos mais completos disponíveis
    anos = sorted(df["year"].dropna().unique())
    if len(anos) >= 5:
        ano_ini = int(anos[0])
        ano_fim = int(anos[min(len(anos)-1, 29)])  # tenta ~30 anos
    else:
        ano_ini, ano_fim = (int(anos[0]), int(anos[-1]))
    base_ini, base_fim = st.select_slider(
        "Período de referência (baseline) para normalização",
        options=anos,
        value=(ano_ini, ano_fim)
    )

# Flags de úmido/seco
df["is_wet"] = df["precip"] >= limiar_umido
df["is_dry"] = ~df["is_wet"]

# -------------------------
# Funções auxiliares
# -------------------------
def compute_dry_spells_lengths(s: pd.Series) -> list[int]:
    """
    Recebe uma série booleana 'is_dry' (ordenada no tempo) e retorna
    a lista dos comprimentos das sequências consecutivas de True.
    """
    lengths = []
    run = 0
    for v in s:
        if bool(v):
            run += 1
        else:
            if run > 0:
                lengths.append(run)
                run = 0
    if run > 0:
        lengths.append(run)
    return lengths

def yearly_metrics(group: pd.DataFrame) -> pd.Series:
    # PRCPTOT
    prcptot = group["precip"].sum(skipna=True)
    # Dias úmidos
    du = int(group["is_wet"].sum())
    # SDII
    sdii = prcptot / du if du > 0 else np.nan
    # Dry spells
    lengths = compute_dry_spells_lengths(group["is_dry"])
    cdd = int(max(lengths)) if lengths else 0
    dsl_medio = float(np.mean(lengths)) if lengths else 0.0
    # Dias secos (contagem simples)
    dias_secos = int(group["is_dry"].sum())
    return pd.Series(
        {
            "PRCPTOT": prcptot,
            "DU": du,
            "SDII": sdii,
            "CDD": cdd,                # máximo de dias secos consecutivos (ETCCDI)
            "DSL_medio": dsl_medio,    # média da duração de veranicos no ano
            "DryDays": dias_secos
        }
    )

# -------------------------
# Métricas anuais
# -------------------------
annual = df.groupby("year", as_index=True).apply(yearly_metrics)

# -------------------------
# Baseline e HY-INT
# -------------------------
baseline = annual.loc[(annual.index >= base_ini) & (annual.index <= base_fim)].copy()

mean_pr = baseline["PRCPTOT"].mean(skipna=True)
mean_sdii = baseline["SDII"].mean(skipna=True)

annual["PR_norm"] = annual["PRCPTOT"] / mean_pr if mean_pr and not np.isnan(mean_pr) else np.nan
annual["SDII_norm"] = annual["SDII"] / mean_sdii if mean_sdii and not np.isnan(mean_sdii) else np.nan
annual["HY_INT"] = annual["PR_norm"] * annual["SDII_norm"]

# -------------------------
# Saída
# -------------------------
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Baseline PRCPTOT (mm/ano)", f"{mean_pr:,.1f}" if pd.notna(mean_pr) else "—")
col2.metric("Baseline SDII (mm/dia úmido)", f"{mean_sdii:,.2f}" if pd.notna(mean_sdii) else "—")
col3.metric("Último ano HY-INT", f"{annual['HY_INT'].dropna().iloc[-1]:.3f}" if annual["HY_INT"].notna().any() else "—")
col4.metric("Último ano DSL médio (dias)", f"{annual['DSL_medio'].iloc[-1]:.1f}" if len(annual) else "—")
col5.metric("Último ano CDD (dias)", f"{annual['CDD'].iloc[-1]:.0f}" if len(annual) else "—")

st.subheader("📅 Tabela anual — HY-INT e Dry Spells")
show_cols = ["PRCPTOT","DU","SDII","PR_norm","SDII_norm","HY_INT","DryDays","DSL_medio","CDD"]
st.dataframe(
    annual[show_cols].round({"PRCPTOT":1,"SDII":2,"PR_norm":3,"SDII_norm":3,"HY_INT":3,"DSL_medio":2}),
    use_container_width=True
)

st.caption(
    "Definições: PRCPTOT = precipitação total anual; DU = dias úmidos (precip ≥ limiar); "
    "SDII = PRCPTOT/DU; HY-INT = (PRCPTOT/⟨PRCPTOT⟩_base)×(SDII/⟨SDII⟩_base); "
    "DryDays = nº de dias secos; DSL_medio = média do tamanho dos veranicos no ano; "
    "CDD = maior sequência de dias secos no ano."
)
