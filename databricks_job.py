# Databricks notebook source
# ============================================================
# Cloud Election Sentinel - Databricks Job
# Actualiza data simulada cada 15 minutos
# Escribe en las tablas reales del dashboard:
#   candidates, locations, vote_results, event_logs, ces_job_runs
# SIN argparse, SIN pandas, SIN numpy, SIN toml
# ============================================================

import os
import random
from datetime import datetime, timezone
import psycopg2


# ============================================================
# 1. CREDENCIALES SEGURAS
# Lee desde dbutils.widgets (Databricks) o variables de entorno.
# Configura los widgets en: Job > Parameters con los nombres:
#   postgres_user, postgres_password, postgres_host,
#   postgres_port, postgres_dbname, force_run
# ============================================================

def get_widget(name: str, default: str = "") -> str:
    """Lee un widget de Databricks. Si no existe, retorna el default."""
    try:
        return dbutils.widgets.get(name)  # noqa: F821  (dbutils es nativo de Databricks)
    except Exception:
        return default


POSTGRES_USER = (
    get_widget("postgres_user")
    or os.getenv("POSTGRES_USER", "")
)
POSTGRES_PASSWORD = (
    get_widget("postgres_password")
    or os.getenv("POSTGRES_PASSWORD", "")
)
POSTGRES_HOST = (
    get_widget("postgres_host")
    or os.getenv("POSTGRES_HOST", "aws-0-us-east-1.pooler.supabase.com")
)
POSTGRES_PORT = (
    get_widget("postgres_port")
    or os.getenv("POSTGRES_PORT", "6543")
)
POSTGRES_DBNAME = (
    get_widget("postgres_dbname")
    or os.getenv("POSTGRES_DBNAME", "postgres")
)

# force_run = "true"  → siempre ejecuta aunque ya haya corrido en este bloque de 15 min.
# force_run = "false" → modo producción, previene duplicados.
FORCE_RUN = str(
    get_widget("force_run") or os.getenv("FORCE_RUN", "false")
).lower() == "true"

if not POSTGRES_USER or not POSTGRES_PASSWORD or not POSTGRES_HOST:
    raise RuntimeError(
        "Faltan credenciales. Configura postgres_user, postgres_password "
        "y postgres_host en los Parameters del Job de Databricks."
    )


# ============================================================
# 2. CONEXIÓN
# ============================================================

def get_connection():
    return psycopg2.connect(
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DBNAME,
        sslmode="require",
        connect_timeout=10,
    )


# ============================================================
# 3. TABLA DE CONTROL DE EJECUCIONES
# Solo esta tabla es propia del job. El resto son las tablas
# reales que lee el dashboard de Streamlit.
# ============================================================

DDL_JOB_CONTROL = """
CREATE TABLE IF NOT EXISTS ces_job_runs (
    execution_key TEXT PRIMARY KEY,
    executed_at   TIMESTAMPTZ DEFAULT NOW(),
    nuevas_actas  INTEGER DEFAULT 0,
    zonas_criticas INTEGER DEFAULT 0
);
"""


# ============================================================
# 4. DATA DE REFERENCIA
# Debe coincidir exactamente con los candidatos y locations
# que seed_supabase.py cargó en Supabase.
# ============================================================

# Nombres de candidatos en el mismo orden que se insertaron.
# El job los lee de la BD dinámicamente; esta lista es solo
# para la distribución regional de votos.
CANDIDATE_ORDER = [
    "Ana Kori",
    "José Paredes",
    "Renato Vargas",
    "Alonso Medina",
    "Óscar Rivas",
    "Miguel Salas",
    "Raúl Torres",
]

# Regiones con problemas conocidos → mayor probabilidad de retraso.
ZONAS_RIESGO = {"Puno", "Huancavelica", "Ucayali", "Loreto", "Amazonas"}

