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

# Refresca Streamlit cada 60 segundos para leer cambios de Supabase
if st_autorefresh is not None:
    st_autorefresh(interval=60 * 1000, key="auto_refresh_cloud_election")

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


# ==========================================================
# Datos demo de respaldo si la BD aún no está conectada
# ==========================================================
CANDIDATES_DEMO = pd.DataFrame(
    [
        (1, "Ana Kori", "Fuerza Popular", "K", "#1F66B1"),
        (2, "José Paredes", "Juntos por el Perú", "JP", "#2F7CC0"),
        (3, "Renato Vargas", "Renovación Popular", "R", "#7DBAE0"),
        (4, "Alonso Medina", "Alianza Popular", "AP", "#88C3E8"),
        (5, "Óscar Rivas", "Obras por el Perú", "OBRAS", "#9CCEEB"),
        (6, "Miguel Salas", "País para Todos", "PPT", "#73B3D7"),
        (7, "Raúl Torres", "Acción Popular", "APOP", "#60A3CB"),
    ],
    columns=["candidate_id", "candidate_name", "party_name", "party_symbol", "display_color"],
)

LOCATIONS_DEMO = pd.DataFrame(
    [
        (1, "Lima", "Lima", "Lima", -12.0464, -77.0428, 30140, 30140, 0, 0, 920.0),
        (2, "La Libertad", "Trujillo", "Trujillo", -8.1116, -79.0288, 7900, 7900, 0, 0, 310.0),
        (3, "Piura", "Piura", "Piura", -5.1945, -80.6328, 6700, 6700, 0, 0, 285.0),
        (4, "Arequipa", "Arequipa", "Arequipa", -16.4090, -71.5375, 7600, 7600, 0, 0, 340.0),
        (5, "Cusco", "Cusco", "Cusco", -13.5319, -71.9675, 5200, 5200, 0, 0, 160.0),
        (6, "Puno", "Puno", "Puno", -15.8402, -70.0219, 4800, 4800, 0, 0, 95.0),
        (7, "Junín", "Huancayo", "Huancayo", -12.0651, -75.2049, 5400, 5400, 0, 0, 230.0),
        (8, "Huancavelica", "Huancavelica", "Huancavelica", -12.7864, -74.9764, 3200, 3200, 0, 0, 82.0),
        (9, "Amazonas", "Chachapoyas", "Chachapoyas", -6.2317, -77.8690, 2410, 2410, 0, 0, 76.0),
        (10, "Ucayali", "Coronel Portillo", "Callería", -8.3791, -74.5539, 6873, 6873, 0, 0, 88.0),
    ],
    columns=[
        "location_id",
        "region",
        "province",
        "district",
        "latitude",
        "longitude",
        "total_actas",
        "actas_contabilizadas",
        "actas_pendientes",
        "actas_observadas",
        "velocidad_actas_hora",
    ],
)

