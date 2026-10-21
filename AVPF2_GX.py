# -*- coding: utf-8 -*-
"""
AVPF-2 | Analítica de datos aplicada a Ingeniería Civil (Estructuras y Materiales)
Concreto permeable: compromiso resistencia-permeabilidad (laboratorio) y
colmatación en el tiempo (campo, ensayos ASTM C1701 con fecha real).

Fuentes:
  A) Laboratorio: 48 mezclas (granito/dolerita). Huang et al. (2020), Construction and
     Building Materials, Tabla 6 (PII S0950061820327641). Sin fecha de ensayo.
  B) Campo: US EPA ORD, doi.org/10.23719/1520736 (OConnor y Borst, 2022).
     Ensayos fechados 2009-2012 (PICP original) y 2017-2020 (PICP nuevo).

Uso:  python AVPF2_GX.py   ->  outputs/ + Dashboard_AVPF2_GX.html
Requiere: pandas, numpy, scikit-learn, matplotlib, openpyxl (plotly es opcional).
"""
import json, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import cross_val_score, KFold
from sklearn.metrics import r2_score, mean_squared_error

GRUPO = "GX"   # <- reemplazar por su número de grupo (ej. "G3")
BASE = os.path.dirname(os.path.abspath(__file__))
DATA, OUT = os.path.join(BASE, "data"), os.path.join(BASE, "outputs")
os.makedirs(OUT, exist_ok=True)
R = {}  # diccionario de resultados (se exporta a outputs/resultados.json)


# ---------------------------------------------------------------- 1. LIMPIEZA
def cargar_laboratorio():
    """Carga y depura las 48 mezclas de laboratorio."""
    df = pd.read_csv(os.path.join(DATA, "concreto_permeable_laboratorio.csv"))
    n0 = len(df)
    num = ["Porosidad_pct", "Relacion_agua_cemento", "Resistencia_compresion_MPa", "Permeabilidad_mm_s"]
    for c in ("Agregado", "Gradacion"):
        df[c] = df[c].astype(str).str.strip()                    # corrige espacios
    df[num] = df[num].apply(pd.to_numeric, errors="coerce")      # fuerza numérico
    nulos = int(df.isna().sum().sum())
    df = df.dropna(subset=num).drop_duplicates().reset_index(drop=True)
    assert (df[num] > 0).all().all(), "valores no positivos"      # consistencia física
    R["lab_limpieza"] = {"registros_inicial": n0, "nulos": nulos, "registros_final": len(df)}
    return df


def cargar_epa():
    """Carga las dos hojas fechadas de la EPA y las unifica (mm/h)."""
    f = os.path.join(DATA, "EPA_infiltracion_PICP_Edison.xlsx")
    orig = pd.read_excel(f, sheet_name="PICP for Multi-regression data", header=3, usecols="C:L")
    nuevo = pd.read_excel(f, sheet_name="New PICP Data", header=3, usecols="C:M")
    orig["Pavimento"], nuevo["Pavimento"] = "PICP original (2009-2012)", "PICP nuevo (2017-2020)"
    df = pd.concat([orig, nuevo], ignore_index=True)
    df.columns = [c.strip() for c in df.columns]                 # 'Days ' -> 'Days'
    n0 = len(df)
    df["Fecha"] = pd.to_datetime(df["Date"], errors="coerce")    # 'Average' -> NaT
    filas_resumen = int(df["Fecha"].isna().sum())                # fila de promedios de la fuente
    df = df.dropna(subset=["Fecha", "Infiltration (mm/h)", "Days"])
    df = df.drop_duplicates().reset_index(drop=True)
    df = df.rename(columns={"Infiltration (mm/h)": "Infiltracion_mm_h", "Days": "Dias",
                            "Curb Distance (m)": "Dist_bordillo_m", "Edge Distance (m)": "Dist_borde_m",
                            "Half Lot": "Mitad"})
    df["Fecha"] = df["Fecha"].dt.normalize()
    df["Infiltracion_mm_s"] = df["Infiltracion_mm_h"] / 3600.0   # mm/h -> mm/s (comparar con lab)
    df["Mes_vida"] = np.floor(df["Dias"] / 30.4).astype(int)     # edad en meses
    R["epa_limpieza"] = {"registros_inicial": n0, "filas_resumen_eliminadas": filas_resumen,
                         "registros_final": len(df), "campanas_fecha": int(df["Fecha"].nunique())}
    return df


