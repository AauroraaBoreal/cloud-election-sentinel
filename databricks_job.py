# Databricks notebook source
# ============================================================
# Cloud Election Sentinel - Databricks Job SIMPLE
# Actualiza data simulada cada 15 minutos
# Proyecto pequeño: 1 tabla principal + logs + control de ejecución
# SIN IA, SIN pandas, SIN numpy, SIN toml
# ============================================================

import os
import argparse
import random
from datetime import datetime, timezone
import psycopg2


# ============================================================
# 1. CONFIGURACIÓN SEGURA SUPABASE
# ============================================================
# Las credenciales ya NO van escritas en el código.
# Debes pasarlas desde Databricks en el campo Parameters
# o como variables de entorno.
#
# Si usas POOLER de Supabase, el usuario debe ser:
# postgres.TU_PROJECT_REF

def get_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("--postgres_user", default=os.getenv("POSTGRES_USER", ""))
    parser.add_argument("--postgres_password", default=os.getenv("POSTGRES_PASSWORD", ""))
    parser.add_argument("--postgres_host", default=os.getenv("POSTGRES_HOST", "aws-1-us-east-1.pooler.supabase.com"))
    parser.add_argument("--postgres_port", default=os.getenv("POSTGRES_PORT", "6543"))
    parser.add_argument("--postgres_dbname", default=os.getenv("POSTGRES_DBNAME", "postgres"))
    parser.add_argument("--force_run", default=os.getenv("FORCE_RUN", "true"))

    args, _ = parser.parse_known_args()
    return args


args = get_args()

POSTGRES_USER = args.postgres_user
POSTGRES_PASSWORD = args.postgres_password
POSTGRES_HOST = args.postgres_host
POSTGRES_PORT = args.postgres_port
POSTGRES_DBNAME = args.postgres_dbname

# Para probar varias veces manualmente, usa true.
# Cuando lo programes cada 15 minutos, usa false.
FORCE_RUN = str(args.force_run).lower() == "true"

if not POSTGRES_USER or not POSTGRES_PASSWORD or not POSTGRES_HOST:
    raise Exception(
        "Faltan credenciales. Configura postgres_user, postgres_password y postgres_host en Parameters del Job."
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
        connect_timeout=10
    )


# ============================================================
# 3. TABLAS PEQUEÑAS
# ============================================================

DDL = """
CREATE TABLE IF NOT EXISTS ces_conteo (
    id SERIAL PRIMARY KEY,
    region TEXT UNIQUE NOT NULL,
    provincia TEXT NOT NULL,
    distrito TEXT NOT NULL,

    actas_total INTEGER NOT NULL,
    actas_contabilizadas INTEGER DEFAULT 0,
    actas_pendientes INTEGER DEFAULT 0,
    avance_pct NUMERIC(6,2) DEFAULT 0,
    velocidad_actas_hora NUMERIC(10,2) DEFAULT 0,
    ultimo_ingreso_actas INTEGER DEFAULT 0,

    estado TEXT DEFAULT 'Sin información',
    color_estado TEXT DEFAULT 'gray',
    motivo_retraso TEXT,
    detalle_retraso TEXT,

    votos_a INTEGER DEFAULT 0,
    votos_b INTEGER DEFAULT 0,
    votos_c INTEGER DEFAULT 0,
    votos_d INTEGER DEFAULT 0,
    votos_e INTEGER DEFAULT 0,

    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ces_logs (
    id SERIAL PRIMARY KEY,
    fecha_hora TIMESTAMPTZ DEFAULT NOW(),
    tipo TEXT NOT NULL,
    evento TEXT NOT NULL,
    detalle TEXT
);

CREATE TABLE IF NOT EXISTS ces_job_runs (
    execution_key TEXT PRIMARY KEY,
    executed_at TIMESTAMPTZ DEFAULT NOW(),
    nuevas_actas INTEGER DEFAULT 0,
    zonas_criticas INTEGER DEFAULT 0
);
"""