PROBLEMAS = {
    "Puno": [
        ("Corte eléctrico intermitente", "Interrupciones de energía reducen la velocidad de registro de actas."),
        ("Demora logística", "El traslado de actas desde zonas alejadas tarda más de lo previsto."),
        ("Conectividad limitada", "La conexión inestable retrasa la actualización del conteo."),
    ],
    "Huancavelica": [
        ("Condición de ruta", "Las rutas de acceso presentan demoras para trasladar actas."),
        ("Validación manual adicional", "Algunas actas requieren revisión antes de ser contabilizadas."),
    ],
    "Ucayali": [
        ("Traslado lento", "El traslado desde zonas alejadas retrasa el ingreso de actas."),
        ("Conectividad intermitente", "La red no permite actualizar la información con normalidad."),
    ],
    "Loreto": [
        ("Transporte fluvial", "El traslado por río genera demoras en la llegada de actas."),
        ("Condición climática", "Las lluvias dificultan el traslado del material electoral."),
    ],
    "Amazonas": [
        ("Acceso difícil", "Las rutas remotas retrasan el traslado de actas."),
        ("Conectividad baja", "Zona con cobertura limitada de red."),
    ],
    "_default": [
        ("Alta carga temporal", "El volumen de actas genera una demora operativa momentánea."),
        ("Carga operativa", "El centro de procesamiento registra alta demanda temporal."),
    ],
}


# ============================================================
# 5. FUNCIONES AUXILIARES
# ============================================================

