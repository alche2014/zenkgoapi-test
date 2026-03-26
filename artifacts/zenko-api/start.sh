#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Running Django migrations..."
python3 manage.py migrate --no-input --fake-initial

echo "Starting Django development server on port ${PORT:-8000}..."
python3 manage.py runserver 0.0.0.0:${PORT:-8000}
