# App Backend

This project is a project aimed at [brief project description]. This README provides instructions for developers to set up the project locally using a virtual environment (venv).

## Prerequisites

- Python 3.x
- Git

# App Backend

This repository contains the backend for the ACET project. The instructions below cover local development, PostgreSQL database setup, Docker usage, and Alembic migrations.

## Prerequisites

- Python 3.8+ or compatible
- Git
- Docker & Docker Compose (for containerized setup)

## Local development (virtualenv)

1. Clone the repository:

    ```sh
    git clone git@bitbucket.org:LogicielEngineer/acet-backend.git
    cd acet-backend
    ```

2. Create and activate a virtual environment:

    Windows:

    ```powershell
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    ```

    macOS / Linux:

    ```sh
    python -m venv venv
    source venv/bin/activate
    ```

3. Install Python dependencies:

    ```sh
    pip install -r src/requirements.txt
    ```

4. Configure environment variables (see Postgres section below).

5. Run the application:

    ```sh
    python src/main.py
    ```

## PostgreSQL database setup

You can run Postgres locally (installed on host) or via Docker. The app expects a `DATABASE_URL` environment variable in the standard SQLAlchemy format, e.g.: 

```
postgresql://<user>:<password>@<host>:<port>/<database>
```

Example `.env` values:

```
DATABASE_URL=postgresql://acet_user:secret@localhost:5432/acet_db
```

Start Postgres with Docker Compose (example):

```yaml
version: '3.8'
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: acet_user
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: acet_db
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

Save that snippet as `docker-compose.db.yml` and start the DB with:

```sh
docker compose -f docker-compose.db.yml up -d
```

After Postgres is running, set `DATABASE_URL` accordingly and the app will connect.

## Docker (app container)

There is a `Dockerfile` and a `docker-compose.yml` in the repository. Typical usage to build and run the app with the DB from above:

```sh
# build the app image
docker compose build

# start db + app (if docker-compose.yml links services)
docker compose up -d
```

If you run the DB separately, ensure the app service's `DATABASE_URL` env var points at the running Postgres.

## Alembic migrations

Alembic is configured in this repository (see `alembic.ini` and `alembic/`). Use the following commands to manage migrations locally or inside the container.

Ensure `DATABASE_URL` is set before running these commands.

Create a new revision (auto-generate migration from models):

Generate initial migration (if not done yet):

```sh
alembic revision --autogenerate -m "Initial"

```sh
alembic revision --autogenerate -m "describe changes"
```

Apply migrations (upgrade to latest):

```sh
alembic upgrade head
```

Downgrade one revision:

```sh
alembic downgrade -1
```

Running Alembic via Docker Compose (if Alembic is available in the container):

```sh
# open a shell in the app service and run alembic commands
docker compose run --rm app sh -c "alembic upgrade head"
```

Notes:

- Alembic's env is configured under `alembic/env.py` and should read the `DATABASE_URL` environment variable. If you need a different env var name, update `alembic/env.py` accordingly.
- Keep model changes and generated migration messages clear and focused.

## Example environment variables

```
DATABASE_URL=postgresql://acet_user:secret@db:5432/acet_db
FLASK_ENV=development
SECRET_KEY=replace-with-secure-value
```

## Running migrations during CI / Production deploy

- In CI: set `DATABASE_URL` and run `alembic upgrade head` as part of the deploy pipeline.
- In Docker-based deploys: either run Alembic as an init job or as a one-off container step before starting the app.

## Contributing

Please read `CONTRIBUTING.md` for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.

## Acknowledgments

- [List of contributors or resources]


# 1. Drop and recreate the database
docker exec -it autobus_backend bash

# Inside container
psql -U your_user -d postgres -c "DROP DATABASE your_db;"
psql -U your_user -d postgres -c "CREATE DATABASE your_db;"

# 2. Remove all migration files except __init__.py
rm -rf alembic/versions/*.py
touch alembic/versions/__init__.py

# 3. Create fresh migration
alembic revision --autogenerate -m "initial_migration"

# 4. Apply it
alembic upgrade head