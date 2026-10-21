# AVPF-2 · Concreto permeable: resistencia, permeabilidad y colmatación

Proyecto de analítica de datos aplicada a Ingeniería Civil (Estructuras y Materiales) para el curso
*Herramientas de Desarrollo Profesional Civil* (UTP). Integrantes: Calle Veliz, Mario · Yarleque Chuna, Daniela · Maza Sanchez, Yerick.

## Problema y objetivo
El concreto permeable debe equilibrar **resistencia a la compresión** y **capacidad de infiltración**, y su infiltración
disminuye con el tiempo por colmatación. Se analizan ambos aspectos con datos verificables, se construyen KPIs, un
dashboard interactivo y modelos predictivos para apoyar decisiones de diseño y mantenimiento.

## Fuentes de datos (dos fuentes complementarias, no son el mismo experimento)
| Fuente | Contenido | Registros | Fechas de ensayo |
|---|---|---|---|
| A. Huang et al. (2020), *Construction and Building Materials*, Tabla 6 (PII S0950061820327641) | Laboratorio: granito/dolerita, porosidad 12–21 %, a/c 0.20–0.30, resistencia (MPa), permeabilidad (mm/s) | 48 | No publicadas |
| B. US EPA ORD, https://doi.org/10.23719/1520736 (OConnor y Borst, 2022, *J. Green Building* 17(4)) | Campo: infiltración ASTM C1701 en adoquines permeables (PICP) | 379 ensayos en 70 fechas | Sí: 2009-2012 y 2017-2020 |

**Antes de entregar, verificar:** (1) que los 48 registros coinciden con la Tabla 6 de Huang et al. y completar autores,
volumen y DOI; (2) la licencia del dataset EPA (https://pasteur.epa.gov/license/sciencehub-license.html) antes de
republicar el archivo en GitHub. No se generó ningún dato simulado.

## Estructura
```
AVPF2_GX.py                 # limpieza, KPIs, EDA, modelos, dashboard y figuras
generar_informe.py          # informe técnico en PDF (ejecutar después del script principal)
Dashboard_AVPF2_GX.html     # dashboard exportado (Plotly)
Informe_AVPF2_GX.pdf        # informe técnico
data/                       # datasets originales
outputs/                    # datos limpios, figuras, resultados.json
```
Renombrar `GX` con el número de grupo (archivos y variable `GRUPO` al inicio de ambos scripts).

## Ejecución
```
pip install -r requirements.txt
python AVPF2_GX.py
python generar_informe.py
```
El dashboard carga Plotly.js desde una red de distribución, por lo que requiere conexión a internet al abrirlo.

## Metodología resumida
- **Limpieza (pandas):** nulos, duplicados, tipos numéricos, normalización de columnas, eliminación de una fila de promedios
  de la fuente EPA (380 → 379 registros), conversión de fechas y de unidades (mm/h → mm/s).
- **KPIs (8):** resistencia y permeabilidad medias, % de mezclas aptas (criterio del grupo: f'c ≥ 20 MPa y k ≥ 1.0 mm/s),
  correlación f'c–k, número de ensayos fechados, pérdida de infiltración (2 pavimentos) y % de ensayos con colmatación.
- **EDA:** descriptivos, CV, correlación de Pearson, anomalías por IQR.
- **Modelos (Scikit-Learn):** laboratorio, lineal (R² = 0.348) y polinomial grado 2 sobre porosidad y a/c (R² = 0.865, validación cruzada 0.807);
  campo, regresión lineal sobre ln(infiltración) vs. edad (R² = 0.891 con medias mensuales, 0.309 con ensayos individuales).

## Hallazgos principales
1. Más porosidad → más permeabilidad y menos resistencia; a/c = 0.25 da la mayor resistencia media en la muestra.
2. La permeabilidad sola explica solo el 35 % de f'c; porosidad y a/c juntas explican mucho más.
3. El PICP nuevo perdió 76 % de infiltración entre 2017 y 2020 (2020 solo incluye ene–mar); el original, 24 % entre 2009 y 2012.

## Limitaciones
Muestra de laboratorio pequeña y sin fechas; dolerita ensayada con una sola gradación; la serie de campo es de adoquines
permeables, no de concreto vaciado; la proyección a 1500 días es una extrapolación.