LOCATIONS_DEMO = pd.DataFrame(
    [
        (1, "Lima Metropolitana", "Lima", "Lima", -12.0464, -77.0428, 30140, 24610, 5530, 215, 1025.4),
        (2, "La Libertad", "Trujillo", "Trujillo", -8.1116, -79.0288, 7900, 6125, 1775, 68, 255.2),
        (3, "Piura", "Piura", "Piura", -5.1945, -80.6328, 6700, 4925, 1775, 74, 205.2),
        (4, "Arequipa", "Arequipa", "Arequipa", -16.4090, -71.5375, 7600, 6420, 1180, 58, 267.5),
        (5, "Cajamarca", "Cajamarca", "Cajamarca", -7.1617, -78.5128, 5900, 3920, 1980, 92, 163.3),
        (6, "Cusco", "Cusco", "Cusco", -13.5319, -71.9675, 5200, 3650, 1550, 80, 152.1),
        (7, "Junin", "Huancayo", "Huancayo", -12.0651, -75.2049, 5400, 4310, 1090, 47, 179.6),
        (8, "Lambayeque", "Chiclayo", "Chiclayo", -6.7714, -79.8409, 5000, 4210, 790, 35, 175.4),
        (9, "Ancash", "Santa", "Chimbote", -9.0745, -78.5936, 5100, 3320, 1780, 83, 138.3),
        (10, "Puno", "Puno", "Puno", -15.8402, -70.0219, 4800, 2850, 1950, 96, 118.8),
    ],
    columns=[
        "location_id",
        "region",
        "province",
        "district",
        "latitude",
        "longitude",
        "total_actas",
        "actas_contabilizadas",
        "actas_pendientes",
        "actas_observadas",
        "velocidad_actas_hora",
    ],
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


def build_demo_votes() -> pd.DataFrame:
    rows = []
    for _, loc in LOCATIONS_DEMO.iterrows():
        total_valid_votes = int(loc["actas_contabilizadas"] * 320)
        shares = _region_modifier(loc["region"])
        votes = np.floor(total_valid_votes * shares).astype(int)
        votes[0] += total_valid_votes - int(votes.sum())
        for candidate_id, valid_votes in zip(CANDIDATES_DEMO["candidate_id"], votes):
            rows.append((loc["location_id"], candidate_id, int(valid_votes)))
    return pd.DataFrame(rows, columns=["location_id", "candidate_id", "valid_votes"])


LOGS_DEMO = pd.DataFrame(
    [
        (datetime.now() - timedelta(minutes=5), "Actualización", "Carga de dataset", "Dataset actas_2026_05_24.csv cargado correctamente"),
        (datetime.now() - timedelta(minutes=10), "Procesamiento", "Cálculo de métricas", "Métricas actualizadas para todas las regiones"),
        (datetime.now() - timedelta(minutes=20), "Simulación", "Escenario ejecutado", "Escenario: ingreso de actas rurales al 50%"),
        (datetime.now() - timedelta(minutes=35), "Actualización", "Actualización de actas", "Se actualizaron 90,223 actas en la base de datos"),
        (datetime.now() - timedelta(minutes=50), "Sistema", "Inicio de sesión", "Usuario: admin"),
        (datetime.now() - timedelta(minutes=70), "Sistema", "Conexión a BD", "Conexión a Supabase exitosa"),
        (datetime.now() - timedelta(minutes=90), "Procesamiento", "Limpieza de datos", "Datos validados y transformados correctamente"),
    ],
    columns=["event_time", "event_type", "event_name", "detail"],
)


# ==========================================================
# Conexión a Supabase
# ==========================================================
@st.cache_resource(show_spinner=False)
def get_connection():
    try:
        if psycopg2 is None:
            return None

        postgres = st.secrets["postgres"]

        conn = psycopg2.connect(
            user=postgres["USER"],
            password=postgres["PASSWORD"],
            host=postgres["HOST"],
            port=postgres.get("PORT", "5432"),
            dbname=postgres.get("DBNAME", "postgres"),
            sslmode="require",
            connect_timeout=10,
        )

        # Importante para que la conexión cacheada vea los nuevos datos del Job
        conn.autocommit = True

        return conn

    except Exception:
        return None


def read_sql(query: str, params: Optional[Tuple] = None) -> Optional[pd.DataFrame]:
    conn = get_connection()

    if conn is None:
        return None

    try:
        return pd.read_sql_query(query, conn, params=params)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None


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


def load_ces_data() -> Optional[tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """
    Lee la data que actualiza Databricks:
    - ces_conteo
    - ces_logs

    Luego transforma esa data al formato que ya usan:
    - Resumen
    - Resultados
    - Mapa
    - Reportes
    - Logs
    """

    conteo = read_sql(
        """
        SELECT
            id,
            region,
            provincia,
            distrito,
            actas_total,
            actas_contabilizadas,
            actas_pendientes,
            avance_pct,
            velocidad_actas_hora,
            ultimo_ingreso_actas,
            estado,
            color_estado,
            motivo_retraso,
            detalle_retraso,
            votos_a,
            votos_b,
            votos_c,
            votos_d,
            votos_e,
            updated_at
        FROM ces_conteo
        ORDER BY region
        """
    )

    if conteo is None or conteo.empty:
        return None

    # Candidatos conectados a las columnas votos_a, votos_b, votos_c, votos_d, votos_e
    candidates = pd.DataFrame(
        [
            (1, "Candidata A", "Fuerza Popular", "K", "#1F66B1"),
            (2, "Candidato B", "Juntos por el Perú", "JP", "#2F7CC0"),
            (3, "Candidato C", "Renovación Popular", "R", "#7DBAE0"),
            (4, "Candidato D", "Alianza Popular", "AP", "#88C3E8"),
            (5, "Candidato E", "Acción Popular", "APOP", "#9CCEEB"),
        ],
        columns=[
            "candidate_id",
            "candidate_name",
            "party_name",
            "party_symbol",
            "display_color",
        ],
    )

    coords = {
        "Lima": (-12.0464, -77.0428),
        "Arequipa": (-16.4090, -71.5375),
        "Cusco": (-13.5319, -71.9675),
        "Puno": (-15.8402, -70.0219),
        "Huancavelica": (-12.7864, -74.9764),
        "Ucayali": (-8.3791, -74.5539),
        "Loreto": (-3.7437, -73.2516),
    }

    locations = conteo.copy()

    locations["location_id"] = locations["id"]
    locations["province"] = locations["provincia"]
    locations["district"] = locations["distrito"]
    locations["total_actas"] = locations["actas_total"]
    locations["actas_observadas"] = 0
    locations["latitude"] = locations["region"].map(lambda x: coords.get(x, (-9.3, -75.1))[0])
    locations["longitude"] = locations["region"].map(lambda x: coords.get(x, (-9.3, -75.1))[1])

    locations = locations[
        [
            "location_id",
            "region",
            "province",
            "district",
            "latitude",
            "longitude",
            "total_actas",
            "actas_contabilizadas",
            "actas_pendientes",
            "actas_observadas",
            "velocidad_actas_hora",
            "ultimo_ingreso_actas",
            "avance_pct",
            "estado",
            "color_estado",
            "motivo_retraso",
            "detalle_retraso",
            "updated_at",
        ]
    ]

    vote_rows = []

    for _, row in conteo.iterrows():
        vote_rows.append(
            {
                "location_id": int(row["id"]),
                "candidate_id": 1,
                "valid_votes": int(row["votos_a"] or 0),
            }
        )
        vote_rows.append(
            {
                "location_id": int(row["id"]),
                "candidate_id": 2,
                "valid_votes": int(row["votos_b"] or 0),
            }
        )
        vote_rows.append(
            {
                "location_id": int(row["id"]),
                "candidate_id": 3,
                "valid_votes": int(row["votos_c"] or 0),
            }
        )
        vote_rows.append(
            {
                "location_id": int(row["id"]),
                "candidate_id": 4,
                "valid_votes": int(row["votos_d"] or 0),
            }
        )
        vote_rows.append(
            {
                "location_id": int(row["id"]),
                "candidate_id": 5,
                "valid_votes": int(row["votos_e"] or 0),
            }
        )

    votes = pd.DataFrame(vote_rows)

    logs = read_sql(
        """
        SELECT
            fecha_hora AS event_time,
            tipo AS event_type,
            evento AS event_name,
            detalle AS detail
        FROM ces_logs
        ORDER BY fecha_hora DESC
        LIMIT 50
        """
    )

    if logs is None or logs.empty:
        logs = LOGS_DEMO.copy()

    return candidates, locations, votes, logs


def load_legacy_data() -> Optional[tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """
    Respaldo por si aún quieres leer las tablas antiguas.
    Pero la prioridad será ces_conteo.
    """
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

    if candidates is None or locations is None or votes is None:
        return None

    if candidates.empty or locations.empty or votes.empty:
        return None

    if logs is None or logs.empty:
        logs = LOGS_DEMO.copy()

    return candidates, locations, votes, logs


@st.cache_data(ttl=30, show_spinner=False)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, bool]:
    # 1. Primero lee la data nueva generada por Databricks
    ces_data = load_ces_data()

    if ces_data is not None:
        candidates, locations, votes, logs = ces_data
        return candidates, locations, votes, logs, True

    # 2. Si no existe ces_conteo, lee las tablas antiguas
    legacy_data = load_legacy_data()

    if legacy_data is not None:
        candidates, locations, votes, logs = legacy_data
        return candidates, locations, votes, logs, True

    # 3. Último respaldo: demo local
    return (
        CANDIDATES_DEMO.copy(),
        LOCATIONS_DEMO.copy(),
        build_demo_votes(),
        LOGS_DEMO.copy(),
        False,
    )


# ==========================================================
# Transformaciones
# ==========================================================
def apply_filters(locations: pd.DataFrame) -> pd.DataFrame:
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


def render_header(db_connected: bool) -> None:
    now_text = datetime.now().strftime("%d/%m/%Y %I:%M %p").lower().replace("am", "a. m.").replace("pm", "p. m.")
    status = "Conectado a Supabase" if db_connected else "Modo demo: sin conexión a Supabase"
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
                use_container_width=True, 
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
                    use_container_width=True, 
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
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Actas Pendientes": st.column_config.NumberColumn(format="%d"),
                        "% Pendiente": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
                        "Velocidad (Actas/h)": st.column_config.NumberColumn(format="%.1f")
                    }
                )