# ============================================================
# 4. DATA SIMULADA PEQUEÑA
# ============================================================

REGIONES = [
    ("Lima", "Lima", "Comas", 1500),
    ("Arequipa", "Arequipa", "Cercado", 1000),
    ("Cusco", "Cusco", "Wanchaq", 900),
    ("Puno", "Puno", "Juliaca", 1100),
    ("Huancavelica", "Huancavelica", "Ascensión", 700),
    ("Ucayali", "Coronel Portillo", "Callería", 800),
    ("Loreto", "Maynas", "Iquitos", 950),
]

PROBLEMAS = {
    "Puno": [
        ("Corte eléctrico intermitente", "Interrupciones de energía reducen la velocidad de registro de actas."),
        ("Demora logística", "El traslado de actas desde zonas alejadas tarda más de lo previsto."),
        ("Conectividad limitada", "La conexión inestable retrasa la actualización del conteo.")
    ],
    "Huancavelica": [
        ("Condición de ruta", "Las rutas de acceso presentan demoras para trasladar actas."),
        ("Validación manual adicional", "Algunas actas requieren revisión antes de ser contabilizadas.")
    ],
    "Ucayali": [
        ("Traslado lento", "El traslado desde zonas alejadas retrasa el ingreso de actas."),
        ("Conectividad intermitente", "La red no permite actualizar la información con normalidad.")
    ],
    "Loreto": [
        ("Transporte fluvial", "El traslado por río genera demoras en la llegada de actas."),
        ("Condición climática", "Las lluvias dificultan el traslado del material electoral.")
    ],
    "Lima": [
        ("Alta carga temporal", "El volumen de actas genera una demora operativa momentánea.")
    ],
    "Arequipa": [
        ("Carga operativa", "El centro de procesamiento registra alta demanda temporal.")
    ],
    "Cusco": [
        ("Demora logística", "Algunos locales alejados tardan más en enviar actas.")
    ],
}


# ============================================================
# 5. FUNCIONES AUXILIARES
# ============================================================

