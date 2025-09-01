import os
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="HY-INT | Dias Úmidos & Secos", layout="wide")

st.title("Índices Hidroclimáticos (HY-INT)")
st.markdown(
    "Calcule **Média da Precipitação em Dias Úmidos**, "
    "**Duração Média dos Períodos Secos** e **HY-INT** "
    "(adimensional, normalizado pela média da amostra). "
    "Agora com **gráficos interativos em Plotly**, **filtro por ano**, e **tabela anual** com as colunas solicitadas."
)

# Parâmetros ajustáveis
wet_thr = st.number_input("Limiar de dias úmidos (mm) > ", value=1.0, step=0.1)
dry_thr = st.number_input("Limiar de dias secos (mm) ≤ ", value=1.0, step=0.1)


# ----------------- Funções utilitárias -----------------
def parse_date_pt(s):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(s), fmt)
        except Exception:
            continue
    return pd.NaT


def safe_read_csv(path: str) -> pd.DataFrame:
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc, sep=None, engine="python")
        except Exception:
            pass
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc, sep=";")
        except Exception:
            pass
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc, sep=",")
        except Exception:
            pass
    raise RuntimeError("Falha ao ler o CSV. Verifique encoding/separador.")


def compute_segments(d: pd.DataFrame, dry_thr: float) -> pd.DataFrame:
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
    d = d.sort_values("_date").copy()
    wet = d["_pr"] > wet_thr
    mean_wet_pr = d.loc[wet, "_pr"].mean() if wet.any() else 0.0
    seg = compute_segments(d, dry_thr)
    dry_spells = seg[seg["is_dry"]]
    mean_dry_spell = dry_spells["length"].mean() if not dry_spells.empty else 0.0
    raw_product = mean_wet_pr * mean_dry_spell
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


def count_dry_spells(d: pd.DataFrame, dry_thr: float) -> int:
    is_dry = d["_pr"] <= dry_thr
    start_spells = is_dry & (~is_dry.shift(1).fillna(False))
    return int(start_spells.sum())


def build_yearly_table(df: pd.DataFrame, wet_thr: float, dry_thr: float, group_col: str | None):
    df = df.copy()
    df["ano"] = df["_date"].dt.year

    def _agg(sub: pd.DataFrame):
        pr_sum = float(sub["_pr"].sum())
        wet_days = int((sub["_pr"] > wet_thr).sum())
        dry_days = int((sub["_pr"] <= dry_thr).sum())
        n_dry_spells = int(count_dry_spells(sub, dry_thr))
        item6 = pr_sum / wet_days if wet_days > 0 else np.nan
        dsl = dry_days / n_dry_spells if n_dry_spells > 0 else np.nan
        return pd.Series({
            "Ano de referência": int(sub["ano"].iloc[0]),
            "Precipitação acumulada (mm)": round(pr_sum, 3),
            "Quantidade de dias úmidos": wet_days,
            "Quantidade de dias secos": dry_days,
            "Intervalos de dias secos consecutivos": n_dry_spells,
            "Item 2 / Item 3 (mm/dia)": round(item6, 3) if not np.isnan(item6) else np.nan,
            "DSL": round(dsl, 3) if not np.isnan(dsl) else np.nan,
        })

    if group_col:
        grp_cols = [group_col, "ano"]
        res = (
            df.groupby(grp_cols, as_index=False)
              .apply(lambda g: _agg(g))
              .reset_index(drop=True)
        )
        res = res[[group_col, "Ano de referência", "Precipitação acumulada (mm)",
                   "Quantidade de dias úmidos", "Quantidade de dias secos",
                   "Intervalos de dias secos consecutivos",
                   "Item 2 / Item 3 (mm/dia)", "DSL"]]
        res = res.sort_values([group_col, "Ano de referência"]).reset_index(drop=True)
    else:
        res = (
            df.groupby("ano", as_index=False)
              .apply(lambda g: _agg(g))
              .reset_index(drop=True)
        )
        res = res[["Ano de referência", "Precipitação acumulada (mm)",
                   "Quantidade de dias úmidos", "Quantidade de dias secos",
                   "Intervalos de dias secos consecutivos",
                   "Item 2 / Item 3 (mm/dia)", "DSL"]]
        res = res.sort_values(["Ano de referência"]).reset_index(drop=True)

    return res


# ----------------- Leitura do CSV fixo -----------------
file_path = os.path.join(os.path.dirname(__file__), "indice_hy.csv")

if not os.path.exists(file_path):
    st.error(
        f"Arquivo {file_path} não encontrado. "
        "Coloque um arquivo 'indice_hy.csv' no mesmo diretório do app."
    )
    st.stop()

df = safe_read_csv(file_path)
df.columns = [str(c).strip() for c in df.columns]

precip_candidates = ["precipitacao", "precipitação", "chuva", "pp", "prcp", "precisao", "precisão"]
date_candidates = ["data", "date", "dia"]
group_candidates = ["bacia", "estacao", "estação", "reservatorio", "reservatório", "local", "id", "serie"]

