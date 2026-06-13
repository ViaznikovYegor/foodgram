#!/bin/sh
set -e

echo "======================================="
echo "Starting Foodgram Backend"
echo "======================================="

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Initialization completed!"
echo "======================================="

exec "$@"