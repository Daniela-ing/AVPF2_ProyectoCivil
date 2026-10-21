# -*- coding: utf-8 -*-
"""Genera Informe_AVPF2_GX.pdf a partir de outputs/resultados.json y las figuras.
Ejecutar DESPUÉS de AVPF2_GX.py:  python generar_informe.py"""
import json, os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.platypus import KeepTogether, SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak

GRUPO = "GX"
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "outputs")
R = json.load(open(os.path.join(OUT, "resultados.json"), encoding="utf-8"))
PN, PO = "PICP nuevo (2017-2020)", "PICP original (2009-2012)"


def t(s):  # caracteres fuera de la fuente estándar del PDF
    for a, b in (("≥", ">="), ("→", "->"), ("≈", "~"), ("−", "-")):
        s = s.replace(a, b)
    return s


ss = getSampleStyleSheet()
N = ParagraphStyle("N", parent=ss["BodyText"], alignment=TA_JUSTIFY, fontSize=10, leading=13.5, spaceAfter=6)
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=14, textColor=colors.HexColor("#c8102e"), spaceBefore=10, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=11, spaceBefore=6, spaceAfter=4)
CAP = ParagraphStyle("CAP", parent=N, fontSize=8.5, leading=11, alignment=TA_CENTER, textColor=colors.HexColor("#444444"))
CT = ParagraphStyle("CT", parent=N, alignment=TA_CENTER, fontSize=11, leading=15)
P = lambda s, st=N: Paragraph(t(s), st)


def fig(nombre, ancho, pie):
    img = Image(os.path.join(OUT, nombre)); r = img.imageHeight / img.imageWidth
    img.drawWidth, img.drawHeight = ancho * cm, ancho * r * cm
    return [KeepTogether([img, P(pie, CAP), Spacer(1, 6)])]


TC = ParagraphStyle("TC", parent=N, fontSize=8.5, leading=10.5, alignment=0, spaceAfter=0)
TH = ParagraphStyle("TH", parent=TC, textColor=colors.white, fontName="Helvetica-Bold")


def tabla(datos, anchos):
    datos = [[Paragraph(t(str(c)), TH if i == 0 else TC) for c in f] for i, f in enumerate(datos)]
    tb = Table(datos, colWidths=[a * cm for a in anchos], repeatRows=1)
    tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#c8102e")), 
                            ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("GRID", (0, 0), (-1, -1), .4, colors.grey),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f8")]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return [tb, Spacer(1, 8)]


ml, mc, I, C = R["modelo_lab"], R["modelo_campo"], R["interpretaciones"], R["conclusiones"]
desc, ac, pp = R["lab_desc"], R["lab_por_ac"], R["lab_por_poro"]
S = []

# ---- Carátula
S += [Spacer(1, 3 * cm), P("<b>UNIVERSIDAD TECNOLÓGICA DEL PERÚ</b>", CT), Spacer(1, 10),
      P("Curso: Herramientas de Desarrollo Profesional Civil", CT), Spacer(1, 40),
      P("<b>AVANCE DE PROYECTO FINAL 2 (AVPF-2)</b>", ParagraphStyle("x", parent=CT, fontSize=16, leading=22)), Spacer(1, 10),
      P("<b>Concreto permeable: compromiso resistencia – permeabilidad y colmatación en el tiempo mediante un dashboard interactivo</b>", CT),
      Spacer(1, 40), P("Integrantes:<br/>Calle Veliz, Mario<br/>Yarleque Chuna, Daniela<br/>Maza Sanchez, Yerick", CT), Spacer(1, 16),
      P("Docente: Jimenez Pesantes, Hilder Javier<br/>Octubre, 2026", CT), PageBreak()]

