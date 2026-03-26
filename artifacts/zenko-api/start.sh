#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Running Django migrations..."

# Check whether the django_migrations tracking table already exists in the DB.
# If it does, the DB has a prior schema and we need to reconcile the migration
# history before running migrate (handles cases where migrations were applied
# directly or in a partial state). If it doesn't exist, this is a fresh DB and
# we can run migrate normally to create everything from scratch.
MIGRATIONS_TABLE_EXISTS=$(python3 - <<'EOF'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zenko.settings")
django.setup()
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute(
        "SELECT EXISTS(SELECT FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='django_migrations')"
    )
    print("yes" if cursor.fetchone()[0] else "no")
EOF
)

if [ "$MIGRATIONS_TABLE_EXISTS" = "yes" ]; then
    echo "Existing schema detected — reconciling migration history..."
    # Fake-mark any migrations that are in the codebase but missing from the
    # django_migrations table. This prevents Django from trying to re-apply
    # SQL that is already reflected in the database schema.
    python3 manage.py migrate --no-input --fake
fi

# Apply any migrations that are genuinely new (not yet in the DB schema).
# On a fresh DB this creates all tables. On an existing DB after --fake above
# this is typically a no-op.
python3 manage.py migrate --no-input

echo "Starting Gunicorn on port ${PORT:-8000}..."
exec gunicorn zenko.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