def execution_key_15min():
    now = datetime.now(timezone.utc)
    slot = (now.minute // 15) * 15
    return now.strftime("%Y%m%d%H") + f"{slot:02d}"


def get_problem(region):
    return random.choice(PROBLEMAS.get(region, PROBLEMAS["Lima"]))


def vote_distribution(region, total_votes):
    if region in ["Puno", "Cusco", "Huancavelica"]:
        weights = [0.18, 0.27, 0.13, 0.18, 0.24]
    elif region in ["Ucayali", "Loreto"]:
        weights = [0.20, 0.16, 0.14, 0.18, 0.32]
    else:
        weights = [0.30, 0.20, 0.18, 0.16, 0.16]

    return [int(total_votes * w) for w in weights]


def classify_status(total, counted, batch, issue_active, motivo, detalle):
    avance = round((counted / total) * 100, 2)
    velocidad = batch * 4

    if counted >= total:
        return "Conteo completo", "green", None, None, avance, velocidad

    if issue_active and batch <= 5:
        return "Retraso crítico", "red", motivo, detalle, avance, velocidad

    if batch <= 10:
        return "Avance bajo", "orange", motivo, detalle, avance, velocidad

    if avance >= 80:
        return "Avance alto", "green", None, None, avance, velocidad

    if avance >= 50:
        return "Avance medio", "yellow", None, None, avance, velocidad

    return "Avance bajo", "orange", "Conteo en proceso", "La zona aún presenta bajo avance de actas.", avance, velocidad


# ============================================================
# 6. CREAR TABLAS Y CARGA INICIAL
# ============================================================

def setup_database(cursor):
    cursor.execute(DDL)


def seed_initial_data(cursor):
    cursor.execute("SELECT COUNT(*) FROM ces_conteo")
    count = cursor.fetchone()[0]

    if count > 0:
        return

    for region, provincia, distrito, total in REGIONES:
        counted = random.randint(int(total * 0.20), int(total * 0.35))
        pending = total - counted
        avance = round((counted / total) * 100, 2)

        total_votes = counted * random.randint(120, 180)
        votos = vote_distribution(region, total_votes)

        cursor.execute(
            """
            INSERT INTO ces_conteo (
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
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0, 0, 'Avance bajo', 'orange',
                    'Conteo inicial', 'La zona se encuentra en etapa inicial de procesamiento.',
                    %s, %s, %s, %s, %s, NOW())
            """,
            (
                region, provincia, distrito,
                total, counted, pending, avance,
                votos[0], votos[1], votos[2], votos[3], votos[4]
            )
        )

    cursor.execute(
        """
        INSERT INTO ces_logs (tipo, evento, detalle)
        VALUES ('Sistema', 'Carga inicial', 'Se cargó data inicial simulada para el dashboard electoral.')
        """
    )


# ============================================================
# 7. ACTUALIZACIÓN SIMULADA
# ============================================================

# ============================================================
# 7. REINICIO AUTOMÁTICO DEL CONTEO
# ============================================================

def conteo_global_completo(cursor):
    """
    Verifica si todas las regiones llegaron al 100%.
    """
    cursor.execute("""
        SELECT COUNT(*)
        FROM ces_conteo
        WHERE actas_contabilizadas < actas_total
    """)
    pendientes = cursor.fetchone()[0]

    return pendientes == 0


def reiniciar_conteo(cursor):
    """
    Reinicia el conteo electoral simulado.
    Se ejecuta cuando todas las regiones llegaron al 100%.
    """
    print("🔄 Conteo al 100%. Reiniciando simulación electoral...")

    for region, provincia, distrito, total in REGIONES:
        counted = random.randint(int(total * 0.20), int(total * 0.35))
        pending = total - counted
        avance = round((counted / total) * 100, 2)

        total_votes = counted * random.randint(120, 180)
        votos = vote_distribution(region, total_votes)

        cursor.execute(
            """
            UPDATE ces_conteo
            SET
                provincia = %s,
                distrito = %s,
                actas_total = %s,
                actas_contabilizadas = %s,
                actas_pendientes = %s,
                avance_pct = %s,
                velocidad_actas_hora = 0,
                ultimo_ingreso_actas = 0,
                estado = 'Avance bajo',
                color_estado = 'orange',
                motivo_retraso = 'Nuevo ciclo de conteo',
                detalle_retraso = 'El conteo anterior llegó al 100%, por lo que se inició una nueva simulación electoral.',
                votos_a = %s,
                votos_b = %s,
                votos_c = %s,
                votos_d = %s,
                votos_e = %s,
                updated_at = NOW()
            WHERE region = %s
            """,
            (
                provincia,
                distrito,
                total,
                counted,
                pending,
                avance,
                votos[0],
                votos[1],
                votos[2],
                votos[3],
                votos[4],
                region
            )
        )

    cursor.execute(
        """
        INSERT INTO ces_logs (tipo, evento, detalle)
        VALUES (%s, %s, %s)
        """,
        (
            "Sistema",
            "Reinicio automático del conteo",
            "Todas las regiones llegaron al 100% de actas contabilizadas. Se inició un nuevo ciclo de simulación."
        )
    )

    # Limpia el historial de ejecuciones para que el nuevo ciclo no choque con ciclos anteriores.
    cursor.execute("DELETE FROM ces_job_runs;")

def simulate_update(cursor):
    cursor.execute(
        """
        SELECT
            id,
            region,
            provincia,
            distrito,
            actas_total,
            actas_contabilizadas
        FROM ces_conteo
        ORDER BY id
        """
    )

    rows = cursor.fetchall()

    total_new_actas = 0
    zonas_criticas = 0

    for row in rows:
        row_id = row[0]
        region = row[1]
        provincia = row[2]
        distrito = row[3]
        total = int(row[4])
        counted = int(row[5])

        remaining = total - counted

        if remaining <= 0:
            cursor.execute(
                """
                UPDATE ces_conteo
                SET
                    actas_contabilizadas = actas_total,
                    actas_pendientes = 0,
                    avance_pct = 100,
                    velocidad_actas_hora = 0,
                    ultimo_ingreso_actas = 0,
                    estado = 'Conteo completo',
                    color_estado = 'green',
                    motivo_retraso = NULL,
                    detalle_retraso = NULL,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (row_id,)
            )
            continue

        zonas_riesgo = ["Puno", "Huancavelica", "Ucayali", "Loreto"]

        issue_active = region in zonas_riesgo and random.random() < 0.65

        if issue_active:
            batch = random.randint(0, 6)
        else:
            batch = random.randint(8, 30)

        batch = min(batch, remaining)

        new_counted = counted + batch
        new_pending = total - new_counted

        motivo, detalle = get_problem(region)

        estado, color, motivo_final, detalle_final, avance, velocidad = classify_status(
            total,
            new_counted,
            batch,
            issue_active,
            motivo,
            detalle
        )

        total_votes_new = batch * random.randint(120, 180)
        votos = vote_distribution(region, total_votes_new)

        cursor.execute(
            """
            UPDATE ces_conteo
            SET
                actas_contabilizadas = %s,
                actas_pendientes = %s,
                avance_pct = %s,
                velocidad_actas_hora = %s,
                ultimo_ingreso_actas = %s,
                estado = %s,
                color_estado = %s,
                motivo_retraso = %s,
                detalle_retraso = %s,
                votos_a = votos_a + %s,
                votos_b = votos_b + %s,
                votos_c = votos_c + %s,
                votos_d = votos_d + %s,
                votos_e = votos_e + %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                new_counted,
                new_pending,
                avance,
                velocidad,
                batch,
                estado,
                color,
                motivo_final,
                detalle_final,
                votos[0],
                votos[1],
                votos[2],
                votos[3],
                votos[4],
                row_id
            )
        )

        total_new_actas += batch

        if estado == "Retraso crítico":
            zonas_criticas += 1

            cursor.execute(
                """
                INSERT INTO ces_logs (tipo, evento, detalle)
                VALUES (%s, %s, %s)
                """,
                (
                    "Alerta",
                    "Retraso crítico detectado",
                    f"{region} - {provincia} - {distrito}: {motivo_final}. Último ingreso: {batch} actas. Avance: {avance}%."
                )
            )

    cursor.execute(
        """
        INSERT INTO ces_logs (tipo, evento, detalle)
        VALUES (%s, %s, %s)
        """,
        (
            "Actualización",
            "Carga simulada de actas",
            f"Se ingresaron {total_new_actas} nuevas actas. Zonas críticas detectadas: {zonas_criticas}."
        )
    )

    return total_new_actas, zonas_criticas


