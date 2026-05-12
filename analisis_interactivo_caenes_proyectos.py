import json
import math
import pandas as pd
from pathlib import Path
from plotly.offline import get_plotlyjs

# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================

pd.set_option("display.float_format", lambda x: f"{x:,.2f}")
pd.set_option("display.max_columns", 120)
pd.set_option("display.width", 260)

BASE_DIR = Path(__file__).parent
DATOS_DIR = BASE_DIR / "datos"
SALIDAS_DIR = BASE_DIR / "salidas"
SALIDAS_DIR.mkdir(exist_ok=True)

archivo = DATOS_DIR / "Base_manzana_entidad_CPV24.csv"

PROYECTOS = {
    "San Francisco": "13401061001001",
    "Flor del Valle": "13119191001001",
    "Sauces del Sol": "13119121001001"
}

# =========================================================
# VARIABLES CAENES
# =========================================================
# CAENES = Clasificador de Actividades Económicas Nacional
# para encuestas sociodemográficas.
#
# Las columnas reales detectadas en tu base son:
# n_caenes_A hasta n_caenes_U
#
# El denominador para porcentajes será:
# total_ocupados_clasificados = suma de todas las categorías CAENES

VARIABLES_CAENES = {
    "n_caenes_A": "Agricultura y pesca",
    "n_caenes_B": "Minería",
    "n_caenes_C": "Industrias manufactureras",
    "n_caenes_D": "Electricidad y gas",
    "n_caenes_E": "Agua y residuos",
    "n_caenes_F": "Construcción",
    "n_caenes_G": "Comercio y reparación vehicular",
    "n_caenes_H": "Transporte y almacenamiento",
    "n_caenes_I": "Alojamiento y comidas",
    "n_caenes_J": "Información y comunicaciones",
    "n_caenes_K": "Actividades financieras y de seguros",
    "n_caenes_L": "Actividades inmobiliarias",
    "n_caenes_M": "Servicios profesionales",
    "n_caenes_N": "Servicios administrativos",
    "n_caenes_O": "Administración pública",
    "n_caenes_P": "Enseñanza",
    "n_caenes_Q": "Salud y asistencia social",
    "n_caenes_R": "Arte y recreación",
    "n_caenes_S": "Otros servicios",
    "n_caenes_T": "Hogares empleadores",
    "n_caenes_U": "Organizaciones extraterritoriales"
}

VARIABLES_NECESARIAS = list(VARIABLES_CAENES.keys())

# =========================================================
# FUNCIONES
# =========================================================

def safe_pct(numerador, denominador):
    if pd.isna(denominador) or denominador == 0:
        return 0
    return (numerador / denominador) * 100

def convertir_a_float_lista(serie):
    return [float(x) for x in serie]

def calcular_rango_log_superior(payload, key_grafico, niveles=("regional", "comunal", "manzana")):
    max_val = 1

    for proyecto in payload.values():
        source = proyecto[key_grafico]

        for nivel in niveles:
            valores = source[nivel]
            if valores:
                max_val = max(max_val, max(valores))

    max_val = max(1, max_val)
    return math.ceil(math.log10(max_val))

# =========================================================
# CARGA DE DATOS
# =========================================================

df = pd.read_csv(
    archivo,
    sep=";",
    encoding="utf-8-sig",
    low_memory=False
)

df.columns = df.columns.str.strip()

df["MANZENT"] = df["MANZENT"].astype(str).str.strip()
df["COD_REGION"] = pd.to_numeric(df["COD_REGION"], errors="coerce")
df["CUT"] = pd.to_numeric(df["CUT"], errors="coerce")

for col in VARIABLES_NECESARIAS:
    if col not in df.columns:
        print("\nColumnas CAENES encontradas en la base:")
        for c in df.columns:
            if "caenes" in c.lower():
                print(" -", c)

        raise ValueError(f"No existe la columna requerida: {col}")

    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

region_rm = df[df["COD_REGION"] == 13].copy()

print("=" * 90)
print("ANÁLISIS INTERACTIVO CAENES - PROYECTOS")
print("=" * 90)
print("\nBase completa:", df.shape)
print("Región Metropolitana:", region_rm.shape)

print("\nColumnas utilizadas:")
for col, label in VARIABLES_CAENES.items():
    print(f"{label}: {col}")

