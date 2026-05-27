from __future__ import annotations
 
from datetime import datetime, timedelta
from typing import Optional, Tuple
import unicodedata
 
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
 
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

try:
    import psycopg2
except Exception:
    psycopg2 = None
 
 
# ==========================================================
# Configuración general
# ==========================================================
st.set_page_config(
    page_title="Cloud Election Sentinel",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="expanded",
)
 
PRIMARY = "#003C7D"
SECONDARY = "#0B5CAB"
LIGHT_BLUE = "#EAF4FF"
TEXT_DARK = "#1F2937"
 
 
# ==========================================================
# Estilos tipo dashboard ONPE
# ==========================================================
st.markdown(
    f"""
    <style>
        .main {{
            background: #F6F8FB;
        }}
        section[data-testid="stSidebar"] {{
            background: #FFFFFF;
            border-right: 1px solid #E5E7EB;
        }}
        .block-container {{
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }}
        .top-card {{
            background: white;
            border: 1px solid #E5E7EB;
            border-radius: 14px;
            padding: 18px 22px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.05);
        }}
        .metric-card {{
            background: white;
            border: 1px solid #E5E7EB;
            border-radius: 14px;
            padding: 16px;
            min-height: 118px;
            box-shadow: 0 2px 7px rgba(0,0,0,0.04);
        }}
        .metric-title {{
            color: #334155;
            font-size: 0.82rem;
            font-weight: 600;
        }}
        .metric-value {{
            color: {TEXT_DARK};
            font-size: 2rem;
            font-weight: 800;
            margin-top: 6px;
        }}
        .metric-help {{
            color: #64748B;
            font-size: 0.78rem;
            margin-top: 2px;
        }}
        .section-card {{
            background: white;
            border: 1px solid #E5E7EB;
            border-radius: 14px;
            padding: 18px;
            box-shadow: 0 2px 7px rgba(0,0,0,0.04);
        }}
        .small-note {{
            background: #EDF6FF;
            color: {PRIMARY};
            padding: 10px 12px;
            border-radius: 8px;
            font-size: 0.82rem;
        }}
        .status-pill {{
            background: #E8F8EE;
            color: #18864B;
            border: 1px solid #B7E6C8;
            border-radius: 999px;
            display: inline-block;
            padding: 6px 12px;
            font-size: 0.82rem;
            font-weight: 600;
        }}
        .brand-title {{
            color: {PRIMARY};
            font-size: 1.7rem;
            font-weight: 800;
            line-height: 1.1;
        }}
        .brand-subtitle {{
            color: #334155;
            font-size: 0.9rem;
        }}
        .nav-hint {{
            color: #64748B;
            font-size: 0.80rem;
        }}
        div[data-testid="stMetric"] {{
            background: white;
            border-radius: 14px;
            padding: 14px;
            border: 1px solid #E5E7EB;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)
 
 
BASE_SHARE = np.array([28.5, 18.7, 16.2, 13.4, 8.9, 6.3, 4.5], dtype=float)
BASE_SHARE = BASE_SHARE / BASE_SHARE.sum()
 
 
def _region_modifier(region: str) -> np.ndarray:
    modifiers = {
        "Lima": [1.15, 1.05, 1.00, 0.92, 0.88, 0.95, 0.90],
        "La Libertad": [1.05, 1.00, 1.03, 0.96, 1.00, 0.96, 0.92],
        "Piura": [1.03, 0.98, 0.95, 1.02, 1.04, 1.02, 0.97],
        "Arequipa": [1.00, 1.02, 1.10, 0.98, 0.92, 0.96, 0.94],
        "Cusco": [0.88, 1.08, 0.96, 1.14, 1.05, 1.04, 1.02],
        "Puno": [0.80, 1.16, 0.90, 1.22, 1.05, 1.10, 1.04],
        "Junín": [0.94, 1.06, 1.00, 1.04, 1.06, 1.00, 1.00],
        "Huancavelica": [0.75, 1.18, 0.88, 1.24, 1.12, 1.08, 1.02],
        "Amazonas": [0.78, 1.12, 0.92, 1.18, 1.16, 1.08, 1.02],
        "Ucayali": [0.82, 1.10, 0.94, 1.14, 1.18, 1.06, 1.02],
    }
    arr = np.array(modifiers.get(region, [1] * len(BASE_SHARE)), dtype=float)
    share = BASE_SHARE * arr
    return share / share.sum()
 
 
# ==========================================================
# Conexión a Supabase
# ==========================================================
def _build_connection():
    """Crea una nueva conexión a Supabase. Sin caché para poder reconectar."""
    if psycopg2 is None:
        return None, "psycopg2 no está instalado"
    try:
        postgres = st.secrets["postgres"]
    except Exception:
        return None, "No se encontró la sección [postgres] en secrets.toml"
    try:
        conn = psycopg2.connect(
            user=postgres["USER"],
            password=postgres["PASSWORD"],
            host=postgres["HOST"],
            port=postgres.get("PORT", "5432"),
            dbname=postgres.get("DBNAME", "postgres"),
            sslmode="require",
            connect_timeout=10,
        )
        return conn, None
    except Exception as e:
        return None, str(e)
 
 
def get_connection():
    """Retorna conexión activa; reconecta si fue cerrada por timeout."""
    if "db_conn" not in st.session_state or st.session_state["db_conn"] is None:
        conn, err = _build_connection()
        st.session_state["db_conn"] = conn
        st.session_state["db_conn_error"] = err
    else:
        conn = st.session_state["db_conn"]
        # Verifica que la conexión sigue viva
        try:
            conn.isolation_level  # propiedad que lanza si está cerrada
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        except Exception:
            conn, err = _build_connection()
            st.session_state["db_conn"] = conn
            st.session_state["db_conn_error"] = err
    return st.session_state.get("db_conn")
 
 
def read_sql(query: str, params: Optional[Tuple] = None) -> Optional[pd.DataFrame]:
    conn = get_connection()

    if conn is None:
        return None

    try:
        df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        # Forzar reconexión en el próximo intento
        st.session_state.pop("db_conn", None)
        return None
 

def _has_columns(df: pd.DataFrame | None, columns: list[str]) -> bool:
    return isinstance(df, pd.DataFrame) and all(col in df.columns for col in columns)
 

def _validate_supabase_schema(candidates: pd.DataFrame, locations: pd.DataFrame, votes: pd.DataFrame) -> tuple[bool, str]:
    if candidates.empty or locations.empty or votes.empty:
        return False, "Uno o más datasets están vacíos."
    if not _has_columns(candidates, ["candidate_id", "candidate_name", "party_name", "party_symbol", "display_color"]):
        return False, "La tabla de candidatos no contiene las columnas esperadas."
    if not _has_columns(locations, ["location_id", "region", "province", "district", "total_actas", "actas_contabilizadas", "actas_pendientes", "velocidad_actas_hora"]):
        return False, "La tabla de ubicaciones no contiene las columnas esperadas."
    if not _has_columns(votes, ["location_id", "candidate_id", "valid_votes"]):
        return False, "La tabla de votos no contiene las columnas esperadas."
    return True, ""
 

def insert_log(event_type: str, event_name: str, detail: str) -> None:
    """
    Guarda logs desde Streamlit en la tabla nueva ces_logs.
    """
    conn = get_connection()

    if conn is None:
        return

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ces_logs (tipo, evento, detalle)
                VALUES (%s, %s, %s)
                """,
                (event_type, event_name, detail),
            )
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
 
 
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, bool]:
    """
    Carga datos desde Supabase. Usa session_state como caché liviano (60s TTL) para no reconectar en cada rerun.
    """
    cache_key = "data_cache"
    cache_ts_key = "data_cache_ts"
    ttl = 60  # segundos
 
    now = datetime.now().timestamp()
    if (
        cache_key in st.session_state
        and cache_ts_key in st.session_state
        and (now - st.session_state[cache_ts_key]) < ttl
    ):
        return st.session_state[cache_key]
 
    candidates = read_sql("SELECT * FROM candidates ORDER BY candidate_id")
    locations = read_sql("SELECT * FROM locations ORDER BY region, province, district")
    votes = read_sql("SELECT location_id, candidate_id, valid_votes FROM vote_results")

    logs = read_sql(
        """
        SELECT event_time, event_type, event_name, detail
        FROM event_logs
        ORDER BY event_time DESC
        LIMIT 50
        """
    )
 
    if candidates is None or locations is None or votes is None or candidates.empty or locations.empty or votes.empty:
        result = (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), False)
    else:
        if logs is None:
            logs = pd.DataFrame(columns=["event_time", "event_type", "event_name", "detail"])
        result = (candidates, locations, votes, logs, True)
 
    st.session_state[cache_key] = result
    st.session_state[cache_ts_key] = now
    return result
 
 
