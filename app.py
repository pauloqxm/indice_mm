import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO

st.set_page_config(page_title="INT, DSL, HY-INT (norm.) e R95 — Anual, Sazonal e JFMAMJ", layout="wide")

# =====================================================
# Util: geração de arquivos para download
# =====================================================
def df_to_xls_bytes(df: pd.DataFrame, sheet_name: str = "Dados") -> bytes | None:
    """Tenta gerar .xls (xlwt). Retorna None se xlwt não estiver disponível."""
    try:
        import xlwt  # noqa: F401  # apenas para checar disponibilidade
        bio = BytesIO()
        with pd.ExcelWriter(bio, engine="xlwt") as writer:
            df.to_excel(writer, index=True, sheet_name=sheet_name)
        bio.seek(0)
        return bio.getvalue()
    except Exception:
        return None

def df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Dados") -> bytes:
    """Gera .xlsx usando xlsxwriter (fallback para openpyxl)."""
    bio = BytesIO()
    engine = None
    for eng in ("xlsxwriter", "openpyxl"):
        try:
            engine = eng
            with pd.ExcelWriter(bio, engine=eng) as writer:
                df.to_excel(writer, index=True, sheet_name=sheet_name)
            break
        except Exception:
            bio = BytesIO()
            continue
    if engine is None:
        # Último fallback: CSV dentro de xlsx writer indisponível (caso extremo)
        # Aqui devolvemos CSV em bytes com extensão .xlsx não sendo ideal.
        # Mas em ambientes normais um dos engines existe.
        csv_bytes = df.to_csv(index=True).encode("utf-8")
        return csv_bytes
    bio.seek(0)
    return bio.getvalue()