def outliers_iqr(s):
    q1, q3 = s.quantile([.25, .75]); i = q3 - q1
    return (s < q1 - 1.5 * i) | (s > q3 + 1.5 * i)


# ------------------------------------------------- 2. EDA, KPIs Y MODELOS
def analizar(lab, epa):
    num = ["Porosidad_pct", "Relacion_agua_cemento", "Resistencia_compresion_MPa", "Permeabilidad_mm_s"]
    desc = lab[num].describe().T
    desc["CV_pct"] = desc["std"] / desc["mean"] * 100
    corr = lab[num].corr()
    R["lab_desc"] = desc.round(3).to_dict("index")
    R["lab_corr"] = corr.round(3).to_dict()
    R["lab_por_ac"] = lab.groupby("Relacion_agua_cemento")[num[2:]].mean().round(2).to_dict("index")
    R["lab_por_poro"] = lab.groupby("Porosidad_pct")[num[2:]].mean().round(2).to_dict("index")
    g, d = lab[(lab.Agregado == "Granite") & (lab.Gradacion == "5-10 mm")], lab[lab.Agregado == "Dolerite"]
    R["comp_agregado_5_10"] = {"granito_MPa": round(g.Resistencia_compresion_MPa.mean(), 2),
                               "dolerita_MPa": round(d.Resistencia_compresion_MPa.mean(), 2)}
    # anomalías laboratorio (IQR 1.5)
    ol = lab[outliers_iqr(lab.Permeabilidad_mm_s) | outliers_iqr(lab.Resistencia_compresion_MPa)]
    R["lab_anomalias"] = ol.to_dict("records")

    # --- campo: estadísticos por pavimento y por año, anomalías, pérdida
    epa["Anio"] = epa["Fecha"].dt.year
    R["epa_desc"] = epa.groupby("Pavimento")["Infiltracion_mm_h"].describe().round(0).to_dict("index")
    anual = epa.groupby(["Pavimento", "Anio"])["Infiltracion_mm_h"].agg(["count", "mean"]).round(0)
    R["epa_anual"] = {f"{p}|{a}": v for (p, a), v in anual.to_dict("index").items()}
    epa["Anomalia"] = epa.groupby("Pavimento")["Infiltracion_mm_h"].transform(lambda s: outliers_iqr(s))
    R["epa_anomalias"] = epa.groupby("Pavimento")["Anomalia"].sum().astype(int).to_dict()
    perd = {}
    for p, gp in epa.groupby("Pavimento"):
        m = gp.groupby("Anio")["Infiltracion_mm_h"].mean()
        perd[p] = round((1 - m.iloc[-1] / m.iloc[0]) * 100, 1)
    R["perdida_infiltracion_pct"] = perd
    nuevo = epa[epa.Pavimento.str.startswith("PICP nuevo")]
    R["pct_colmatacion_nuevo"] = round(nuevo["Assessment"].isin(["Clogging", "Clogged"]).mean() * 100, 1)
    R["epa_corr_nuevo"] = nuevo[["Infiltracion_mm_h", "Dias", "Dist_bordillo_m", "Dist_borde_m"]].corr().round(3).to_dict()

    # --- KPIs
    ok = ((lab.Resistencia_compresion_MPa >= 20) & (lab.Permeabilidad_mm_s >= 1.0))
    R["kpis"] = [
        ("Resistencia media (lab)", f"{lab.Resistencia_compresion_MPa.mean():.1f}", "MPa"),
        ("Permeabilidad media (lab)", f"{lab.Permeabilidad_mm_s.mean():.2f}", "mm/s"),
        ("Mezclas con f'c ≥ 20 MPa y k ≥ 1.0 mm/s*", f"{ok.mean() * 100:.0f}", f"% ({int(ok.sum())} de {len(lab)})"),
        ("Correlación f'c – k (r)", f"{corr.loc[num[2], num[3]]:.2f}", "Pearson"),
        ("Ensayos de campo con fecha", f"{len(epa)}", f"{epa.Fecha.nunique()} fechas, {epa.Fecha.min():%Y}–{epa.Fecha.max():%Y}"),
        ("Pérdida de infiltración PICP nuevo", f"{perd['PICP nuevo (2017-2020)']:.0f}", "% entre 2017 y 2020"),
        ("Pérdida de infiltración PICP original", f"{perd['PICP original (2009-2012)']:.0f}", "% entre 2009/10 y 2012"),
        ("Ensayos con colmatación (PICP nuevo)", f"{R['pct_colmatacion_nuevo']:.0f}", "% 'Clogging' o 'Clogged'"),
    ]

    # --- Modelo 1 (lab): regresión lineal simple y polinomial grado 2
    y = lab.Resistencia_compresion_MPa.values
    kf = KFold(6, shuffle=True, random_state=42)
    X1 = lab[["Permeabilidad_mm_s"]].values
    lin = LinearRegression().fit(X1, y)
    X2 = lab[["Porosidad_pct", "Relacion_agua_cemento"]].values
    pol = make_pipeline(PolynomialFeatures(2), LinearRegression()).fit(X2, y)
    lab["f_c_pred"] = pol.predict(X2)
    ejemplo = pol.predict([[15, 0.25]])[0]
    R["modelo_lab"] = {
        "lineal_k": {"pendiente": round(float(lin.coef_[0]), 3), "intercepto": round(float(lin.intercept_), 3),
                     "R2": round(lin.score(X1, y), 3)},
        "polinomial2": {"R2": round(r2_score(y, lab.f_c_pred), 3),
                        "R2_cv": round(cross_val_score(make_pipeline(PolynomialFeatures(2), LinearRegression()), X2, y, cv=kf, scoring="r2").mean(), 3),
                        "RMSE_MPa": round(mean_squared_error(y, lab.f_c_pred) ** .5, 2),
                        "pred_poro15_ac025_MPa": round(float(ejemplo), 1)}}
    # --- Modelo 2 (campo): regresión lineal sobre ln(infiltración) vs. edad (decaimiento exponencial,
    #     monótono; evita proyecciones físicamente absurdas de un polinomio fuera del rango)
    R["modelo_campo"], curvas = {}, {}
    for p, gp in epa.groupby("Pavimento"):
        m = gp.groupby("Mes_vida")[["Dias", "Infiltracion_mm_h"]].mean()
        x, yy = m[["Dias"]].values, m["Infiltracion_mm_h"].values
        mod = LinearRegression().fit(x, np.log(yy))
        pred = lambda d: np.exp(mod.predict(np.asarray(d, dtype=float).reshape(-1, 1)))
        xt, yt = gp[["Dias"]].values, gp["Infiltracion_mm_h"].values
        xf = np.linspace(x.min(), 1500, 60)
        curvas[p] = (m, xf, pred(xf))
        R["modelo_campo"][p] = {"R2_medias_mensuales": round(r2_score(yy, pred(x)), 3), "n_meses": len(m),
                                "R2_ensayos_individuales": round(r2_score(yt, pred(xt)), 3),
                                "tasa_decaimiento_pct_por_100_dias": round((1 - float(np.exp(mod.coef_[0] * 100))) * 100, 1),
                                "pred_dia_1500_mm_h": round(float(pred([1500])[0]), 0)}
    return lab, epa, desc, corr, curvas


