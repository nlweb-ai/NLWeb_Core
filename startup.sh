#!/bin/bash
# Startup script for Azure Web App
# Note: Dependencies are installed automatically by Azure during deployment

# Start the NLWeb server using gunicorn with aiohttp worker
gunicorn nlweb_core.simple_server:create_app \
  --bind=0.0.0.0:${PORT:-8000} \
  --worker-class aiohttp.GunicornWebWorker \
  --workers 1 \
  --timeout 600 \
  --access-logfile - \
  --error-logfile -