precip_cols = [c for c in df.columns if c.strip().lower() in precip_candidates]
date_cols = [c for c in df.columns if c.strip().lower() in date_candidates]
group_cols = [c for c in df.columns if c.strip().lower() in group_candidates]

precip_col = st.selectbox("Coluna de precipitação (mm)", precip_cols or df.columns.tolist())
date_col = st.selectbox("Coluna de data", date_cols or df.columns.tolist())
group_opt = ["(sem agrupamento)"] + (group_cols or [])
group_sel = st.selectbox("Coluna de agrupamento (opcional)", group_opt)

df["_date"] = df[date_col].apply(parse_date_pt)
if df[precip_col].dtype == object:
    pr_clean = df[precip_col].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    df["_pr"] = pd.to_numeric(pr_clean, errors="coerce")
else:
    df["_pr"] = pd.to_numeric(df[precip_col], errors="coerce")
df["_pr"] = df["_pr"].fillna(0.0)
df = df.dropna(subset=["_date"]).sort_values("_date").reset_index(drop=True)

# Filtro por intervalo de anos
df["ano"] = df["_date"].dt.year
min_year = int(df["ano"].min())
max_year = int(df["ano"].max())
if min_year > max_year:
    min_year, max_year = max_year, min_year
if min_year == max_year:
    year_range = (min_year, max_year)
    st.info(f"Dados disponíveis apenas para o ano {min_year}.")
else:
    year_range = st.slider("Selecione o intervalo de anos", min_value=min_year, max_value=max_year, value=(min_year, max_year), step=1)
df = df[(df["ano"] >= year_range[0]) & (df["ano"] <= year_range[1])].copy()
st.caption(f"Período filtrado: {year_range[0]}–{year_range[1]}")

# Índices globais (mantidos)
if group_sel != "(sem agrupamento)":
    res = df.groupby(group_sel, as_index=False).apply(lambda g: compute_metrics(g, wet_thr, dry_thr)).reset_index(drop=True)
    first_col = group_sel
else:
    res = compute_metrics(df, wet_thr, dry_thr).to_frame().T
    res.insert(0, "grupo", "serie_unica")
    first_col = "grupo"

mean_raw = res["hy_int_raw"].replace(0, np.nan).mean()
res["hy_int"] = np.where((~np.isnan(mean_raw)) & (mean_raw != 0), res["hy_int_raw"] / mean_raw, np.nan)

# Tabela anual solicitada
st.markdown("### Tabela anual")
group_col_for_table = None if group_sel == "(sem agrupamento)" else group_sel
tabela_anual = build_yearly_table(df, wet_thr, dry_thr, group_col_for_table)
st.dataframe(tabela_anual)

st.download_button("Baixar Tabela Anual (CSV)", tabela_anual.to_csv(index=False).encode("utf-8"), "tabela_anual_hy_int.csv", "text/csv")

# Gráficos
st.markdown("### Gráficos")
if group_sel != "(sem agrupamento)":
    grupos_disponiveis = df[group_sel].dropna().unique().tolist()
    grupo_focus = st.selectbox("Selecione um grupo para gráficos temporais", ["(todos)"] + grupos_disponiveis)
    if grupo_focus != "(todos)":
        dplot = df[df[group_sel] == grupo_focus].sort_values("_date").copy()
    else:
        dplot = df.sort_values("_date").copy()
else:
    dplot = df.sort_values("_date").copy()

fig1 = go.Figure()
fig1.add_trace(go.Scatter(x=dplot["_date"], y=dplot["_pr"], mode="lines", name="Precipitação"))
fig1.update_layout(title="Precipitação diária", xaxis_title="Data", yaxis_title="mm")
st.plotly_chart(fig1, use_container_width=True)

seg_plot = compute_segments(dplot, dry_thr)
dry_lengths = seg_plot.loc[seg_plot["is_dry"], "length"]
if not dry_lengths.empty:
    fig2 = go.Figure()
    fig2.add_trace(go.Histogram(x=dry_lengths, nbinsx=int(dry_lengths.max())))
    fig2.update_layout(title="Distribuição das durações dos períodos secos", xaxis_title="Duração (dias)", yaxis_title="Frequência")
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("Não há períodos secos no recorte atual.")

wet_mask = dplot["_pr"] > wet_thr
wet_vals = dplot.loc[wet_mask, "_pr"]
if not wet_vals.empty:
    fig3 = go.Figure()
    fig3.add_trace(go.Histogram(x=wet_vals))
    fig3.update_layout(title="Distribuição da precipitação em dias úmidos", xaxis_title="Precipitação (mm)", yaxis_title="Frequência")
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("Não há dias úmidos no recorte atual.")

if group_sel != "(sem agrupamento)":
    met_sel = st.selectbox("Métrica para comparar entre grupos", ["media_precipitacao_dias_umidos", "duracao_media_periodos_secos", "hy_int"])
    fig4 = go.Figure()
    fig4.add_trace(go.Bar(x=res[first_col].astype(str), y=res[met_sel]))
    fig4.update_layout(title=f"Comparação entre grupos: {met_sel}", xaxis_title="Grupo", yaxis_title=met_sel)
    st.plotly_chart(fig4, use_container_width=True)