# ----------------------------------------------------- 3. FIGURAS (Plotly)
def lay(titulo, x, y, **kw):
    d = dict(title={"text": titulo}, xaxis={"title": {"text": x}}, yaxis={"title": {"text": y}},
             template="plotly_white", margin={"t": 60, "l": 70, "r": 20, "b": 60},
             legend={"orientation": "h", "y": -0.25}, height=420)
    d.update(kw); return d


def figuras(lab, epa, corr, curvas):
    F, col = {}, {"Granite": "#c0392b", "Dolerite": "#2471a3"}
    F["hist"] = {"data": [dict(type="histogram", x=g.Resistencia_compresion_MPa.tolist(), name=a, nbinsx=12,
                               opacity=.7, marker={"color": col[a]}) for a, g in lab.groupby("Agregado")],
                 "layout": lay("Distribución de la resistencia a la compresión", "Resistencia a la compresión (MPa)",
                               "Frecuencia (n.º de mezclas)", barmode="overlay")}
    xs = np.linspace(lab.Permeabilidad_mm_s.min(), lab.Permeabilidad_mm_s.max(), 50)
    ml = R["modelo_lab"]["lineal_k"]
    F["scatter"] = {"data": [dict(type="scatter", mode="markers", x=g.Permeabilidad_mm_s.tolist(),
                                  y=g.Resistencia_compresion_MPa.tolist(), name=a, marker={"color": col[a], "size": 9},
                                  text=[f"Porosidad {p}% | a/c {c} | {gr}" for p, c, gr in zip(g.Porosidad_pct, g.Relacion_agua_cemento, g.Gradacion)])
                             for a, g in lab.groupby("Agregado")] +
                    [dict(type="scatter", mode="lines", x=xs.tolist(), y=(ml["intercepto"] + ml["pendiente"] * xs).tolist(),
                          name=f"Regresión lineal (R²={ml['R2']})", line={"color": "#333", "dash": "dash"})],
                    "layout": lay("Resistencia vs. permeabilidad", "Permeabilidad (mm/s)", "Resistencia a la compresión (MPa)")}
    nombres = ["Porosidad (%)", "Relación a/c", "f'c (MPa)", "k (mm/s)"]
    F["heat"] = {"data": [dict(type="heatmap", z=corr.values.round(2).tolist(), x=nombres, y=nombres, zmin=-1, zmax=1,
                               colorscale="RdBu", reversescale=True, text=corr.values.round(2).tolist(),
                               texttemplate="%{text}", colorbar={"title": {"text": "r de Pearson"}})],
                 "layout": lay("Matriz de correlación (laboratorio)", "Variable", "Variable", height=430)}
    pav = ["PICP original (2009-2012)", "PICP nuevo (2017-2020)"]; cp = ["#7f8c8d", "#e67e22"]
    tr = []
    for p, c in zip(pav, cp):
        g = epa[epa.Pavimento == p]
        mm = g.groupby(pd.Grouper(key="Fecha", freq="MS"))["Infiltracion_mm_h"].mean().dropna()
        tr += [dict(type="scatter", mode="markers", x=g.Fecha.dt.strftime("%Y-%m-%d").tolist(), y=g.Infiltracion_mm_h.tolist(),
                    name=f"{p}: ensayos", marker={"color": c, "size": 4, "opacity": .3}),
               dict(type="scatter", mode="lines+markers", x=mm.index.strftime("%Y-%m-%d").tolist(), y=mm.round(0).tolist(),
                    name=f"{p}: media mensual", line={"color": c, "width": 3})]
    F["serie"] = {"data": tr, "layout": lay("Infiltración superficial en el tiempo (ASTM C1701)", "Fecha de ensayo",
                                            "Tasa de infiltración (mm/h)", xaxis={"title": {"text": "Fecha de ensayo"}, "rangeslider": {"visible": True}}, height=500)}
    F["box"] = {"data": [dict(type="box", y=g.Infiltracion_mm_h.tolist(), name=str(a), boxpoints="outliers")
                         for a, g in epa[epa.Pavimento == pav[1]].groupby("Anio")],
                "layout": lay("Dispersión anual de la infiltración (PICP nuevo) y detección de anomalías", "Año de ensayo", "Tasa de infiltración (mm/h)")}
    mn = lab.Resistencia_compresion_MPa
    F["m_lab"] = {"data": [dict(type="scatter", mode="markers", x=mn.tolist(), y=lab.f_c_pred.round(2).tolist(), name="Mezclas",
                                marker={"color": "#2471a3", "size": 9}),
                           dict(type="scatter", mode="lines", x=[mn.min(), mn.max()], y=[mn.min(), mn.max()], name="Ajuste perfecto (1:1)", line={"dash": "dash", "color": "#333"})],
                  "layout": lay(f"Modelo polinomial grado 2: f'c = f(porosidad, a/c)  |  R² = {R['modelo_lab']['polinomial2']['R2']}",
                                "f'c observada (MPa)", "f'c predicha (MPa)")}
    p = pav[1]; m, xf, yf = curvas[p]
    F["m_campo"] = {"data": [dict(type="scatter", mode="markers", x=m.Dias.round(0).tolist(), y=m.Infiltracion_mm_h.round(0).tolist(), name="Media mensual observada", marker={"color": "#e67e22", "size": 9}),
                             dict(type="scatter", mode="lines", x=xf.round(0).tolist(), y=yf.round(0).tolist(), name="Exponencial (ln lineal), con proyección", line={"color": "#333", "dash": "dash"})],
                    "layout": lay(f"Regresión lineal de ln(infiltración) vs. edad, PICP nuevo  |  R² (medias) = {R['modelo_campo'][p]['R2_medias_mensuales']}",
                                  "Edad del pavimento (días desde instalación)", "Infiltración media mensual (mm/h)")}
    return F