# ==========================================================
# Transformaciones
# ==========================================================
def apply_filters(locations: pd.DataFrame) -> pd.DataFrame:
    if locations.empty or "region" not in locations.columns:
        st.warning("No hay datos de ubicación disponibles para aplicar filtros.")
        return locations

    st.markdown("#### Filtros")
    c1, c2, c3, c4, c5 = st.columns([1, 1.2, 1.2, 1.2, 1.1])
 
    with c1:
        country = st.selectbox("País", ["Perú"], index=0)
    with c2:
        regions = ["Todas"] + sorted(locations["region"].dropna().unique().tolist())
        region = st.selectbox("Región", regions)
    with c3:
        province_df = locations if region == "Todas" else locations[locations["region"] == region]
        provinces = ["Todas"] + sorted(province_df["province"].dropna().unique().tolist())
        province = st.selectbox("Provincia", provinces)
    with c4:
        district_df = province_df if province == "Todas" else province_df[province_df["province"] == province]
        districts = ["Todos"] + sorted(district_df["district"].dropna().unique().tolist())
        district = st.selectbox("Distrito", districts)
    with c5:
        period = st.selectbox("Periodo", ["Total", "Última hora", "Últimas 6 horas"])
 
    filtered = locations.copy()
    if region != "Todas":
        filtered = filtered[filtered["region"] == region]
    if province != "Todas":
        filtered = filtered[filtered["province"] == province]
    if district != "Todos":
        filtered = filtered[filtered["district"] == district]
 
    return filtered
 
 
def joined_results(
    candidates: pd.DataFrame, locations: pd.DataFrame, votes: pd.DataFrame
) -> pd.DataFrame:
    if locations.empty or votes.empty or candidates.empty:
        return pd.DataFrame(
            columns=[
                "location_id",
                "candidate_id",
                "valid_votes",
                "candidate_name",
                "party_name",
                "party_symbol",
                "display_color",
                "region",
                "province",
                "district",
            ]
        )
    if not _has_columns(locations, ["location_id"]) or not _has_columns(votes, ["location_id", "candidate_id"]) or not _has_columns(candidates, ["candidate_id"]):
        return pd.DataFrame(
            columns=[
                "location_id",
                "candidate_id",
                "valid_votes",
                "candidate_name",
                "party_name",
                "party_symbol",
                "display_color",
                "region",
                "province",
                "district",
            ]
        )

    # Primero se toman solo las ubicaciones que quedaron después de aplicar filtros
    location_ids = locations["location_id"].dropna().unique()
 
    # Luego se filtran los votos para quedarse solo con esas ubicaciones
    filtered_votes = votes[votes["location_id"].isin(location_ids)].copy()
 
    # Finalmente se unen candidatos + ubicación geográfica
    data = filtered_votes.merge(
        candidates,
        on="candidate_id",
        how="left"
    ).merge(
        locations[["location_id", "region", "province", "district"]],
        on="location_id",
        how="inner"
    )
 
    return data
 
 
def candidate_summary(data: pd.DataFrame) -> pd.DataFrame:
    summary = (
        data.groupby(["candidate_id", "candidate_name", "party_name", "party_symbol", "display_color"], as_index=False)[
            "valid_votes"
        ]
        .sum()
        .sort_values("valid_votes", ascending=False)
    )
    total_votes = summary["valid_votes"].sum()
    summary["percentage"] = np.where(total_votes > 0, summary["valid_votes"] / total_votes * 100, 0)
    return summary
 
 
def general_metrics(locations: pd.DataFrame, summary: pd.DataFrame) -> dict:
    total_actas = int(locations["total_actas"].sum())
    counted = int(locations["actas_contabilizadas"].sum())
    pending = int(locations["actas_pendientes"].sum())
    progress = counted / total_actas * 100 if total_actas else 0
    avg_speed = float(locations["velocidad_actas_hora"].mean()) if not locations.empty else 0
    global_speed = float(locations["velocidad_actas_hora"].sum()) if not locations.empty else 0
    slow_threshold = avg_speed * 0.70
    critical = int((locations["velocidad_actas_hora"] < slow_threshold).sum()) if avg_speed > 0 else 0
 
    if len(summary) >= 2:
        diff = float(summary.iloc[0]["percentage"] - summary.iloc[1]["percentage"])
    else:
        diff = 0
    stability = min(99, max(55, 70 + diff * 1.6))
 
    return {
        "total_actas": total_actas,
        "counted": counted,
        "pending": pending,
        "progress": progress,
        "avg_speed": avg_speed,
        "global_speed": global_speed,
        "critical": critical,
        "stability": stability,
        "slow_threshold": slow_threshold,
    }
 
 
def format_int(value: float) -> str:
    return f"{int(round(value)):,}".replace(",", " ").replace(" ", ",")
 

def resumen_insights(metrics: dict, summary: pd.DataFrame) -> list[str]:
    insights: list[str] = []
    if metrics["total_actas"] == 0:
        return ["⚠️ No hay actas registradas para generar un diagnóstico."]

    if metrics["progress"] < 35:
        insights.append(
            f"⏳ Solo se ha contabilizado {metrics['progress']:.0f}% de las actas. El resultado parcial puede cambiar cuando se procesen las actas restantes."
        )
    elif metrics["progress"] < 75:
        insights.append(
            f"⏳ Se ha procesado {metrics['progress']:.0f}% de las actas, con {format_int(metrics['pending'])} pendientes. El conteo aún está en desarrollo."
        )
    else:
        insights.append(
            f"⏳ El conteo está avanzado ({metrics['progress']:.0f}% de actas), por lo que el resultado parcial es más representativo."
        )

    if metrics["critical"] > 0:
        insights.append(
            f"📍 Hay {metrics['critical']} departamento(s) con velocidad de procesamiento baja respecto al promedio. Esos lugares pueden retrasar el cierre del conteo."
        )
    else:
        insights.append(
            "📍 No se detectan departamentos con retraso crítico de procesamiento en el corte actual."
        )

    if len(summary) > 1:
        leader = summary.iloc[0]
        runner_up = summary.iloc[1]
        leader_diff = float(leader["percentage"] - runner_up["percentage"])
        if leader_diff < 3:
            insights.append(
                f"🔎 El margen entre {leader['candidate_name']} y {runner_up['candidate_name']} es de {leader_diff:.1f} puntos; la carrera sigue siendo cerrada."
            )
        elif leader_diff < 7:
            insights.append(
                f"🔎 {leader['candidate_name']} lidera por {leader_diff:.1f} puntos sobre {runner_up['candidate_name']}, una ventaja moderada."
            )
        else:
            insights.append(
                f"🔎 {leader['candidate_name']} mantiene una ventaja clara de {leader_diff:.1f} puntos sobre {runner_up['candidate_name']}."
            )
    else:
        insights.append(
            "🔎 No hay suficiente información de candidatos para determinar la competitividad del resultado."
        )

    if metrics["progress"] < 90 or metrics["critical"] > 0 or metrics["pending"] > 0:
        insights.append(
            "💡 Hay motivos para usar el simulador: permite ver cómo las actas pendientes y los retrasos podrían afectar el resultado."
        )
    else:
        insights.append(
            "💡 El simulador ayuda a comparar escenarios aunque el conteo actual es relativamente estable."
        )

    return insights


