#!/bin/sh
set -e

if [ -n "$DB_HOST" ]; then
    python -m app.db.wait_for_db
    echo "Running Alembic migrations..."
    alembic upgrade head
fi

exec "$@"