# ------------------------------------------------ 4. CONCLUSIONES Y HTML
def textos(lab, epa):
    c, ml, mc = R["lab_corr"], R["modelo_lab"], R["modelo_campo"]
    pn, po = "PICP nuevo (2017-2020)", "PICP original (2009-2012)"
    ac = R["lab_por_ac"]; pp = R["lab_por_poro"]; ag = R["comp_agregado_5_10"]
    I = {
        "hist": f"La resistencia media es {lab.Resistencia_compresion_MPa.mean():.1f} MPa con CV de {R['lab_desc']['Resistencia_compresion_MPa']['CV_pct']:.0f}%. La cola izquierda (7.6–27 MPa) corresponde casi por completo a a/c = 0.20, pasta rígida que no envuelve bien al agregado.",
        "scatter": f"Existe relación inversa (r = {c['Resistencia_compresion_MPa']['Permeabilidad_mm_s']}), pero la permeabilidad explica solo el {ml['lineal_k']['R2'] * 100:.0f}% de la variabilidad de f'c: no basta como único predictor de diseño.",
        "heat": f"La permeabilidad se asocia sobre todo a la porosidad (r = {c['Permeabilidad_mm_s']['Porosidad_pct']}); porosidad y a/c son independientes (r ≈ 0), propio de un diseño factorial balanceado, lo que permite separar sus efectos.",
        "serie": f"El PICP nuevo pierde {R['perdida_infiltracion_pct'][pn]:.0f}% de su infiltración entre 2017 y 2020, mientras que el PICP original pierde {R['perdida_infiltracion_pct'][po]:.0f}% en 2009-2012: la colmatación avanza de forma rápida y acelerada al inicio de la vida útil.",
        "box": f"La dispersión es muy alta dentro de cada año (colmatación localizada). Se detectaron {R['epa_anomalias'][pn]} anomalías (IQR) en el PICP nuevo y {R['epa_anomalias'][po]} en el original; son puntos críticos que conviene inspeccionar en obra, no errores de medición a descartar.",
        "m_lab": f"El modelo polinomial grado 2 alcanza R² = {ml['polinomial2']['R2']} (validación cruzada {ml['polinomial2']['R2_cv']}, RMSE {ml['polinomial2']['RMSE_MPa']} MPa). Predicción de ejemplo: porosidad 15% y a/c 0.25 → {ml['polinomial2']['pred_poro15_ac025_MPa']} MPa.",
        "m_campo": f"La regresión lineal sobre ln(infiltración) implica una caída de {mc[pn]['tasa_decaimiento_pct_por_100_dias']}% cada 100 días. Con medias mensuales el ajuste es R² = {mc[pn]['R2_medias_mensuales']} (n = {mc[pn]['n_meses']} meses), pero con ensayos individuales cae a {mc[pn]['R2_ensayos_individuales']}: la edad explica la tendencia, no la variabilidad espacial. La proyección a 1500 días ({mc[pn]['pred_dia_1500_mm_h']:.0f} mm/h) es una extrapolación orientativa.",
    }
    C = [f"Porosidad: al subir de 12% a 21% la resistencia media baja de {pp[12]['Resistencia_compresion_MPa']} a {pp[21]['Resistencia_compresion_MPa']} MPa y la permeabilidad sube de {pp[12]['Permeabilidad_mm_s']} a {pp[21]['Permeabilidad_mm_s']} mm/s. Pavimentos de tráfico ligero: 12–15%; filtración y drenaje: 18–21%.",
         f"Relación a/c: la resistencia media es {ac[0.2]['Resistencia_compresion_MPa']} MPa con a/c = 0.20 frente a {ac[0.25]['Resistencia_compresion_MPa']} MPa con 0.25; se recomienda 0.25–0.30 y no bajar de 0.25.",
         f"Agregado (comparación equivalente, gradación 5-10 mm): dolerita {ag['dolerita_MPa']} MPa vs. granito {ag['granito_MPa']} MPa. La dolerita solo se ensayó con una gradación, por lo que la ventaja no puede generalizarse sin más datos.",
         f"Campo: la infiltración inicial del PICP nuevo (~{R['epa_anual'][pn + '|2017']['mean']:.0f} mm/h en 2017) cae a ~{R['epa_anual'][pn + '|2020']['mean']:.0f} mm/h en 2020 y el {R['pct_colmatacion_nuevo']:.0f}% de sus ensayos se clasifica como colmatación. Se debe programar inspección con ASTM C1701 y mantenimiento preventivo desde los primeros años.",
         "Limitaciones: los datos de laboratorio y de campo provienen de materiales y métodos distintos (concreto permeable en probetas vs. adoquines permeables in situ); se usan de forma complementaria, no como un mismo experimento. n = 48 en laboratorio, sin fechas de ensayo; la proyección de campo es extrapolación."]
    return I, C