def render_header(db_connected: bool) -> None:
    now_text = datetime.now().strftime("%d/%m/%Y %I:%M %p").lower().replace("am", "a. m.").replace("pm", "p. m.")
    status = "Conectado a Supabase" if db_connected else "Sin conexión a Supabase"
    st.markdown(
        f"""
        <div class="top-card">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:16px;">
                <div style="display:flex; gap:14px; align-items:center;">
                    <div style="font-size:2.2rem;">🗳️</div>
                    <div>
                        <div class="brand-title">Cloud Election Sentinel</div>
                        <div class="brand-subtitle">Sistema analítico del conteo electoral</div>
                    </div>
                </div>
                <div style="text-align:right;">
                    <div style="color:#334155; font-size:0.82rem;">Actualizado: {now_text}</div>
                    <div class="status-pill">● Actualizado hace 5 minutos</div>
                    <div class="nav-hint" style="margin-top:6px;">{status}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
 
 
def metric_card(title: str, value: str, help_text: str, icon: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span class="metric-title">{title}</span>
                <span style="font-size:1.4rem;">{icon}</span>
            </div>
            <div class="metric-value">{value}</div>
            <div class="metric-help">{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
 
 
def make_bar_chart(summary: pd.DataFrame) -> go.Figure:
    chart = summary.copy()
    chart["label"] = chart["party_symbol"] + "<br>" + chart["party_name"]
    fig = px.bar(
        chart,
        x="label",
        y="percentage",
        text=chart["percentage"].map(lambda x: f"{x:.1f}%"),
        color="party_name",
        color_discrete_sequence=chart["display_color"].tolist(),
        hover_data={"candidate_name": True, "valid_votes": ":,", "percentage": ":.2f", "party_name": False},
    )
    fig.update_traces(textposition="outside", marker_line_width=0, cliponaxis=False)
    fig.update_layout(
        height=360,
        showlegend=False,
        margin=dict(l=10, r=10, t=25, b=10),
        yaxis_title="% de votos válidos",
        xaxis_title="",
        yaxis_ticksuffix="%",
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color=TEXT_DARK),
    )
    return fig
 
 
def make_votes_chart(summary: pd.DataFrame) -> go.Figure:
    chart = summary.copy()
    fig = px.bar(
        chart,
        x="valid_votes",
        y="party_name",
        orientation="h",
        text=chart["valid_votes"].map(lambda x: format_int(x)),
        color="party_name",
        color_discrete_sequence=chart["display_color"].tolist(),
    )
    fig.update_layout(
        height=390,
        showlegend=False,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="Votos válidos",
        yaxis_title="",
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    fig.update_yaxes(autorange="reversed")
    return fig
 
 
def make_map(locations: pd.DataFrame, metrics: dict) -> go.Figure:
    map_df = locations.copy()

    # Si la BD ya trae estado desde Databricks, usamos ese estado.
    # Si no existe, lo calculamos por velocidad como respaldo. -------- 
    if "estado" not in map_df.columns:
        threshold = metrics["slow_threshold"]
        map_df["estado"] = np.where(
            map_df["velocidad_actas_hora"] < threshold,
            "Retraso crítico",
            np.where(
                map_df["velocidad_actas_hora"] < metrics["avg_speed"],
                "Avance medio",
                "Avance alto",
            ),
        )
    else:
        map_df["estado"] = map_df["estado"].fillna("Sin información")

    map_df["avance"] = np.where(
        map_df["total_actas"] > 0,
        map_df["actas_contabilizadas"] / map_df["total_actas"] * 100,
        0,
    )


    
    color_map = {
        "Avance alto": "#5DBB73",
        "Avance medio": "#F4C64E",
        "Retraso crítico": "#F05A5A",
    }
    fig = px.scatter_mapbox(
        map_df,
        lat="latitude",
        lon="longitude",
        size="total_actas",
        color="estado",
        color_discrete_map=color_map,
        hover_name="region",
        hover_data={
            "province": True,
            "district": True,
            "avance": ":.1f",
            "velocidad_actas_hora": ":.1f",
            "latitude": False,
            "longitude": False,
            "total_actas": ":,",
        },
        zoom=4.3,
        center={"lat": -9.3, "lon": -75.1},
        height=520,
    )
    fig.update_layout(
        mapbox_style="open-street-map",
        margin=dict(l=0, r=0, t=0, b=0),
        legend_title_text="Nivel de avance",
    )
    return fig
 
 
TOP_ELECTORAL_DEPARTMENTS = [
    "Lima Metropolitana",
    "La Libertad",
    "Piura",
    "Arequipa",
    "Cajamarca",
    "Cusco",
    "Junin",
    "Lambayeque",
    "Ancash",
    "Puno",
]
 
DEPARTMENT_ALIASES = {
    "lima": "Lima Metropolitana",
    "lima metropolitana": "Lima Metropolitana",
    "la libertad": "La Libertad",
    "piura": "Piura",
    "arequipa": "Arequipa",
    "cajamarca": "Cajamarca",
    "cusco": "Cusco",
    "junin": "Junin",
    "lambayeque": "Lambayeque",
    "ancash": "Ancash",
    "puno": "Puno",
}
 
DEPARTMENT_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "id": "Lima Metropolitana", "properties": {"name": "Lima Metropolitana"}, "geometry": {"type": "Polygon", "coordinates": [[[-77.30, -11.55], [-76.65, -11.55], [-76.55, -12.35], [-77.25, -12.50], [-77.50, -12.05], [-77.30, -11.55]]]}},
        {"type": "Feature", "id": "La Libertad", "properties": {"name": "La Libertad"}, "geometry": {"type": "Polygon", "coordinates": [[[-79.75, -6.80], [-77.25, -6.90], [-77.05, -8.80], [-78.70, -8.95], [-79.65, -8.25], [-79.75, -6.80]]]}},
        {"type": "Feature", "id": "Piura", "properties": {"name": "Piura"}, "geometry": {"type": "Polygon", "coordinates": [[[-81.25, -3.65], [-79.25, -3.45], [-79.05, -5.60], [-80.60, -6.20], [-81.30, -5.25], [-81.25, -3.65]]]}},
        {"type": "Feature", "id": "Arequipa", "properties": {"name": "Arequipa"}, "geometry": {"type": "Polygon", "coordinates": [[[-75.20, -14.40], [-70.65, -14.55], [-70.25, -17.70], [-72.20, -17.95], [-74.60, -16.85], [-75.20, -14.40]]]}},
        {"type": "Feature", "id": "Cajamarca", "properties": {"name": "Cajamarca"}, "geometry": {"type": "Polygon", "coordinates": [[[-79.35, -4.60], [-77.10, -4.65], [-77.05, -7.75], [-78.80, -7.90], [-79.55, -6.35], [-79.35, -4.60]]]}},
        {"type": "Feature", "id": "Cusco", "properties": {"name": "Cusco"}, "geometry": {"type": "Polygon", "coordinates": [[[-73.95, -11.05], [-70.15, -11.10], [-69.70, -14.85], [-72.00, -15.15], [-73.90, -13.75], [-73.95, -11.05]]]}},
        {"type": "Feature", "id": "Junin", "properties": {"name": "Junin"}, "geometry": {"type": "Polygon", "coordinates": [[[-76.40, -10.50], [-73.35, -10.65], [-73.15, -12.95], [-75.30, -13.35], [-76.55, -12.10], [-76.40, -10.50]]]}},
        {"type": "Feature", "id": "Lambayeque", "properties": {"name": "Lambayeque"}, "geometry": {"type": "Polygon", "coordinates": [[[-80.75, -5.45], [-79.15, -5.55], [-79.05, -7.10], [-80.10, -7.20], [-80.70, -6.55], [-80.75, -5.45]]]}},
        {"type": "Feature", "id": "Ancash", "properties": {"name": "Ancash"}, "geometry": {"type": "Polygon", "coordinates": [[[-78.95, -8.10], [-76.65, -8.15], [-76.45, -10.65], [-77.75, -10.90], [-78.95, -9.95], [-78.95, -8.10]]]}},
        {"type": "Feature", "id": "Puno", "properties": {"name": "Puno"}, "geometry": {"type": "Polygon", "coordinates": [[[-71.85, -13.00], [-68.70, -13.15], [-68.45, -17.30], [-70.20, -17.55], [-71.75, -16.05], [-71.85, -13.00]]]}},
    ],
}
 
 
def _clean_department(value: object) -> str:
    text = "" if pd.isna(value) else str(value).strip()
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    return DEPARTMENT_ALIASES.get(normalized, text)
 
 
def _elapsed_hours(locations: pd.DataFrame) -> float:
    for column in ("tiempo_transcurrido_horas", "horas_transcurridas", "elapsed_hours"):
        if column in locations.columns and pd.to_numeric(locations[column], errors="coerce").notna().any():
            return max(float(pd.to_numeric(locations[column], errors="coerce").median()), 1.0)
 
    start_columns = [c for c in ("fecha_inicio_conteo", "started_at", "created_at") if c in locations.columns]
    end_columns = [c for c in ("fecha_actualizacion", "updated_at", "processed_at") if c in locations.columns]
    if start_columns:
        start = pd.to_datetime(locations[start_columns[0]], errors="coerce").min()
        end = pd.to_datetime(locations[end_columns[0]], errors="coerce").max() if end_columns else datetime.now()
        if pd.notna(start) and pd.notna(end):
            return max((end - start).total_seconds() / 3600, 1.0)
 
    if "velocidad_actas_hora" in locations.columns:
        speed = pd.to_numeric(locations["velocidad_actas_hora"], errors="coerce").replace(0, np.nan)
        counted = pd.to_numeric(locations["actas_contabilizadas"], errors="coerce")
        elapsed = (counted / speed).replace([np.inf, -np.inf], np.nan).median()
        if pd.notna(elapsed):
            return max(float(elapsed), 1.0)
 
    return 24.0
 
 
def _top_vote_labels(locations: pd.DataFrame, candidates: pd.DataFrame | None, votes: pd.DataFrame | None) -> pd.DataFrame:
    if candidates is None or votes is None or candidates.empty or votes.empty:
        return pd.DataFrame(columns=["region_map", "votos_principales"])
 
    vote_df = votes.merge(locations[["location_id", "region_map"]], on="location_id", how="inner")
    vote_df = vote_df.merge(candidates[["candidate_id", "candidate_name", "party_name"]], on="candidate_id", how="left")
    grouped = (
        vote_df.groupby(["region_map", "candidate_name", "party_name"], as_index=False)["valid_votes"]
        .sum()
        .sort_values(["region_map", "valid_votes"], ascending=[True, False])
    )
 
    labels = []
    for region, group in grouped.groupby("region_map"):
        top = group.head(2)
        label = "<br>".join(
            f"{row['candidate_name']} ({row['party_name']}): {format_int(row['valid_votes'])}"
            for _, row in top.iterrows()
        )
        labels.append({"region_map": region, "votos_principales": label})
    return pd.DataFrame(labels)
 
 
def prepare_mapa_dataframe(
    locations: pd.DataFrame, candidates: pd.DataFrame | None = None, votes: pd.DataFrame | None = None
) -> pd.DataFrame:
    if locations.empty or "region" not in locations.columns:
        return pd.DataFrame()

    df = locations.copy()
    df["region_map"] = df["region"].map(_clean_department)
    df = df[df["region_map"].isin(TOP_ELECTORAL_DEPARTMENTS)].copy()
    if df.empty:
        return df
 
    elapsed_hours = _elapsed_hours(df)
    grouped = (
        df.groupby("region_map", as_index=False)
        .agg(
            total_actas=("total_actas", "sum"),
            actas_contabilizadas=("actas_contabilizadas", "sum"),
            actas_pendientes=("actas_pendientes", "sum"),
            actas_observadas=("actas_observadas", "sum"),
            latitude=("latitude", "mean"),
            longitude=("longitude", "mean"),
        )
    )
    grouped["avance_pct"] = np.where(
        grouped["total_actas"] > 0, grouped["actas_contabilizadas"] / grouped["total_actas"] * 100, 0
    )
    grouped["velocidad_actas_hora"] = grouped["actas_contabilizadas"] / elapsed_hours
    grouped["pendiente_pct"] = np.where(
        grouped["total_actas"] > 0, grouped["actas_pendientes"] / grouped["total_actas"] * 100, 0
    )
    avg_progress = float(grouped["avance_pct"].mean())
    avg_speed = float(grouped["velocidad_actas_hora"].mean())
    high_pending = float(grouped["pendiente_pct"].quantile(0.70))
    grouped["bajo_promedio"] = grouped["avance_pct"] < avg_progress
    grouped["menor_rendimiento"] = grouped["velocidad_actas_hora"] < avg_speed
    grouped["alta_pendiente"] = grouped["pendiente_pct"] >= high_pending
    grouped["anomalia_score"] = np.where(grouped["bajo_promedio"] | grouped["menor_rendimiento"], 1, 0)
    grouped["estado_analitico"] = np.select(
        [grouped["alta_pendiente"], grouped["bajo_promedio"] | grouped["menor_rendimiento"]],
        ["Alta carga pendiente", "Bajo el promedio"],
        default="Rendimiento esperado",
    )
 
    vote_labels = _top_vote_labels(df[["location_id", "region_map"]], candidates, votes)
    grouped = grouped.merge(vote_labels, on="region_map", how="left")
    grouped["votos_principales"] = grouped["votos_principales"].fillna("Sin votos disponibles")
    grouped["region_map"] = pd.Categorical(grouped["region_map"], TOP_ELECTORAL_DEPARTMENTS, ordered=True)
    return grouped.sort_values("region_map").reset_index(drop=True)
 
 
def make_choropleth_map(map_df: pd.DataFrame, metric: str) -> go.Figure:
    metric_config = {
        "% de avance": ("avance_pct", "% avance", [[0, "#F05A5A"], [0.5, "#F4C64E"], [1, "#2E8B57"]], [0, 100]),
        "Velocidad de procesamiento": ("velocidad_actas_hora", "Actas/hora", "Blues", None),
        "Anomalias": ("anomalia_score", "Anomalia", [[0, "#D9F0DD"], [0.49, "#D9F0DD"], [0.5, "#F4A3A3"], [1, "#F05A5A"]], [0, 1]),
    }
    column, title, colorscale, value_range = metric_config[metric]
    zmin, zmax = value_range if value_range else (None, None)
 
    fig = go.Figure()
    fig.add_trace(
        go.Choroplethmapbox(
            geojson=DEPARTMENT_GEOJSON,
            locations=map_df["region_map"].astype(str),
            z=map_df[column],
            featureidkey="id",
            colorscale=colorscale,
            zmin=zmin,
            zmax=zmax,
            marker_line_width=1.0,
            marker_line_color="#FFFFFF",
            colorbar=dict(title=title, thickness=14, len=0.72),
            customdata=np.stack(
                [
                    map_df["region_map"].astype(str),
                    map_df["avance_pct"],
                    map_df["velocidad_actas_hora"],
                    map_df["actas_pendientes"],
                    map_df["pendiente_pct"],
                    map_df["estado_analitico"],
                    map_df["votos_principales"],
                ],
                axis=-1,
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Avance: %{customdata[1]:.1f}%<br>"
                "Velocidad: %{customdata[2]:,.1f} actas/hora<br>"
                "Pendientes: %{customdata[3]:,} (%{customdata[4]:.1f}%)<br>"
                "Estado: %{customdata[5]}<br><br>"
                "<b>Votos principales</b><br>%{customdata[6]}"
                "<extra></extra>"
            ),
        )
    )
 
    anomaly_df = map_df[map_df["bajo_promedio"] | map_df["menor_rendimiento"]]
    if not anomaly_df.empty:
        fig.add_trace(
            go.Choroplethmapbox(
                geojson=DEPARTMENT_GEOJSON,
                locations=anomaly_df["region_map"].astype(str),
                z=np.zeros(len(anomaly_df)),
                featureidkey="id",
                colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
                showscale=False,
                marker_line_width=3.2,
                marker_line_color="#B91C1C",
                hoverinfo="skip",
            )
        )
 
    fig.add_trace(
        go.Scattermapbox(
            lat=map_df["latitude"],
            lon=map_df["longitude"],
            mode="markers+text",
            marker=dict(size=8, color="#111827"),
            text=map_df["region_map"].astype(str),
            textfont=dict(size=10, color="#111827"),
            textposition="top center",
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.update_layout(
        height=560,
        mapbox=dict(style="carto-positron", center={"lat": -10.5, "lon": -75.1}, zoom=4.15),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="white",
        font=dict(color=TEXT_DARK),
        showlegend=False,
    )
    return fig
 
 
def render_mapa(locations: pd.DataFrame, candidates: pd.DataFrame | None = None, votes: pd.DataFrame | None = None) -> pd.DataFrame:
    map_df = prepare_mapa_dataframe(locations, candidates, votes)
    if map_df.empty:
        st.warning("No hay datos para los 10 departamentos de mayor carga electoral.")
        return map_df
 
    metric = st.radio(
        "Metrica del mapa",
        ["% de avance", "Velocidad de procesamiento", "Anomalias"],
        horizontal=True,
        label_visibility="collapsed",
    )
    fig = make_choropleth_map(map_df, metric)
 
    try:
        selection = st.plotly_chart(
            fig,
            use_container_width=True,
            on_select="rerun",
            selection_mode="points",
            key="mapa_departamental",
        )
    except TypeError:
        selection = None
        st.plotly_chart(fig, use_container_width=True)
 
    selected_region = None
    selection_payload = {}
    if selection:
        selection_payload = selection.get("selection", {}) if hasattr(selection, "get") else getattr(selection, "selection", {})
    if selection_payload and selection_payload.get("points"):
        point = selection_payload["points"][0]
        selected_region = point.get("location")
        if not selected_region and point.get("customdata"):
            selected_region = point["customdata"][0]
    if selected_region is None:
        selected_region = st.selectbox("Detalle territorial", map_df["region_map"].astype(str).tolist())
 
    st.session_state["mapa_departamentos_what_if"] = map_df[
        [
            "region_map",
            "total_actas",
            "actas_contabilizadas",
            "actas_pendientes",
            "avance_pct",
            "pendiente_pct",
            "velocidad_actas_hora",
            "bajo_promedio",
            "menor_rendimiento",
            "alta_pendiente",
        ]
    ].copy()
    st.session_state["mapa_departamentos_prioritarios"] = map_df[map_df["alta_pendiente"]]["region_map"].astype(str).tolist()
 
    detail = locations.copy()
    detail["region_map"] = detail["region"].map(_clean_department)
    detail = detail[detail["region_map"].astype(str) == str(selected_region)]
    st.markdown(f"#### Detalle: {selected_region}")
    if {"province", "district"}.issubset(detail.columns) and not detail.empty:
        detail_table = (
            detail.groupby(["province", "district"], as_index=False)
            .agg(
                total_actas=("total_actas", "sum"),
                actas_contabilizadas=("actas_contabilizadas", "sum"),
                actas_pendientes=("actas_pendientes", "sum"),
            )
            .sort_values("actas_pendientes", ascending=False)
        )
        detail_table["avance_pct"] = np.where(
            detail_table["total_actas"] > 0,
            detail_table["actas_contabilizadas"] / detail_table["total_actas"] * 100,
            0,
        )
        detail_table.columns = ["Provincia", "Distrito", "Actas totales", "Procesadas", "Pendientes", "% avance"]
        st.dataframe(detail_table, use_container_width=True, hide_index=True)
    else:
        st.info("El dataset actual no incluye detalle de provincia o distrito para esta seleccion.")
 
    return map_df
 
 
def page_resumen(candidates, locations, votes, db_connected: bool = False):
    schema_ok, schema_msg = _validate_supabase_schema(candidates, locations, votes)
    if not db_connected or not schema_ok:
        db_error = st.session_state.get("db_conn_error", "")
        msg = "⚠️ No hay datos disponibles desde Supabase."
        if schema_msg:
            msg += f" {schema_msg}"
        if db_error:
            msg += f" Error: `{db_error}`"
        st.warning(msg)
        return

    filtered_locations = apply_filters(locations)
    data = joined_results(candidates, filtered_locations, votes)
    summary = candidate_summary(data)
    metrics = general_metrics(filtered_locations, summary)
 
    # Aviso de estado de datos -----------------------------------------------
    if not db_connected:
        db_error = st.session_state.get("db_conn_error", "")
        msg = "⚠️ No hay conexión activa a Supabase."
        if db_error:
            msg += f" Error: `{db_error}`"
        st.warning(msg)
    else:
        # Botón para refrescar manualmente los datos
        col_ref, _ = st.columns([1, 4])
        with col_ref:
            if st.button("🔄 Actualizar datos", use_container_width=True):
                st.session_state.pop("data_cache", None)
                st.session_state.pop("data_cache_ts", None)
                st.rerun()
 
    st.write("")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metric_card("Avance nacional", f"{metrics['progress']:.0f}%", "Actas contabilizadas", "📊")
    with c2:
        metric_card("Velocidad promedio", format_int(metrics["global_speed"]), "Actas / hora", "⏱️")
    with c3:
        metric_card("Regiones críticas", str(metrics["critical"]), "Con retraso significativo", "⚠️")
    with c4:
        metric_card("Estabilidad del resultado", f"{metrics['stability']:.0f}%", "Bajo riesgo de cambio", "✅")
    with c5:
        metric_card("Actas pendientes", format_int(metrics["pending"]), "Por contabilizar", "📄")
 
    st.write("")
    left, right = st.columns([2.2, 1])
    with left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Resultados por candidato")
        st.caption("Porcentaje de votos válidos")
        if summary.empty:
            st.info("No hay resultados para los filtros seleccionados.")
        else:
            st.plotly_chart(make_bar_chart(summary), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
 
    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Interpretación del conteo")
        if not summary.empty:
            lider = summary.iloc[0]
            segundo = summary.iloc[1] if len(summary) > 1 else None
            st.markdown(
                f"🏆 **{lider['candidate_name']}** ({lider['party_name']}) lidera "
                f"con **{lider['percentage']:.1f}%**."
            )
            if segundo is not None:
                diff = lider["percentage"] - segundo["percentage"]
                st.markdown(
                    f"📊 Diferencia con el 2.° lugar: **{diff:.1f} pp** "
                    f"({segundo['candidate_name']})"
                )
            st.markdown(
                f"📄 Actas contabilizadas: **{format_int(metrics['counted'])}** "
                f"de {format_int(metrics['total_actas'])} ({metrics['progress']:.1f}%)"
            )
        st.divider()
        for insight in resumen_insights(metrics, summary):
            st.write(insight)
        fuente = "Supabase PostgreSQL" if db_connected else "Sin datos disponibles"
        st.caption(f"Fuente: {fuente}")
        st.markdown("</div>", unsafe_allow_html=True)
 
    st.write("")
    fuente_nota = "Supabase PostgreSQL (datos reales)" if db_connected else "Sin datos disponibles"
    st.markdown(
        f"<div class='small-note'>Total de actas: <b>{format_int(metrics['total_actas'])}</b>. Fuente: {fuente_nota}.</div>",
        unsafe_allow_html=True,
    )
 
 
def page_resultados(candidates, locations, votes):
    if not _has_columns(locations, ["region", "province", "district"]) or not _has_columns(locations, ["location_id"]):
        st.warning("No hay datos geográficos completos para mostrar resultados. Verifica la conexión a Supabase.")
        return
    if not _has_columns(candidates, ["candidate_id"]) or not _has_columns(votes, ["location_id", "candidate_id"]):
        st.warning("No hay datos de candidatos o votos completos para mostrar resultados. Verifica la conexión a Supabase.")
        return

    # ======================================================
    # Estilos visuales propios del módulo de resultados
    # ======================================================
    st.markdown(
        """
        <style>
            .result-hero {
                background: linear-gradient(135deg, #003C7D 0%, #0B5CAB 55%, #1F78D1 100%);
                color: white;
                padding: 26px 30px;
                border-radius: 18px;
                margin-bottom: 22px;
                box-shadow: 0 8px 22px rgba(0, 60, 125, 0.18);
            }
            .result-hero h2 {
                margin: 0;
                font-size: 2rem;
                font-weight: 800;
                letter-spacing: -0.5px;
            }
            .result-hero p {
                margin-top: 8px;
                margin-bottom: 0;
                color: #EAF4FF;
                font-size: 0.95rem;
            }
            .result-pill {
                display: inline-block;
                background: rgba(255,255,255,0.16);
                border: 1px solid rgba(255,255,255,0.28);
                color: white;
                padding: 6px 12px;
                border-radius: 999px;
                font-size: 0.78rem;
                font-weight: 700;
                margin-bottom: 12px;
            }
            .res-metric {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 18px;
                padding: 18px 18px;
                min-height: 125px;
                box-shadow: 0 5px 15px rgba(15, 23, 42, 0.06);
                transition: all 0.2s ease;
            }
            .res-metric:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 22px rgba(15, 23, 42, 0.09);
            }
            .res-metric-top {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
            }
            .res-metric-title {
                color: #64748B;
                font-size: 0.82rem;
                font-weight: 700;
            }
            .res-metric-icon {
                background: #EAF4FF;
                color: #003C7D;
                width: 34px;
                height: 34px;
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.1rem;
            }
            .res-metric-value {
                color: #111827;
                font-size: 1.9rem;
                font-weight: 800;
                line-height: 1.1;
            }
            .res-metric-help {
                color: #64748B;
                font-size: 0.78rem;
                margin-top: 8px;
            }
            .leader-card {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 16px;
                padding: 16px;
                min-height: 120px;
                box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
            }
            .leader-rank {
                color: #003C7D;
                font-size: 0.78rem;
                font-weight: 800;
                text-transform: uppercase;
                margin-bottom: 8px;
            }
            .leader-name {
                color: #111827;
                font-size: 1rem;
                font-weight: 800;
                margin-bottom: 4px;
            }
            .leader-party {
                color: #64748B;
                font-size: 0.82rem;
                margin-bottom: 10px;
            }
            .leader-percent {
                color: #0B5CAB;
                font-size: 1.35rem;
                font-weight: 800;
            }
            .insight-box {
                background: #EAF4FF;
                border-left: 5px solid #0B5CAB;
                color: #003C7D;
                padding: 15px 18px;
                border-radius: 14px;
                font-size: 0.92rem;
                margin-top: 8px;
                margin-bottom: 18px;
            }
            .section-title {
                font-size: 1.35rem;
                font-weight: 800;
                color: #111827;
                margin-bottom: 4px;
            }
            .section-subtitle {
                font-size: 0.82rem;
                color: #64748B;
                margin-bottom: 14px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
 
    # ======================================================
    # Cabecera visual
    # ======================================================
    st.markdown(
        """
        <div class="result-hero">
            <div class="result-pill">Módulo de resultados</div>
            <h2>Resultados electorales</h2>
            <p>Consulta consolidada de votos por candidato, organización política y zona geográfica.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
 
    # ======================================================
    # Filtros
    # ======================================================
    with st.container(border=True):
        st.markdown("### Filtros de consulta")
        st.caption("Selecciona una zona para recalcular votos, ranking, avance de actas y descarga.")
 
        f1, f2, f3 = st.columns(3)
 
        with f1:
            regiones = ["Todas"] + sorted(locations["region"].dropna().unique().tolist())
            region_seleccionada = st.selectbox("Región", regiones, key="res_region")
 
        base_provincia = locations.copy()
        if region_seleccionada != "Todas":
            base_provincia = base_provincia[base_provincia["region"] == region_seleccionada]
 
        with f2:
            provincias = ["Todas"] + sorted(base_provincia["province"].dropna().unique().tolist())
            provincia_seleccionada = st.selectbox("Provincia", provincias, key="res_province")
 
        base_distrito = base_provincia.copy()
        if provincia_seleccionada != "Todas":
            base_distrito = base_distrito[base_distrito["province"] == provincia_seleccionada]
 
        with f3:
            distritos = ["Todos"] + sorted(base_distrito["district"].dropna().unique().tolist())
            distrito_seleccionado = st.selectbox("Distrito", distritos, key="res_district")
 
    # ======================================================
    # Aplicar filtros
    # ======================================================
    filtered_locations = locations.copy()
 
    if region_seleccionada != "Todas":
        filtered_locations = filtered_locations[filtered_locations["region"] == region_seleccionada]
 
    if provincia_seleccionada != "Todas":
        filtered_locations = filtered_locations[filtered_locations["province"] == provincia_seleccionada]
 
    if distrito_seleccionado != "Todos":
        filtered_locations = filtered_locations[filtered_locations["district"] == distrito_seleccionado]
 
    if filtered_locations.empty:
        st.warning("No hay información disponible para los filtros seleccionados.")
        return
 
    data = joined_results(candidates, filtered_locations, votes)
    summary = candidate_summary(data).reset_index(drop=True)
 
    if summary.empty:
        st.warning("No hay resultados electorales disponibles para esta consulta.")
        return
 
    summary.insert(0, "posicion", range(1, len(summary) + 1))
 
    # ======================================================
    # Cálculo de métricas principales
    # ======================================================
    total_votes = int(summary["valid_votes"].sum())
    total_actas = int(filtered_locations["total_actas"].sum())
    actas_contabilizadas = int(filtered_locations["actas_contabilizadas"].sum())
 
    if "actas_pendientes" in filtered_locations.columns:
        actas_pendientes = int(filtered_locations["actas_pendientes"].sum())
    else:
        actas_pendientes = max(total_actas - actas_contabilizadas, 0)
 
    avance_pct = (actas_contabilizadas / total_actas * 100) if total_actas > 0 else 0
 
    lider = summary.iloc[0]
    segundo = summary.iloc[1] if len(summary) > 1 else None
    diferencia = lider["percentage"] - segundo["percentage"] if segundo is not None else 0
 
    def res_metric(icon, title, value, help_text):
        st.markdown(
            f"""
            <div class="res-metric">
                <div class="res-metric-top">
                    <div class="res-metric-title">{title}</div>
                    <div class="res-metric-icon">{icon}</div>
                </div>
                <div class="res-metric-value">{value}</div>
                <div class="res-metric-help">{help_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
 
    st.write("")
    m1, m2, m3, m4 = st.columns(4)
 
    with m1:
        res_metric("🗳️", "Votos válidos", format_int(total_votes), "Total acumulado según filtros")
 
    with m2:
        res_metric("📄", "Actas contabilizadas", format_int(actas_contabilizadas), f"{avance_pct:.1f}% de avance")
 
    with m3:
        res_metric("🏆", "Líder actual", lider["party_name"], f"{lider['percentage']:.2f}% de votos válidos")
 
    with m4:
        res_metric("📊", "Diferencia 1.º vs 2.º", f"{diferencia:.2f} pp", "Puntos porcentuales")
 
    st.write("")
 
    # ======================================================
    # Lectura rápida
    # ======================================================
    if segundo is not None:
        insight = (
            f"Con los filtros aplicados, <b>{lider['candidate_name']}</b> de <b>{lider['party_name']}</b> "
            f"lidera con <b>{lider['percentage']:.2f}%</b> de votos válidos. "
            f"La diferencia frente a <b>{segundo['candidate_name']}</b> es de <b>{diferencia:.2f} puntos porcentuales</b>. "
            f"El avance de actas en esta consulta es de <b>{avance_pct:.1f}%</b>."
        )
    else:
        insight = (
            f"Con los filtros aplicados, se registra información para <b>{lider['candidate_name']}</b> "
            f"con un avance de actas de <b>{avance_pct:.1f}%</b>."
        )
 
    st.markdown(f"<div class='insight-box'>{insight}</div>", unsafe_allow_html=True)
    st.progress(min(avance_pct / 100, 1.0), text=f"Avance de actas procesadas: {avance_pct:.1f}%")
 
    # ======================================================
    # Podio de candidatos
    # ======================================================
    st.write("")
    st.markdown("### Podio de resultados")
    st.caption("Primeras posiciones según la consulta seleccionada")
 
    podium_cols = st.columns(3)
    medals = ["🥇 Primer lugar", "🥈 Segundo lugar", "🥉 Tercer lugar"]
 
    for idx, col in enumerate(podium_cols):
        if idx < len(summary):
            row = summary.iloc[idx]
            with col:
                st.markdown(
                    f"""
                    <div class="leader-card">
                        <div class="leader-rank">{medals[idx]}</div>
                        <div class="leader-name">{row['candidate_name']}</div>
                        <div class="leader-party">{row['party_name']}</div>
                        <div class="leader-percent">{row['percentage']:.2f}%</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
 
    # ======================================================
    # Gráfico y ranking
    # ======================================================
    st.write("")
    left, right = st.columns([1.35, 1])
 
    with left:
        with st.container(border=True):
            st.markdown('<div class="section-title">Distribución de votos</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="section-subtitle">Votos válidos acumulados por organización política</div>',
                unsafe_allow_html=True,
            )
 
            chart = summary.sort_values("valid_votes", ascending=True).copy()
            color_map = dict(zip(chart["party_name"], chart["display_color"]))
 
            fig = px.bar(
                chart,
                x="valid_votes",
                y="party_name",
                orientation="h",
                text=chart["valid_votes"].map(format_int),
                color="party_name",
                color_discrete_map=color_map,
                hover_data={
                    "candidate_name": True,
                    "valid_votes": ":,",
                    "percentage": ":.2f",
                    "party_name": False,
                },
            )
 
            fig.update_traces(
                textposition="outside",
                cliponaxis=False,
                marker_line_width=0,
                hovertemplate="<b>%{customdata[0]}</b><br>Votos: %{x:,}<br>Porcentaje: %{customdata[2]:.2f}%<extra></extra>",
            )
 
            fig.update_layout(
                height=430,
                showlegend=False,
                margin=dict(l=10, r=35, t=10, b=10),
                xaxis_title="Votos válidos",
                yaxis_title="",
                plot_bgcolor="white",
                paper_bgcolor="white",
                font=dict(color=TEXT_DARK),
                xaxis=dict(showgrid=True, gridcolor="#E5E7EB"),
                yaxis=dict(showgrid=False),
            )
 
            st.plotly_chart(fig, use_container_width=True)
 
    with right:
        with st.container(border=True):
            st.markdown('<div class="section-title">Ranking de candidatos</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="section-subtitle">Ordenado de mayor a menor votación</div>',
                unsafe_allow_html=True,
            )
 
            tabla = summary[
                ["posicion", "candidate_name", "party_name", "valid_votes", "percentage"]
            ].copy()
 
            tabla = tabla.rename(
                columns={
                    "posicion": "Puesto",
                    "candidate_name": "Candidato",
                    "party_name": "Organización política",
                    "valid_votes": "Votos",
                    "percentage": "% votos",
                }
            )
 
            st.dataframe(
                tabla,
                use_container_width=True,
                hide_index=True,
                height=390,
                column_config={
                    "Puesto": st.column_config.NumberColumn("Puesto", format="%d"),
                    "Votos": st.column_config.NumberColumn("Votos", format="%d"),
                    "% votos": st.column_config.ProgressColumn(
                        "% votos",
                        format="%.2f%%",
                        min_value=0,
                        max_value=100,
                    ),
                },
            )
 
    # ======================================================
    # Avance de actas y descarga
    # ======================================================
    st.write("")
    col_a, col_b = st.columns([1.2, 1])
 
    with col_a:
        with st.container(border=True):
            st.markdown('<div class="section-title">Avance de actas de la consulta</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="section-subtitle">Detalle territorial usado para calcular los resultados</div>',
                unsafe_allow_html=True,
            )
 
            avance_tabla = filtered_locations[
                ["region", "province", "district", "total_actas", "actas_contabilizadas", "actas_pendientes"]
            ].copy()
 
            avance_tabla["% avance"] = np.where(
                avance_tabla["total_actas"] > 0,
                avance_tabla["actas_contabilizadas"] / avance_tabla["total_actas"] * 100,
                0,
            )
 
            avance_tabla = avance_tabla.rename(
                columns={
                    "region": "Región",
                    "province": "Provincia",
                    "district": "Distrito",
                    "total_actas": "Actas totales",
                    "actas_contabilizadas": "Procesadas",
                    "actas_pendientes": "Pendientes",
                }
            )
 
            st.dataframe(
                avance_tabla,
                use_container_width=True,
                hide_index=True,
                height=280,
                column_config={
                    "Actas totales": st.column_config.NumberColumn("Actas totales", format="%d"),
                    "Procesadas": st.column_config.NumberColumn("Procesadas", format="%d"),
                    "Pendientes": st.column_config.NumberColumn("Pendientes", format="%d"),
                    "% avance": st.column_config.ProgressColumn(
                        "% avance",
                        format="%.1f%%",
                        min_value=0,
                        max_value=100,
                    ),
                },
            )
 
    with col_b:
        with st.container(border=True):
            st.markdown('<div class="section-title">Exportar resultados</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="section-subtitle">Descarga la información filtrada para reportes o evidencias.</div>',
                unsafe_allow_html=True,
            )
 
            exportar = summary[
                ["posicion", "candidate_name", "party_name", "valid_votes", "percentage"]
            ].copy()
 
            exportar = exportar.rename(
                columns={
                    "posicion": "puesto",
                    "candidate_name": "candidato",
                    "party_name": "organizacion_politica",
                    "valid_votes": "votos_validos",
                    "percentage": "porcentaje",
                }
            )
 
            st.download_button(
                "⬇️ Descargar resultados en CSV",
                exportar.to_csv(index=False).encode("utf-8"),
                "resultados_electorales_filtrados.csv",
                "text/csv",
                use_container_width=True,
            )
 
            st.write("")
            st.markdown("#### Resumen de la consulta")
            st.markdown(
                f"""
                - **Actas totales:** {format_int(total_actas)}
                - **Actas procesadas:** {format_int(actas_contabilizadas)}
                - **Actas pendientes:** {format_int(actas_pendientes)}
                - **Avance:** {avance_pct:.1f}%
                """
            )
 
 
def page_mapa(locations, candidates, votes):
    st.markdown("## Analisis territorial del conteo")
    st.caption("Mapa coropletico de los 10 departamentos con mayor carga electoral")

    if locations.empty or candidates.empty or votes.empty:
        st.warning("No hay datos disponibles para mostrar el mapa. Verifica la conexión a Supabase.")
        return

    map_df = render_mapa(locations, candidates, votes)
    if map_df.empty:
        return
 
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avance promedio", f"{map_df['avance_pct'].mean():.1f}%")
    c2.metric("Velocidad total", f"{map_df['velocidad_actas_hora'].sum():,.0f}", "actas/hora")
    c3.metric("Bajo promedio", str(int(map_df["anomalia_score"].sum())))
    c4.metric("Alta pendiente", str(int(map_df["alta_pendiente"].sum())))
 
    left, right = st.columns([1.15, 1])
    with left:
        st.markdown("### Departamentos con menor rendimiento")
        risk = map_df[map_df["bajo_promedio"] | map_df["menor_rendimiento"]].copy()
        if risk.empty:
            st.success("No hay departamentos bajo el promedio actual.")
        else:
            risk["brecha_avance"] = (map_df["avance_pct"].mean() - risk["avance_pct"]).clip(lower=0)
            risk_table = risk[
                ["region_map", "avance_pct", "velocidad_actas_hora", "pendiente_pct", "brecha_avance", "estado_analitico"]
            ].sort_values(["brecha_avance", "pendiente_pct"], ascending=False)
            risk_table.columns = ["Departamento", "% avance", "Actas/hora", "% pendiente", "Brecha avance", "Estado"]
            st.dataframe(risk_table, use_container_width=True, hide_index=True)
 
    with right:
        st.markdown("### Insumos para simulacion")
        what_if = map_df[map_df["alta_pendiente"]].copy()
        if what_if.empty:
            st.info("No hay departamentos con carga pendiente alta en el corte actual.")
        else:
            what_if_table = what_if[["region_map", "actas_pendientes", "pendiente_pct", "velocidad_actas_hora"]]
            what_if_table.columns = ["Departamento", "Actas pendientes", "% pendiente", "Actas/hora"]
            st.dataframe(what_if_table, use_container_width=True, hide_index=True)
    return
 
    data = joined_results(candidates, locations, votes)
    summary = candidate_summary(data)
    metrics = general_metrics(locations, summary)
 
    st.markdown("## Análisis por región")
    st.caption("Nivel de avance del conteo y velocidad de procesamiento")
 
    left, right = st.columns([2, 1])
    with left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.plotly_chart(make_map(locations, metrics), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
 
    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Nivel de avance")
        st.write("🟢 Avance alto")
        st.write("🟡 Avance medio")
        st.write("🔴 Retraso crítico")
        st.divider()
        st.markdown("### Regiones críticas")
        critical = locations[locations["velocidad_actas_hora"] < metrics["slow_threshold"]].copy()
        if critical.empty:
            st.success("No hay regiones críticas con el umbral actual.")
        else:
            critical["retraso_estimado"] = (
                100 - critical["velocidad_actas_hora"] / max(metrics["avg_speed"], 1) * 100
            ).clip(lower=0)
            for _, row in critical.sort_values("retraso_estimado", ascending=False).iterrows():
                st.write(f"**{row['region']}** — {row['retraso_estimado']:.0f}% bajo el promedio")
        st.markdown("</div>", unsafe_allow_html=True)


def region_modifier_for_simulation(region: str, candidates_count: int) -> np.ndarray:
    """
    Retorna la distribución de votos por región ajustada a la cantidad real de candidatos.
    Usa la misma lógica base del dashboard, pero evita errores si hay más/menos candidatos.
    """
    if candidates_count <= 0:
        return np.array([], dtype=float)

    shares = _region_modifier(region)

    if len(shares) >= candidates_count:
        shares = shares[:candidates_count]
    else:
        extra = np.repeat(1 / candidates_count, candidates_count - len(shares))
        shares = np.concatenate([shares, extra])

    total = shares.sum()
    if total <= 0:
        return np.repeat(1 / candidates_count, candidates_count)

    return shares / total


def get_target_locations(
    locations: pd.DataFrame,
    scenario: str,
    rural_intake: int,
    delay_hours: int,
) -> tuple[pd.DataFrame, float]:
    """
    Selecciona las ubicaciones que entran a la simulación y calcula el factor de actas a ingresar.
    """
    if locations.empty or "actas_pendientes" not in locations.columns:
        return pd.DataFrame(columns=locations.columns), 0.0

    target = locations.copy()
    target["actas_pendientes"] = pd.to_numeric(target["actas_pendientes"], errors="coerce").fillna(0)
    if "velocidad_actas_hora" in target.columns:
        target["velocidad_actas_hora"] = pd.to_numeric(
            target["velocidad_actas_hora"],
            errors="coerce"
        ).fillna(0)
    else:
        target["velocidad_actas_hora"] = 0.0

    # Solo tiene sentido simular zonas con actas pendientes.
    target = target[target["actas_pendientes"] > 0].copy()
    if target.empty:
        return target, 0.0

    intake_factor = max(0, min(float(rural_intake), 100)) / 100
    delay_factor = max(0, 1 - (max(0, float(delay_hours)) / 24))

    rural_regions = [
        "Cusco",
        "Puno",
        "Huancavelica",
        "Amazonas",
        "Ucayali",
        "Junín",
        "Cajamarca",
    ]

    if scenario == "Ingreso de actas rurales":
        rural_target = target[target["region"].isin(rural_regions)].copy()
        if not rural_target.empty:
            target = rural_target
        factor = intake_factor

    elif scenario == "Retraso en regiones críticas":
        avg_speed = float(target["velocidad_actas_hora"].mean()) if not target.empty else 0
        if avg_speed > 0:
            critical_target = target[target["velocidad_actas_hora"] < avg_speed * 0.70].copy()
        else:
            critical_target = target.copy()

        if "estado" in target.columns:
            estado_critico = target[
                target["estado"].astype(str).str.contains("Retraso|bajo|crítico|critico", case=False, na=False)
            ].copy()
            critical_target = pd.concat([critical_target, estado_critico]).drop_duplicates()

        if not critical_target.empty:
            target = critical_target

        # A mayor retraso, menor ingreso efectivo de actas.
        factor = intake_factor * delay_factor

    else:  # Actualización uniforme del conteo
        factor = intake_factor

    return target, factor


def simulate_result(
    summary: pd.DataFrame,
    locations: pd.DataFrame,
    scenario: str,
    rural_intake: int,
    delay_hours: int,
) -> pd.DataFrame:
    simulated = summary.copy()
    simulated["sim_votes"] = simulated["valid_votes"].astype(float)

    target_locations, factor = get_target_locations(
        locations,
        scenario,
        rural_intake,
        delay_hours,
    )

    votes_per_acta = 320
    candidates_count = len(simulated)

    for _, loc in target_locations.iterrows():
        pending_actas = float(loc["actas_pendientes"])
        new_actas = pending_actas * factor

        if new_actas <= 0:
            continue

        shares = region_modifier_for_simulation(str(loc["region"]), candidates_count)

        for idx, candidate_id in enumerate(simulated["candidate_id"].tolist()):
            extra_votes = new_actas * votes_per_acta * shares[idx]
            simulated.loc[simulated["candidate_id"] == candidate_id, "sim_votes"] += extra_votes

    total_sim_votes = simulated["sim_votes"].sum()

    simulated["sim_percentage"] = np.where(
        total_sim_votes > 0,
        simulated["sim_votes"] / total_sim_votes * 100,
        0,
    )

    simulated["sim_votes"] = simulated["sim_votes"].round().astype(int)

    return simulated.sort_values("sim_percentage", ascending=False)
 
def page_simulador(candidates, locations, votes):
    if not _has_columns(locations, ["location_id"]) or not _has_columns(candidates, ["candidate_id"]) or not _has_columns(votes, ["location_id", "candidate_id", "valid_votes"]):
        st.warning("No hay datos completos para simular escenarios. Verifica la conexión a Supabase.")
        return

    data = joined_results(candidates, locations, votes)
    summary = candidate_summary(data)
 
    st.markdown("## Simulador de escenarios")
    st.caption("Analiza cómo podrían cambiar los resultados según el ingreso de actas pendientes o rurales.")
 
    left, right = st.columns([1, 1.25])
    with left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        scenario = st.selectbox(
            "Escenario",
            [
                "Ingreso de actas rurales",
                "Retraso en regiones críticas",
                "Actualización uniforme del conteo",
            ],
        )
        rural_intake = st.slider("Porcentaje de actas rurales ingresadas", 0, 100, 50, 5)
        delay_hours = st.slider("Retraso en regiones críticas (horas)", 0, 24, 6, 1)
 
        run = st.button("▶ Ejecutar simulación", type="primary", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if summary.empty:
        st.warning("No hay resultados electorales disponibles para ejecutar la simulación.")
        return

    simulated = simulate_result(summary, locations, scenario, rural_intake, delay_hours)
    current_leader = summary.iloc[0]
    simulated_leader = simulated.iloc[0]
    difference = simulated_leader["sim_percentage"] - current_leader["percentage"]
    confidence = max(55, min(95, 86 - abs(difference) * 4 - delay_hours * 0.4))
 
    if run:
        insert_log("Simulación", "Escenario ejecutado", f"{scenario}: rural={rural_intake}%, retraso={delay_hours}h")
        # Forzar recarga de datos en el siguiente ciclo
        st.session_state.pop("data_cache", None)
        st.session_state.pop("data_cache_ts", None)
 
    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Resultado de la simulación")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Resultado actual", f"{current_leader['percentage']:.1f}%", current_leader["party_name"])
        m2.metric("Resultado simulado", f"{simulated_leader['sim_percentage']:.1f}%", simulated_leader["party_name"])
        m3.metric("Diferencia", f"{difference:+.1f}%", "Variación del líder")
        m4.metric("Nivel de confianza", f"{confidence:.0f}%", "Escenario")
 
        fig = px.bar(
            simulated,
            x="party_name",
            y="sim_percentage",
            text=simulated["sim_percentage"].map(lambda x: f"{x:.1f}%"),
            color="party_name",
            color_discrete_sequence=simulated["display_color"].tolist(),
        )
        fig.update_layout(
            height=300,
            showlegend=False,
            margin=dict(l=10, r=10, t=15, b=10),
            yaxis_title="% simulado",
            xaxis_title="",
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        fig.update_traces(textposition="outside", cliponaxis=False)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
 
    st.write("")
    st.markdown(
        "<div class='small-note'>Nota: los resultados simulados son referenciales y se calculan mediante reglas de escenario, no mediante IA.</div>",
        unsafe_allow_html=True,
    )
 
 
def page_reportes(candidates, locations, votes):
    if not _has_columns(locations, ["location_id"]) or not _has_columns(candidates, ["candidate_id"]) or not _has_columns(votes, ["location_id", "candidate_id"]):
        st.warning("No hay datos completos para generar reportes. Verifica la conexión a Supabase.")
        return

    st.markdown("## Reportes")
    st.caption("Exportación básica de resultados y avance de actas")
 
    data = joined_results(candidates, locations, votes)
    summary = candidate_summary(data)
 
    tab1, tab2, tab3 = st.tabs(["Resumen por candidato", "Avance geográfico", "Dataset completo"])
    with tab1:
        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar resumen CSV",
            summary.to_csv(index=False).encode("utf-8"),
            "resumen_candidatos.csv",
            "text/csv",
        )
    with tab2:
        st.dataframe(locations, use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar avance CSV",
            locations.to_csv(index=False).encode("utf-8"),
            "avance_geografico.csv",
            "text/csv",
        )
    with tab3:
        st.dataframe(data, use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar dataset CSV",
            data.to_csv(index=False).encode("utf-8"),
            "dataset_electoral.csv",
            "text/csv",
        )
 
 
def page_logs(logs: pd.DataFrame):
    st.markdown("## Registro de eventos (Logs)")
    st.caption("Trazabilidad de procesos y acciones del sistema")
 
    table = logs.copy()
    if "event_time" in table.columns:
        table["event_time"] = pd.to_datetime(table["event_time"]).dt.strftime("%d/%m/%Y %I:%M:%S %p")
    table.columns = ["Fecha y hora", "Tipo", "Evento", "Detalle"]
    st.dataframe(table, use_container_width=True, hide_index=True)
 
 
def page_acerca(db_connected: bool):
    st.markdown("## Acerca de Cloud Election Sentinel")
    st.write(
        "Esta base web replica una vista tipo ONPE para analizar el avance del conteo electoral. "
        "Está desarrollada únicamente con Python, Streamlit y Supabase/PostgreSQL."
    )
 
    c1, c2, c3 = st.columns(3)
    c1.info("**Frontend:** Streamlit")
    c2.info("**Base de datos:** Supabase PostgreSQL")
    c3.info("**Repositorio:** GitHub + rama de trabajo")
 
    st.markdown("### Flujo técnico")
    st.code(
        """
        Dataset electoral → Python/Databricks job → Supabase PostgreSQL → Streamlit Cloud → Usuario web
        """.strip(),
        language="text",
    )
    st.markdown("### Estado")
    st.success("Conexión activa a Supabase" if db_connected else "No conectado a Supabase. Configura secrets para usar datos reales.")
 
 
# ==========================================================
# App principal
# ==========================================================
def main():
    candidates, locations, votes, logs, db_connected = load_data()
 
    with st.sidebar:
        st.markdown("## 🗳️ Cloud Election Sentinel")
        st.caption("Sistema analítico del conteo electoral")
        option = st.radio(
            "Menú",
            ["Resumen", "Resultados", "Mapa", "Simulador", "Reportes", "Logs", "Acerca de"],
            label_visibility="collapsed",
        )
        st.divider()
        st.caption("Base web en Python · Streamlit · Supabase")
 
    render_header(db_connected)
 
    if option == "Resumen":
        page_resumen(candidates, locations, votes, db_connected)
    elif option == "Resultados":
        page_resultados(candidates, locations, votes)
    elif option == "Mapa":
        page_mapa(locations, candidates, votes)
    elif option == "Simulador":
        page_simulador(candidates, locations, votes)
    elif option == "Reportes":
        page_reportes(candidates, locations, votes)
    elif option == "Logs":
        page_logs(logs)
    else:
        page_acerca(db_connected)
 
 
if __name__ == "__main__":
    main()
