#!/bin/bash
set -e

echo "Starting Musico..."

# Run migrations on the actual machine (which has the volume mounted)
echo "Running migrations..."
python manage.py migrate --noinput

# Start the web server
echo "Starting Gunicorn..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3
