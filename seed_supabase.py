"""
Carga datos demo de conteo electoral en Supabase PostgreSQL.
Ejecutar luego de correr ddl.sql en Supabase SQL Editor.

Local:
    python seed_supabase.py

Requiere .streamlit/secrets.toml con la sección [postgres].
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import os
import math

import numpy as np
import psycopg2
import toml


CANDIDATES = [
    ("Ana Kori", "Fuerza Popular", "K", "#1F66B1"),
    ("José Paredes", "Juntos por el Perú", "JP", "#2F7CC0"),
    ("Renato Vargas", "Renovación Popular", "R", "#7DBAE0"),
    ("Alonso Medina", "Alianza Popular", "AP", "#88C3E8"),
    ("Óscar Rivas", "Obras por el Perú", "OBRAS", "#9CCEEB"),
    ("Miguel Salas", "País para Todos", "PPT", "#73B3D7"),
    ("Raúl Torres", "Acción Popular", "APOP", "#60A3CB"),
]

# 10 departamentos priorizados con mayor carga o interés de análisis.
LOCATIONS = [
    ("Lima", "Lima", "Lima", -12.0464, -77.0428, 30140, 30140, 0, 0, 920.0),
    ("La Libertad", "Trujillo", "Trujillo", -8.1116, -79.0288, 7900, 7900, 0, 0, 310.0),
    ("Piura", "Piura", "Piura", -5.1945, -80.6328, 6700, 6700, 0, 0, 285.0),
    ("Arequipa", "Arequipa", "Arequipa", -16.4090, -71.5375, 7600, 7600, 0, 0, 340.0),
    ("Cusco", "Cusco", "Cusco", -13.5319, -71.9675, 5200, 5200, 0, 0, 160.0),
    ("Puno", "Puno", "Puno", -15.8402, -70.0219, 4800, 4800, 0, 0, 95.0),
    ("Junín", "Huancayo", "Huancayo", -12.0651, -75.2049, 5400, 5400, 0, 0, 230.0),
    ("Huancavelica", "Huancavelica", "Huancavelica", -12.7864, -74.9764, 3200, 3200, 0, 0, 82.0),
    ("Amazonas", "Chachapoyas", "Chachapoyas", -6.2317, -77.8690, 2410, 2410, 0, 0, 76.0),
    ("Ucayali", "Coronel Portillo", "Callería", -8.3791, -74.5539, 6873, 6873, 0, 0, 88.0),
]

BASE_SHARE = np.array([28.5, 18.7, 16.2, 13.4, 8.9, 6.3, 4.5], dtype=float)
BASE_SHARE = BASE_SHARE / BASE_SHARE.sum()


def load_secrets() -> dict:
    secrets_path = Path(".streamlit/secrets.toml")
    if secrets_path.exists():
        return toml.load(secrets_path)["postgres"]

    # Alternativa para ejecución en entornos con variables de entorno.
    return {
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", ""),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "DBNAME": os.environ.get("POSTGRES_DBNAME", "postgres"),
    }


def connect():
    s = load_secrets()
    return psycopg2.connect(
        user=s["USER"],
        password=s["PASSWORD"],
        host=s["HOST"],
        port=s.get("PORT", "5432"),
        dbname=s.get("DBNAME", "postgres"),
        sslmode="require",
    )


def region_modifier(region: str) -> np.ndarray:
    """Pequeña variación regional para que el dashboard no se vea plano."""
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


def main():
    conn = connect()
    cur = conn.cursor()

    ddl = Path("ddl.sql").read_text(encoding="utf-8")
    cur.execute(ddl)

    # cur.execute("TRUNCATE vote_results, locations, candidates, event_logs RESTART IDENTITY CASCADE;")

    for name, party, symbol, color in CANDIDATES:
        cur.execute(
            """
            INSERT INTO candidates (candidate_name, party_name, party_symbol, display_color)
            VALUES (%s, %s, %s, %s)
            """,
            (name, party, symbol, color),
        )

    candidate_ids = list(range(1, len(CANDIDATES) + 1))

    for location in LOCATIONS:
        region, province, district, lat, lon, total, counted, pending, observed, speed = location
        cur.execute(
            """
            INSERT INTO locations (
                region, province, district, latitude, longitude,
                total_actas, actas_contabilizadas, actas_pendientes,
                actas_observadas, velocidad_actas_hora
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING location_id
            """,
            (region, province, district, lat, lon, total, counted, pending, observed, speed),
        )
        location_id = cur.fetchone()[0]

        total_valid_votes = int(counted * 320)
        shares = region_modifier(region)
        votes = np.floor(total_valid_votes * shares).astype(int)
        difference = total_valid_votes - int(votes.sum())
        votes[0] += difference

        for candidate_id, valid_votes in zip(candidate_ids, votes):
            cur.execute(
                """
                INSERT INTO vote_results (location_id, candidate_id, valid_votes)
                VALUES (%s, %s, %s)
                ON CONFLICT (location_id, candidate_id)
                DO UPDATE SET valid_votes = EXCLUDED.valid_votes, updated_at = now()
                """,
                (location_id, candidate_id, int(valid_votes)),
            )

    logs = [
        ("Actualización", "Carga de dataset", "Dataset actas_2026_05_24.csv cargado correctamente"),
        ("Procesamiento", "Cálculo de métricas", "Métricas actualizadas para todas las regiones"),
        ("Simulación", "Escenario ejecutado", "Escenario: ingreso de actas rurales al 50%"),
        ("Actualización", "Actualización de actas", "Se actualizaron 90,223 actas en la base de datos"),
        ("Sistema", "Inicio de sesión", "Usuario: admin"),
        ("Sistema", "Conexión a BD", "Conexión a Supabase exitosa"),
        ("Procesamiento", "Limpieza de datos", "Datos validados y transformados correctamente"),
    ]

    for event_type, event_name, detail in logs:
        cur.execute(
            """
            INSERT INTO event_logs (event_type, event_name, detail)
            VALUES (%s, %s, %s)
            """,
            (event_type, event_name, detail),
        )

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Datos demo cargados correctamente en Supabase.")


if __name__ == "__main__":
    main()