def execution_key_15min() -> str:
    """Clave única para el bloque de 15 minutos actual (UTC)."""
    now = datetime.now(timezone.utc)
    slot = (now.minute // 15) * 15
    return now.strftime("%Y%m%d%H") + f"{slot:02d}"


def get_problem(region: str):
    options = PROBLEMAS.get(region, PROBLEMAS["_default"])
    return random.choice(options)


def vote_distribution(region: str, total_votes: int) -> list:
    """
    Distribución de votos por candidato según región.
    Siete candidatos, mismos pesos que usa seed_supabase.py.
    """
    BASE = [28.5, 18.7, 16.2, 13.4, 8.9, 6.3, 4.5]

    MODIFIERS = {
        "Lima":         [1.15, 1.05, 1.00, 0.92, 0.88, 0.95, 0.90],
        "La Libertad":  [1.05, 1.00, 1.03, 0.96, 1.00, 0.96, 0.92],
        "Piura":        [1.03, 0.98, 0.95, 1.02, 1.04, 1.02, 0.97],
        "Arequipa":     [1.00, 1.02, 1.10, 0.98, 0.92, 0.96, 0.94],
        "Cusco":        [0.88, 1.08, 0.96, 1.14, 1.05, 1.04, 1.02],
        "Puno":         [0.80, 1.16, 0.90, 1.22, 1.05, 1.10, 1.04],
        "Junín":        [0.94, 1.06, 1.00, 1.04, 1.06, 1.00, 1.00],
        "Huancavelica": [0.75, 1.18, 0.88, 1.24, 1.12, 1.08, 1.02],
        "Amazonas":     [0.78, 1.12, 0.92, 1.18, 1.16, 1.08, 1.02],
        "Ucayali":      [0.82, 1.10, 0.94, 1.14, 1.18, 1.06, 1.02],
    }

    mods = MODIFIERS.get(region, [1.0] * 7)
    raw = [BASE[i] * mods[i] for i in range(7)]
    total_raw = sum(raw)
    shares = [r / total_raw for r in raw]

    votes = [int(total_votes * s) for s in shares]
    # Ajusta diferencia de redondeo al primer candidato
    diff = total_votes - sum(votes)
    votes[0] += diff
    return votes


def classify_status(total, counted, batch, issue_active, motivo, detalle):
    avance = round((counted / total) * 100, 2) if total > 0 else 0.0
    velocidad = round(batch * 4, 2)  # extrapolación a 1 hora (ciclos de 15 min)

    if counted >= total:
        return "Conteo completo", 100.0, velocidad, None, None

    if issue_active and batch <= 5:
        return "Retraso crítico", avance, velocidad, motivo, detalle

    if batch <= 10:
        return "Avance bajo", avance, velocidad, motivo, detalle

    if avance >= 80:
        return "Avance alto", avance, velocidad, None, None

    if avance >= 50:
        return "Avance medio", avance, velocidad, None, None

    return "Avance bajo", avance, velocidad, "Conteo en proceso", "La zona aún presenta bajo avance de actas."


# ============================================================
# 6. SETUP: tabla de control
# ============================================================

def setup_job_control(cursor):
    """Crea la tabla ces_job_runs si no existe. No toca las tablas del dashboard."""
    cursor.execute(DDL_JOB_CONTROL)


# ============================================================
# 7. VERIFICAR REINICIO DE CICLO
# Si todas las locations llegaron al 100%, reinicia el conteo
# para que la simulación siga siendo útil.
# ============================================================

def conteo_global_completo(cursor) -> bool:
    cursor.execute(
        "SELECT COUNT(*) FROM locations WHERE actas_contabilizadas < total_actas"
    )
    return cursor.fetchone()[0] == 0


def reiniciar_conteo(cursor):
    """
    Reinicia actas_contabilizadas a un valor inicial aleatorio (20-35%)
    y resetea votos a 0 para empezar un nuevo ciclo de simulación.
    Escribe un log en event_logs para que sea visible en el dashboard.
    """
    print("🔄 Conteo al 100% en todas las regiones. Reiniciando ciclo de simulación...")

    cursor.execute("SELECT location_id, total_actas FROM locations ORDER BY location_id")
    rows = cursor.fetchall()

    for location_id, total in rows:
        total = int(total)
        counted = random.randint(int(total * 0.20), int(total * 0.35))
        pending = total - counted
        avance = round((counted / total) * 100, 2)

        cursor.execute(
            """
            UPDATE locations
            SET
                actas_contabilizadas  = %s,
                actas_pendientes      = %s,
                actas_observadas      = 0,
                velocidad_actas_hora  = 0,
                updated_at            = NOW()
            WHERE location_id = %s
            """,
            (counted, pending, location_id),
        )

        # Resetea votos a 0
        cursor.execute(
            """
            UPDATE vote_results
            SET valid_votes = 0, updated_at = NOW()
            WHERE location_id = %s
            """,
            (location_id,),
        )

    cursor.execute(
        """
        INSERT INTO event_logs (event_type, event_name, detail)
        VALUES ('Sistema', 'Reinicio automático del conteo',
                'Todas las regiones alcanzaron el 100%%. Se inició un nuevo ciclo de simulación.')
        """
    )

    # Limpia historial de runs para que el nuevo ciclo no colisione con claves anteriores.
    cursor.execute("DELETE FROM ces_job_runs")
    print("✅ Reinicio completado.")


# ============================================================
# 8. ACTUALIZACIÓN SIMULADA (escribe en tablas del dashboard)
# ============================================================

def simulate_update(cursor):
    """
    Actualiza actas_contabilizadas / pendientes / velocidad en `locations`
    y suma votos incrementales en `vote_results`.
    Registra alertas en `event_logs`.
    """
    # Leer locations y sus candidatos de una sola vez
    cursor.execute(
        """
        SELECT l.location_id, l.region, l.total_actas, l.actas_contabilizadas
        FROM   locations l
        ORDER  BY l.location_id
        """
    )
    locations = cursor.fetchall()

    # Leer candidate_ids en orden para hacer la distribución
    cursor.execute("SELECT candidate_id FROM candidates ORDER BY candidate_id")
    candidate_ids = [r[0] for r in cursor.fetchall()]

    total_new_actas = 0
    zonas_criticas = 0

    for location_id, region, total, counted in locations:
        total   = int(total)
        counted = int(counted)
        remaining = total - counted

        # Ya está al 100% → solo asegura que los campos estén limpios
        if remaining <= 0:
            cursor.execute(
                """
                UPDATE locations
                SET
                    actas_contabilizadas = total_actas,
                    actas_pendientes     = 0,
                    velocidad_actas_hora = 0,
                    updated_at           = NOW()
                WHERE location_id = %s
                """,
                (location_id,),
            )
            continue

        issue_active = region in ZONAS_RIESGO and random.random() < 0.65

        batch = random.randint(0, 6) if issue_active else random.randint(8, 30)
        batch = min(batch, remaining)

        new_counted = counted + batch
        new_pending = total - new_counted

        motivo, detalle = get_problem(region)
        estado, avance, velocidad, motivo_final, detalle_final = classify_status(
            total, new_counted, batch, issue_active, motivo, detalle
        )

        cursor.execute(
            """
            UPDATE locations
            SET
                actas_contabilizadas = %s,
                actas_pendientes     = %s,
                velocidad_actas_hora = %s,
                updated_at           = NOW()
            WHERE location_id = %s
            """,
            (new_counted, new_pending, velocidad, location_id),
        )

        # Distribuir votos del batch entre candidatos
        total_votes_batch = batch * random.randint(120, 180)
        votos = vote_distribution(region, total_votes_batch)

        for candidate_id, voto_incremental in zip(candidate_ids, votos):
            cursor.execute(
                """
                INSERT INTO vote_results (location_id, candidate_id, valid_votes)
                VALUES (%s, %s, %s)
                ON CONFLICT (location_id, candidate_id)
                DO UPDATE SET
                    valid_votes = vote_results.valid_votes + EXCLUDED.valid_votes,
                    updated_at  = NOW()
                """,
                (location_id, candidate_id, voto_incremental),
            )

        total_new_actas += batch

        if estado == "Retraso crítico":
            zonas_criticas += 1
            cursor.execute(
                """
                INSERT INTO event_logs (event_type, event_name, detail)
                VALUES ('Alerta', 'Retraso crítico detectado', %s)
                """,
                (
                    f"{region} — {motivo_final}. "
                    f"Último ingreso: {batch} actas. Avance: {avance}%.",
                ),
            )

    # Log general de la ejecución
    cursor.execute(
        """
        INSERT INTO event_logs (event_type, event_name, detail)
        VALUES ('Actualización', 'Carga simulada de actas', %s)
        """,
        (
            f"Se ingresaron {total_new_actas} nuevas actas. "
            f"Zonas críticas detectadas: {zonas_criticas}.",
        ),
    )

    return total_new_actas, zonas_criticas


# ============================================================
# 9. MAIN
# ============================================================

def main():
    key = execution_key_15min()

    print("=" * 52)
    print("  Cloud Election Sentinel — Databricks Job")
    print(f"  Execution key : {key}")
    print(f"  Force run     : {FORCE_RUN}")
    print("=" * 52)

    conn = get_connection()
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        # 1. Crear tabla de control si no existe
        setup_job_control(cursor)

        # 2. Deduplicación: si este bloque de 15 min ya corrió, salir
        cursor.execute(
            "SELECT 1 FROM ces_job_runs WHERE execution_key = %s",
            (key,),
        )
        already_ran = cursor.fetchone() is not None

        if already_ran and not FORCE_RUN:
            print("ℹ️  Este bloque de 15 minutos ya fue ejecutado. Nada que hacer.")
            conn.commit()
            return

        # 3. Reinicio automático si todas las regiones llegaron al 100%
        if conteo_global_completo(cursor):
            reiniciar_conteo(cursor)

        # 4. Actualización simulada
        nuevas_actas, zonas_criticas = simulate_update(cursor)

        # 5. Registrar ejecución (ON CONFLICT DO NOTHING protege contra race condition)
        cursor.execute(
            """
            INSERT INTO ces_job_runs (execution_key, nuevas_actas, zonas_criticas)
            VALUES (%s, %s, %s)
            ON CONFLICT (execution_key) DO NOTHING
            """,
            (key, nuevas_actas, zonas_criticas),
        )

        conn.commit()

        print("✅ Job ejecutado correctamente.")
        print(f"   Nuevas actas    : {nuevas_actas}")
        print(f"   Zonas críticas  : {zonas_criticas}")

    except Exception as exc:
        conn.rollback()
        print(f"❌ Error durante la ejecución: {exc}")
        raise

    finally:
        cursor.close()
        conn.close()


main()