def page_resumen(candidates, locations, votes):
    filtered_locations = apply_filters(locations)
    data = joined_results(candidates, filtered_locations, votes)
    summary = candidate_summary(data)
    metrics = general_metrics(filtered_locations, summary)

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
        st.plotly_chart(make_bar_chart(summary), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown("### Interpretación del conteo")
        st.write("🗳️ El avance del conteo se concentra principalmente en zonas urbanas.")
        st.write("⏳ Las regiones con menor velocidad pueden modificar la lectura del resultado parcial.")
        st.write("📍 El análisis geográfico ayuda a ubicar zonas con procesamiento lento.")
        st.write("🔎 El simulador permite evaluar escenarios sin usar inteligencia artificial.")
        st.markdown("[Ver análisis detallado →](#)")
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    st.markdown(
        f"<div class='small-note'>Datos referenciales. Total de actas: <b>{format_int(metrics['total_actas'])}</b>. Fuente: dataset público/simulado con estructura ONPE.</div>",
        unsafe_allow_html=True,
    )


def page_resultados(candidates, locations, votes):
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


def simulate_result(summary: pd.DataFrame, rural_intake: int, delay_hours: int) -> pd.DataFrame:
    simulated = summary.copy()
    # Ajuste determinístico: no es IA, solo fórmula de escenario.
    rural_factor = (rural_intake - 50) / 100
    delay_factor = delay_hours / 24
    effects = np.array([-0.035, 0.025, -0.010, 0.030, 0.018, 0.012, 0.006])
    delay_effects = np.array([0.004, -0.006, 0.002, -0.005, 0.002, 0.001, 0.002])
    current = simulated["percentage"].to_numpy() / 100
    adjusted = current + effects[: len(current)] * rural_factor + delay_effects[: len(current)] * delay_factor
    adjusted = np.clip(adjusted, 0.001, None)
    adjusted = adjusted / adjusted.sum()
    simulated["sim_percentage"] = adjusted * 100
    total_votes = simulated["valid_votes"].sum()
    simulated["sim_votes"] = (adjusted * total_votes).round().astype(int)
    return simulated.sort_values("sim_percentage", ascending=False)


def page_simulador(candidates, locations, votes):
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

    simulated = simulate_result(summary, rural_intake, delay_hours)
    current_leader = summary.iloc[0]
    simulated_leader = simulated.iloc[0]
    difference = simulated_leader["sim_percentage"] - current_leader["percentage"]
    confidence = max(55, min(95, 86 - abs(difference) * 4 - delay_hours * 0.4))

    if run:
        insert_log("Simulación", "Escenario ejecutado", f"{scenario}: rural={rural_intake}%, retraso={delay_hours}h")
        st.cache_data.clear()

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
    st.success("Conexión activa a Supabase" if db_connected else "La app está usando datos demo hasta configurar Supabase")


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
        page_resumen(candidates, locations, votes) # <- Aquí agregamos db_connected
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