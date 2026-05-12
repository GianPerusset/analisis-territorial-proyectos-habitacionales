import json
import pandas as pd
from pathlib import Path
from plotly.offline import get_plotlyjs

# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================

pd.set_option("display.float_format", lambda x: f"{x:,.2f}")
pd.set_option("display.max_columns", 50)
pd.set_option("display.width", 220)

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

VARIABLES_CONTEOS = {
    "n_per": "Personas",
    "n_hog": "Hogares",
    "n_viv_hacinadas": "Viviendas hacinadas",
    "n_deficit_cuantitativo": "Déficit cuantitativo"
}

VARIABLES_NECESARIAS = [
    "n_per",
    "n_hog",
    "n_viv_hacinadas",
    "n_deficit_cuantitativo",
    "n_vp_ocupada"
]

# =========================================================
# FUNCIONES
# =========================================================

def safe_pct(numerador, denominador):
    if pd.isna(denominador) or denominador == 0:
        return 0
    return (numerador / denominador) * 100

def safe_ratio(numerador, denominador):
    if pd.isna(denominador) or denominador == 0:
        return 0
    return numerador / denominador

def convertir_a_float_lista(serie):
    return [float(x) for x in serie]

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
        raise ValueError(f"No existe la columna requerida: {col}")
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

region_rm = df[df["COD_REGION"] == 13].copy()

print("=" * 90)
print("ANÁLISIS INTERACTIVO HABITACIONAL - PROYECTOS")
print("=" * 90)
print("\nBase completa:", df.shape)
print("Región Metropolitana:", region_rm.shape)

# =========================================================
# CONSTRUIR DATOS PARA HTML
# =========================================================

payload = {}
detalle_proyectos = []
registros_excel = []

orden_conteos = list(VARIABLES_CONTEOS.values())

orden_indicadores = [
    "Personas por hogar",
    "Viviendas hacinadas (%)",
    "Déficit cuantitativo (%)"
]

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
        "x": orden_conteos,
        "regional": [],
        "comunal": [],
        "manzana": []
    }

    indicadores = {
        "x": orden_indicadores,
        "regional": [],
        "comunal": [],
        "manzana": []
    }

    for nivel_key, base in bases.items():
        suma = base[VARIABLES_NECESARIAS].sum()

        # -------------------------
        # Conteos absolutos
        # -------------------------
        valores_conteos = [
            suma["n_per"],
            suma["n_hog"],
            suma["n_viv_hacinadas"],
            suma["n_deficit_cuantitativo"]
        ]

        conteos[nivel_key] = convertir_a_float_lista(valores_conteos)

        # -------------------------
        # Indicadores relativos
        # -------------------------
        personas = suma["n_per"]
        hogares = suma["n_hog"]
        viviendas_hacinadas = suma["n_viv_hacinadas"]
        deficit = suma["n_deficit_cuantitativo"]
        viviendas_ocupadas = suma["n_vp_ocupada"]

        valores_indicadores = [
            safe_ratio(personas, hogares),
            safe_pct(viviendas_hacinadas, viviendas_ocupadas),
            safe_pct(deficit, hogares)
        ]

        indicadores[nivel_key] = convertir_a_float_lista(valores_indicadores)

        # -------------------------
        # Excel largo
        # -------------------------
        for indicador, valor in zip(orden_conteos, valores_conteos):
            registros_excel.append({
                "Proyecto seleccionado": nombre_proyecto,
                "Comuna proyecto": comuna_nombre,
                "MANZENT": manzent,
                "Tipo gráfico": "Conteos",
                "Nivel": nivel_key,
                "Indicador": indicador,
                "Valor": float(valor)
            })

        for indicador, valor in zip(orden_indicadores, valores_indicadores):
            registros_excel.append({
                "Proyecto seleccionado": nombre_proyecto,
                "Comuna proyecto": comuna_nombre,
                "MANZENT": manzent,
                "Tipo gráfico": "Indicadores relativos",
                "Nivel": nivel_key,
                "Indicador": indicador,
                "Valor": float(valor)
            })

    payload[nombre_proyecto] = {
        "proyecto": nombre_proyecto,
        "manzent": manzent,
        "comuna": comuna_nombre,
        "cut": cut_comuna,
        "conteos": conteos,
        "indicadores": indicadores
    }

df_detalle = pd.DataFrame(detalle_proyectos)
df_excel = pd.DataFrame(registros_excel)

print("\nDetalle de proyectos encontrados:")
print(df_detalle)

# =========================================================
# GUARDAR EXCEL DE RESPALDO
# =========================================================

ruta_excel = SALIDAS_DIR / "14_resumen_habitacional_proyectos.xlsx"

with pd.ExcelWriter(ruta_excel, engine="openpyxl") as writer:
    df_detalle.to_excel(writer, sheet_name="Detalle_proyectos", index=False)
    df_excel.to_excel(writer, sheet_name="Datos_largos", index=False)

print("\nArchivo Excel creado:")
print(ruta_excel)

