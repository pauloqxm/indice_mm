# hy_int_app.py
import os
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

st.set_page_config(page_title="HY-INT | Dias Úmidos & Secos", layout="wide")

st.title("Índices Hidroclimáticos (HY-INT)")
st.markdown(
    "Calcule **Média da Precipitação em Dias Úmidos**, "
    "**Duração Média dos Períodos Secos** e **HY-INT** "
    "(adimensional, normalizado pela média da amostra). "
    "Inclui **gráficos** e leitura **robusta** do CSV."
)

# Parâmetros (podem ser ajustados no app)
wet_thr = st.number_input("Limiar de dias úmidos (mm) > ", value=1.0, step=0.1)
dry_thr = st.number_input("Limiar de dias secos (mm) ≤ ", value=1.0, step=0.1)


# ----------------- Utilidades -----------------
def parse_date_pt(s):
    """Tenta interpretar datas em formatos comuns no BR e ISO."""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(s), fmt)
        except Exception:
            continue
    return pd.NaT


def safe_read_csv(path: str) -> pd.DataFrame:
    """
    Leitura robusta do CSV:
      1) Tenta autodetectar separador (engine=python) em encodings comuns
      2) Tenta separador ';'
      3) Tenta separador ','
    """
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

    # 1) Autodetect sep
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc, sep=None, engine="python")
        except Exception:
            pass

    # 2) Força ';'
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc, sep=";")
        except Exception:
            pass

    # 3) Força ','
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc, sep=",")
        except Exception:
            pass

    raise RuntimeError("Falha ao ler o CSV. Verifique encoding e separador.")


def compute_segments(d: pd.DataFrame, dry_thr: float) -> pd.DataFrame:
    """
    Cria segmentos consecutivos de seco/úmido e calcula a duração de cada segmento.
    """
    is_dry = d["_pr"] <= dry_thr
    seg_id = (is_dry != is_dry.shift(1)).cumsum()
    seg = d.groupby(seg_id, as_index=False).agg(
        start=("_date", "first"),
        end=("_date", "last"),
        is_dry=("_pr", lambda s: (s <= dry_thr).all()),
        length=("_pr", "size"),
    )
    return seg


def compute_metrics(d: pd.DataFrame, wet_thr: float, dry_thr: float) -> pd.Series:
    """
    Calcula:
      - média de precipitação em dias úmidos (> wet_thr)
      - duração média dos períodos secos (consecutivos ≤ dry_thr)
      - HY-INT bruto (produto) e contagens auxiliares
    """
    d = d.sort_values("_date").copy()

    wet = d["_pr"] > wet_thr
    mean_wet_pr = d.loc[wet, "_pr"].mean() if wet.any() else 0.0

    seg = compute_segments(d, dry_thr)
    dry_spells = seg[seg["is_dry"]]
    mean_dry_spell = dry_spells["length"].mean() if not dry_spells.empty else 0.0

    raw_product = mean_wet_pr * mean_dry_spell  # base p/ HY-INT

    return pd.Series(
        {
            "media_precipitacao_dias_umidos": mean_wet_pr,
            "duracao_media_periodos_secos": mean_dry_spell,
            "hy_int_raw": raw_product,
            "n_dias": len(d),
            "n_dias_umidos": int(wet.sum()),
            "n_dias_secos": int((d["_pr"] <= dry_thr).sum()),
        }
    )


# ----------------- Leitura do CSV fixo -----------------
file_path = os.path.join(os.path.dirname(__file__), "indice_hy.csv")

if not os.path.exists(file_path):
    st.error(
        f"Arquivo {file_path} não encontrado. "
        "Coloque um arquivo 'indice_hy.csv' no mesmo diretório do app."
    )
    st.stop()

try:
    df = safe_read_csv(file_path)
except Exception as e:
    st.exception(e)
    st.stop()

# Normaliza nomes de colunas
df.columns = [str(c).strip() for c in df.columns]

# Tentativas de detecção automática das colunas (editáveis no app)
precip_candidates = [
    "precipitacao",
    "precipitação",
    "chuva",
    "pp",
    "prcp",
    "precisao",
    "precisão",
]
date_candidates = ["data", "date", "dia"]
group_candidates = [
    "bacia",
    "estacao",
    "estação",
    "reservatorio",
    "reservatório",
    "local",
    "id",
    "serie",
]

precip_cols = [c for c in df.columns if c.strip().lower() in precip_candidates]
date_cols = [c for c in df.columns if c.strip().lower() in date_candidates]
group_cols = [c for c in df.columns if c.strip().lower() in group_candidates]

precip_col = st.selectbox("Coluna de precipitação (mm)", precip_cols or df.columns.tolist())
date_col = st.selectbox("Coluna de data", date_cols or df.columns.tolist())
group_opt = ["(sem agrupamento)"] + (group_cols or [])
group_sel = st.selectbox("Coluna de agrupamento (opcional)", group_opt)