PLANTILLA = """<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dashboard AVPF-2 | Concreto permeable</title>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"></script>
<style>body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f6f8;color:#1c2833}
header{background:#c8102e;color:#fff;padding:18px 28px}header h1{margin:0;font-size:22px}header p{margin:4px 0 0;font-size:13px;opacity:.9}
main{max-width:1200px;margin:auto;padding:16px}h2{border-left:5px solid #c8102e;padding-left:10px;margin:28px 0 10px;font-size:18px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.kpi{background:#fff;border-radius:8px;padding:12px 14px;box-shadow:0 1px 3px #0002}
.kpi b{display:block;font-size:26px;color:#c8102e}.kpi span{font-size:12px;color:#566573}.kpi small{display:block;font-size:11px;color:#7f8c8d}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:14px}.card{background:#fff;border-radius:8px;padding:8px;box-shadow:0 1px 3px #0002}
.card p{font-size:13px;margin:4px 10px 10px;color:#2c3e50}.card p:before{content:"Interpretación técnica: ";font-weight:600}
.concl{background:#fff;border-radius:8px;padding:6px 24px;box-shadow:0 1px 3px #0002}.concl li{margin:8px 0;font-size:14px}
footer{font-size:12px;color:#566573;padding:16px 28px}@media(max-width:560px){.grid{grid-template-columns:1fr}}</style></head><body>
<header><h1>Concreto permeable: resistencia, permeabilidad y colmatación</h1>
<p>AVPF-2 · Ingeniería Civil – Estructuras y Materiales · Fuentes: Huang et al. (2020) y US EPA ORD (doi:10.23719/1520736)</p></header><main>
<h2>Indicadores clave (KPIs)</h2><div class="kpis">__KPIS__</div>
<small>* Criterio de diseño del grupo, no una norma.</small>
<h2>A. Laboratorio: compromiso resistencia – permeabilidad (48 mezclas)</h2><div class="grid">__LAB__</div>
<h2>B. Campo: serie temporal de infiltración (ensayos ASTM C1701 con fecha real)</h2><div class="grid">__CAMPO__</div>
<h2>Modelos predictivos (Scikit-Learn)</h2><div class="grid">__MOD__</div>
<h2>Conclusiones técnicas</h2><div class="concl"><ul>__CONCL__</ul></div></main>
<footer>Generado con AVPF2___GRUPO__.py · pandas, scikit-learn y Plotly. Los gráficos son interactivos (zoom, hover, clic en la leyenda).</footer>
<script>const F=__FIGS__;for(const k in F){Plotly.newPlot('g_'+k,F[k].data,F[k].layout,{responsive:true,displaylogo:false});}</script></body></html>"""