def offer_xls_download(df: pd.DataFrame, base_filename: str, sheet_name: str = "Dados"):
    """Mostra botão de download priorizando .xls; faz fallback para .xlsx se necessário."""
    xls_bytes = df_to_xls_bytes(df, sheet_name=sheet_name)
    if xls_bytes is not None:
        st.download_button(
            "⬇️ Baixar (XLS)",
            data=xls_bytes,
            file_name=f"{base_filename}.xls",
            mime="application/vnd.ms-excel"
        )
    else:
        xlsx_bytes = df_to_xlsx_bytes(df, sheet_name=sheet_name)
        st.download_button(
            "⬇️ Baixar (XLSX)",
            data=xlsx_bytes,
            file_name=f"{base_filename}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.info("Pacote 'xlwt' não disponível neste ambiente — gerado .xlsx em vez de .xls.")

# =====================================================
# Leitura / preparo
# =====================================================
@st.cache_data
def load_data_from_path(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    return _prepare_df(df)

def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara o DataFrame:
      - aceita 'date' (case-insensitive)
      - aceita 'precip' OU 'pr' (case-insensitive); se 'pr', renomeia para 'precip'
      - converte tipos e adiciona colunas auxiliares
    """
    df = df.copy()
    cols_lower = {c.lower(): c for c in df.columns}

    # date
    if "date" not in cols_lower:
        raise ValueError("O CSV precisa ter a coluna 'date'.")
    date_col = cols_lower["date"]
    if date_col != "date":
        df = df.rename(columns={date_col: "date"})

    # precip ou pr
    if "precip" in cols_lower:
        precip_col = cols_lower["precip"]
        if precip_col != "precip":
            df = df.rename(columns={precip_col: "precip"})
    elif "pr" in cols_lower:
        pr_col = cols_lower["pr"]
        df = df.rename(columns={pr_col: "precip"})
    else:
        raise ValueError("O CSV precisa ter a coluna 'precip' (ou 'pr').")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["precip"] = pd.to_numeric(df["precip"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    return df

st.title("🌧️ INT, DSL, HY-INT (norm.) e R95 — Anual, Sazonal (DJF/MAM/JJA/SON) e Semestre (JFMAMJ)")

uploaded = st.file_uploader("Envie o CSV (colunas: date, precip ou pr)", type=["csv"])
if uploaded is not None:
    raw = pd.read_csv(uploaded)
    df = _prepare_df(raw)
else:
    df = load_data_from_path("bacia_banabuiu.csv")

# =====================================================
# Parâmetros
# =====================================================
with st.sidebar:
    st.header("Parâmetros")
    limiar_umido = st.number_input("Limiar de dia úmido (mm)", value=1.0, step=0.1, min_value=0.0)
    anos = sorted(df["year"].unique().tolist())
    anos_sel = st.multiselect("Filtrar anos (opcional)", anos, default=anos)

    st.divider()
    st.subheader("Período-base do R95 (percentil 95)")
    if len(anos) >= 5:
        base_ini_default = anos[0]
        base_fim_default = anos[min(len(anos)-1, 29)]
    else:
        base_ini_default, base_fim_default = anos[0], anos[-1]
    base_ini, base_fim = st.select_slider(
        "Selecione o período-base (anos inclusive)",
        options=anos, value=(base_ini_default, base_fim_default)
    )

if anos_sel:
    df = df[df["year"].isin(anos_sel)].copy()

# =====================================================
# Marcadores de sazonalidade
# =====================================================
def season_label(month: int) -> str:
    if month in (12, 1, 2): return "DJF"
    if month in (3, 4, 5):  return "MAM"
    if month in (6, 7, 8):  return "JJA"
    return "SON"  # 9,10,11

def season_year(row) -> int:
    # Dezembro conta para o ano seguinte (rotulado pelo ano de JF)
    return row["year"] + 1 if row["month"] == 12 else row["year"]

df["season"] = df["month"].apply(season_label)
df["season_year"] = df.apply(season_year, axis=1)
df["is_JFMAMJ"] = df["month"].between(1, 6)  # semestre jan–jun
df["half_label"] = np.where(df["is_JFMAMJ"], "JFMAMJ", "JASOND")
df["half_year"] = df["year"]

# =====================================================
# Cálculos auxiliares
# =====================================================
def dry_spell_lengths(is_dry_bool: pd.Series) -> list[int]:
    """Comprimentos das sequências consecutivas de True (dias secos)."""
    runs, run = [], 0
    for v in is_dry_bool:
        if bool(v):
            run += 1
        else:
            if run > 0:
                runs.append(run)
                run = 0
    if run > 0:
        runs.append(run)
    return runs

def compute_r95_threshold(df_base: pd.DataFrame, wet_thresh: float) -> float:
    """Percentil 95 calculado no período-base apenas sobre dias úmidos."""
    wet = df_base.loc[df_base["precip"] >= wet_thresh, "precip"].dropna()
    if wet.empty:
        return np.nan
    return float(np.percentile(wet, 95))

def compute_block_metrics(g: pd.DataFrame, wet_thresh: float, r95_thresh: float) -> pd.Series:
    """Métricas do bloco (sem HY-INT). HY-INT será calculado depois das normalizações."""
    is_wet = g["precip"] >= wet_thresh
    is_dry = ~is_wet

    prcptot = g["precip"].sum(skipna=True)
    rainy = int(is_wet.sum())
    INT = prcptot / rainy if rainy > 0 else np.nan

    lengths = dry_spell_lengths(is_dry)
    DSL = float(np.mean(lengths)) if lengths else 0.0
    CDD = int(max(lengths)) if lengths else 0

    # R95 (usando threshold do período-base)
    if pd.notna(r95_thresh):
        mask_r95 = g["precip"] >= r95_thresh
        R95pTOT = g.loc[mask_r95, "precip"].sum(skipna=True)
        R95pDAYS = int(mask_r95.sum())
    else:
        R95pTOT, R95pDAYS = np.nan, 0

    return pd.Series(
        {
            "PRCPTOT_mm": prcptot,
            "Dias_chuvosos": rainy,
            "INT_mm_dia": INT,
            "DSL_dias": DSL,
            "CDD_dias": CDD,
            "Dias_secos": int(is_dry.sum()),
            "N_periodos_secos": len(lengths),
            "R95pTOT_mm": R95pTOT,
            "R95pDAYS": R95pDAYS
        }
    )

def add_normalized_cols(df_metrics: pd.DataFrame) -> pd.DataFrame:
    """Adiciona INT_norm, DSL_norm e HY_INT = INT_norm × DSL_norm ao bloco."""
    df_out = df_metrics.copy()
    mean_int = df_out["INT_mm_dia"].mean(skipna=True)
    mean_dsl = df_out["DSL_dias"].mean(skipna=True)

    df_out["INT_norm"] = df_out["INT_mm_dia"] / mean_int if mean_int and not np.isnan(mean_int) else np.nan
    df_out["DSL_norm"] = df_out["DSL_dias"] / mean_dsl if mean_dsl and not np.isnan(mean_dsl) else np.nan

    # HY-INT normalizado
    df_out["HY_INT"] = df_out["INT_norm"] * df_out["DSL_norm"]
    return df_out

# =====================================================
# Threshold R95 no período-base
# =====================================================
base_mask = (df["year"] >= base_ini) & (df["year"] <= base_fim)
r95_threshold = compute_r95_threshold(df.loc[base_mask], limiar_umido)

# =====================================================
# Cálculo por blocos
# =====================================================
annual = (
    df.groupby("year", as_index=True)
      .apply(lambda g: compute_block_metrics(g, limiar_umido, r95_threshold))
      .sort_index()
)
annual = add_normalized_cols(annual)

seasonal = (
    df.groupby(["season_year", "season"], as_index=True)
      .apply(lambda g: compute_block_metrics(g, limiar_umido, r95_threshold))
      .sort_index()
)
seasonal = add_normalized_cols(seasonal)

half = (
    df.groupby(["half_year", "half_label"], as_index=True)
      .apply(lambda g: compute_block_metrics(g, limiar_umido, r95_threshold))
      .sort_index()
)
half_jfmamj = half.xs("JFMAMJ", level="half_label", drop_level=False)
half_jfmamj = add_normalized_cols(half_jfmamj)

# =====================================================
# TABS: Anual | Sazonal | JFMAMJ
# =====================================================
tab1, tab2, tab3 = st.tabs(["Anual", "Sazonal (DJF/MAM/JJA/SON)", "Semestre JFMAMJ"])

# ---------------- Anual ----------------
with tab1:
    st.subheader("📅 Resultados anuais")
    cols = [
        "PRCPTOT_mm","Dias_chuvosos","INT_mm_dia","INT_norm",
        "DSL_dias","DSL_norm","HY_INT","CDD_dias","Dias_secos",
        "N_periodos_secos","R95pTOT_mm","R95pDAYS"
    ]
    df_annual_view = annual[cols].round({
        "PRCPTOT_mm":1, "INT_mm_dia":2, "INT_norm":3,
        "DSL_dias":2, "DSL_norm":3, "HY_INT":3, "R95pTOT_mm":1
    })
    st.dataframe(df_annual_view, use_container_width=True)

    if not annual.empty:
        ultimo_ano = int(annual.index.max())
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Último ano", f"{ultimo_ano}")
        c2.metric("INT (mm/dia)", f"{annual.loc[ultimo_ano, 'INT_mm_dia']:.2f}" if pd.notna(annual.loc[ultimo_ano, "INT_mm_dia"]) else "—")
        c3.metric("DSL (dias)", f"{annual.loc[ultimo_ano, 'DSL_dias']:.2f}")
        c4.metric("HY-INT (norm.)", f"{annual.loc[ultimo_ano, 'HY_INT']:.3f}" if pd.notna(annual.loc[ultimo_ano, "HY_INT"]) else "—")
        c5.metric("R95pTOT (mm)", f"{annual.loc[ultimo_ano, 'R95pTOT_mm']:.1f}" if pd.notna(annual.loc[ultimo_ano, 'R95pTOT_mm']) else "—")

    st.download_button(
        "⬇️ Baixar anual (CSV)",
        data=df_annual_view.to_csv(index=True).encode("utf-8"),
        file_name="int_dsl_hyintNorm_r95_anual.csv",
        mime="text/csv"
    )
    offer_xls_download(df_annual_view, base_filename="int_dsl_hyintNorm_r95_anual", sheet_name="Anual")

    st.markdown("### 📈 Gráficos (Anual)")
    # INT_norm e HY-INT (linhas)
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=annual.index, y=annual["INT_norm"], mode="lines+markers", name="INT_norm"))
    fig1.add_trace(go.Scatter(x=annual.index, y=annual["HY_INT"], mode="lines+markers", name="HY-INT (norm.)", yaxis="y2"))
    fig1.update_layout(
        title="INT_norm e HY-INT (norm.) por ano",
        xaxis_title="Ano",
        yaxis=dict(title="INT_norm"),
        yaxis2=dict(title="HY-INT (norm.)", overlaying="y", side="right"),
        hovermode="x unified"
    )
    st.plotly_chart(fig1, use_container_width=True)

    # DSL_norm e CDD (barras)
    fig2 = go.Figure(data=[
        go.Bar(x=annual.index, y=annual["DSL_norm"], name="DSL_norm"),
        go.Bar(x=annual.index, y=annual["CDD_dias"], name="CDD (máx dias secos)")
    ])
    fig2.update_layout(
        title="DSL_norm e CDD por ano",
        barmode="group",
        xaxis_title="Ano",
        hovermode="x unified"
    )
    st.plotly_chart(fig2, use_container_width=True)

    # R95pTOT e R95pDAYS
    fig3 = go.Figure()
    fig3.add_trace(go.Bar(x=annual.index, y=annual["R95pTOT_mm"], name="R95pTOT (mm)"))
    fig3.add_trace(go.Scatter(x=annual.index, y=annual["R95pDAYS"], mode="lines+markers", name="R95pDAYS", yaxis="y2"))
    fig3.update_layout(
        title=f"R95 (base {base_ini}-{base_fim}) — Total (mm) e Dias",
        xaxis_title="Ano",
        yaxis=dict(title="R95pTOT (mm)"),
        yaxis2=dict(title="R95pDAYS (dias)", overlaying="y", side="right"),
        hovermode="x unified"
    )
    st.plotly_chart(fig3, use_container_width=True)

# ---------------- Sazonal ----------------
with tab2:
    st.subheader("📆 Resultados sazonais — DJF, MAM, JJA, SON")
    saz = seasonal.reset_index().rename(columns={"season_year": "ano", "season": "temporada"}).set_index(["ano","temporada"])
    cols = [
        "PRCPTOT_mm","Dias_chuvosos","INT_mm_dia","INT_norm",
        "DSL_dias","DSL_norm","HY_INT","CDD_dias","Dias_secos",
        "N_periodos_secos","R95pTOT_mm","R95pDAYS"
    ]
    df_sazonal_view = saz[cols].round({
        "PRCPTOT_mm":1, "INT_mm_dia":2, "INT_norm":3,
        "DSL_dias":2, "DSL_norm":3, "HY_INT":3, "R95pTOT_mm":1
    })
    st.dataframe(df_sazonal_view, use_container_width=True)

    st.download_button(
        "⬇️ Baixar sazonal (CSV)",
        data=df_sazonal_view.to_csv(index=True).encode("utf-8"),
        file_name="int_dsl_hyintNorm_r95_sazonal.csv",
        mime="text/csv"
    )
    offer_xls_download(df_sazonal_view, base_filename="int_dsl_hyintNorm_r95_sazonal", sheet_name="Sazonal")

    st.markdown("### 📈 Gráficos (Sazonal)")
    for metric, title, ylab in [
        ("INT_norm", "INT_norm sazonal", "INT_norm"),
        ("HY_INT", "HY-INT (norm.) sazonal", "HY-INT (norm.)"),
        ("DSL_norm", "DSL_norm sazonal", "DSL_norm"),
        ("R95pTOT_mm", f"R95pTOT sazonal (base {base_ini}-{base_fim})", "R95pTOT (mm)")
    ]:
        piv = saz.reset_index().pivot(index="ano", columns="temporada", values=metric)
        fig = px.line(piv, markers=True, title=title)
        fig.update_layout(xaxis_title="Ano", yaxis_title=ylab, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

# ---------------- JFMAMJ ----------------
with tab3:
    st.subheader("🗓️ Semestre — JFMAMJ (Jan–Jun)")
    sem = half_jfmamj.reset_index().rename(columns={"half_year": "ano", "half_label": "semestre"}).set_index(["ano","semestre"])
    cols = [
        "PRCPTOT_mm","Dias_chuvosos","INT_mm_dia","INT_norm",
        "DSL_dias","DSL_norm","HY_INT","CDD_dias","Dias_secos",
        "N_periodos_secos","R95pTOT_mm","R95pDAYS"
    ]
    df_sem_view = sem[cols].round({
        "PRCPTOT_mm":1, "INT_mm_dia":2, "INT_norm":3,
        "DSL_dias":2, "DSL_norm":3, "HY_INT":3, "R95pTOT_mm":1
    })
    st.dataframe(df_sem_view, use_container_width=True)

    st.download_button(
        "⬇️ Baixar JFMAMJ (CSV)",
        data=df_sem_view.to_csv(index=True).encode("utf-8"),
        file_name="int_dsl_hyintNorm_r95_JFMAMJ.csv",
        mime="text/csv"
    )
    offer_xls_download(df_sem_view, base_filename="int_dsl_hyintNorm_r95_JFMAMJ", sheet_name="JFMAMJ")

# Rodapé
st.caption(
    f"Definições: Dia úmido = precip ≥ limiar ({limiar_umido:.1f} mm). "
    "INT_mm_dia = soma da precipitação / nº de dias chuvosos no bloco. "
    "DSL_dias = média das durações dos períodos secos no bloco. "
    "INT_norm = INT_mm_dia / média(INT_mm_dia) no bloco. "
    "DSL_norm = DSL_dias / média(DSL_dias) no bloco. "
    "HY-INT (norm.) = INT_norm × DSL_norm. "
    "CDD = maior sequência seca. "
    f"R95pTOT/R95pDAYS: limiar do percentil 95 calculado sobre dias úmidos no período-base {base_ini}-{base_fim}."
)