# =========================================================
# CONSTRUIR DATOS PARA HTML
# =========================================================

payload = {}
detalle_proyectos = []
registros_excel = []
registros_diferencias_excel = []

orden_variables = list(VARIABLES_CAENES.keys())
orden_labels = list(VARIABLES_CAENES.values())

for nombre_proyecto, manzent in PROYECTOS.items():
    manzana = df[df["MANZENT"] == manzent].copy()

    if manzana.empty:
        print(f"\n⚠️ No se encontró la manzana para {nombre_proyecto} ({manzent})")
        continue

    comuna_nombre = manzana["COMUNA"].iloc[0]
    cut_comuna = int(manzana["CUT"].iloc[0])
    comuna = df[df["CUT"] == cut_comuna].copy()

    detalle_proyectos.append({
        "Proyecto": nombre_proyecto,
        "MANZENT": manzent,
        "Comuna": comuna_nombre,
        "CUT": cut_comuna,
        "Filas manzana": len(manzana),
        "Filas comuna": len(comuna)
    })

    bases = {
        "regional": region_rm,
        "comunal": comuna,
        "manzana": manzana
    }

    conteos = {
        "y": orden_labels,
        "regional": [],
        "comunal": [],
        "manzana": []
    }

    porcentajes = {
        "y": orden_labels,
        "regional": [],
        "comunal": [],
        "manzana": []
    }

    for nivel_key, base in bases.items():
        suma = base[VARIABLES_NECESARIAS].sum()

        valores_conteos = [float(suma[var]) for var in orden_variables]
        total_ocupados_clasificados = float(sum(valores_conteos))

        valores_porcentajes = [
            safe_pct(valor, total_ocupados_clasificados)
            for valor in valores_conteos
        ]

        conteos[nivel_key] = convertir_a_float_lista(valores_conteos)
        porcentajes[nivel_key] = convertir_a_float_lista(valores_porcentajes)

        for var, label, valor_conteo, valor_pct in zip(
            orden_variables,
            orden_labels,
            valores_conteos,
            valores_porcentajes
        ):
            registros_excel.append({
                "Proyecto seleccionado": nombre_proyecto,
                "Comuna proyecto": comuna_nombre,
                "MANZENT": manzent,
                "Variable": var,
                "Actividad económica CAENES": label,
                "Nivel": nivel_key,
                "Personas ocupadas": float(valor_conteo),
                "Total ocupados clasificados CAENES": float(total_ocupados_clasificados),
                "% sobre ocupados clasificados": float(valor_pct)
            })

    # =====================================================
    # DIFERENCIAS DE DISTRIBUCIÓN
    # =====================================================

    diferencia_vs_rm = []
    diferencia_vs_comuna = []

    for i, categoria in enumerate(orden_labels):
        valor_manzana = porcentajes["manzana"][i]
        valor_regional = porcentajes["regional"][i]
        valor_comunal = porcentajes["comunal"][i]

        dif_rm = valor_manzana - valor_regional
        dif_comuna = valor_manzana - valor_comunal

        diferencia_vs_rm.append(float(dif_rm))
        diferencia_vs_comuna.append(float(dif_comuna))

        registros_diferencias_excel.append({
            "Proyecto seleccionado": nombre_proyecto,
            "Comuna proyecto": comuna_nombre,
            "MANZENT": manzent,
            "Actividad económica CAENES": categoria,
            "Diferencia manzana vs Región Metropolitana": dif_rm,
            "Diferencia manzana vs comuna": dif_comuna
        })

    diferencias = {
        "x": [
            "Manzana vs Región Metropolitana",
            "Manzana vs comuna"
        ],
        "y": orden_labels,
        "z": [
            [diferencia_vs_rm[i], diferencia_vs_comuna[i]]
            for i in range(len(orden_labels))
        ]
    }

    payload[nombre_proyecto] = {
        "proyecto": nombre_proyecto,
        "manzent": manzent,
        "comuna": comuna_nombre,
        "cut": cut_comuna,
        "conteos": conteos,
        "porcentajes": porcentajes,
        "diferencias": diferencias
    }

df_detalle = pd.DataFrame(detalle_proyectos)
df_excel = pd.DataFrame(registros_excel)
df_diferencias_excel = pd.DataFrame(registros_diferencias_excel)

