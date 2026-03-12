# App Backend

This repository contains the backend for the **Lebe project**. This
README provides instructions for developers to set up the project
locally using a virtual environment, configure PostgreSQL, run the
application using Docker, and manage database migrations with Alembic.

------------------------------------------------------------------------

# Prerequisites

Before setting up the project, ensure you have the following installed:

-   Python **3.8+**
-   Git
-   Docker
-   Docker Compose

------------------------------------------------------------------------

# Local Development (Virtual Environment)

## 1. Clone the Repository

``` sh
git clone https://github.com/Logicielltd/lebe-backend
cd lebe-backend
```

## 2. Create and Activate a Virtual Environment

### Windows

``` powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### macOS / Linux

``` sh
python -m venv venv
source venv/bin/activate
```

## 3. Install Dependencies

``` sh
pip install -r src/requirements.txt
```

## 4. Configure Environment Variables

Create a `.env` file and configure your environment variables.

Example:

    DATABASE_URL=postgresql://lebe_user:secret@localhost:5432/lebe_db
    FLASK_ENV=development
    SECRET_KEY=replace-with-secure-value

## 5. Run the Application

``` sh
python src/main.py
```

------------------------------------------------------------------------

# PostgreSQL Database Setup

Database connection format:

    postgresql://<user>:<password>@<host>:<port>/<database>

Example:

    DATABASE_URL=postgresql://lebe_user:secret@localhost:5432/lebe_db

------------------------------------------------------------------------

# Running PostgreSQL with Docker

Create a file named:

    docker-compose.db.yml

Example configuration:

``` yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: lebe_user
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: lebe_db
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

Start PostgreSQL:

``` sh
docker compose -f docker-compose.db.yml up -d
```

------------------------------------------------------------------------

# Running the Application with Docker

Build the application:

``` sh
docker compose build
```

Run the services:

``` sh
docker compose up -d
```

Ensure the `DATABASE_URL` environment variable points to the running
PostgreSQL service.

------------------------------------------------------------------------

# Docker Development & Debugging

Docker Compose commands must be run from the directory containing
`docker-compose.yml`.

Example:

``` sh
cd /var/www/lebe-backend
```

## Viewing Docker Logs

Follow backend logs in real-time:

``` sh
docker compose logs -f backend
```

View last 100 lines:

``` sh
docker compose logs --tail=100 backend
```

View logs for all services:

``` sh
docker compose logs -f
```

## Rebuilding Containers

If dependencies or Docker configuration change:

``` sh
docker compose down
docker compose up -d --build
```

Rebuild only backend:

``` sh
docker compose up -d --build backend
```

## Restart Backend Container

If code changes but image rebuild is not needed:

``` sh
docker compose restart backend
```

Then check logs:

``` sh
docker compose logs -f backend
```

## Check Running Containers

``` sh
docker ps
```

Formatted output:

``` sh
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

## Inspect Environment Variables

``` sh
docker exec lebe_backend printenv
```

``` sh
docker inspect lebe_backend | grep -A 20 '"Env"'
```

------------------------------------------------------------------------

# Typical Deployment Workflow

``` sh
cd /var/www/lebe-backend
git pull
docker compose down
docker compose up -d --build
docker compose logs -f backend
```

------------------------------------------------------------------------

# Optional Deployment Shortcut

Edit bash configuration:

``` sh
nano ~/.bashrc
```

Add:

``` sh
alias lebedeploy="cd /var/www/lebe-backend && git pull && docker compose down && docker compose up -d --build && docker compose logs -f backend"
```

Reload bash:

``` sh
source ~/.bashrc
```

Deploy using:

``` sh
lebedeploy
```

------------------------------------------------------------------------

# Alembic Migrations

Create migration:

``` sh
alembic revision --autogenerate -m "describe changes"
```

Apply migrations:

``` sh
alembic upgrade head
```

Downgrade one revision:

``` sh
alembic downgrade -1
```

Run migrations via Docker:

``` sh
docker compose run --rm app sh -c "alembic upgrade head"
```

------------------------------------------------------------------------

# Reset Database and Migrations

Access container:

``` sh
docker exec -it autobus_backend bash
```

Drop and recreate database:

``` sh
psql -U your_user -d postgres -c "DROP DATABASE your_db;"
psql -U your_user -d postgres -c "CREATE DATABASE your_db;"
```

Remove old migrations:

``` sh
rm -rf alembic/versions/*.py
touch alembic/versions/__init__.py
```

Create fresh migration:

``` sh
alembic revision --autogenerate -m "initial_migration"
```

Apply migration:

``` sh
alembic upgrade head
```

------------------------------------------------------------------------

# Running Migrations in CI / Production

Run during deployment:

``` sh
alembic upgrade head
```

------------------------------------------------------------------------

# Contributing

Please read `CONTRIBUTING.md` for contribution guidelines.

------------------------------------------------------------------------

# License

This project is licensed under the **MIT License**.

------------------------------------------------------------------------

# Acknowledgments

-   Contributors to the LEBE project
-   Open-source tools used in this project