# ---- 1. Introducción
S += [P("1. Introducción", H1),
      P("El concreto permeable es un material de estructura abierta que deja infiltrar el agua de lluvia hacia el subsuelo y reduce la escorrentía en pavimentos, estacionamientos y áreas peatonales. Su diseño plantea un compromiso técnico: aumentar la porosidad favorece la permeabilidad, pero reduce la resistencia a la compresión; además, con el uso los poros se colmatan por sedimentos y la capacidad drenante disminuye."),
      P("<b>Problema de Ingeniería Civil (Estructuras y Materiales):</b> definir dosificaciones que equilibren resistencia y drenaje, y anticipar la pérdida de infiltración durante la vida útil del pavimento."),
      P("<b>Objetivo del análisis:</b> (i) cuantificar la relación entre porosidad, relación agua/cemento (a/c), resistencia y permeabilidad con datos de laboratorio; (ii) analizar la evolución temporal de la infiltración con ensayos de campo fechados; (iii) construir KPIs, un dashboard interactivo y modelos predictivos que apoyen decisiones de diseño y mantenimiento.")]

# ---- 2. Datos
S += [P("2. Descripción de los datos", H1),
      P("Se emplean dos fuentes verificables y complementarias. <b>No son el mismo experimento</b>: la fuente A caracteriza el material en probetas de laboratorio y la fuente B monitorea adoquines permeables in situ."),
      ] + tabla([["", "A. Laboratorio", "B. Campo (serie temporal)"],
                 ["Fuente", "Huang et al. (2020), Construction and Building Materials, Tabla 6 (PII S0950061820327641)", "US EPA ORD, doi:10.23719/1520736; OConnor y Borst (2022), J. Green Building 17(4)"],
                 ["Registros", f"{R['lab_limpieza']['registros_final']} mezclas", f"{R['epa_limpieza']['registros_final']} ensayos en {R['epa_limpieza']['campanas_fecha']} fechas (2009-2012 y 2017-2020)"],
                 ["Variables", "Agregado, gradación, porosidad, a/c, resistencia, permeabilidad", "Fecha, mitad del lote, distancias a bordillo y borde, tiempo e infiltración, edad, evaluación"],
                 ["Unidades", "% ; adimensional ; MPa ; mm/s", "m ; s ; mm/h ; días"],
                 ["Fechas de ensayo", "No publicadas (datos de artículo)", "Reales, por ensayo ASTM C1701"]], [3, 6.5, 7.5]) + [
      P("<i>Nota de transparencia:</i> la tabla de laboratorio fue transcrita por el grupo desde la publicación; las fechas de ensayo solo existen en la fuente B y no se generó ningún dato simulado.")]

# ---- 3. Metodología
S += [P("3. Metodología", H1),
      P(f"<b>Limpieza (pandas).</b> Laboratorio: {R['lab_limpieza']['nulos']} nulos y 0 duplicados en {R['lab_limpieza']['registros_inicial']} registros; se normalizaron textos, se forzó formato numérico y se verificó que todas las magnitudes fueran positivas. Campo: se unieron las hojas del PICP original y del PICP nuevo, se normalizaron los nombres de columna (la fuente trae espacios finales), se eliminó {R['epa_limpieza']['filas_resumen_eliminadas']} fila de promedios de la fuente que no era un ensayo ({R['epa_limpieza']['registros_inicial']} a {R['epa_limpieza']['registros_final']} registros), se convirtieron las fechas a formato fecha y se derivó la infiltración en mm/s y la edad en meses."),
      P("<b>KPIs.</b> Se construyeron ocho indicadores (Sección 4). <b>Análisis exploratorio:</b> estadísticos descriptivos, coeficiente de variación, matriz de correlación de Pearson y detección de anomalías con el criterio del rango intercuartílico (1.5 x IQR). <b>Modelos (Scikit-Learn):</b> regresión lineal y polinomial de grado 2 con validación cruzada (6 pliegues) para laboratorio, y regresión lineal sobre el logaritmo de la infiltración para campo. <b>Visualización:</b> Plotly (interactiva) en el dashboard y Matplotlib en este informe. <b>Control de versiones:</b> repositorio GitHub con código, datos, dashboard y README.")]