def a_json(F):
    """Valida con Plotly (si está instalado) y serializa las figuras."""
    conv = lambda o: o.tolist() if hasattr(o, "tolist") else float(o)
    try:
        import plotly.graph_objects as go, plotly.io as pio
        return "{" + ",".join(f'"{k}":{pio.to_json(go.Figure(v))}' for k, v in F.items()) + "}"
    except Exception:
        return json.dumps(F, default=conv)


def dashboard(F, I, C):
    card = lambda k: f'<div class="card"><div id="g_{k}"></div><p>{I[k]}</p></div>'
    kp = "".join(f'<div class="kpi"><span>{a}</span><b>{b}</b><small>{c}</small></div>' for a, b, c in R["kpis"])
    html = (PLANTILLA.replace("__KPIS__", kp).replace("__LAB__", "".join(card(k) for k in ("hist", "scatter", "heat")))
            .replace("__CAMPO__", "".join(card(k) for k in ("serie", "box")))
            .replace("__MOD__", "".join(card(k) for k in ("m_lab", "m_campo")))
            .replace("__CONCL__", "".join(f"<li>{t}</li>" for t in C)).replace("__GRUPO__", GRUPO)
            .replace("__FIGS__", a_json(F)))
    ruta = os.path.join(BASE, f"Dashboard_AVPF2_{GRUPO}.html")
    open(ruta, "w", encoding="utf-8").write(html)
    return ruta


