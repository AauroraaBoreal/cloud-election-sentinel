# cloud-election-sentinel

# Cloud Election Sentinel

Base web tipo ONPE para analizar el conteo de actas electorales.

**Stack:** Python + Streamlit + Supabase PostgreSQL + GitHub + Streamlit Cloud.

## 1. Estructura

```text
cloud_election_sentinel_onpe/
├── app.py
├── ddl.sql
├── seed_supabase.py
├── requirements.txt
├── .gitignore
└── .streamlit/
    └── secrets.toml.example
```

## 2. Crear rama en GitHub

```bash
git clone URL_DE_TU_REPO
cd NOMBRE_DEL_REPO
git checkout -b aura
```

Copia los archivos de este proyecto dentro del repo y luego ejecuta:

```bash
git add .
git commit -m "Base web Cloud Election Sentinel en Streamlit"
git push -u origin aura
```

Luego crea el Pull Request desde GitHub cuando tu equipo lo revise.

## 3. Crear tablas en Supabase

1. Entra a tu proyecto de Supabase.
2. Ve a **SQL Editor**.
3. Copia y ejecuta el contenido de `ddl.sql`.

## 4. Configurar secretos

Para local:

```bash
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edita `.streamlit/secrets.toml` con tus credenciales de Supabase:

```toml
[postgres]
USER = "postgres"
PASSWORD = "TU_PASSWORD_SUPABASE"
HOST = "db.xxxxxxxxxxxxx.supabase.co"
PORT = "5432"
DBNAME = "postgres"
```

En Streamlit Cloud coloca lo mismo en:

```text
App settings > Secrets
```

## 5. Cargar datos demo en Supabase

```bash
pip install -r requirements.txt
python seed_supabase.py
```

## 6. Ejecutar localmente

```bash
streamlit run app.py
```

## 7. Desplegar en Streamlit Cloud

1. Sube tu rama `aura` a GitHub.
2. Entra a Streamlit Community Cloud.
3. Crea una app nueva desde tu repositorio.
4. Selecciona:
   - Branch: `dayana`
   - Main file path: `app.py`
5. Agrega los secrets de Supabase.
6. Deploy.

## 8. Qué incluye la app

- Resumen general del conteo.
- Resultados por candidato.
- Filtros por región, provincia y distrito.
- Mapa referencial por región.
- Simulador de escenarios sin IA.
- Reportes descargables en CSV.
- Registro de eventos/logs.

## 9. Importante

El proyecto no usa inteligencia artificial. El simulador funciona con reglas determinísticas para escenarios referenciales.