# ---- 4. Dashboard
S += [PageBreak(), P("4. Dashboard", H1),
      P("El archivo <b>Dashboard_AVPF2_" + GRUPO + ".html</b> integra los KPIs, las visualizaciones interactivas (zoom, información al pasar el cursor, activación de series desde la leyenda y control deslizante de fechas), la serie temporal, los dos modelos predictivos y las conclusiones técnicas. Se abre con cualquier navegador con conexión a internet (carga Plotly desde una red de distribución).")
      ] + tabla([["KPI", "Valor", "Unidad / criterio"]] + [[a, b, c] for a, b, c in R["kpis"]], [7.2, 2.3, 7.5]) + [
      P("* Criterio de diseño definido por el grupo para el KPI de mezclas aptas; no corresponde a una norma.", CAP)]

# ---- 5. Resultados
S += [PageBreak(), P("5. Resultados", H1), P("5.1 Laboratorio: estadística y compromiso resistencia-permeabilidad", H2),
      P(f"La resistencia media es {desc['Resistencia_compresion_MPa']['mean']:.1f} MPa (CV {desc['Resistencia_compresion_MPa']['CV_pct']:.0f}%, rango {desc['Resistencia_compresion_MPa']['min']}–{desc['Resistencia_compresion_MPa']['max']} MPa) y la permeabilidad media {desc['Permeabilidad_mm_s']['mean']:.2f} mm/s (CV {desc['Permeabilidad_mm_s']['CV_pct']:.0f}%, rango {desc['Permeabilidad_mm_s']['min']}–{desc['Permeabilidad_mm_s']['max']} mm/s). La permeabilidad es la variable más dispersa."),
      ] + fig("fig_hist.png", 11.5, "Figura 1. Histograma de la resistencia a la compresión. " + I["hist"]) + fig("fig_scatter.png", 11.5, "Figura 2. Resistencia vs. permeabilidad. " + I["scatter"]) + [PageBreak()] + fig("fig_heat.png", 10.5, "Figura 3. Matriz de correlación. " + I["heat"]) + [
      P(f"Efecto de la dosificación: con a/c = 0.20 la resistencia media es {ac['0.2']['Resistencia_compresion_MPa']} MPa, con 0.25 sube a {ac['0.25']['Resistencia_compresion_MPa']} MPa y con 0.30 es {ac['0.3']['Resistencia_compresion_MPa']} MPa, mientras la permeabilidad baja de {ac['0.2']['Permeabilidad_mm_s']} a {ac['0.3']['Permeabilidad_mm_s']} mm/s. Con porosidad de 12% a 21% la resistencia media baja de {pp['12']['Resistencia_compresion_MPa']} a {pp['21']['Resistencia_compresion_MPa']} MPa y la permeabilidad sube de {pp['12']['Permeabilidad_mm_s']} a {pp['21']['Permeabilidad_mm_s']} mm/s. "
        f"Anomalías (IQR): se detectó {len(R['lab_anomalias'])} registro atípico (granito 10-15 mm, porosidad 21%, a/c 0.20, k = 4.5 mm/s), coherente con la combinación más abierta del diseño; se conservó por ser un resultado experimental plausible."),
      P("5.2 Campo: serie temporal de infiltración", H2),
      P(f"Las {R['epa_limpieza']['registros_final']} mediciones fechadas muestran una pérdida de infiltración de {R['perdida_infiltracion_pct'][PN]:.0f}% en el PICP nuevo (2017 a 2020) y de {R['perdida_infiltracion_pct'][PO]:.0f}% en el PICP original (2009 a 2012). El {R['pct_colmatacion_nuevo']:.0f}% de los ensayos del PICP nuevo fue clasificado por la fuente como 'Clogging' o 'Clogged'. El año 2020 solo incluye ensayos de enero a marzo."),
      ] + fig("fig_serie.png", 13.5, "Figura 4. Serie temporal de infiltración. " + I["serie"]) + [
      P("<b>Interpretación del comportamiento anómalo:</b> " + I["box"])]

