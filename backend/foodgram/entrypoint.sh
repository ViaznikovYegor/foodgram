#!/bin/sh
set -e

echo "======================================="
echo "Starting Foodgram Backend"
echo "======================================="

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --clear --noinput

echo "Initialization completed!"
echo "======================================="

exec "$@"