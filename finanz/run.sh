#!/bin/sh
# Startet die Finanzplanungs-App. Daten liegen im App-Konfigurationsordner (/config, im Backup).
set -e
LOG_LEVEL=$(python3 -c "import json;print(json.load(open('/data/options.json')).get('log_level','info'))" 2>/dev/null || echo info)
export LOG_LEVEL
export FINANZ_DATA=/config
export PORT=8099
exec python3 /app/server.py
