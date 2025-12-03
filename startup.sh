#!/bin/bash

# Set Python path to include the current directory
export PYTHONPATH="${PYTHONPATH}:/home/site/wwwroot"

# Install dependencies (if needed)
pip install -r requirements.txt

# Wait for Postgres to be available (tries for ~60s)
echo "Waiting for database to become available..."
TRIES=0
MAX_TRIES=30
until python - <<'PY' 2>/dev/null
import os,sys
from sqlalchemy import create_engine
url = os.environ.get('SQLALCHEMY_DATABASE_URL') or os.environ.get('DATABASE_URL')
if not url:
	print('no_db_url')
	sys.exit(2)
try:
	create_engine(url).connect()
	print('ok')
	sys.exit(0)
except Exception as e:
	print('notready', e)
	sys.exit(1)
PY
do
	TRIES=$((TRIES+1))
	if [ $TRIES -ge $MAX_TRIES ]; then
		echo "Database did not become available after $((MAX_TRIES*2)) seconds. Proceeding anyway."
		break
	fi
	sleep 2
done

# Ensure Alembic migrations folder exists
mkdir -p alembic/versions

# Autogenerate migrations only when AUTO_MIGRATE=true
if [ "${AUTO_MIGRATE}" = "true" ]; then
	# If there are no revision files in alembic/versions, create an initial autogenerate
	if [ -z "$(ls -A alembic/versions 2>/dev/null)" ]; then
		echo "No Alembic revisions found — creating initial revision"
		python -m alembic revision --autogenerate -m "initial" || true
	else
		# Create an autogenerate revision for any model changes, then delete it if empty
		echo "AUTO_MIGRATE=true — checking for model changes and creating autogenerate revision if needed"
		python -m alembic revision --autogenerate -m "autogen $(date -u +%Y%m%d%H%M%S)" || true
		# Inspect the most recent file created
		LATEST_FILE=$(ls -t alembic/versions | head -n1)
		if [ -n "$LATEST_FILE" ]; then
			if ! grep -q "op\." "alembic/versions/$LATEST_FILE"; then
				echo "No DB-op changes detected in $LATEST_FILE — removing no-op revision"
				rm -f "alembic/versions/$LATEST_FILE"
			else
				echo "Autogenerate created $LATEST_FILE with changes"
			fi
		fi
	fi
else
	echo "AUTO_MIGRATE not set to 'true' — skipping autogenerate step"
fi

# Apply migrations to the database
echo "Applying Alembic migrations (upgrade head)"
python -m alembic upgrade head

# Run the application: use multiple workers for production
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app

