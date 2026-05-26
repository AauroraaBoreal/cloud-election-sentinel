# Databricks notebook source
# MAGIC %pip install toml psycopg2-binary numpy pandas

# COMMAND ----------

# Reinicia el entorno para que Databricks reconozca las librerías instaladas.
# Si tu cluster ya tiene las librerías, puedes comentar esta línea después de la primera ejecución.
dbutils.library.restartPython()

# COMMAND ----------

"""
Cloud Election Sentinel - Job Databricks
---------------------------------------
Objetivo:
    Simular el ingreso progresivo de actas electorales cada 15 minutos,
    guardar la nueva data en Supabase PostgreSQL y registrar incidencias
    cuando una región/distrito presenta bajo avance de conteo.

Uso recomendado:
    1. Subir este archivo al repo clonado en Databricks.
    2. Crear un Job en Databricks que ejecute este notebook cada 15 minutos.
    3. La app en Streamlit solo leerá Supabase y mostrará la data actualizada.

Notas:
    - No usa IA.
    - No usa modelos ML.
    - La simulación se basa en reglas y escenarios operativos plausibles.
    - Si el Job se ejecuta dos veces en la misma ventana de 15 minutos, no duplica data,
      salvo que actives el parámetro force_run = true.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import os
import random

import numpy as np
import pandas as pd
import psycopg2
import toml
from psycopg2.extras import execute_values

# COMMAND ----------

# ==========================================================
# 0. PARÁMETRO OPCIONAL DEL JOB
# ==========================================================
# En Databricks puedes crear un parámetro llamado force_run.
# false = comportamiento normal, evita duplicar data dentro del mismo ciclo de 15 min.
# true  = fuerza la ejecución, útil para probar varias veces manualmente.

try:
    dbutils.widgets.text("force_run", "false", "Forzar ejecución")
    FORCE_RUN = dbutils.widgets.get("force_run").strip().lower() in ["true", "1", "yes", "si", "sí"]
except Exception:
    FORCE_RUN = False

print(f"FORCE_RUN = {FORCE_RUN}")

# COMMAND ----------

# ==========================================================
# 1. CONFIGURACIÓN DE SUPABASE / POSTGRES
# ==========================================================

def find_file_upwards(filename: str) -> Path | None:
    """Busca un archivo desde el directorio actual hacia arriba."""
    current = Path.cwd()
    candidates = [current, *current.parents]
    for base in candidates:
        path = base / filename
        if path.exists():
            return path
    return None


def load_postgres_config() -> dict:
    """
    Prioridad de credenciales:
    1. secrets.toml dentro del repo, similar al archivo pc-job-cc.
    2. Databricks Secrets, si configuraste un scope llamado supabase.
    3. Variables de entorno del cluster/job.

    Formato esperado para secrets.toml:

    [postgres]
    USER = "postgres"
    PASSWORD = "tu_password"
    HOST = "db.xxxxxxxxxxxxx.supabase.co"
    PORT = "5432"
    DBNAME = "postgres"
    """
    secret_path = find_file_upwards("secrets.toml")
    if secret_path:
        print(f"Leyendo credenciales desde: {secret_path}")
        return toml.load(secret_path)["postgres"]

    try:
        print("Leyendo credenciales desde Databricks Secrets: scope supabase")
        return {
            "USER": dbutils.secrets.get(scope="supabase", key="USER"),
            "PASSWORD": dbutils.secrets.get(scope="supabase", key="PASSWORD"),
            "HOST": dbutils.secrets.get(scope="supabase", key="HOST"),
            "PORT": dbutils.secrets.get(scope="supabase", key="PORT"),
            "DBNAME": dbutils.secrets.get(scope="supabase", key="DBNAME"),
        }
    except Exception:
        print("No se encontró secrets.toml ni Databricks Secrets. Usando variables de entorno.")

    return {
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", ""),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "DBNAME": os.getenv("POSTGRES_DBNAME", "postgres"),
    }


cfg = load_postgres_config()

USER = cfg["USER"]
PASSWORD = cfg["PASSWORD"]
HOST = cfg["HOST"]
PORT = cfg.get("PORT", "5432")
DBNAME = cfg.get("DBNAME", "postgres")

if not HOST or not PASSWORD:
    raise ValueError("Faltan credenciales de Supabase/Postgres. Revisa secrets.toml, Databricks Secrets o variables de entorno.")


def get_connection():
    return psycopg2.connect(
        user=USER,
        password=PASSWORD,
        host=HOST,
        port=PORT,
        dbname=DBNAME,
        sslmode="require",
        connect_timeout=10,
    )

print("Configuración cargada correctamente.")
print(f"Host: {HOST}")
print(f"DB: {DBNAME}")

# COMMAND ----------

# ==========================================================
# 2. DDL - TABLAS NECESARIAS EN SUPABASE
# ==========================================================
# Este DDL es idempotente: se puede ejecutar muchas veces sin romper la BD.

DDL_SQL = """
CREATE TABLE IF NOT EXISTS candidates (
    candidate_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    candidate_name TEXT NOT NULL,
    party_name TEXT NOT NULL,
    party_symbol TEXT,
    display_color TEXT DEFAULT '#0B4EA2',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_candidates_name_party
ON candidates(candidate_name, party_name);

CREATE TABLE IF NOT EXISTS locations (
    location_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    region TEXT NOT NULL,
    province TEXT NOT NULL,
    district TEXT NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    total_actas INTEGER NOT NULL DEFAULT 0,
    actas_contabilizadas INTEGER NOT NULL DEFAULT 0,
    actas_pendientes INTEGER NOT NULL DEFAULT 0,
    actas_observadas INTEGER NOT NULL DEFAULT 0,
    velocidad_actas_hora NUMERIC(10,2) NOT NULL DEFAULT 0,
    estado_conteo TEXT DEFAULT 'Sin información',
    motivo_retraso TEXT,
    detalle_retraso TEXT,
    ultimo_incremento_actas INTEGER DEFAULT 0,
    ultimo_incremento_votos INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_location UNIQUE (region, province, district)
);

ALTER TABLE locations ADD COLUMN IF NOT EXISTS estado_conteo TEXT DEFAULT 'Sin información';
ALTER TABLE locations ADD COLUMN IF NOT EXISTS motivo_retraso TEXT;
ALTER TABLE locations ADD COLUMN IF NOT EXISTS detalle_retraso TEXT;
ALTER TABLE locations ADD COLUMN IF NOT EXISTS ultimo_incremento_actas INTEGER DEFAULT 0;
ALTER TABLE locations ADD COLUMN IF NOT EXISTS ultimo_incremento_votos INTEGER DEFAULT 0;

CREATE TABLE IF NOT EXISTS vote_results (
    result_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    location_id BIGINT NOT NULL REFERENCES locations(location_id) ON DELETE CASCADE,
    candidate_id BIGINT NOT NULL REFERENCES candidates(candidate_id) ON DELETE CASCADE,
    valid_votes INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_vote_location_candidate UNIQUE (location_id, candidate_id)
);

CREATE TABLE IF NOT EXISTS event_logs (
    log_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    event_time TIMESTAMPTZ DEFAULT now(),
    event_type TEXT NOT NULL,
    event_name TEXT NOT NULL,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS simulation_runs (
    run_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    run_time TIMESTAMPTZ DEFAULT now(),
    total_new_actas INTEGER DEFAULT 0,
    total_new_votes INTEGER DEFAULT 0,
    regions_critical INTEGER DEFAULT 0,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    event_time TIMESTAMPTZ DEFAULT now(),
    location_id BIGINT REFERENCES locations(location_id) ON DELETE CASCADE,
    region TEXT NOT NULL,
    province TEXT,
    district TEXT,
    severity TEXT NOT NULL,
    incident_type TEXT NOT NULL,
    explanation TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE IF NOT EXISTS job_executions (
    cycle_key TEXT PRIMARY KEY,
    started_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT DEFAULT 'running',
    total_new_actas INTEGER DEFAULT 0,
    total_new_votes INTEGER DEFAULT 0,
    regions_critical INTEGER DEFAULT 0,
    detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_locations_region ON locations(region);
CREATE INDEX IF NOT EXISTS idx_locations_province ON locations(province);
CREATE INDEX IF NOT EXISTS idx_locations_district ON locations(district);
CREATE INDEX IF NOT EXISTS idx_vote_results_location ON vote_results(location_id);
CREATE INDEX IF NOT EXISTS idx_vote_results_candidate ON vote_results(candidate_id);
CREATE INDEX IF NOT EXISTS idx_event_logs_time ON event_logs(event_time DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_time ON incidents(event_time DESC);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_time ON simulation_runs(run_time DESC);
"""

with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(DDL_SQL)
    conn.commit()

print("DDL ejecutado correctamente.")

# COMMAND ----------

# ==========================================================
# 3. DATA BASE INICIAL - CANDIDATOS Y UBICACIONES
# ==========================================================
# Esto solo inserta si no existe. No pisa el avance ya generado.

CANDIDATES = [
    ("Candidata 1", "Fuerza Popular", "K", "#0B3B82"),
    ("Candidato 2", "Juntos por el Perú", "JP", "#0057D9"),
    ("Candidato 3", "Renovación Popular", "R", "#63B3ED"),
    ("Candidato 4", "Alianza Popular", "SOL", "#7EC8E3"),
    ("Candidato 5", "Obras por el Perú", "OBRAS", "#88C9EF"),
    ("Candidato 6", "País para Todos", "PPT", "#A0D8F1"),
    ("Candidato 7", "Acción Popular", "AP", "#B6E0F5"),
]

LOCATIONS = [
    # region, provincia, distrito, lat, lon, total_actas, observadas iniciales
    ("Lima", "Lima", "San Juan de Lurigancho", -11.997, -77.009, 7200, 18),
    ("Lima", "Lima", "Comas", -11.932, -77.040, 5100, 12),
    ("Lima", "Lima", "Villa El Salvador", -12.213, -76.936, 4300, 10),
    ("La Libertad", "Trujillo", "Trujillo", -8.111, -79.028, 3600, 9),
    ("La Libertad", "Trujillo", "El Porvenir", -8.083, -79.000, 2100, 6),
    ("Piura", "Piura", "Piura", -5.194, -80.632, 3900, 10),
    ("Piura", "Sullana", "Sullana", -4.903, -80.685, 2400, 7),
    ("Arequipa", "Arequipa", "Cerro Colorado", -16.376, -71.559, 3000, 8),
    ("Arequipa", "Arequipa", "Paucarpata", -16.430, -71.500, 2200, 6),
    ("Cusco", "Cusco", "Cusco", -13.531, -71.967, 2500, 7),
    ("Cusco", "La Convención", "Santa Ana", -12.867, -72.693, 1300, 4),
    ("Puno", "Puno", "Puno", -15.840, -70.021, 2600, 8),
    ("Puno", "San Román", "Juliaca", -15.499, -70.133, 3000, 10),
    ("Junín", "Huancayo", "Huancayo", -12.065, -75.205, 2700, 7),
    ("Junín", "Satipo", "Satipo", -11.252, -74.638, 1200, 4),
    ("Huancavelica", "Huancavelica", "Huancavelica", -12.787, -74.972, 1100, 4),
    ("Huancavelica", "Tayacaja", "Pampas", -12.398, -74.867, 850, 3),
    ("Amazonas", "Chachapoyas", "Chachapoyas", -6.229, -77.872, 900, 3),
    ("Amazonas", "Bagua", "Bagua", -5.638, -78.531, 950, 3),
    ("Ucayali", "Coronel Portillo", "Callería", -8.379, -74.553, 1700, 5),
    ("Ucayali", "Atalaya", "Raymondi", -10.729, -73.755, 700, 2),
]

INITIAL_PROGRESS_BY_REGION = {
    "Lima": 0.60,
    "La Libertad": 0.52,
    "Piura": 0.42,
    "Arequipa": 0.48,
    "Cusco": 0.35,
    "Puno": 0.28,
    "Junín": 0.40,
    "Huancavelica": 0.24,
    "Amazonas": 0.22,
    "Ucayali": 0.25,
}


def seed_base_data():
    with get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO candidates (candidate_name, party_name, party_symbol, display_color)
                VALUES %s
                ON CONFLICT (candidate_name, party_name) DO NOTHING
                """,
                CANDIDATES,
            )

            for region, province, district, lat, lon, total_actas, observed in LOCATIONS:
                initial_progress = INITIAL_PROGRESS_BY_REGION.get(region, 0.35)
                initial_counted = int(total_actas * initial_progress)
                pending = max(total_actas - initial_counted - observed, 0)
                cur.execute(
                    """
                    INSERT INTO locations (
                        region, province, district, latitude, longitude,
                        total_actas, actas_contabilizadas, actas_pendientes, actas_observadas,
                        velocidad_actas_hora, estado_conteo, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (region, province, district) DO NOTHING
                    """,
                    (
                        region,
                        province,
                        district,
                        lat,
                        lon,
                        total_actas,
                        initial_counted,
                        pending,
                        observed,
                        0,
                        "Sin información",
                    ),
                )

            cur.execute(
                """
                INSERT INTO event_logs (event_type, event_name, detail)
                VALUES (%s, %s, %s)
                """,
                (
                    "Sistema",
                    "Verificación de datos base",
                    "Se verificó la existencia de candidatos y ubicaciones electorales para la simulación.",
                ),
            )
        conn.commit()


seed_base_data()
print("Datos base verificados correctamente.")

# COMMAND ----------

# ==========================================================
# 4. REGLAS DE SIMULACIÓN
# ==========================================================

BASE_SHARE = np.array([28.5, 18.7, 16.2, 13.4, 8.9, 6.3, 4.5], dtype=float)
BASE_SHARE = BASE_SHARE / BASE_SHARE.sum()

# Porcentaje del total de actas que puede ingresar por ciclo de 15 min.
REGION_SPEED_PROFILE = {
    "Lima": (0.010, 0.030),
    "La Libertad": (0.009, 0.024),
    "Piura": (0.006, 0.018),
    "Arequipa": (0.009, 0.024),
    "Cusco": (0.004, 0.014),
    "Puno": (0.001, 0.007),
    "Junín": (0.006, 0.018),
    "Huancavelica": (0.001, 0.006),
    "Amazonas": (0.001, 0.006),
    "Ucayali": (0.001, 0.007),
}

# Probabilidad de que el ciclo tenga una incidencia simulada.
ISSUE_PROBABILITY = {
    "Lima": 0.05,
    "La Libertad": 0.08,
    "Piura": 0.35,
    "Arequipa": 0.08,
    "Cusco": 0.40,
    "Puno": 0.70,
    "Junín": 0.30,
    "Huancavelica": 0.75,
    "Amazonas": 0.75,
    "Ucayali": 0.70,
}

# Problemáticas simuladas, pero realistas para justificar bajo avance.
ISSUE_POOL = {
    "Puno": [
        ("Corte eléctrico intermitente", "Interrupciones de energía en centros de acopio reducen la velocidad de registro y validación de actas."),
        ("Conectividad intermitente", "La transmisión de información desde algunos puntos alejados presenta cortes temporales."),
        ("Traslado de material electoral", "La distancia entre locales de votación y puntos de acopio retrasa el ingreso de nuevas actas."),
    ],
    "Huancavelica": [
        ("Traslado de material electoral", "Rutas rurales y distancia hacia puntos de acopio generan menor ingreso de actas en la última actualización."),
        ("Condición de ruta", "La logística de recolección se ralentiza por tramos de difícil acceso."),
        ("Baja capacidad de digitación", "El volumen pendiente supera la capacidad operativa del turno actual."),
    ],
    "Amazonas": [
        ("Condición de ruta", "Demora en el traslado desde zonas alejadas reduce temporalmente el conteo reportado."),
        ("Conectividad intermitente", "Algunos puntos de digitalización no reportan datos de forma continua."),
        ("Validación manual adicional", "Parte de las actas requiere revisión antes de ser contabilizada."),
    ],
    "Ucayali": [
        ("Conectividad y transporte fluvial", "La dependencia de rutas fluviales y conectividad limitada retrasa el envío de actas."),
        ("Traslado de material electoral", "Algunos paquetes electorales tardan más en llegar al punto de cómputo."),
        ("Conectividad intermitente", "La carga de actas se interrumpe por baja estabilidad de red."),
    ],
    "Cusco": [
        ("Conectividad intermitente", "Algunos puntos de digitalización presentan conexión inestable, por eso el ingreso avanza más lento."),
        ("Carga acumulada", "El lote de actas pendiente supera la capacidad normal de procesamiento del turno."),
    ],
    "Piura": [
        ("Demora logística", "Retraso en el traslado de actas desde locales alejados hacia el centro de cómputo provincial."),
        ("Validación manual adicional", "Algunas actas requieren verificación antes de ser añadidas al consolidado."),
    ],
    "Junín": [
        ("Carga acumulada", "El volumen de actas pendientes supera la capacidad normal de digitación del turno actual."),
        ("Conectividad intermitente", "La transmisión de algunos puntos no se mantiene estable."),
    ],
    "DEFAULT": [
        ("Procesamiento regular", "El conteo avanza dentro del ritmo esperado para la zona."),
        ("Validación manual adicional", "Un grupo menor de actas requiere revisión antes de contabilizarse."),
    ],
}

REGION_VOTE_MODIFIER = {
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


def get_cycle_key() -> str:
    """Agrupa ejecuciones por ventana de 15 minutos en UTC."""
    now = datetime.now(timezone.utc)
    quarter = now.minute // 15
    return f"{now:%Y%m%d%H}-Q{quarter}"


def rng_for_cycle(region: str, location_id: int, cycle_key: str) -> np.random.Generator:
    seed_text = f"{cycle_key}-{region}-{location_id}"
    seed = int(hashlib.sha256(seed_text.encode()).hexdigest()[:8], 16)
    return np.random.default_rng(seed)


def region_share(region: str) -> np.ndarray:
    modifier = np.array(REGION_VOTE_MODIFIER.get(region, [1] * len(BASE_SHARE)), dtype=float)
    share = BASE_SHARE * modifier
    return share / share.sum()


def split_votes_by_candidate(region: str, total_votes: int, rng: np.random.Generator) -> list[int]:
    shares = region_share(region)
    noise = rng.normal(loc=1.0, scale=0.025, size=len(shares))
    shares = shares * noise
    shares = shares / shares.sum()
    votes = np.floor(total_votes * shares).astype(int)
    votes[0] += total_votes - int(votes.sum())
    return votes.tolist()


def choose_issue(region: str, rng: np.random.Generator) -> tuple[str | None, str | None]:
    probability = ISSUE_PROBABILITY.get(region, 0.15)
    if rng.random() > probability:
        return None, None
    options = ISSUE_POOL.get(region, ISSUE_POOL["DEFAULT"])
    idx = int(rng.integers(0, len(options)))
    return options[idx]


def classify_status(progress_pct: float, cycle_speed_hour: float, global_avg_speed: float, has_issue: bool) -> str:
    """Define el estado que usará Streamlit para pintar verde/amarillo/rojo."""
    if progress_pct >= 99.9:
        return "Finalizado"

    critical_threshold = max(global_avg_speed * 0.45, 30)
    medium_threshold = max(global_avg_speed * 0.80, 75)

    if cycle_speed_hour < critical_threshold or (has_issue and progress_pct < 75):
        return "Retraso crítico"
    if cycle_speed_hour < medium_threshold or has_issue:
        return "Avance medio"
    return "Avance alto"

# COMMAND ----------

# ==========================================================
# 5. VALIDAR CICLO DEL JOB PARA NO DUPLICAR DATA
# ==========================================================

cycle_key = get_cycle_key()
print(f"Ciclo actual: {cycle_key}")

registered_cycle = False

with get_connection() as conn:
    with conn.cursor() as cur:
        if not FORCE_RUN:
            cur.execute(
                """
                INSERT INTO job_executions (cycle_key, status, detail)
                VALUES (%s, 'running', %s)
                ON CONFLICT (cycle_key) DO NOTHING
                RETURNING cycle_key
                """,
                (cycle_key, "Inicio de job Databricks para simulación de actas."),
            )
            inserted = cur.fetchone()
            if inserted is None:
                conn.commit()
                print("Este ciclo de 15 minutos ya fue procesado. No se insertará data duplicada.")
                dbutils.notebook.exit("Ciclo ya procesado. Ejecución omitida para evitar duplicidad.")
            registered_cycle = True
    conn.commit()

print("Ciclo registrado correctamente. Iniciando simulación...")

# COMMAND ----------

# ==========================================================
# 6. EJECUTAR SIMULACIÓN E INSERTAR NUEVA DATA
# ==========================================================

summary_rows = []
total_new_actas = 0
total_new_votes = 0
critical_count = 0

try:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT location_id, region, province, district, total_actas,
                       actas_contabilizadas, actas_observadas
                FROM locations
                ORDER BY region, province, district
                """
            )
            locations = cur.fetchall()

            if not locations:
                raise RuntimeError("No hay ubicaciones cargadas en la tabla locations.")

            cur.execute("SELECT COALESCE(AVG(NULLIF(velocidad_actas_hora, 0)), 0) FROM locations")
            previous_avg_speed = float(cur.fetchone()[0] or 0)
            if previous_avg_speed <= 0:
                previous_avg_speed = 150.0

            cur.execute("SELECT candidate_id FROM candidates ORDER BY candidate_id")
            candidate_ids = [row[0] for row in cur.fetchall()]

            if len(candidate_ids) == 0:
                raise RuntimeError("No hay candidatos cargados en la tabla candidates.")

            # Se cierran incidencias anteriores. Si una zona continúa en rojo, se crea una nueva incidencia activa.
            cur.execute("UPDATE incidents SET is_active = false WHERE is_active = true")

            for row in locations:
                location_id, region, province, district, total_actas, counted, observed = row

                total_actas = int(total_actas or 0)
                counted = int(counted or 0)
                observed = int(observed or 0)
                pending = max(total_actas - counted - observed, 0)

                rng = rng_for_cycle(region, int(location_id), cycle_key)

                issue_type = None
                issue_detail = None
                new_actas = 0
                new_votes = 0
                speed_hour = 0.0

                if pending <= 0:
                    status = "Finalizado"
                    new_counted = counted
                    new_pending = 0
                else:
                    min_pct, max_pct = REGION_SPEED_PROFILE.get(region, (0.005, 0.018))
                    issue_type, issue_detail = choose_issue(region, rng)

                    penalty = float(rng.uniform(0.25, 0.65)) if issue_type else 1.0
                    base_increment = int(total_actas * float(rng.uniform(min_pct, max_pct)) * penalty)

                    # Siempre entra al menos 1 acta si hay pendiente, pero sin superar lo pendiente.
                    new_actas = min(pending, max(1, base_increment))

                    # Como el job corre cada 15 minutos, se multiplica por 4 para estimar actas/hora.
                    speed_hour = float(new_actas * 4)
                    progress_after = ((counted + new_actas) / total_actas) * 100 if total_actas else 0

                    status = classify_status(
                        progress_pct=progress_after,
                        cycle_speed_hour=speed_hour,
                        global_avg_speed=previous_avg_speed,
                        has_issue=issue_type is not None,
                    )

                    avg_votes_per_acta = int(rng.integers(240, 361))
                    new_votes = int(new_actas * avg_votes_per_acta)
                    votes_by_candidate = split_votes_by_candidate(region, new_votes, rng)

                    # Si hay más candidatos que los definidos en BASE_SHARE, los votos restantes quedan en 0.
                    if len(candidate_ids) > len(votes_by_candidate):
                        votes_by_candidate += [0] * (len(candidate_ids) - len(votes_by_candidate))

                    for candidate_id, votes_to_add in zip(candidate_ids, votes_by_candidate):
                        cur.execute(
                            """
                            INSERT INTO vote_results (location_id, candidate_id, valid_votes)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (location_id, candidate_id)
                            DO UPDATE SET
                                valid_votes = vote_results.valid_votes + EXCLUDED.valid_votes,
                                updated_at = now()
                            """,
                            (location_id, candidate_id, int(votes_to_add)),
                        )

                    new_counted = min(counted + new_actas, total_actas - observed)
                    new_pending = max(total_actas - new_counted - observed, 0)

                    if status == "Retraso crítico":
                        critical_count += 1
                        if not issue_type:
                            issue_type = "Velocidad bajo el umbral"
                            issue_detail = "El avance del ciclo es menor al promedio esperado de procesamiento para la plataforma."

                        cur.execute(
                            """
                            INSERT INTO incidents (
                                location_id, region, province, district,
                                severity, incident_type, explanation, is_active
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, true)
                            """,
                            (
                                location_id,
                                region,
                                province,
                                district,
                                "Alta",
                                issue_type,
                                issue_detail,
                            ),
                        )

                cur.execute(
                    """
                    UPDATE locations
                    SET actas_contabilizadas = %s,
                        actas_pendientes = %s,
                        velocidad_actas_hora = %s,
                        estado_conteo = %s,
                        motivo_retraso = %s,
                        detalle_retraso = %s,
                        ultimo_incremento_actas = %s,
                        ultimo_incremento_votos = %s,
                        updated_at = now()
                    WHERE location_id = %s
                    """,
                    (
                        new_counted,
                        new_pending,
                        round(speed_hour, 2),
                        status,
                        issue_type,
                        issue_detail,
                        int(new_actas),
                        int(new_votes),
                        location_id,
                    ),
                )

                total_new_actas += int(new_actas)
                total_new_votes += int(new_votes)

                summary_rows.append(
                    {
                        "region": region,
                        "province": province,
                        "district": district,
                        "new_actas": int(new_actas),
                        "new_votes": int(new_votes),
                        "speed_hour": round(speed_hour, 2),
                        "status": status,
                        "issue": issue_type or "Sin incidencia",
                        "pending_after": int(new_pending),
                    }
                )

            detail = (
                f"Job Databricks ejecutado. Ciclo: {cycle_key}. "
                f"Nuevas actas: {total_new_actas}. Nuevos votos: {total_new_votes}. "
                f"Zonas críticas: {critical_count}."
            )

            cur.execute(
                """
                INSERT INTO simulation_runs (total_new_actas, total_new_votes, regions_critical, detail)
                VALUES (%s, %s, %s, %s)
                """,
                (total_new_actas, total_new_votes, critical_count, detail),
            )

            cur.execute(
                """
                INSERT INTO event_logs (event_type, event_name, detail)
                VALUES (%s, %s, %s)
                """,
                ("Actualización", "Ingreso simulado de actas", detail),
            )

            if registered_cycle:
                cur.execute(
                    """
                    UPDATE job_executions
                    SET finished_at = now(),
                        status = 'success',
                        total_new_actas = %s,
                        total_new_votes = %s,
                        regions_critical = %s,
                        detail = %s
                    WHERE cycle_key = %s
                    """,
                    (total_new_actas, total_new_votes, critical_count, detail, cycle_key),
                )

        conn.commit()

except Exception as e:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO event_logs (event_type, event_name, detail)
                VALUES (%s, %s, %s)
                """,
                ("Error", "Error en job Databricks", str(e)),
            )
            if registered_cycle:
                cur.execute(
                    """
                    UPDATE job_executions
                    SET finished_at = now(), status = 'failed', detail = %s
                    WHERE cycle_key = %s
                    """,
                    (str(e), cycle_key),
                )
        conn.commit()
    raise

# COMMAND ----------

# ==========================================================
# 7. RESUMEN DE LA EJECUCIÓN
# ==========================================================

summary_df = pd.DataFrame(summary_rows)

print("✅ Simulación finalizada correctamente.")
print(f"Ciclo: {cycle_key}")
print(f"Nuevas actas ingresadas: {total_new_actas}")
print(f"Nuevos votos simulados: {total_new_votes}")
print(f"Zonas en retraso crítico: {critical_count}")

try:
    display(summary_df)
except Exception:
    print(summary_df.to_string(index=False))
