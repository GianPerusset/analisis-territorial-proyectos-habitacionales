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
# VARIABLES REALES DE TRANSPORTE
# =========================================================
# Columnas detectadas en tu base:
# n_transporte_auto
# n_transporte_publico
# n_transporte_camina
# n_transporte_bicicleta
# n_transporte_motocicleta
# n_transporte_cab_lan_bote
# n_transporte_otros
#
# Denominador:
# Se calcula como la suma de estas categorías.
# Corresponde a personas clasificadas según medio de transporte.

VARIABLES_TRANSPORTE = {
    "Transporte público": ["n_transporte_publico"],
    "Auto particular": ["n_transporte_auto"],
    "Caminando": ["n_transporte_camina"],
    "Otro medio": ["n_transporte_otros", "n_transporte_cab_lan_bote"],
    "Bicicleta": ["n_transporte_bicicleta"],
    "Motocicleta": ["n_transporte_motocicleta"]
}

VARIABLES_NECESARIAS = sorted(
    list({col for columnas in VARIABLES_TRANSPORTE.values() for col in columnas})
)

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

# Validar columnas requeridas
for col in VARIABLES_NECESARIAS:
    if col not in df.columns:
        print("\nColumnas de transporte encontradas en la base:")
        for c in df.columns:
            if "transporte" in c.lower():
                print(" -", c)

        raise ValueError(f"No existe la columna requerida: {col}")

    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

region_rm = df[df["COD_REGION"] == 13].copy()

print("=" * 90)
print("ANÁLISIS INTERACTIVO TRANSPORTE - PROYECTOS")
print("=" * 90)
print("\nBase completa:", df.shape)
print("Región Metropolitana:", region_rm.shape)

print("\nColumnas utilizadas:")
for indicador, columnas in VARIABLES_TRANSPORTE.items():
    print(f"{indicador}: {', '.join(columnas)}")

# =========================================================
# CONSTRUIR DATOS PARA HTML
# =========================================================

payload = {}
detalle_proyectos = []
registros_excel = []
registros_brechas_excel = []

