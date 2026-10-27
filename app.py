"""
Aplicación web interactiva para el análisis de la mortalidad en Colombia, 2019.
Fuente: DANE - Estadísticas Vitales (defunciones no fetales 2019).

Ejecutar localmente:  python app.py   ->  http://127.0.0.1:8050
En producción (Render): gunicorn app:server
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash.dash_table.Format import Format
from dash import Dash, Input, Output, State, ctx, dash_table, dcc, html, no_update

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"

# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------
df = pd.read_csv(
    DATA / "processed" / "mortalidad_2019.csv.gz",
    dtype={"COD_DANE": str, "COD_DEPARTAMENTO": str},
)
for col in ["DEPARTAMENTO", "MUNICIPIO", "SEXO_NOMBRE", "CATEGORIA_EDAD", "MANERA_MUERTE"]:
    df[col] = df[col].astype("category")

with open(DATA / "colombia_departamentos.geojson", encoding="utf-8") as f:
    GEOJSON = json.load(f)

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
MESES_LARGOS = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
                "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

ORDEN_EDAD = [
    ("Mortalidad neonatal", "Menor de 1 mes"),
    ("Mortalidad infantil", "1 a 11 meses"),
    ("Primera infancia", "1 a 4 años"),
    ("Niñez", "5 a 14 años"),
    ("Adolescencia", "15 a 19 años"),
    ("Juventud", "20 a 29 años"),
    ("Adultez temprana", "30 a 44 años"),
    ("Adultez intermedia", "45 a 59 años"),
    ("Vejez", "60 a 84 años"),
    ("Longevidad / Centenarios", "85 a 100+ años"),
    ("Edad desconocida", "Sin información"),
]

COLOR_SEXO = {"Hombre": "#2a6f97", "Mujer": "#e07a5f", "Indeterminado": "#9a9a9a"}
COLOR_PRINCIPAL = "#8c2f39"
PLANTILLA = "plotly_white"
FUENTE = dict(family="Inter, Segoe UI, Arial, sans-serif", size=13, color="#2b2b2b")

DEPARTAMENTOS = sorted(df["DEPARTAMENTO"].cat.categories)
MANERAS = sorted(df["MANERA_MUERTE"].cat.categories)
SEXOS = ["Hombre", "Mujer", "Indeterminado"]


def nombre_corto(nombre: str) -> str:
    """Nombre de departamento legible para ejes (título y abreviatura de San Andrés)."""
    if nombre.upper().startswith("ARCHIPIÉLAGO"):
        return "San Andrés y Prov."
    return nombre.title().replace(" D.C.", " D.C.").replace("Del ", "del ").replace("De ", "de ")


def estilo(fig: go.Figure, alto: int = 420) -> go.Figure:
    fig.update_layout(
        template=PLANTILLA, font=FUENTE, height=alto,
        margin=dict(l=20, r=20, t=60, b=20),
        title_font=dict(size=16, color="#1f1f1f"),
        hoverlabel=dict(font_size=13),
    )
    return fig


def filtrar(sexos, maneras, meses, depto=None) -> pd.DataFrame:
    d = df
    if sexos:
        d = d[d["SEXO_NOMBRE"].isin(sexos)]
    if maneras:
        d = d[d["MANERA_MUERTE"].isin(maneras)]
    if meses:
        d = d[d["MES"].between(meses[0], meses[1])]
    if depto:
        d = d[d["DEPARTAMENTO"] == depto]
    return d


def vacio(titulo: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text="Sin datos para los filtros seleccionados", showarrow=False,
                       font=dict(size=14, color="#777"))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(title=titulo)
    return estilo(fig)


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------
def fig_mapa(d: pd.DataFrame, depto_sel=None) -> go.Figure:
    agg = d.groupby(["COD_DEPARTAMENTO", "DEPARTAMENTO"], observed=True).size().reset_index(name="Muertes")
    if agg.empty:
        return vacio("Total de muertes por departamento")
    fig = px.choropleth(
        agg, geojson=GEOJSON, locations="COD_DEPARTAMENTO",
        featureidkey="properties.DPTO_CCDGO", color="Muertes",
        hover_name="DEPARTAMENTO", hover_data={"COD_DEPARTAMENTO": False, "Muertes": ":,"},
        color_continuous_scale="Reds",
        title="Distribución total de muertes por departamento, 2019",
    )
    fig.update_geos(visible=False, projection_type="mercator",
                    lonaxis_range=[-82.2, -66.5], lataxis_range=[-4.4, 13.6])
    fig.update_layout(coloraxis_colorbar=dict(title="Muertes", tickformat=","))
    if depto_sel:
        sel = agg[agg["DEPARTAMENTO"] == depto_sel]
        if not sel.empty:
            fig.add_trace(go.Choropleth(
                geojson=GEOJSON, locations=sel["COD_DEPARTAMENTO"], z=[1] * len(sel),
                featureidkey="properties.DPTO_CCDGO", showscale=False,
                colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
                marker_line_color="#111", marker_line_width=3, hoverinfo="skip",
            ))
    estilo(fig, 560)
    fig.update_layout(margin=dict(l=0, r=0, t=60, b=0))
    return fig


def fig_lineas(d: pd.DataFrame, titulo_extra: str) -> go.Figure:
    agg = d.groupby("MES").size().reindex(range(1, 13), fill_value=0).reset_index(name="Muertes")
    agg["Mes"] = MESES
    agg["MesLargo"] = MESES_LARGOS
    fig = px.line(agg, x="Mes", y="Muertes", markers=True,
                  title=f"Total de muertes por mes{titulo_extra}",
                  custom_data=["MesLargo"])
    fig.update_traces(line=dict(color=COLOR_PRINCIPAL, width=3), marker=dict(size=9),
                      hovertemplate="%{customdata[0]}: <b>%{y:,}</b> muertes<extra></extra>")
    prom = agg["Muertes"].mean()
    fig.add_hline(y=prom, line_dash="dot", line_color="#888",
                  annotation_text=f"Promedio mensual: {prom:,.0f}", annotation_position="bottom right")
    fig.update_xaxes(title="Mes de defunción")
    fig.update_yaxes(title="Número de muertes", tickformat=",", rangemode="tozero")
    return estilo(fig, 560)


def fig_violentas(d: pd.DataFrame, criterio: str, titulo_extra: str) -> go.Figure:
    if criterio == "X95":
        h = d[d["COD_MUERTE"].str.startswith("X95")]
        sub = "homicidios por arma de fuego (CIE-10 X95)"
    else:
        h = d[d["MANERA_MUERTE"] == "Homicidio"]
        sub = "todos los homicidios (manera de muerte = Homicidio)"
    agg = (h.groupby(["MUNICIPIO", "DEPARTAMENTO"], observed=True).size()
             .reset_index(name="Homicidios").sort_values("Homicidios", ascending=False).head(5))
    titulo = f"5 ciudades más violentas: {sub}{titulo_extra}"
    if agg.empty:
        return vacio(titulo)
    agg["Ciudad"] = agg["MUNICIPIO"].astype(str).str.title()
    fig = px.bar(agg.iloc[::-1], x="Homicidios", y="Ciudad", orientation="h", text="Homicidios",
                 title=titulo, hover_data={"DEPARTAMENTO": True, "Ciudad": False})
    fig.update_traces(marker_color=COLOR_PRINCIPAL, texttemplate="%{text:,}", textposition="outside",
                      cliponaxis=False)
    fig.update_xaxes(title="Número de homicidios", tickformat=",")
    fig.update_yaxes(title="Ciudad (municipio)")
    return estilo(fig)


def fig_menor(d: pd.DataFrame, titulo_extra: str) -> go.Figure:
    agg = (d.groupby(["MUNICIPIO", "DEPARTAMENTO"], observed=True).size()
             .reset_index(name="Muertes"))
    agg = agg[agg["Muertes"] > 0].sort_values(["Muertes", "MUNICIPIO"]).head(10)
    titulo = f"10 ciudades con menor mortalidad{titulo_extra}"
    if agg.empty:
        return vacio(titulo)
    agg["Ciudad"] = agg["MUNICIPIO"].astype(str).str.title() + " (" + agg["DEPARTAMENTO"].astype(str).str.title() + ")"
    fig = px.pie(agg, names="Ciudad", values="Muertes", title=titulo, hole=0.35,
                 color_discrete_sequence=px.colors.qualitative.Safe)
    fig.update_traces(textinfo="value", textposition="inside",
                      hovertemplate="%{label}<br><b>%{value}</b> muerte(s)<br>%{percent} del grupo<extra></extra>")
    fig.update_layout(legend=dict(title="Ciudad (departamento)", font=dict(size=11)))
    return estilo(fig, 460)


def tabla_causas(d: pd.DataFrame):
    agg = (d.groupby(["COD_MUERTE", "NOMBRE_CAUSA"]).size().reset_index(name="Total")
             .sort_values("Total", ascending=False).head(10))
    total = len(d)
    agg.insert(0, "Puesto", range(1, len(agg) + 1))
    agg["% del total"] = (agg["Total"] / total * 100).round(2) if total else 0
    agg = agg.rename(columns={"COD_MUERTE": "Código CIE-10", "NOMBRE_CAUSA": "Causa de muerte"})
    return agg.to_dict("records")


def fig_apiladas(d: pd.DataFrame, modo: str) -> go.Figure:
    agg = d.groupby(["DEPARTAMENTO", "SEXO_NOMBRE"], observed=True).size().reset_index(name="Muertes")
    if agg.empty:
        return vacio("Muertes por sexo en cada departamento")
    agg["DEPARTAMENTO"] = agg["DEPARTAMENTO"].astype(str).map(nombre_corto)
    orden = agg.groupby("DEPARTAMENTO")["Muertes"].sum().sort_values(ascending=False).index.tolist()
    if modo == "pct":
        agg["Valor"] = agg["Muertes"] / agg.groupby("DEPARTAMENTO")["Muertes"].transform("sum") * 100
        ytitulo, fmt = "Porcentaje de muertes (%)", ".1f"
    else:
        agg["Valor"] = agg["Muertes"]
        ytitulo, fmt = "Número de muertes", ","
    fig = px.bar(agg, x="DEPARTAMENTO", y="Valor", color="SEXO_NOMBRE",
                 category_orders={"DEPARTAMENTO": orden, "SEXO_NOMBRE": SEXOS},
                 color_discrete_map=COLOR_SEXO, custom_data=["SEXO_NOMBRE", "Muertes"],
                 title="Total de muertes por sexo en cada departamento, 2019")
    fig.update_traces(hovertemplate="%{x}<br>%{customdata[0]}: <b>%{customdata[1]:,}</b> muertes"
                                    + ("<br>%{y:.1f}% del departamento" if modo == "pct" else "")
                                    + "<extra></extra>")
    fig.update_layout(barmode="stack", legend=dict(title="Sexo", orientation="h", y=1.08, x=1, xanchor="right"))
    fig.update_xaxes(title="Departamento", tickangle=-45)
    fig.update_yaxes(title=ytitulo, tickformat=fmt)
    estilo(fig, 520)
    fig.update_layout(margin=dict(l=20, r=20, t=80, b=20))
    return fig


def fig_histograma(d: pd.DataFrame, titulo_extra: str) -> go.Figure:
    conteo = d["CATEGORIA_EDAD"].value_counts()
    agg = pd.DataFrame({
        "Categoría": [c for c, _ in ORDEN_EDAD],
        "Rango": [r for _, r in ORDEN_EDAD],
    })
    agg["Muertes"] = agg["Categoría"].map(conteo).fillna(0).astype(int)
    agg["Etiqueta"] = agg["Categoría"] + "<br>(" + agg["Rango"] + ")"
    total = agg["Muertes"].sum()
    agg["Pct"] = agg["Muertes"] / total * 100 if total else 0
    fig = go.Figure(go.Bar(
        x=agg["Etiqueta"], y=agg["Muertes"], marker_color=COLOR_PRINCIPAL,
        marker_line_color="white", marker_line_width=1,
        text=agg["Muertes"], texttemplate="%{text:,}", textposition="outside", cliponaxis=False,
        customdata=agg[["Pct"]], hovertemplate="%{x}<br><b>%{y:,}</b> muertes (%{customdata[0]:.1f}%)<extra></extra>",
    ))
    fig.update_layout(bargap=0.02, title=f"Distribución de muertes por grupo de edad (GRUPO_EDAD1){titulo_extra}")
    fig.update_xaxes(title="Grupo de edad (ciclo de vida)", tickfont=dict(size=11))
    fig.update_yaxes(title="Número de muertes", tickformat=",")
    estilo(fig, 480)
    return fig


# ---------------------------------------------------------------------------
# Interfaz
# ---------------------------------------------------------------------------
app = Dash(__name__, title="Mortalidad en Colombia 2019")
server = app.server  # para gunicorn


def tarjeta(titulo, valor_id):
    return html.Div(className="kpi", children=[
        html.Span(titulo, className="kpi-titulo"),
        html.Span(id=valor_id, className="kpi-valor"),
    ])


def panel(*hijos, clase="panel"):
    return html.Div(className=clase, children=list(hijos))


COLUMNAS_TABLA = [
    {"name": "Puesto", "id": "Puesto"},
    {"name": "Código CIE-10", "id": "Código CIE-10"},
    {"name": "Causa de muerte", "id": "Causa de muerte"},
    {"name": "Total de casos", "id": "Total", "type": "numeric",
     "format": Format().group(True)},
    {"name": "% del total", "id": "% del total", "type": "numeric"},
]

app.layout = html.Div(className="contenedor", children=[
    html.Header(className="encabezado", children=[
        html.Div([
            html.H1("Mortalidad en Colombia, 2019"),
            html.P("Análisis interactivo de las defunciones no fetales registradas por el DANE "
                   "(Estadísticas Vitales). Use los filtros para explorar los datos; haga clic en un "
                   "departamento del mapa para enfocar el resto de los gráficos en él."),
        ]),
    ]),

    html.Section(className="filtros", children=[
        html.Div(className="filtro", children=[
            html.Label("Departamento"),
            dcc.Dropdown(id="f-depto", options=[{"label": d.title(), "value": d} for d in DEPARTAMENTOS],
                         placeholder="Toda Colombia", clearable=True),
        ]),
        html.Div(className="filtro", children=[
            html.Label("Sexo"),
            dcc.Checklist(id="f-sexo", options=SEXOS, value=SEXOS, inline=True, className="check"),
        ]),
        html.Div(className="filtro", children=[
            html.Label("Manera de muerte"),
            dcc.Dropdown(id="f-manera", options=MANERAS, multi=True, placeholder="Todas"),
        ]),
        html.Div(className="filtro filtro-ancho", children=[
            html.Label("Meses"),
            dcc.RangeSlider(id="f-meses", min=1, max=12, step=1, value=[1, 12],
                            marks={i + 1: m for i, m in enumerate(MESES)}),
        ]),
        html.Button("Restablecer filtros", id="btn-reset", className="boton"),
    ]),

    html.Section(className="kpis", children=[
        tarjeta("Total de muertes", "k-total"),
        tarjeta("Hombres", "k-hombres"),
        tarjeta("Mujeres", "k-mujeres"),
        tarjeta("Homicidios", "k-homicidios"),
        tarjeta("Mes con más muertes", "k-mes"),
    ]),

    html.Div(className="fila", children=[
        panel(dcc.Graph(id="g-mapa", config={"displaylogo": False, "topojsonURL": "/assets/topojson/"}), clase="panel ancho-5"),
        panel(dcc.Graph(id="g-lineas", config={"displaylogo": False}), clase="panel ancho-7"),
    ]),

    html.Div(className="fila", children=[
        panel(
            html.Div(className="control-graf", children=[
                html.Label("Criterio de violencia:"),
                dcc.RadioItems(id="f-criterio", value="X95", inline=True, options=[
                    {"label": "Arma de fuego (X95)", "value": "X95"},
                    {"label": "Todos los homicidios", "value": "TODOS"},
                ]),
            ]),
            dcc.Graph(id="g-violentas", config={"displaylogo": False}),
            clase="panel ancho-6"),
        panel(dcc.Graph(id="g-menor", config={"displaylogo": False}),
              html.P(id="nota-menor", className="nota"), clase="panel ancho-6"),
    ]),

    panel(
        html.H3("10 principales causas de muerte"),
        html.P(id="sub-tabla", className="nota"),
        dash_table.DataTable(
            id="t-causas", columns=COLUMNAS_TABLA, sort_action="native",
            style_as_list_view=True,
            style_header={"backgroundColor": "#8c2f39", "color": "white", "fontWeight": "600"},
            style_cell={"fontFamily": "Inter, Segoe UI, Arial", "fontSize": 13, "padding": "8px",
                        "textAlign": "left", "whiteSpace": "normal", "height": "auto"},
            style_cell_conditional=[{"if": {"column_id": c}, "textAlign": "right", "width": "110px"}
                                    for c in ["Total", "% del total", "Puesto"]],
            style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#faf6f6"}],
        ),
    ),

    panel(
        html.Div(className="control-graf", children=[
            html.Label("Mostrar:"),
            dcc.RadioItems(id="f-modo", value="abs", inline=True, options=[
                {"label": "Número de muertes", "value": "abs"},
                {"label": "Porcentaje por departamento", "value": "pct"},
            ]),
        ]),
        dcc.Graph(id="g-apiladas", config={"displaylogo": False}),
    ),

    panel(dcc.Graph(id="g-histograma", config={"displaylogo": False})),

    html.Footer(className="pie", children=[
        "Fuente: DANE, Estadísticas Vitales (EEVV) 2019 — defunciones no fetales; catálogo CIE-10; "
        "DIVIPOLA. ",
        html.A("microdatos.dane.gov.co/index.php/catalog/696",
               href="https://microdatos.dane.gov.co/index.php/catalog/696", target="_blank"),
    ]),
])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------
@app.callback(
    Output("f-depto", "value"),
    Output("f-sexo", "value"),
    Output("f-manera", "value"),
    Output("f-meses", "value"),
    Input("g-mapa", "clickData"),
    Input("btn-reset", "n_clicks"),
    State("f-depto", "value"),
    prevent_initial_call=True,
)
def seleccionar_depto(click, _n, actual):
    if ctx.triggered_id == "btn-reset":
        return None, SEXOS, [], [1, 12]
    if click and click.get("points"):
        nombre = click["points"][0].get("hovertext")
        if nombre:
            return (None if nombre == actual else nombre), no_update, no_update, no_update
    return no_update, no_update, no_update, no_update


@app.callback(
    Output("k-total", "children"), Output("k-hombres", "children"), Output("k-mujeres", "children"),
    Output("k-homicidios", "children"), Output("k-mes", "children"),
    Output("g-mapa", "figure"), Output("g-lineas", "figure"), Output("g-violentas", "figure"),
    Output("g-menor", "figure"), Output("nota-menor", "children"),
    Output("t-causas", "data"), Output("sub-tabla", "children"),
    Output("g-apiladas", "figure"), Output("g-histograma", "figure"),
    Input("f-depto", "value"), Input("f-sexo", "value"), Input("f-manera", "value"),
    Input("f-meses", "value"), Input("f-criterio", "value"), Input("f-modo", "value"),
)
def actualizar(depto, sexos, maneras, meses, criterio, modo):
    nacional = filtrar(sexos, maneras, meses)
    d = nacional[nacional["DEPARTAMENTO"] == depto] if depto else nacional
    extra = f" — {depto.title()}" if depto else ""

    total = len(d)
    hombres = int((d["SEXO_NOMBRE"] == "Hombre").sum())
    mujeres = int((d["SEXO_NOMBRE"] == "Mujer").sum())
    homic = int((d["MANERA_MUERTE"] == "Homicidio").sum())
    por_mes = d.groupby("MES").size()
    mes_max = f"{MESES_LARGOS[por_mes.idxmax() - 1]} ({por_mes.max():,})" if not por_mes.empty else "—"

    menor = d.groupby(["MUNICIPIO"], observed=True).size()
    menor = menor[menor > 0]
    n_min = int((menor == menor.min()).sum()) if not menor.empty else 0
    nota = (f"Nota: {n_min} municipios comparten el mínimo de {menor.min()} defunción(es); "
            "los empates se ordenan alfabéticamente." if n_min > 10 else
            "Se cuentan solo municipios con al menos una defunción registrada.")

    sub = (f"Ordenadas de mayor a menor sobre {total:,} defunciones{extra}. "
           "Haga clic en el encabezado de una columna para reordenar.")

    return (
        f"{total:,}", f"{hombres:,}", f"{mujeres:,}", f"{homic:,}", mes_max,
        fig_mapa(nacional, depto), fig_lineas(d, extra), fig_violentas(d, criterio, extra),
        fig_menor(d, extra), nota,
        tabla_causas(d), sub,
        fig_apiladas(nacional, modo), fig_histograma(d, extra),
    )


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)