df_columnas_usadas = pd.DataFrame([
    {"Indicador": label, "Columna base": col}
    for col, label in VARIABLES_CAENES.items()
])

print("\nDetalle de proyectos encontrados:")
print(df_detalle)

# =========================================================
# GUARDAR EXCEL DE RESPALDO
# =========================================================

ruta_excel = SALIDAS_DIR / "38_resumen_caenes_proyectos.xlsx"

with pd.ExcelWriter(ruta_excel, engine="openpyxl") as writer:
    df_detalle.to_excel(writer, sheet_name="Detalle_proyectos", index=False)
    df_columnas_usadas.to_excel(writer, sheet_name="Columnas_usadas", index=False)
    df_excel.to_excel(writer, sheet_name="Datos_CAENES", index=False)
    df_diferencias_excel.to_excel(writer, sheet_name="Diferencias_CAENES", index=False)

print("\nArchivo Excel creado:")
print(ruta_excel)

# =========================================================
# PREPARAR RANGO LOGARÍTMICO GLOBAL
# =========================================================

log_upper_bound = calcular_rango_log_superior(payload, "conteos")

# =========================================================
# CREAR HTML INTERACTIVO
# =========================================================

plotly_js = get_plotlyjs()
data_json = json.dumps(payload, ensure_ascii=False)

ruta_html = SALIDAS_DIR / "39_interactivo_caenes_proyectos.html"

html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>CAENES - Actividades económicas</title>

    <script>
    {plotly_js}
    </script>

    <style>
        body {{
            margin: 0;
            font-family: Arial, sans-serif;
            color: #0f2a44;
            background: #ffffff;
        }}

        .container {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) 300px;
            gap: 24px;
            padding: 28px;
            box-sizing: border-box;
        }}

        .main {{
            min-width: 0;
        }}

        .header {{
            margin-bottom: 16px;
        }}

        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 700;
            color: #0f2a44;
        }}

        .header p {{
            margin: 8px 0 0 0;
            font-size: 14px;
            color: #44546a;
        }}

        .page-title {{
            font-size: 18px;
            font-weight: 700;
            margin: 16px 0 4px 0;
            color: #0f2a44;
        }}

        .page-subtitle {{
            font-size: 13px;
            color: #44546a;
            margin-bottom: 8px;
        }}

        #plot {{
            width: 100%;
            height: 900px;
        }}

        .sidebar {{
            border-left: 1px solid #e5e7eb;
            padding-left: 20px;
            box-sizing: border-box;
        }}

        .sidebar-card {{
            position: sticky;
            top: 20px;
        }}

        .sidebar h2 {{
            font-size: 18px;
            margin: 0 0 12px 0;
            color: #0f2a44;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 10px 0;
            font-size: 14px;
        }}

        .legend-color {{
            width: 14px;
            height: 14px;
            border-radius: 3px;
            display: inline-block;
        }}

        .control-block {{
            margin-top: 26px;
        }}

        label {{
            display: block;
            font-weight: 700;
            font-size: 13px;
            margin-bottom: 8px;
        }}

        select {{
            width: 100%;
            padding: 9px 10px;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            background: #ffffff;
            color: #0f2a44;
            font-size: 14px;
        }}

        .tab-buttons {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 8px;
        }}

        .tab-button {{
            border: 1px solid #cbd5e1;
            background: #ffffff;
            color: #0f2a44;
            padding: 10px;
            border-radius: 6px;
            cursor: pointer;
            text-align: left;
            font-size: 14px;
        }}

        .tab-button.active {{
            background: #0f2a44;
            color: #ffffff;
            border-color: #0f2a44;
        }}

        .note {{
            margin-top: 22px;
            font-size: 12px;
            color: #64748b;
            line-height: 1.45;
        }}

        @media (max-width: 1100px) {{
            .container {{
                grid-template-columns: 1fr;
            }}

            .sidebar {{
                border-left: none;
                border-top: 1px solid #e5e7eb;
                padding-left: 0;
                padding-top: 18px;
            }}

            .sidebar-card {{
                position: static;
            }}
        }}
    </style>
</head>