orden_labels = list(VARIABLES_TRANSPORTE.keys())

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

        valores_conteos = []

        for indicador, columnas in VARIABLES_TRANSPORTE.items():
            valor = sum(float(suma[col]) for col in columnas)
            valores_conteos.append(valor)

        total_personas_clasificadas = float(sum(valores_conteos))

        valores_porcentajes = [
            safe_pct(valor, total_personas_clasificadas)
            for valor in valores_conteos
        ]

        conteos[nivel_key] = convertir_a_float_lista(valores_conteos)
        porcentajes[nivel_key] = convertir_a_float_lista(valores_porcentajes)

        for indicador, columnas, valor_conteo, valor_pct in zip(
            orden_labels,
            VARIABLES_TRANSPORTE.values(),
            valores_conteos,
            valores_porcentajes
        ):
            registros_excel.append({
                "Proyecto seleccionado": nombre_proyecto,
                "Comuna proyecto": comuna_nombre,
                "MANZENT": manzent,
                "Medio de transporte": indicador,
                "Columnas base": ", ".join(columnas),
                "Nivel": nivel_key,
                "Personas": float(valor_conteo),
                "Personas clasificadas": float(total_personas_clasificadas),
                "% sobre personas clasificadas": float(valor_pct)
            })

    # =====================================================
    # BRECHAS PARA MATRIZ DE COLOR
    # =====================================================

    brecha_vs_rm = []
    brecha_vs_comuna = []

    for i, categoria in enumerate(orden_labels):
        valor_manzana = porcentajes["manzana"][i]
        valor_regional = porcentajes["regional"][i]
        valor_comunal = porcentajes["comunal"][i]

        brecha_rm = valor_manzana - valor_regional
        brecha_comuna = valor_manzana - valor_comunal

        brecha_vs_rm.append(float(brecha_rm))
        brecha_vs_comuna.append(float(brecha_comuna))

        registros_brechas_excel.append({
            "Proyecto seleccionado": nombre_proyecto,
            "Comuna proyecto": comuna_nombre,
            "MANZENT": manzent,
            "Medio de transporte": categoria,
            "Brecha manzana vs Región Metropolitana": brecha_rm,
            "Brecha manzana vs comuna": brecha_comuna
        })

    brechas = {
        "x": [
            "Manzana vs Región Metropolitana",
            "Manzana vs comuna"
        ],
        "y": orden_labels,
        "z": [
            [brecha_vs_rm[i], brecha_vs_comuna[i]]
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
        "brechas": brechas
    }

df_detalle = pd.DataFrame(detalle_proyectos)
df_excel = pd.DataFrame(registros_excel)
df_brechas_excel = pd.DataFrame(registros_brechas_excel)

df_columnas_usadas = pd.DataFrame([
    {
        "Medio de transporte": indicador,
        "Columnas base": ", ".join(columnas)
    }
    for indicador, columnas in VARIABLES_TRANSPORTE.items()
])

print("\nDetalle de proyectos encontrados:")
print(df_detalle)

# =========================================================
# GUARDAR EXCEL DE RESPALDO
# =========================================================

ruta_excel = SALIDAS_DIR / "34_resumen_transporte_proyectos.xlsx"

with pd.ExcelWriter(ruta_excel, engine="openpyxl") as writer:
    df_detalle.to_excel(writer, sheet_name="Detalle_proyectos", index=False)
    df_columnas_usadas.to_excel(writer, sheet_name="Columnas_usadas", index=False)
    df_excel.to_excel(writer, sheet_name="Datos_transporte", index=False)
    df_brechas_excel.to_excel(writer, sheet_name="Brechas_transporte", index=False)

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

ruta_html = SALIDAS_DIR / "35_interactivo_transporte_proyectos.html"

html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Medio de transporte usado por personas que trabajan fuera de su vivienda</title>

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
                <h1>Medio de transporte usado por personas que trabajan fuera de su vivienda</h1>
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
                            Página 1 — Personas por medio de transporte
                        </button>
                        <button class="tab-button" id="btnPorcentajes">
                            Página 2 — % sobre personas clasificadas
                        </button>
                        <button class="tab-button" id="btnBrechas">
                            Página 3 — Matriz de color de brechas
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
                    La página 2 muestra la distribución porcentual del medio de transporte usado por personas que trabajan fuera de su vivienda, sobre el total de personas clasificadas en cada nivel territorial. “Otro medio” agrupa otros medios y caballo/lancha/bote.
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
        const btnBrechas = document.getElementById("btnBrechas");
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
            const valueFormat = page === "conteos" ? "%{{x:,.0f}}" : "%{{x:.2f}}%";

            if (levelKey === "regional") {{
                return (
                    "<b>Nivel territorial:</b> Región Metropolitana<br>" +
                    "<b>Medio de transporte:</b> %{{y}}<br>" +
                    "<b>Valor:</b> " + valueFormat +
                    "<extra></extra>"
                );
            }}

            if (levelKey === "comunal") {{
                return (
                    "<b>Nivel territorial:</b> Comuna<br>" +
                    "<b>Comuna:</b> %{{customdata[0]}}<br>" +
                    "<b>Medio de transporte:</b> %{{y}}<br>" +
                    "<b>Valor:</b> " + valueFormat +
                    "<extra></extra>"
                );
            }}

            return (
                "<b>Nivel territorial:</b> Manzana / proyecto<br>" +
                "<b>Proyecto:</b> %{{customdata[0]}}<br>" +
                "<b>Comuna:</b> %{{customdata[1]}}<br>" +
                "<b>MANZENT:</b> %{{customdata[2]}}<br>" +
                "<b>Medio de transporte:</b> %{{y}}<br>" +
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

            const y = source.y;

            return LEVELS.map(level => {{
                const x = source[level.key];

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

        function buildBrechaTrace() {{
            const projectData = DATA[currentProject];
            const source = projectData.brechas;

            const z = source.z;
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
                y: source.y,
                z: z,
                text: text,
                texttemplate: "%{{text}}",
                textfont: {{
                    color: "#0f2a44",
                    size: 13
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
                    title: "Brecha<br>pp"
                }},
                hovertemplate:
                    "<b>Comparación:</b> %{{x}}<br>" +
                    "<b>Medio de transporte:</b> %{{y}}<br>" +
                    "<b>Brecha:</b> %{{z:.2f}} pp<br>" +
                    "<extra></extra>"
            }}];
        }}

        function buildTraces() {{
            if (currentPage === "brechas") {{
                return buildBrechaTrace();
            }}

            return buildBarTraces();
        }}

        function buildLayout() {{
            const projectData = DATA[currentProject];

            const isConteos = currentPage === "conteos";
            const isPorcentajes = currentPage === "porcentajes";
            const isBrechas = currentPage === "brechas";

            let pageTitleText = "";
            let pageSubtitleText = "";

            if (isConteos) {{
                pageTitleText = "Página 1: Personas por medio de transporte";
                pageSubtitleText = "Comparación de magnitudes absolutas entre Región Metropolitana, comuna y manzana.";
            }}

            if (isPorcentajes) {{
                pageTitleText = "Página 2: Distribución porcentual del medio de transporte";
                pageSubtitleText = "Comparación proporcional sobre personas clasificadas.";
            }}

            if (isBrechas) {{
                pageTitleText = "Página 3: Matriz de color de brechas por medio de transporte";
                pageSubtitleText = "Brecha porcentual de la manzana respecto de la Región Metropolitana y su comuna.";
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

            if (isBrechas) {{
                return {{
                    template: "plotly_white",
                    showlegend: false,
                    margin: {{
                        l: 240,
                        r: 80,
                        t: 30,
                        b: 120
                    }},
                    xaxis: {{
                        title: "Comparación",
                        automargin: true
                    }},
                    yaxis: {{
                        title: "Medio de transporte",
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
                ? "Número de personas"
                : "% sobre personas clasificadas";

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
                    l: 240,
                    r: 30,
                    t: 30,
                    b: 80
                }},
                xaxis: xAxisConfig,
                yaxis: {{
                    title: "Medio de transporte",
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
            btnBrechas.classList.remove("active");

            if (currentPage === "conteos") {{
                btnConteos.classList.add("active");
            }}

            if (currentPage === "porcentajes") {{
                btnPorcentajes.classList.add("active");
            }}

            if (currentPage === "brechas") {{
                btnBrechas.classList.add("active");
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

        btnBrechas.addEventListener("click", () => {{
            currentPage = "brechas";
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