# =========================================================
# CREAR HTML INTERACTIVO
# =========================================================

plotly_js = get_plotlyjs()
data_json = json.dumps(payload, ensure_ascii=False)

ruta_html = SALIDAS_DIR / "15_interactivo_habitacional_proyectos.html"

html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Comparación territorial de indicadores habitacionales</title>

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
            height: 720px;
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
                <h1>Comparación territorial de indicadores habitacionales</h1>
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
                            Página 1 — Conteos absolutos
                        </button>
                        <button class="tab-button" id="btnIndicadores">
                            Página 2 — Indicadores relativos
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
                    La escala logarítmica ayuda a comparar región, comuna y manzana en un mismo gráfico.
                    En la página de indicadores relativos, la escala se mantiene lineal porque los valores son tasas o porcentajes.
                </div>
            </div>
        </aside>
    </div>

    <script>
        const DATA = {data_json};

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
        const btnIndicadores = document.getElementById("btnIndicadores");
        const subtitle = document.getElementById("subtitle");
        const pageTitle = document.getElementById("pageTitle");
        const pageSubtitle = document.getElementById("pageSubtitle");

        Object.keys(DATA).forEach(project => {{
            const option = document.createElement("option");
            option.value = project;
            option.textContent = project;
            projectSelect.appendChild(option);
        }});

        function hoverTemplate(levelKey, page) {{
            const valueFormat = page === "conteos" ? "%{{y:,.0f}}" : "%{{y:,.2f}}";

            if (levelKey === "regional") {{
                return (
                    "<b>Nivel territorial:</b> Región Metropolitana<br>" +
                    "<b>Indicador:</b> %{{x}}<br>" +
                    "<b>Valor:</b> " + valueFormat +
                    "<extra></extra>"
                );
            }}

            if (levelKey === "comunal") {{
                return (
                    "<b>Nivel territorial:</b> Comuna<br>" +
                    "<b>Comuna:</b> %{{customdata[0]}}<br>" +
                    "<b>Indicador:</b> %{{x}}<br>" +
                    "<b>Valor:</b> " + valueFormat +
                    "<extra></extra>"
                );
            }}

            return (
                "<b>Nivel territorial:</b> Manzana / proyecto<br>" +
                "<b>Proyecto:</b> %{{customdata[0]}}<br>" +
                "<b>Comuna:</b> %{{customdata[1]}}<br>" +
                "<b>MANZENT:</b> %{{customdata[2]}}<br>" +
                "<b>Indicador:</b> %{{x}}<br>" +
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

        function buildTraces() {{
            const projectData = DATA[currentProject];
            const source = currentPage === "conteos"
                ? projectData.conteos
                : projectData.indicadores;

            const x = source.x;

            return LEVELS.map(level => {{
                const y = source[level.key];

                return {{
                    type: "bar",
                    x: x,
                    y: y,
                    name: level.name,
                    marker: {{
                        color: level.color
                    }},
                    customdata: customDataForLevel(level.key, projectData, y.length),
                    hovertemplate: hoverTemplate(level.key, currentPage),
                    cliponaxis: false
                }};
            }});
        }}

        function buildLayout() {{
            const projectData = DATA[currentProject];

            const isConteos = currentPage === "conteos";

            const yAxisType = isConteos ? currentScale : "linear";
            const yAxisTitle = isConteos ? "Cantidad" : "Valor del indicador";

            const pageTitleText = isConteos
                ? "Página 1: Conteos absolutos"
                : "Página 2: Indicadores relativos";

            const pageSubtitleText = isConteos
                ? "Comparación de magnitudes absolutas entre Región Metropolitana, comuna y manzana."
                : "Comparación proporcional para observar intensidad territorial, no solo magnitud.";

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

            const yAxisConfig = {{
                title: yAxisTitle,
                type: yAxisType,
                automargin: true
            }};

            if (isConteos && currentScale === "log") {{
                yAxisConfig.range = [0, 7];
            }}

            if (isConteos && currentScale === "linear") {{
                yAxisConfig.rangemode = "tozero";
            }}

            if (!isConteos) {{
                yAxisConfig.rangemode = "tozero";
            }}

            return {{
                barmode: "group",
                template: "plotly_white",
                showlegend: false,
                margin: {{
                    l: 80,
                    r: 30,
                    t: 30,
                    b: 120
                }},
                xaxis: {{
                    title: "Indicador",
                    tickangle: -15,
                    automargin: true
                }},
                yaxis: yAxisConfig,
                hoverlabel: {{
                    bgcolor: "#0f2a44",
                    font: {{
                        color: "#ffffff"
                    }}
                }}
            }};
        }}

        function updateButtons() {{
            if (currentPage === "conteos") {{
                btnConteos.classList.add("active");
                btnIndicadores.classList.remove("active");
            }} else {{
                btnConteos.classList.remove("active");
                btnIndicadores.classList.add("active");
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

        btnIndicadores.addEventListener("click", () => {{
            currentPage = "indicadores";
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