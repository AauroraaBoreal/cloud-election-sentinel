from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Tuple

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
    data = votes.merge(candidates, on="candidate_id", how="left").merge(
        locations[["location_id", "region", "province", "district"]], on="location_id", how="left"
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
    # Si no existe, lo calculamos por velocidad como respaldo.
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
    data = joined_results(candidates, locations, votes)
    summary = candidate_summary(data)
    total_votes = int(summary["valid_votes"].sum())

    st.markdown("## Resultados electorales")
    st.caption("Vista consolidada por candidato y organización política")

    c1, c2, c3 = st.columns(3)
    c1.metric("Votos válidos", format_int(total_votes))
    c2.metric("Candidatos", str(len(summary)))
    c3.metric("Actas contabilizadas", format_int(locations["actas_contabilizadas"].sum()))

    left, right = st.columns([1.3, 1])
    with left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.plotly_chart(make_votes_chart(summary), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        table = summary[["candidate_name", "party_name", "valid_votes", "percentage"]].copy()
        table.columns = ["Candidato", "Organización política", "Votos", "%"]
        table["Votos"] = table["Votos"].map(format_int)
        table["%"] = table["%"].map(lambda x: f"{x:.2f}%")
        st.dataframe(table, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)


def page_mapa(locations, candidates, votes):
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
        page_resumen(candidates, locations, votes)
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
