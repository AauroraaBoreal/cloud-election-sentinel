from __future__ import annotations
 
from datetime import datetime, timedelta
from typing import Optional, Tuple
import unicodedata
 
import numpy as np
import pandas as pd
# pyrefly: ignore [missing-import]
import plotly.express as px
# pyrefly: ignore [missing-import]
import plotly.graph_objects as go
import streamlit as st
 

try:
    import psycopg2
except Exception:
    psycopg2 = None
 
 
# ==========================================================
# Configuración general
# ==========================================================
# v4: sin use_container_width, simulador con variación visible y compatible con Streamlit moderno.
_PAGE_CONFIG_RESULT = st.set_page_config(
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
_CSS_RESULT = st.markdown(
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
        "Lima Metropolitana": [1.15, 1.05, 1.00, 0.92, 0.88, 0.95, 0.90],
        "La Libertad": [1.05, 1.00, 1.03, 0.96, 1.00, 0.96, 0.92],
        "Piura": [1.03, 0.98, 0.95, 1.02, 1.04, 1.02, 0.97],
        "Arequipa": [1.00, 1.02, 1.10, 0.98, 0.92, 0.96, 0.94],
        "Cajamarca": [0.90, 1.10, 0.98, 1.12, 1.05, 1.00, 0.95],
        "Cusco": [0.88, 1.08, 0.96, 1.14, 1.05, 1.04, 1.02],
        "Junín": [0.94, 1.06, 1.00, 1.04, 1.06, 1.00, 1.00],
        "Lambayeque": [1.02, 0.99, 1.01, 0.97, 1.02, 0.98, 0.95],
        "Áncash": [0.95, 1.03, 0.97, 1.05, 1.02, 0.99, 0.96],
        "Puno": [0.80, 1.16, 0.90, 1.22, 1.05, 1.10, 1.04],
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
    # --- BLINDAJE DEFENSIVO ANTI-KEYERROR (Mayerly UX Fix) ---
    
    # 1. Total de Actas (Seguro)
    if "total_actas" in locations.columns:
        total_actas = int(locations["total_actas"].sum())
    elif "actas_totales" in locations.columns:
        total_actas = int(locations["actas_totales"].sum())
    else:
        total_actas = 0

    # 2. Extracción segura con valores por defecto (Si no existen, asume 0)
    counted = int(locations["actas_contabilizadas"].sum()) if "actas_contabilizadas" in locations.columns else 0
    pending = int(locations["actas_pendientes"].sum()) if "actas_pendientes" in locations.columns else 0
    
    # 3. Progreso
    progress = counted / total_actas * 100 if total_actas else 0
    
    # 4. Velocidades y Umbrales Críticos de forma segura
    has_speed = "velocidad_actas_hora" in locations.columns and not locations.empty
    
    avg_speed = float(locations["velocidad_actas_hora"].mean()) if has_speed else 0
    global_speed = float(locations["velocidad_actas_hora"].sum()) if has_speed else 0
    slow_threshold = avg_speed * 0.70
    
    critical = int((locations["velocidad_actas_hora"] < slow_threshold).sum()) if has_speed and avg_speed > 0 else 0
 
    # 5. Cálculo de estabilidad electoral basado en la diferencia (ONPE style)
    if len(summary) >= 2 and "percentage" in summary.columns:
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

    # Blindaje defensivo contra errores de base de datos / columnas faltantes
    if "total_actas" not in map_df.columns and "actas_totales" in map_df.columns:
        map_df["total_actas"] = map_df["actas_totales"]
    elif "total_actas" not in map_df.columns:
        map_df["total_actas"] = 0
        
    for col in ["actas_contabilizadas", "velocidad_actas_hora", "latitude", "longitude"]:
        if col not in map_df.columns:
            map_df[col] = 0.0

    # Rellenar nulos de manera segura
    map_df["total_actas"] = pd.to_numeric(map_df["total_actas"], errors="coerce").fillna(0).astype(int)
    map_df["actas_contabilizadas"] = pd.to_numeric(map_df["actas_contabilizadas"], errors="coerce").fillna(0).astype(int)
    map_df["velocidad_actas_hora"] = pd.to_numeric(map_df["velocidad_actas_hora"], errors="coerce").fillna(0.0).astype(float)
    map_df["latitude"] = pd.to_numeric(map_df["latitude"], errors="coerce").fillna(0.0)
    map_df["longitude"] = pd.to_numeric(map_df["longitude"], errors="coerce").fillna(0.0)

    # Si la BD ya trae estado desde Databricks, usamos ese estado.
    # Si no existe, lo calculamos por velocidad como respaldo. -------- 
    if "estado" not in map_df.columns:
        threshold = metrics.get("slow_threshold", 0)
        avg_speed = metrics.get("avg_speed", 0)
        map_df["estado"] = np.where(
            map_df["velocidad_actas_hora"] < threshold,
            "Retraso crítico",
            np.where(
                map_df["velocidad_actas_hora"] < avg_speed,
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
    
    # Previene error de Plotly si el DataFrame está vacío o no tiene datos válidos
    if map_df.empty:
        fig = go.Figure()
        fig.update_layout(
            mapbox_style="open-street-map",
            margin=dict(l=0, r=0, t=0, b=0),
        )
        return fig

    # Asegura que total_actas no sea <= 0 para evitar errores de Plotly size
    map_df["total_actas_size"] = map_df["total_actas"].clip(lower=1)

    fig = px.scatter_mapbox(
        map_df,
        lat="latitude",
        lon="longitude",
        size="total_actas_size",
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
    # Paleta ONPE/Perú adaptable a Fondos Claros y Oscuros
    metric_config = {
        "% de avance": ("avance_pct", "% Avance", [[0, "#E5E7EB"], [0.3, "#FCA5A5"], [0.7, "#FEF08A"], [1, "#BBF7D0"]], [0, 100]),
        "Velocidad de procesamiento": ("velocidad_actas_hora", "Actas/h", [[0, "#EFF6FF"], [1, "#1E3A8A"]], None),
        "Anomalias": ("anomalia_score", "Alerta", [[0, "#F3F4F6"], [0.49, "#F3F4F6"], [0.5, "#FEE2E2"], [1, "#EF4444"]], [0, 1]),
    }
    column, title, colorscale, value_range = metric_config[metric]
    zmin, zmax = value_range if value_range else (None, None)
 
    fig = go.Figure()
    
    # Única capa base oficial: Mapa Poligonal de Departamentos (Sin duplicados ni solapamientos)
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
            marker_line_color="var(--background-color)", # Línea de frontera adaptativa al tema claro/oscuro
            colorbar=dict(
                title=dict(text=f"<b>{title}</b>", font=dict(size=11, color="gray")),
                thickness=15, 
                len=0.6,
                x=0.98,
                y=0.5
            ),
            customdata=np.stack(
                [
                    map_df["region_map"].astype(str),
                    map_df["avance_pct"],
                    map_df["velocidad_actas_hora"],
                    map_df["actas_pendientes"],
                    map_df["pendiente_pct"],
                    map_df["estado_analitico"]
                ],
                axis=-1,
            ),
            hovertemplate=(
                "<b>📍 Región: %{customdata[0]}</b><br><br>"
                "📊 Avance: <b>%{customdata[1]:.1f}%</b><br>"
                "⚡ Velocidad: <b>%{customdata[2]:,.1f} actas/h</b><br>"
                "⚠️ Pendientes: <b>%{customdata[3]:,} (%{customdata[4]:.1f}%)</b><br>"
                "📋 Estado: <b>%{customdata[5]}</b>"
                "<extra></extra>"
            ),
        )
    )
 
    # Resaltado limpio de bordes para alertas críticas (En lugar de figuras sólidas encima)
    anomaly_df = map_df[map_df["bajo_promedio"] | map_df["menor_rendimiento"]]
    if not anomaly_df.empty:
        fig.add_trace(
            go.Choroplethmapbox(
                geojson=DEPARTMENT_GEOJSON,
                locations=anomaly_df["region_map"].astype(str),
                z=np.ones(len(anomaly_df)),
                featureidkey="id",
                colorscale=[[0, "rgba(220, 38, 38, 0.05)"], [1, "rgba(220, 38, 38, 0.05)"]], # Fondo casi invisible, solo resalta bordes
                showscale=False,
                marker_line_width=2.5,
                marker_line_color="#DC2626", # Borde Rojo Alerta Institucional
                hoverinfo="skip",
            )
        )
 
    # Configuración del contenedor del mapa
    fig.update_layout(
        height=550,
        mapbox=dict(
            style="carto-positron", # Fondo de mapa limpio y minimalista gris claro
            center={"lat": -9.19, "lon": -75.01}, # Centrado geográfico exacto de Perú
            zoom=4.6
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)", # Fondo transparente para integrarse con Temas Claro/Oscuro
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return fig

def render_mapa(locations: pd.DataFrame, candidates: pd.DataFrame | None = None, votes: pd.DataFrame | None = None) -> pd.DataFrame:
    map_df = prepare_mapa_dataframe(locations, candidates, votes)
    if map_df.empty:
        st.warning("No hay datos para los 10 departamentos de mayor carga electoral.")
        return map_df
 
    # Selector de capa interactiva con diseño de pastillas (UX mejorado)
    st.markdown("##### 🗺️ Selecciona la capa analítica del Mapa:")
    metric = st.radio(
        "Metrica del mapa",
        ["% de avance", "Velocidad de procesamiento", "Anomalias"],
        horizontal=True,
        label_visibility="collapsed",
    )
    
    # Renderizado del mapa interactivo
    fig = make_choropleth_map(map_df, metric)
    try:
        selection = st.plotly_chart(
            fig,
            width="stretch",
            on_select="rerun",
            selection_mode="points",
            key="mapa_departamental",
        )
    except TypeError:
        selection = None
        st.plotly_chart(fig, width="stretch")
 
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
        selected_region = st.selectbox("🔍 Filtrar detalle territorial específico:", map_df["region_map"].astype(str).tolist())
 
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
 
    # ======================================================
    # CONTENEDOR DETALLE TERRITORIAL INTERACTIVO (UX CARD)
    # ======================================================
    detail = locations.copy()
    detail["region_map"] = detail["region"].map(_clean_department)
    detail = detail[detail["region_map"].astype(str) == str(selected_region)]
    
    st.write("")
    with st.container(border=True):
        st.markdown(f"### 📍 Desglose Geográfico: {selected_region}")
        st.caption("Visualización de actas a nivel provincial y distrital en la región seleccionada.")
        
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
            
            # Formateo dinámico UX con barra de progreso integrada
            st.dataframe(
                detail_table, 
                width="stretch", 
                hide_index=True,
                column_config={
                    "Actas totales": st.column_config.NumberColumn(format="%d"),
                    "Procesadas": st.column_config.NumberColumn(format="%d"),
                    "Pendientes": st.column_config.NumberColumn(format="%d"),
                    "% avance": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)
                }
            )
        else:
            st.info("El dataset actual no incluye detalle de provincia o distrito para esta selección.")
 
    return map_df

def page_mapa(locations, candidates, votes):
    # Cabecera Estilizada
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #091E3A 0%, #2E8B57 100%); color: white; padding: 22px; border-radius: 14px; margin-bottom: 20px;">
            <h2 style='margin:0; font-weight:800;'>🗺️ Análisis Territorial del Conteo</h2>
            <p style='margin:5px 0 0 0; opacity:0.85;'>Módulo geoespacial interactivo para la detección de anomalías y velocidad de procesamiento en regiones prioritarias.</p>
        </div>
        """, 
        unsafe_allow_html=True
    )

    if locations.empty or candidates.empty or votes.empty:
        st.warning("No hay datos disponibles para mostrar el mapa. Verifica la conexión a Supabase.")
        return

    # Inyección del mapa y captura del DataFrame procesado
    map_df = render_mapa(locations, candidates, votes)
    if map_df.empty:
        return
 
    # ======================================================
    # DASHBOARD LIVE DE MÉTRICAS (KPI GRID COLORIDO)
    # ======================================================
    st.write("")
    st.markdown("#### 📈 Indicadores Clave de Control (KPIs)")
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.markdown(
            f"""<div style="background-color: #EBF5FF; border-left: 5px solid #3B82F6; padding: 15px; border-radius: 8px;">
                <span style="color: #1E40AF; font-size: 13px; font-weight: bold; text-transform: uppercase;">Avance Promedio</span>
                <h2 style="color: #1E3A8A; margin: 5px 0 0 0; font-weight: 800;">{map_df['avance_pct'].mean():.1f}%</h2>
                <span style="color: #1F2937; font-size: 11px;">Macro-regiones</span>
            </div>""", unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f"""<div style="background-color: #ECFDF5; border-left: 5px solid #10B981; padding: 15px; border-radius: 8px;">
                <span style="color: #065F46; font-size: 13px; font-weight: bold; text-transform: uppercase;">Velocidad Global</span>
                <h2 style="color: #064E3B; margin: 5px 0 0 0; font-weight: 800;">{map_df['velocidad_actas_hora'].sum():,.0f}</h2>
                <span style="color: #1F2937; font-size: 11px;">Actas por hora</span>
            </div>""", unsafe_allow_html=True
        )
    with c3:
        anomalias = int(map_df["anomalia_score"].sum())
        bg_anom = "#FEF2F2" if anomalias > 0 else "#ECFDF5"
        border_anom = "#EF4444" if anomalias > 0 else "#10B981"
        text_anom = "#991B1B" if anomalias > 0 else "#065F46"
        st.markdown(
            f"""<div style="background-color: {bg_anom}; border-left: 5px solid {border_anom}; padding: 15px; border-radius: 8px;">
                <span style="color: {text_anom}; font-size: 13px; font-weight: bold; text-transform: uppercase;">Regiones con Retraso</span>
                <h2 style="color: {text_anom}; margin: 5px 0 0 0; font-weight: 800;">{anomalias}</h2>
                <span style="color: #1F2937; font-size: 11px;">Bajo el promedio objetivo</span>
            </div>""", unsafe_allow_html=True
        )
    with c4:
        st.markdown(
            f"""<div style="background-color: #FFFBEB; border-left: 5px solid #F59E0B; padding: 15px; border-radius: 8px;">
                <span style="color: #92400E; font-size: 13px; font-weight: bold; text-transform: uppercase;">Alta Carga Pendiente</span>
                <h2 style="color: #78350F; margin: 5px 0 0 0; font-weight: 800;">{int(map_df['alta_pendiente'].sum())}</h2>
                <span style="color: #1F2937; font-size: 11px;">Zonas críticas identificadas</span>
            </div>""", unsafe_allow_html=True
        )

    # ======================================================
    # SECCIÓN INFERIOR COMPLEMENTARIA (TABLAS DE CONTROL ACCIONABLES)
    # ======================================================
    st.write("")
    left, right = st.columns([1.15, 1])
    
    with left:
        with st.container(border=True):
            st.markdown("### 🚨 Alerta: Departamentos con Menor Rendimiento")
            st.caption("Zonas cuya velocidad es inferior en más del 30% respecto al promedio.")
            risk = map_df[map_df["bajo_promedio"] | map_df["menor_rendimiento"]].copy()
            if risk.empty:
                st.success("🎉 Excelente: No hay departamentos bajo el promedio actual en este corte.")
            else:
                risk["brecha_avance"] = (map_df["avance_pct"].mean() - risk["avance_pct"]).clip(lower=0)
                risk_table = risk[
                    ["region_map", "avance_pct", "velocidad_actas_hora", "pendiente_pct", "brecha_avance", "estado_analitico"]
                ].sort_values(["brecha_avance", "pendiente_pct"], ascending=False)
                risk_table.columns = ["Departamento", "% Avance", "Actas/Hora", "% Pendiente", "Brecha Avance", "Estado Crítico"]
                
                st.dataframe(
                    risk_table, 
                    width="stretch", 
                    hide_index=True,
                    column_config={
                        "% Avance": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
                        "Brecha Avance": st.column_config.NumberColumn(format="%.1f pp"),
                        "Actas/Hora": st.column_config.NumberColumn(format="%.1f")
                    }
                )
 
    with right:
        with st.container(border=True):
            st.markdown("### 🎛️ Insumos Críticos para el Simulador")
            st.caption("Bolsas de actas pendientes recomendadas para simulaciones estratégicas What-If[cite: 1].")
            what_if = map_df[map_df["alta_pendiente"]].copy()
            if what_if.empty:
                st.info("No se detectan departamentos con carga acumulada crítica para simulación.")
            else:
                what_if_table = what_if[["region_map", "actas_pendientes", "pendiente_pct", "velocidad_actas_hora"]]
                what_if_table.columns = ["Departamento", "Actas Pendientes", "% Pendiente", "Velocidad (Actas/h)"]
                
                st.dataframe(
                    what_if_table, 
                    width="stretch", 
                    hide_index=True,
                    column_config={
                        "Actas Pendientes": st.column_config.NumberColumn(format="%d"),
                        "% Pendiente": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
                        "Velocidad (Actas/h)": st.column_config.NumberColumn(format="%.1f")
                    }
                )

    # ======================================================
    # ANÁLISIS DE REGIONES CRÍTICAS Y MAPA DE PUNTOS
    # ======================================================
    st.write("")
    data = joined_results(candidates, locations, votes)
    summary = candidate_summary(data)
    metrics = general_metrics(locations, summary)
 
    st.markdown("## Análisis por región")
    st.caption("Nivel de avance del conteo y velocidad de procesamiento")
 
    left, right = st.columns([2, 1])
    with left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        fig_map = make_map(locations, metrics)
        st.plotly_chart(fig_map, width="stretch")
        st.markdown("</div>", unsafe_allow_html=True)
 
    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Nivel de avance")
        st.write("🟢 Avance alto")
        st.write("🟡 Avance medio")
        st.write("🔴 Retraso crítico")
        st.divider()
        st.markdown("### Regiones críticas")
        
        # Filtrado seguro contra KeyErrors de base de datos
        if "velocidad_actas_hora" in locations.columns:
            critical = locations[locations["velocidad_actas_hora"] < metrics.get("slow_threshold", 0)].copy()
        else:
            critical = pd.DataFrame()
            
        if critical.empty or "velocidad_actas_hora" not in critical.columns:
            st.success("No hay regiones críticas con el umbral actual.")
        else:
            avg_speed = max(metrics.get("avg_speed", 1), 1)
            critical["retraso_estimado"] = (
                100 - critical["velocidad_actas_hora"] / avg_speed * 100
            ).clip(lower=0)
            for _, row in critical.sort_values("retraso_estimado", ascending=False).iterrows():
                st.write(f"**{row['region']}** — {row['retraso_estimado']:.0f}% bajo el promedio")
        st.markdown("</div>", unsafe_allow_html=True)

def page_resumen(candidates, locations, votes, db_connected):
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
            if st.button("🔄 Actualizar datos", width="stretch"):
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
            st.plotly_chart(make_bar_chart(summary), width="stretch")
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
 
            st.plotly_chart(fig, width="stretch")
 
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
                width="stretch",
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
                width="stretch",
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
                width="stretch",
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
 
 



def _fit_array(values: list[float], size: int) -> np.ndarray:
    """Ajusta una lista de pesos a la cantidad real de candidatos."""
    if size <= 0:
        return np.array([], dtype=float)

    arr = np.array(values, dtype=float)
    if len(arr) >= size:
        arr = arr[:size]
    else:
        arr = np.concatenate([arr, np.repeat(1.0, size - len(arr))])

    total = arr.sum()
    if total <= 0:
        return np.repeat(1 / size, size)
    return arr / total


def region_modifier_for_simulation(region: str, candidates_count: int, scenario: str = "") -> np.ndarray:
    """
    Retorna la distribución simulada por región.
    La simulación aplica un sesgo visible por escenario para que los sliders sí cambien el resultado.
    """
    if candidates_count <= 0:
        return np.array([], dtype=float)

    shares = _region_modifier(region)
    if len(shares) >= candidates_count:
        shares = shares[:candidates_count]
    else:
        shares = np.concatenate([shares, np.repeat(1 / candidates_count, candidates_count - len(shares))])

    # Pesos por escenario. Están alineados al orden de candidate_id ascendente.
    # Sirven para que el simulador sea pedagógico y muestre variaciones reales en pantalla.
    if scenario == "Ingreso de actas rurales":
        boost = _fit_array([0.18, 2.75, 0.38, 3.10, 1.85, 1.35, 0.95], candidates_count)
    elif scenario == "Retraso en regiones críticas":
        boost = _fit_array([0.22, 2.45, 0.45, 2.85, 2.05, 1.45, 1.00], candidates_count)
    else:  # Actualización uniforme del conteo
        boost = _fit_array([0.90, 1.12, 1.04, 1.08, 1.02, 0.98, 0.96], candidates_count)

    shares = shares * boost
    total = shares.sum()
    if total <= 0:
        return np.repeat(1 / candidates_count, candidates_count)
    return shares / total


def get_target_locations(
    locations: pd.DataFrame,
    scenario: str,
    rural_intake: int,
    delay_hours: int,
) -> tuple[pd.DataFrame, float, str]:
    """
    Selecciona ubicaciones y calcula cuántas actas entran al escenario.

    Si Supabase ya tiene 0 actas pendientes, crea una bolsa referencial basada en total_actas.
    Esto evita que el simulador quede congelado en el mismo porcentaje.
    """
    if locations.empty:
        return pd.DataFrame(), 0.0, "Sin ubicaciones disponibles"

    target = locations.copy()

    for col in ["actas_pendientes", "actas_observadas", "total_actas", "velocidad_actas_hora"]:
        if col not in target.columns:
            target[col] = 0
        target[col] = pd.to_numeric(target[col], errors="coerce").fillna(0)

    rural_regions = [
        "Cusco",
        "Puno",
        "Junín",
        "Junin",
        "Cajamarca",
        "Áncash",
        "Ancash",
    ]

    if scenario == "Ingreso de actas rurales":
        subset = target[target["region"].isin(rural_regions)].copy()
        if not subset.empty:
            target = subset
        fallback_rate = 1.10
        factor = max(0, min(float(rural_intake), 100)) / 100
        label = "actas rurales proyectadas"

    elif scenario == "Retraso en regiones críticas":
        avg_speed = float(target["velocidad_actas_hora"].mean()) if not target.empty else 0
        critical = target[target["velocidad_actas_hora"] <= avg_speed].copy() if avg_speed > 0 else target.copy()

        if "estado" in target.columns:
            by_status = target[
                target["estado"].astype(str).str.contains("Retraso|bajo|crítico|critico", case=False, na=False)
            ].copy()
            critical = pd.concat([critical, by_status]).drop_duplicates()

        if not critical.empty:
            target = critical

        fallback_rate = 1.25
        intake_factor = max(0, min(float(rural_intake), 100)) / 100
        delay_impact = 0.70 + (max(0, min(float(delay_hours), 24)) / 24) * 0.55
        factor = max(0.10, intake_factor * delay_impact)
        label = "actas críticas proyectadas"

    else:  # Actualización uniforme del conteo
        fallback_rate = 0.55
        factor = max(0, min(float(rural_intake), 100)) / 100
        label = "actas proyectadas de actualización uniforme"

    # Base real: pendientes. Si la bolsa real es muy pequeña, usa una bolsa referencial
    # para que el cambio se vea en el gráfico y en las métricas.
    real_pending = target["actas_pendientes"].clip(lower=0)
    observed_pool = target["actas_observadas"].clip(lower=0)
    min_visible_pool = max(float(target["total_actas"].sum()) * 0.05, 1.0)

    if float(real_pending.sum()) >= min_visible_pool:
        target["sim_pending_actas"] = real_pending
        source_label = "pendientes reales de Supabase"
    elif float(observed_pool.sum()) >= min_visible_pool:
        target["sim_pending_actas"] = observed_pool
        source_label = "actas observadas como bolsa referencial"
    else:
        target["sim_pending_actas"] = (target["total_actas"] * fallback_rate).round().clip(lower=1)
        source_label = "bolsa referencial porque no hay pendientes suficientes"

    target = target[target["sim_pending_actas"] > 0].copy()
    return target, factor, f"{label} usando {source_label}"


def simulate_result(
    summary: pd.DataFrame,
    locations: pd.DataFrame,
    scenario: str,
    rural_intake: int,
    delay_hours: int,
) -> tuple[pd.DataFrame, float, str]:
    """
    Calcula un escenario what-if visible.

    Importante: si la BD ya está al 100% de actas, el simulador usa una bolsa
    proyectada. Además, escala la bolsa para que el cambio se note en pantalla.
    """
    simulated = summary.copy()
    simulated["sim_votes"] = pd.to_numeric(simulated["valid_votes"], errors="coerce").fillna(0).astype(float)

    target_locations, factor, source_label = get_target_locations(
        locations,
        scenario,
        rural_intake,
        delay_hours,
    )

    votes_per_acta = 320
    candidate_ids = sorted(simulated["candidate_id"].dropna().astype(int).unique().tolist())
    candidates_count = len(candidate_ids)
    used_actas = 0.0

    # Guardamos los votos extra separados para poder escalarlos de forma visible.
    extra_by_candidate = {candidate_id: 0.0 for candidate_id in candidate_ids}

    for _, loc in target_locations.iterrows():
        pending_actas = float(loc.get("sim_pending_actas", 0))
        new_actas = pending_actas * factor

        if new_actas <= 0:
            continue

        used_actas += new_actas
        shares = region_modifier_for_simulation(str(loc.get("region", "")), candidates_count, scenario)

        for idx, candidate_id in enumerate(candidate_ids):
            extra_by_candidate[candidate_id] += new_actas * votes_per_acta * shares[idx]

    current_total_votes = float(simulated["sim_votes"].sum())
    added_votes = float(sum(extra_by_candidate.values()))

    # Si el volumen proyectado es pequeño frente al total nacional, Streamlit muestra casi lo mismo.
    # Por eso se escala solo para fines de simulación visual y pedagógica.
    if added_votes > 0 and current_total_votes > 0:
        slider_strength = max(0.0, min(float(rural_intake), 100.0)) / 100.0
        delay_strength = max(0.0, min(float(delay_hours), 24.0)) / 24.0
        if scenario == "Actualización uniforme del conteo":
            min_visible_ratio = 0.10 + 0.12 * slider_strength
        elif scenario == "Ingreso de actas rurales":
            min_visible_ratio = 0.18 + 0.28 * slider_strength
        else:
            min_visible_ratio = 0.20 + 0.25 * slider_strength + 0.12 * delay_strength

        target_added_votes = current_total_votes * min_visible_ratio
        if added_votes < target_added_votes:
            visual_multiplier = target_added_votes / added_votes
            extra_by_candidate = {k: v * visual_multiplier for k, v in extra_by_candidate.items()}
            used_actas *= visual_multiplier

    for candidate_id, extra_votes in extra_by_candidate.items():
        simulated.loc[simulated["candidate_id"].astype(int) == candidate_id, "sim_votes"] += extra_votes

    total_sim_votes = simulated["sim_votes"].sum()
    simulated["sim_percentage"] = np.where(
        total_sim_votes > 0,
        simulated["sim_votes"] / total_sim_votes * 100,
        0,
    )

    simulated["sim_votes"] = simulated["sim_votes"].round().astype(int)
    simulated = simulated.sort_values("sim_percentage", ascending=False).reset_index(drop=True)

    return simulated, used_actas, source_label


def page_simulador(candidates, locations, votes):
    if not _has_columns(locations, ["location_id"]) or not _has_columns(candidates, ["candidate_id"]) or not _has_columns(votes, ["location_id", "candidate_id", "valid_votes"]):
        st.warning("No hay datos completos para simular escenarios. Verifica la conexión a Supabase.")
        return

    data = joined_results(candidates, locations, votes)
    summary = candidate_summary(data)

    st.markdown("## 🎛️ Simulador interactivo de escenarios")
    st.info(
        "💡 **¿Cómo funciona?** Este simulador te permite proyectar cómo cambiarían los resultados "
        "finales si se procesan las actas pendientes de contabilizar bajo diferentes condiciones "
        "geográficas o de velocidad. Elige un escenario y usa los controles para analizar el impacto."
    )

    if summary.empty:
        st.warning("No hay resultados electorales disponibles para ejecutar la simulación.")
        return

    left, right = st.columns([1.1, 1.25])

    with left:
        with st.container(border=True):
            st.markdown("### 🛠️ Configuración de la simulación")
            
            scenario = st.selectbox(
                "1. Selecciona el escenario a simular",
                [
                    "Ingreso de actas rurales",
                    "Retraso en regiones críticas",
                    "Actualización uniforme del conteo",
                ],
                help="Elige qué tipo de sesgo de ingreso de actas pendientes deseas analizar."
            )
            
            # Explicador contextual del escenario
            if scenario == "Ingreso de actas rurales":
                st.markdown(
                    "<div style='font-size: 0.85rem; color: #555; background-color: #f9f9f9; padding: 10px; border-radius: 6px; border-left: 3px solid #3B82F6; margin-bottom: 12px;'>"
                    "🌾 **Ingreso de actas rurales**: Simula el ingreso de actas de zonas rurales que suelen tardar más en procesarse. "
                    "Estas regiones suelen tener tendencias de votación marcadamente diferentes a las urbanas."
                    "</div>",
                    unsafe_allow_html=True
                )
            elif scenario == "Retraso en regiones críticas":
                st.markdown(
                    "<div style='font-size: 0.85rem; color: #555; background-color: #f9f9f9; padding: 10px; border-radius: 6px; border-left: 3px solid #EF4444; margin-bottom: 12px;'>"
                    "⚠️ **Retraso en regiones críticas**: Simula el impacto de un estrangulamiento logístico o corte en las regiones "
                    "con velocidades de conteo más bajas, afectando el orden y flujo de votos al centro nacional."
                    "</div>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    "<div style='font-size: 0.85rem; color: #555; background-color: #f9f9f9; padding: 10px; border-radius: 6px; border-left: 3px solid #10B981; margin-bottom: 12px;'>"
                    "📈 **Actualización uniforme**: Proyecta el ingreso del total de actas pendientes "
                    "asumiendo que siguen exactamente el mismo patrón de votación promedio registrado hasta el momento."
                    "</div>",
                    unsafe_allow_html=True
                )

            rural_intake = st.slider(
                "2. Avance de carga proyectado (%)", 
                0, 100, 50, 5,
                help="Ajusta el porcentaje de actas pendientes del escenario que deseas procesar e incorporar en el conteo simulado."
            )
            
            # Mostrar slider de retraso solo en el escenario correspondiente
            if scenario == "Retraso en regiones críticas":
                delay_hours = st.slider(
                    "3. Horas de retraso proyectadas", 
                    0, 24, 6, 1,
                    help="Mayor retraso simula un impacto más severo de cuello de botella logístico en la velocidad del procesamiento."
                )
            else:
                delay_hours = 0
                
            st.markdown("<br>", unsafe_allow_html=True)
            run = st.button("▶ Registrar Simulación en Logs", type="primary", width="stretch")

    simulated, used_actas, source_label = simulate_result(summary, locations, scenario, rural_intake, delay_hours)
    current_leader = summary.iloc[0]
    simulated_leader = simulated.iloc[0]
    difference = float(simulated_leader["sim_percentage"] - current_leader["percentage"])
    confidence = max(55, min(95, 86 - abs(difference) * 4 - delay_hours * 0.4))

    if run:
        insert_log(
            "Simulación",
            "Escenario ejecutado",
            f"{scenario}: ingreso={rural_intake}%, retraso={delay_hours}h, actas proyectadas={used_actas:.0f}",
        )
        st.session_state.pop("data_cache", None)
        st.session_state.pop("data_cache_ts", None)

    with right:
        with st.container(border=True):
            st.markdown("### 📊 Resultados de la proyección")
            
            # Alertas visuales intuitivas si cambia el ganador
            if simulated_leader["candidate_id"] != current_leader["candidate_id"]:
                st.warning(
                    f"⚠️ **¡CAMBIO DE LIDERAZGO DETECTADO!**<br>"
                    f"Bajo esta proyección, **{simulated_leader['candidate_name']}** ({simulated_leader['party_name']}) "
                    f"pasa a liderar la elección, superando a **{current_leader['candidate_name']}**.",
                    icon="⚠️"
                )
            else:
                st.success(
                    f"✅ **Liderazgo estable**:<br>"
                    f"**{simulated_leader['candidate_name']}** ({simulated_leader['party_name']}) "
                    f"mantiene el primer lugar en este escenario proyectado.",
                    icon="✅"
                )

            st.write("")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Resultado actual", f"{current_leader['percentage']:.1f}%", current_leader["party_name"])
            m2.metric("Resultado simulado", f"{simulated_leader['sim_percentage']:.1f}%", simulated_leader["party_name"])
            
            # Mostrar diferencia de forma legible
            diff_label = "Variación de porcentaje"
            m3.metric("Diferencia", f"{difference:+.1f} pp", diff_label)
            m4.metric("Confianza del modelo", f"{confidence:.0f}%", "Estimación")

            st.caption(f"**Base de actas simuladas:** {format_int(used_actas)} actas tomadas de {source_label}.")

            # Cuadro de comparación de votación simulada vs real
            st.write("")
            st.markdown("#### Tabla comparativa de resultados:")
            comparison_df = pd.merge(
                summary[["candidate_name", "party_name", "percentage"]],
                simulated[["candidate_name", "sim_percentage"]],
                on="candidate_name",
                suffixes=("_actual", "_simulado")
            )
            comparison_df["Variación"] = comparison_df["sim_percentage"] - comparison_df["percentage"]
            comparison_df.columns = ["Candidato", "Partido", "% Actual", "% Proyectado", "Variación (pp)"]
            
            st.dataframe(
                comparison_df,
                width="stretch",
                hide_index=True,
                column_config={
                    "% Actual": st.column_config.NumberColumn(format="%.2f%%"),
                    "% Proyectado": st.column_config.NumberColumn(format="%.2f%%"),
                    "Variación (pp)": st.column_config.NumberColumn(format="%+.2f pp")
                }
            )

            # Gráfico de barras de resultados simulados
            st.write("")
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
                yaxis_title="% de votos simulados",
                xaxis_title="",
                plot_bgcolor="white",
                paper_bgcolor="white",
            )
            fig.update_traces(textposition="outside", cliponaxis=False)
            st.plotly_chart(fig, width="stretch")

    st.write("")
    st.markdown(
        "<div class='small-note'>Nota: los resultados simulados son referenciales. Si no existen actas pendientes en Supabase, el simulador usa una bolsa proyectada para que los escenarios se puedan comparar.</div>",
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
        st.dataframe(summary, width="stretch", hide_index=True)
        st.download_button(
            "Descargar resumen CSV",
            summary.to_csv(index=False).encode("utf-8"),
            "resumen_candidatos.csv",
            "text/csv",
        )
    with tab2:
        st.dataframe(locations, width="stretch", hide_index=True)
        st.download_button(
            "Descargar avance CSV",
            locations.to_csv(index=False).encode("utf-8"),
            "avance_geografico.csv",
            "text/csv",
        )
    with tab3:
        st.dataframe(data, width="stretch", hide_index=True)
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
    st.dataframe(table, width="stretch", hide_index=True)
 
 
def page_acerca(db_connected: bool):
    st.markdown("## 🏢 Acerca de Cloud Election Sentinel")
    st.write(
        "Esta plataforma web proporciona una interfaz analítica en tiempo real para visualizar y "
        "auditar el avance del procesamiento de actas electorales (estilo ONPE). "
        "Desarrollado de extremo a extremo utilizando Python, Streamlit, Databricks y Supabase PostgreSQL."
    )
    
    st.write("")
    
    # Misión, Visión y Objetivo en columnas estilizadas
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            """
            <div style="background-color: #EAF4FF; border-left: 5px solid #003C7D; padding: 18px; border-radius: 8px; min-height: 250px;">
                <h4 style="color: #003C7D; margin-top: 0;">🎯 Misión</h4>
                <p style="font-size: 0.88rem; line-height: 1.4; color: #1F2937;">
                    Garantizar la transparencia electoral mediante herramientas analíticas interactivas y 
                    proyecciones en tiempo real que faciliten la visualización y auditoría del escrutinio nacional, 
                    permitiendo a los ciudadanos entender el flujo del conteo paso a paso.
                </p>
            </div>
            """, unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            """
            <div style="background-color: #ECFDF5; border-left: 5px solid #10B981; padding: 18px; border-radius: 8px; min-height: 250px;">
                <h4 style="color: #065F46; margin-top: 0;">👁️ Visión</h4>
                <p style="font-size: 0.88rem; line-height: 1.4; color: #1F2937;">
                    Convertirnos en el estándar tecnológico académico de referencia para el análisis, 
                    simulación y auditoría independiente de procesos electorales en entornos cloud, 
                    promoviendo el acceso público a datos limpios y entendimiento estadístico.
                </p>
            </div>
            """, unsafe_allow_html=True
        )
    with c3:
        st.markdown(
            """
            <div style="background-color: #FFFBEB; border-left: 5px solid #F59E0B; padding: 18px; border-radius: 8px; min-height: 250px;">
                <h4 style="color: #92400E; margin-top: 0;">🥅 Objetivo de la Página</h4>
                <p style="font-size: 0.88rem; line-height: 1.4; color: #1F2937;">
                    Ofrecer una visualización intuitiva y dinámica de la votación, estimar y detectar anomalías 
                    de procesamiento geográfico, y proveer un simulador estratégico robusto 
                    para proyectar escenarios electorales realistas a partir de actas pendientes.
                </p>
            </div>
            """, unsafe_allow_html=True
        )
        
    st.write("")
    st.markdown("### ⚙️ Flujo Técnico del Sistema")
    st.code(
        "Dataset electoral → Ingesta/Simulación con Databricks Job → Supabase PostgreSQL (Cloud DB) → Dashboard Streamtlit Cloud → Usuario final",
        language="text"
    )
    
    st.write("")
    st.markdown("### 🌐 Infraestructura y Estado")
    i1, i2, i3 = st.columns(3)
    i1.info("**Frontend:** Streamlit & Plotly")
    i2.info("**Base de Datos:** Supabase PostgreSQL")
    i3.info("**Carga de datos:** Databricks Job Scheduler")
    
    st.write("")
    if db_connected:
        st.success("🟢 Conexión activa y segura con base de datos en Supabase PostgreSQL.")
    else:
        st.warning("⚠️ No conectado a Supabase. Configura las variables en secrets.toml para habilitar la visualización en tiempo real.")
 
 
# ==========================================================
# App principal
# ==========================================================
def main():
    candidates, locations, votes, logs, db_connected = load_data()

    #with st.sidebar:
    #    st.markdown("## 🗳️ Cloud Election Sentinel")
    #    st.caption("Sistema analítico del conteo electoral")
    #    option = st.radio(
    #        "Menú",
    #        ["Resumen", "Resultados", "Mapa", "Simulador", "Reportes", "Logs", "Acerca de"],
    #        label_visibility="collapsed",
    #    )
    #    st.divider()
    #    st.caption("Base web en Python · Streamlit · Supabase")

    #render_header(db_connected)

    with st.sidebar:
        # Título Institucional
        st.markdown(
            """
            <div style="text-align: center; padding: 10px 0; border-bottom: 2px solid #003C7D; margin-bottom: 20px;">
                <h3 style="margin: 0; color: #003C7D; font-weight: 800; font-size: 20px;">🗳️ ELECTION SENTINEL</h3>
                <span style="font-size: 11px; letter-spacing: 1px; color: #6B7280; font-weight: bold;">ONPE CLOUD ANALYTICS</span>
            </div>
            """, unsafe_allow_html=True
        )
        
        # Inyección de CSS para transformar los Radio Buttons en Botones Institucionales
        st.markdown(
            """
            <style>
                /* Ocultar el círculo nativo de los radio buttons */
                div[data-testid="stSidebar"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
                    font-weight: 600 !important;
                    font-size: 14px !important;
                }
                div[data-testid="stSidebar"] div[role="radiogroup"] label {
                    background-color: var(--secondary-background-color);
                    border: 1px solid var(--border-color);
                    padding: 12px 16px !important;
                    border-radius: 8px !important;
                    margin-bottom: 8px !important;
                    transition: all 0.2s ease;
                    width: 100%;
                    cursor: pointer;
                }
                /* Ocultar el círculo de selección por defecto */
                div[data-testid="stSidebar"] div[role="radiogroup"] label [data-testid="stWidgetSelectionMarker"] {
                    display: none !important;
                }
                /* Estilo cuando el botón está seleccionado (Colores ONPE / Perú) */
                div[data-testid="stSidebar"] div[role="radiogroup"] [data-checked="true"] label {
                    background: linear-gradient(90deg, #003C7D 0%, #0B5CAB 100%) !important;
                    color: white !important;
                    border-color: #003C7D !important;
                    box-shadow: 0 4px 6px -1px rgba(0, 60, 125, 0.2);
                }
                /* Efecto Hover */
                div[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
                    border-color: #003C7D !important;
                    transform: translateX(3px);
                }
            </style>
            """, unsafe_allow_html=True
        )
        
        options = ["Resumen", "Resultados", "Mapa", "Simulador", "Reportes", "Logs", "Acerca de"]
        option = st.radio("Menú", options, label_visibility="collapsed")
        
        st.markdown("<br><hr style='border-color: var(--border-color);'><br>", unsafe_allow_html=True)
        st.caption("🇵🇪 Sistema de Control de Actas Oficial · USIL 2026")
 
    render_header(db_connected)
 
    if option == "Resumen":
        page_resumen(candidates, locations, votes, db_connected) # <- Aquí agregamos db_connected
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
    _APP_RESULT = main()