# ------------------------------------- 5. FIGURAS ESTÁTICAS PARA EL INFORME
def estaticas(lab, epa, corr, curvas):
    pn, po = "PICP nuevo (2017-2020)", "PICP original (2009-2012)"
    def guardar(nombre):
        plt.tight_layout(); plt.savefig(os.path.join(OUT, nombre), dpi=150); plt.close()
    for a, g in lab.groupby("Agregado"):
        plt.hist(g.Resistencia_compresion_MPa, bins=10, alpha=.65, label=a)
    plt.title("Distribución de la resistencia a la compresión"); plt.xlabel("Resistencia a la compresión (MPa)")
    plt.ylabel("Frecuencia (n.º de mezclas)"); plt.legend(); guardar("fig_hist.png")
    ml = R["modelo_lab"]["lineal_k"]; xs = np.linspace(lab.Permeabilidad_mm_s.min(), lab.Permeabilidad_mm_s.max(), 50)
    for a, g in lab.groupby("Agregado"):
        plt.scatter(g.Permeabilidad_mm_s, g.Resistencia_compresion_MPa, label=a)
    plt.plot(xs, ml["intercepto"] + ml["pendiente"] * xs, "k--", label=f"Regresión lineal (R²={ml['R2']})")
    plt.title("Resistencia vs. permeabilidad"); plt.xlabel("Permeabilidad (mm/s)")
    plt.ylabel("Resistencia a la compresión (MPa)"); plt.legend(); guardar("fig_scatter.png")
    n = ["Porosidad (%)", "a/c", "f'c (MPa)", "k (mm/s)"]
    plt.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1); plt.colorbar(label="r de Pearson")
    plt.xticks(range(4), n, rotation=20); plt.yticks(range(4), n)
    for i in range(4):
        for j in range(4): plt.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center")
    plt.title("Matriz de correlación (laboratorio)"); guardar("fig_heat.png")
    for p, c in ((po, "gray"), (pn, "tab:orange")):
        g = epa[epa.Pavimento == p]; mm = g.groupby(pd.Grouper(key="Fecha", freq="MS"))["Infiltracion_mm_h"].mean().dropna()
        plt.scatter(g.Fecha, g.Infiltracion_mm_h, s=6, alpha=.3, color=c); plt.plot(mm.index, mm.values, color=c, lw=2, label=p)
    plt.title("Infiltración superficial en el tiempo (ASTM C1701)"); plt.xlabel("Fecha de ensayo")
    plt.ylabel("Tasa de infiltración (mm/h)"); plt.legend(); guardar("fig_serie.png")
    plt.scatter(lab.Resistencia_compresion_MPa, lab.f_c_pred, color="tab:blue")
    r = [lab.Resistencia_compresion_MPa.min(), lab.Resistencia_compresion_MPa.max()]; plt.plot(r, r, "k--", label="1:1")
    plt.title(f"Modelo polinomial grado 2 (R²={R['modelo_lab']['polinomial2']['R2']})"); plt.xlabel("f'c observada (MPa)")
    plt.ylabel("f'c predicha (MPa)"); plt.legend(); guardar("fig_modelo_lab.png")
    m, xf, yf = curvas[pn]
    plt.scatter(m.Dias, m.Infiltracion_mm_h, color="tab:orange", label="Media mensual observada"); plt.plot(xf, yf, "k--", label="Exponencial (ln lineal), proyección")
    plt.title(f"Regresión sobre ln(infiltración), PICP nuevo (R²={R['modelo_campo'][pn]['R2_medias_mensuales']})")
    plt.xlabel("Edad del pavimento (días desde instalación)"); plt.ylabel("Infiltración media mensual (mm/h)"); plt.legend(); guardar("fig_modelo_campo.png")


if __name__ == "__main__":
    lab, epa = cargar_laboratorio(), cargar_epa()
    lab, epa, desc, corr, curvas = analizar(lab, epa)
    F = figuras(lab, epa, corr, curvas)
    I, C = textos(lab, epa)
    R["interpretaciones"], R["conclusiones"] = I, C
    lab.to_csv(os.path.join(OUT, "lab_limpio.csv"), index=False)
    epa.drop(columns=["Date"]).to_csv(os.path.join(OUT, "campo_epa_limpio.csv"), index=False)
    estaticas(lab, epa, corr, curvas)
    json.dump(R, open(os.path.join(OUT, "resultados.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print("Dashboard:", dashboard(F, I, C))
    print(json.dumps({k: R[k] for k in ("lab_limpieza", "epa_limpieza", "modelo_lab", "modelo_campo", "perdida_infiltracion_pct")}, ensure_ascii=False, indent=1))