# ============================================================
# 8. MAIN
# ============================================================

def main():
    key = execution_key_15min()

    print("===================================================")
    print("Cloud Election Sentinel - Job SIMPLE")
    print("Execution key:", key)
    print("Force run:", FORCE_RUN)
    print("===================================================")

    conn = get_connection()
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        setup_database(cursor)
        seed_initial_data(cursor)

        cursor.execute(
            "SELECT 1 FROM ces_job_runs WHERE execution_key = %s",
            (key,)
        )
        exists = cursor.fetchone()

        if exists and not FORCE_RUN:
            print("Este bloque de 15 minutos ya fue ejecutado. No se duplica data.")
            conn.commit()
            return

        nuevas_actas, zonas_criticas = simulate_update(cursor)

        cursor.execute(
            """
            INSERT INTO ces_job_runs (
                execution_key,
                nuevas_actas,
                zonas_criticas
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (execution_key)
            DO NOTHING
            """,
            (key, nuevas_actas, zonas_criticas)
        )

        conn.commit()

        print("✅ Job ejecutado correctamente")
        print("Nuevas actas:", nuevas_actas)
        print("Zonas críticas:", zonas_criticas)

    except Exception as e:
        conn.rollback()
        print("❌ Error:", str(e))
        raise e

    finally:
        cursor.close()
        conn.close()


main()