# Conversões
df["_date"] = df[date_col].apply(parse_date_pt)

# Trata números com vírgula decimal: "1.234,56" -> "1234.56"
if df[precip_col].dtype == object:
    pr_clean = (
        df[precip_col]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    df["_pr"] = pd.to_numeric(pr_clean, errors="coerce")
else:
    df["_pr"] = pd.to_numeric(df[precip_col], errors="coerce")

df["_pr"] = df["_pr"].fillna(0.0)

# Remove datas inválidas e ordena
df = df.dropna(subset=["_date"]).sort_values("_date").reset_index(drop=True)

# ----------------- Cálculo dos índices -----------------
if group_sel != "(sem agrupamento)":
    res = (
        df.groupby(group_sel, as_index=False)
        .apply(lambda g: compute_metrics(g, wet_thr, dry_thr))
        .reset_index(drop=True)
    )
    first_col = group_sel
else:
    res = compute_metrics(df, wet_thr, dry_thr).to_frame().T
    res.insert(0, "grupo", "serie_unica")
    first_col = "grupo"

# HY-INT adimensional: normaliza pelo valor médio da amostra
mean_raw = res["hy_int_raw"].replace(0, np.nan).mean()
res["hy_int"] = np.where(
    (~np.isnan(mean_raw)) & (mean_raw != 0), res["hy_int_raw"] / mean_raw, np.nan
)

show_cols = [
    first_col,
    "media_precipitacao_dias_umidos",
    "duracao_media_periodos_secos",
    "hy_int",
    "hy_int_raw",
    "n_dias",
    "n_dias_umidos",
    "n_dias_secos",
]
st.dataframe(res[show_cols])

st.download_button(
    "Baixar resultados (CSV)",
    res.to_csv(index=False).encode("utf-8"),
    "resultados_hy_int.csv",
    "text/csv",
)

# ----------------- Gráficos -----------------
st.markdown("### Gráficos")

# Recorte para gráficos temporais
if group_sel != "(sem agrupamento)":
    grupos_disponiveis = df[group_sel].dropna().unique().tolist()
    grupo_focus = st.selectbox(
        "Selecione um grupo para gráficos temporais", ["(todos)"] + grupos_disponiveis
    )
    if grupo_focus != "(todos)":
        dplot = df[df[group_sel] == grupo_focus].sort_values("_date").copy()
    else:
        dplot = df.sort_values("_date").copy()
else:
    dplot = df.sort_values("_date").copy()

# 1) Série temporal de precipitação diária
st.markdown("**Série temporal de precipitação diária (mm)**")
fig1 = plt.figure()
plt.plot(dplot["_date"], dplot["_pr"])
plt.xlabel("Data")
plt.ylabel("Precipitação (mm)")
plt.title("Precipitação diária")
st.pyplot(fig1)

# 2) Histograma das durações dos períodos secos
st.markdown("**Distribuição das durações dos períodos secos (dias)**")
seg_plot = compute_segments(dplot, dry_thr)
dry_lengths = seg_plot.loc[seg_plot["is_dry"], "length"]
if not dry_lengths.empty:
    fig2 = plt.figure()
    bins = list(range(1, int(dry_lengths.max()) + 2))
    plt.hist(dry_lengths, bins=bins, align="left", rwidth=0.8)
    plt.xlabel("Duração do período seco (dias)")
    plt.ylabel("Frequência")
    plt.title("Histograma das durações dos períodos secos")
    st.pyplot(fig2)
else:
    st.info("Não há períodos secos no recorte atual.")

# 3) Histograma da precipitação em dias úmidos
st.markdown("**Distribuição da precipitação em dias úmidos (mm)**")
wet_mask = dplot["_pr"] > wet_thr
wet_vals = dplot.loc[wet_mask, "_pr"]
if not wet_vals.empty:
    fig3 = plt.figure()
    plt.hist(wet_vals.dropna())
    plt.xlabel("Precipitação (mm)")
    plt.ylabel("Frequência")
    plt.title("Histograma da precipitação em dias úmidos")
    st.pyplot(fig3)
else:
    st.info("Não há dias úmidos no recorte atual.")

# 4) Barras comparando métricas por grupo (se houver grupos)
if group_sel != "(sem agrupamento)":
    st.markdown("**Comparação entre grupos**")
    met_sel = st.selectbox(
        "Métrica para comparar entre grupos",
        [
            "media_precipitacao_dias_umidos",
            "duracao_media_periodos_secos",
            "hy_int",
        ],
    )
    fig4 = plt.figure()
    x = res[first_col].astype(str).tolist()
    y = res[met_sel].astype(float).tolist()
    plt.bar(x, y)
    plt.xlabel("Grupo")
    plt.ylabel(met_sel)
    plt.title(f"Comparação por grupo: {met_sel}")
    plt.xticks(rotation=45, ha="right")
    st.pyplot(fig4)