<body>
    <div class="container">
        <main class="main">
            <div class="header">
                <h1>Personas ocupadas según actividad económica (CAENES)</h1>
                <p id="subtitle"></p>
            </div>

            <div class="page-title" id="pageTitle"></div>
            <div class="page-subtitle" id="pageSubtitle"></div>

            <div id="plot"></div>
        </main>

        <aside class="sidebar">
            <div class="sidebar-card">
                <h2>Nivel territorial</h2>

                <div class="legend-item">
                    <span class="legend-color" style="background:#4E79A7;"></span>
                    Región Metropolitana
                </div>

                <div class="legend-item">
                    <span class="legend-color" style="background:#F28E2B;"></span>
                    Comuna
                </div>

                <div class="legend-item">
                    <span class="legend-color" style="background:#59A14F;"></span>
                    Manzana / proyecto
                </div>

                <div class="control-block">
                    <label for="projectSelect">Seleccionar proyecto</label>
                    <select id="projectSelect"></select>
                </div>

                <div class="control-block">
                    <label>Página del análisis</label>
                    <div class="tab-buttons">
                        <button class="tab-button active" id="btnConteos">
                            Página 1 — Personas ocupadas por actividad
                        </button>
                        <button class="tab-button" id="btnPorcentajes">
                            Página 2 — Distribución porcentual CAENES
                        </button>
                        <button class="tab-button" id="btnDiferencias">
                            Página 3 — Diferencias de distribución
                        </button>
                    </div>
                </div>

                <div class="control-block">
                    <label for="scaleSelect">Escala del gráfico de conteos</label>
                    <select id="scaleSelect">
                        <option value="log">Escala logarítmica</option>
                        <option value="linear">Escala lineal</option>
                    </select>
                </div>

                <div class="note">
                    CAENES corresponde al Clasificador de Actividades Económicas Nacional para encuestas sociodemográficas. La página 2 muestra la distribución porcentual sobre el total de personas ocupadas clasificadas. La página 3 no representa mejor o peor desempeño, sino diferencias de distribución relativa entre la manzana y los niveles comunal y regional.
                </div>
            </div>
        </aside>
    </div>

    <script>
        const DATA = {data_json};
        const LOG_UPPER_BOUND = {log_upper_bound};

        const LEVELS = [
            {{
                key: "regional",
                name: "Región Metropolitana",
                color: "#4E79A7"
            }},
            {{
                key: "comunal",
                name: "Comuna",
                color: "#F28E2B"
            }},
            {{
                key: "manzana",
                name: "Manzana / proyecto",
                color: "#59A14F"
            }}
        ];

        let currentProject = Object.keys(DATA)[0];
        let currentPage = "conteos";
        let currentScale = "log";

        const projectSelect = document.getElementById("projectSelect");
        const scaleSelect = document.getElementById("scaleSelect");
        const btnConteos = document.getElementById("btnConteos");
        const btnPorcentajes = document.getElementById("btnPorcentajes");
        const btnDiferencias = document.getElementById("btnDiferencias");
        const subtitle = document.getElementById("subtitle");
        const pageTitle = document.getElementById("pageTitle");
        const pageSubtitle = document.getElementById("pageSubtitle");

        Object.keys(DATA).forEach(project => {{
            const option = document.createElement("option");
            option.value = project;
            option.textContent = project;
            projectSelect.appendChild(option);
        }});

        function indicesVisiblesYOrdenados(projectData) {{
            const y = projectData.conteos.y;
            const reg = projectData.conteos.regional;
            const com = projectData.conteos.comunal;
            const man = projectData.conteos.manzana;

            let indices = [];

            for (let i = 0; i < y.length; i++) {{
                const maximo = Math.max(reg[i], com[i], man[i]);
                if (maximo > 0) {{
                    indices.push(i);
                }}
            }}

            indices.sort((a, b) => {{
                const manDiff = man[b] - man[a];
                if (manDiff !== 0) return manDiff;

                const comDiff = com[b] - com[a];
                if (comDiff !== 0) return comDiff;

                return reg[b] - reg[a];
            }});

            return indices;
        }}

        function filtrarSegunIndices(lista, indices) {{
            return indices.map(i => lista[i]);
        }}

        function hoverTemplate(levelKey, page) {{
            const valueFormat = page === "conteos" ? "%{{x:,.0f}}" : "%{{x:.2f}}%";

            if (levelKey === "regional") {{
                return (
                    "<b>Nivel territorial:</b> Región Metropolitana<br>" +
                    "<b>Actividad económica:</b> %{{y}}<br>" +
                    "<b>Valor:</b> " + valueFormat +
                    "<extra></extra>"
                );
            }}

            if (levelKey === "comunal") {{
                return (
                    "<b>Nivel territorial:</b> Comuna<br>" +
                    "<b>Comuna:</b> %{{customdata[0]}}<br>" +
                    "<b>Actividad económica:</b> %{{y}}<br>" +
                    "<b>Valor:</b> " + valueFormat +
                    "<extra></extra>"
                );
            }}

            return (
                "<b>Nivel territorial:</b> Manzana / proyecto<br>" +
                "<b>Proyecto:</b> %{{customdata[0]}}<br>" +
                "<b>Comuna:</b> %{{customdata[1]}}<br>" +
                "<b>MANZENT:</b> %{{customdata[2]}}<br>" +
                "<b>Actividad económica:</b> %{{y}}<br>" +
                "<b>Valor:</b> " + valueFormat +
                "<extra></extra>"
            );
        }}

        function customDataForLevel(levelKey, projectData, largo) {{
            if (levelKey === "regional") {{
                return Array.from({{ length: largo }}, () => []);
            }}

            if (levelKey === "comunal") {{
                return Array.from({{ length: largo }}, () => [projectData.comuna]);
            }}

            return Array.from({{ length: largo }}, () => [
                projectData.proyecto,
                projectData.comuna,
                projectData.manzent
            ]);
        }}

        function buildBarTraces() {{
            const projectData = DATA[currentProject];
            const source = currentPage === "conteos"
                ? projectData.conteos
                : projectData.porcentajes;

            const indices = indicesVisiblesYOrdenados(projectData);
            const y = filtrarSegunIndices(source.y, indices);

            return LEVELS.map(level => {{
                const x = filtrarSegunIndices(source[level.key], indices);

                return {{
                    type: "bar",
                    orientation: "h",
                    x: x,
                    y: y,
                    name: level.name,
                    marker: {{
                        color: level.color
                    }},
                    customdata: customDataForLevel(level.key, projectData, x.length),
                    hovertemplate: hoverTemplate(level.key, currentPage),
                    cliponaxis: false
                }};
            }});
        }}

        function buildDiferenciasTrace() {{
            const projectData = DATA[currentProject];
            const source = projectData.diferencias;

            const indices = indicesVisiblesYOrdenados(projectData);

            const y = filtrarSegunIndices(source.y, indices);
            const z = indices.map(i => source.z[i]);

            const zValues = z.flat();
            const maxAbs = Math.max(...zValues.map(value => Math.abs(value)), 1);

            const text = z.map(row =>
                row.map(value => {{
                    const sign = value > 0 ? "+" : "";
                    return sign + value.toFixed(2) + " pp";
                }})
            );

            return [{{
                type: "heatmap",
                x: source.x,
                y: y,
                z: z,
                text: text,
                texttemplate: "%{{text}}",
                textfont: {{
                    color: "#0f2a44",
                    size: 12
                }},
                zmin: -maxAbs,
                zmax: maxAbs,
                zmid: 0,
                colorscale: [
                    [0.00, "#B2182B"],
                    [0.50, "#F7F7F7"],
                    [1.00, "#2166AC"]
                ],
                colorbar: {{
                    title: "Dif.<br>pp"
                }},
                hovertemplate:
                    "<b>Comparación:</b> %{{x}}<br>" +
                    "<b>Actividad económica:</b> %{{y}}<br>" +
                    "<b>Diferencia:</b> %{{z:.2f}} pp<br>" +
                    "<extra></extra>"
            }}];
        }}

        function buildTraces() {{
            if (currentPage === "diferencias") {{
                return buildDiferenciasTrace();
            }}

            return buildBarTraces();
        }}

        function buildLayout() {{
            const projectData = DATA[currentProject];

            const isConteos = currentPage === "conteos";
            const isPorcentajes = currentPage === "porcentajes";
            const isDiferencias = currentPage === "diferencias";

            let pageTitleText = "";
            let pageSubtitleText = "";

            if (isConteos) {{
                pageTitleText = "Página 1: Personas ocupadas según actividad económica";
                pageSubtitleText = "Comparación de magnitudes absolutas entre Región Metropolitana, comuna y manzana.";
            }}

            if (isPorcentajes) {{
                pageTitleText = "Página 2: Distribución porcentual de la actividad económica";
                pageSubtitleText = "Comparación proporcional sobre el total de personas ocupadas clasificadas según CAENES.";
            }}

            if (isDiferencias) {{
                pageTitleText = "Página 3: Diferencias de distribución de actividad económica";
                pageSubtitleText = "Diferencia en puntos porcentuales entre la distribución de la manzana y los niveles regional y comunal.";
            }}

            subtitle.textContent =
                "Proyecto seleccionado: " +
                projectData.proyecto +
                " | Comuna: " +
                projectData.comuna +
                " | MANZENT: " +
                projectData.manzent;

            pageTitle.textContent = pageTitleText;
            pageSubtitle.textContent = pageSubtitleText;

            scaleSelect.disabled = !isConteos;

            if (isDiferencias) {{
                return {{
                    template: "plotly_white",
                    showlegend: false,
                    margin: {{
                        l: 280,
                        r: 80,
                        t: 30,
                        b: 120
                    }},
                    xaxis: {{
                        title: "Comparación",
                        automargin: true
                    }},
                    yaxis: {{
                        title: "Actividad económica",
                        automargin: true,
                        autorange: "reversed"
                    }},
                    hoverlabel: {{
                        bgcolor: "#0f2a44",
                        font: {{
                            color: "#ffffff"
                        }}
                    }}
                }};
            }}

            const xAxisType = isConteos ? currentScale : "linear";
            const xAxisTitle = isConteos
                ? "Número de personas ocupadas"
                : "% sobre ocupados clasificados";

            const xAxisConfig = {{
                title: xAxisTitle,
                type: xAxisType,
                automargin: true
            }};

            if (isConteos && currentScale === "log") {{
                xAxisConfig.range = [0, LOG_UPPER_BOUND];
            }}

            if (isConteos && currentScale === "linear") {{
                xAxisConfig.rangemode = "tozero";
            }}

            if (isPorcentajes) {{
                xAxisConfig.rangemode = "tozero";
            }}

            return {{
                barmode: "group",
                template: "plotly_white",
                showlegend: false,
                margin: {{
                    l: 280,
                    r: 30,
                    t: 30,
                    b: 80
                }},
                xaxis: xAxisConfig,
                yaxis: {{
                    title: "Actividad económica",
                    automargin: true,
                    autorange: "reversed"
                }},
                hoverlabel: {{
                    bgcolor: "#0f2a44",
                    font: {{
                        color: "#ffffff"
                    }}
                }}
            }};
        }}

        function updateButtons() {{
            btnConteos.classList.remove("active");
            btnPorcentajes.classList.remove("active");
            btnDiferencias.classList.remove("active");

            if (currentPage === "conteos") {{
                btnConteos.classList.add("active");
            }}

            if (currentPage === "porcentajes") {{
                btnPorcentajes.classList.add("active");
            }}

            if (currentPage === "diferencias") {{
                btnDiferencias.classList.add("active");
            }}
        }}

        function updatePlot() {{
            updateButtons();

            const traces = buildTraces();
            const layout = buildLayout();

            const config = {{
                responsive: true,
                displaylogo: false,
                modeBarButtonsToRemove: [
                    "lasso2d",
                    "select2d"
                ]
            }};

            Plotly.react("plot", traces, layout, config);
        }}

        projectSelect.addEventListener("change", event => {{
            currentProject = event.target.value;
            updatePlot();
        }});

        scaleSelect.addEventListener("change", event => {{
            currentScale = event.target.value;
            updatePlot();
        }});

        btnConteos.addEventListener("click", () => {{
            currentPage = "conteos";
            updatePlot();
        }});

        btnPorcentajes.addEventListener("click", () => {{
            currentPage = "porcentajes";
            updatePlot();
        }});

        btnDiferencias.addEventListener("click", () => {{
            currentPage = "diferencias";
            updatePlot();
        }});

        updatePlot();
    </script>
</body>
</html>
"""

with open(ruta_html, "w", encoding="utf-8") as f:
    f.write(html)

print("\nArchivo HTML creado:")
print(ruta_html)

print("\nProceso terminado correctamente.")