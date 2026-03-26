#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Running Django migrations..."
# Step 1: Reconcile django_migrations tracking table with the actual DB schema.
# --fake marks any migrations whose tables already exist as applied without running
# them. This handles the case where the DB schema is ahead of the migration history
# (e.g. partial schema from a previous deployment, or tables created out-of-band).
python3 manage.py migrate --no-input --fake

# Step 2: Apply any genuinely new migrations from code that haven't been applied
# to the database yet. This is a no-op when the schema is already current.
python3 manage.py migrate --no-input

echo "Starting Django development server on port ${PORT:-8000}..."
python3 manage.py runserver 0.0.0.0:${PORT:-8000}