# ---- 6. Modelo predictivo
S += [PageBreak(), P("6. Modelo predictivo", H1),
      P(f"<b>Modelo de laboratorio.</b> Variable objetivo: resistencia a la compresión f'c (MPa). Como línea base, la regresión lineal f'c = {ml['lineal_k']['intercepto']} + ({ml['lineal_k']['pendiente']}) x k tiene R² = {ml['lineal_k']['R2']}. Con la regresión polinomial de grado 2 sobre porosidad y a/c el R² sube a <b>{ml['polinomial2']['R2']}</b> (validación cruzada: {ml['polinomial2']['R2_cv']}; RMSE: {ml['polinomial2']['RMSE_MPa']} MPa). Predicción realizada: porosidad 15% y a/c 0.25 dan f'c = {ml['polinomial2']['pred_poro15_ac025_MPa']} MPa."),
      ] + fig("fig_modelo_lab.png", 10.5, "Figura 5. f'c observada vs. predicha. " + I["m_lab"]) + [
      P(f"<b>Modelo de campo.</b> Variable objetivo: infiltración media mensual del PICP nuevo (mm/h). Se ajustó una regresión lineal sobre ln(infiltración) en función de la edad, que equivale a un decaimiento exponencial y evita que un polinomio proyecte una recuperación inexistente. R² = {mc[PN]['R2_medias_mensuales']} con medias mensuales y {mc[PN]['R2_ensayos_individuales']} con ensayos individuales; la caída estimada es {mc[PN]['tasa_decaimiento_pct_por_100_dias']}% cada 100 días y la proyección a 1500 días es {mc[PN]['pred_dia_1500_mm_h']:.0f} mm/h."),
      ] + fig("fig_modelo_campo.png", 10.5, "Figura 6. Modelo de colmatación del PICP nuevo. " + I["m_campo"])

# ---- 7. Conclusiones
S += [PageBreak(), P("7. Conclusiones e interpretación ingenieril", H1)] + [P(f"{i + 1}. {x}") for i, x in enumerate(C)] + [
      P("<b>Aplicaciones prácticas:</b> (a) usar el modelo polinomial como herramienta de predesign para elegir porosidad y a/c según el uso del pavimento; (b) incorporar al plan de operación ensayos periódicos de infiltración (ASTM C1701) y mantenimiento preventivo cuando la tendencia se acerque al valor mínimo definido en el proyecto; (c) registrar fecha de cada ensayo de laboratorio para poder construir series temporales propias en futuras etapas."),
      P("<b>Limitaciones:</b> muestra de laboratorio reducida (48) y sin fechas; dolerita ensayada con una sola gradación; datos de campo de adoquines permeables, no de concreto permeable vaciado; R² por ensayo individual bajo por la variabilidad espacial; proyección fuera del rango observado.")]

# ---- 8. Referencias
S += [P("8. Referencias", H1),
      P("Huang et al. (2020). Impact of aggregate type and size and mineral admixtures on the properties of pervious concrete: An experimental investigation. <i>Construction and Building Materials</i>. ScienceDirect, PII S0950061820327641. (Verificar autores completos, volumen y DOI en la página del editor antes de la entrega.)"),
      P("U.S. EPA Office of Research and Development (2021). Permeable Pavement Infiltration testing and Clogging Prediction (dataset). https://doi.org/10.23719/1520736"),
      P("OConnor, T. y Borst, M. (2022). Predicting Location and Evaluating Progression of Clogging in a Permeable Pavement Parking Lot. <i>Journal of Green Building</i>, 17(4), 3-18. https://doi.org/10.3992/jgb.17.4.3"),
      P("ASTM International. ASTM C1701/C1701M: Standard Test Method for Infiltration Rate of In Place Pervious Concrete.")]


def pie(c, d):
    c.setFont("Helvetica", 8); c.setFillColor(colors.grey)
    c.drawCentredString(A4[0] / 2, 1.2 * cm, f"AVPF-2 · Concreto permeable · pág. {d.page}")


SimpleDocTemplate(os.path.join(BASE, f"Informe_AVPF2_{GRUPO}.pdf"), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                  topMargin=2 * cm, bottomMargin=2 * cm, title="Informe técnico AVPF-2").build(S, onLaterPages=pie)
print("Informe generado")
