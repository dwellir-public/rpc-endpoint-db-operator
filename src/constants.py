#!/usr/bin/env python3

from pathlib import Path

# Strings
SERVICE_NAME = 'endpointdb'
APP_SCRIPT_NAME = 'app.py'
GUNICORN_HARDCODED_ARGS = '--workers=2 --access-logfile=- app:app'
DATABASE_USERNAME = 'dwellir_endpointdb'

# Paths
HOME_PATH = Path('/home/ubuntu')
APP_SCRIPT_PATH = HOME_PATH / APP_SCRIPT_NAME
DB_UTIL_SCRIPT_PATH = HOME_PATH / 'db_util.py'
JWT_SECRET_KEY_PATH = HOME_PATH / 'auth_jwt_secret_key'
AUTH_PASSWORD_PATH = HOME_PATH / 'auth_password'
DATABASE_PATH = HOME_PATH / 'live_database.db'

# Database
TABLE_CHAINS = 'chains'
TABLE_RPC_URLS = 'rpc_urls'
