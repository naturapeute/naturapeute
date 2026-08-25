# Naturapeute clients

This directory contains the public Naturapeute Django application. The Compose setup runs the application, PostgreSQL, and an Nginx proxy for static and uploaded media files.

## Quick start

Requirements:

- Docker Engine or Docker Desktop with Compose v2

Create a local environment file and start the stack:

```sh
cp .env.example .env
docker compose up --build
```

The site is available at <http://localhost:8000>. The first startup runs Django migrations and collects static files before starting the web service.

Create an administrator after the stack is running:

```sh
docker compose exec web python manage.py createsuperuser
```

The admin is available at <http://localhost:8000/admin/>.

## Useful commands

```sh
# Start in the background
docker compose up --build -d

# Follow application logs
docker compose logs -f web

# Run Django checks
docker compose exec web python manage.py check

# Open a Django shell
docker compose exec web python manage.py shell

# Stop the services without deleting data
docker compose down

# Stop the services and delete the database/media volumes
# This is destructive.
docker compose down -v
```

The database, collected static files, and uploaded media are stored in named Docker volumes. A new installation therefore starts with an empty database; application data is not copied into the image. If an existing PostgreSQL dump is available, restore it into the running database using the credentials in `.env` after reviewing the dump.

For a plain SQL dump:

```sh
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < /path/to/dump.sql
```

For a PostgreSQL custom-format dump:

```sh
docker compose exec -T db sh -c 'pg_restore --clean --if-exists --no-owner --no-acl -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < /path/to/dump.dump
```

## Legacy Mongo import

The old `mongo2pg.py` importer runs inside the Compose web image and reads `MONGO_URI` and `MONGO_DATABASE`. It expects a running MongoDB containing the legacy Naturapeute collections. The default URI reaches a MongoDB running on the host from Docker Desktop; override it for another host or database:

```sh
make import-from-mongo
make import-from-mongo MONGO_URI=mongodb://mongo-host:27017/terrapeute MONGO_DATABASE=terrapeute
```

The import updates practices, symptoms, therapists, articles, and related records. Patient records are replaced, so run it only against the intended local database and review the source first. The live Naturapeute server currently uses PostgreSQL and does not provide a running MongoDB endpoint.

The historical underscore spelling remains available:

```sh
make import_from_mongo
```

## Server snapshot

The server is an LXC container reached through the `sweethome` SSH host alias. Download a timestamped copy of the deployed source, static files, uploads, and a PostgreSQL dump with:

```sh
make download-from-server
```

The snapshot is written under the ignored `server-copy/` directory. It excludes the remote virtualenv, Git metadata, and `local_settings.py`, but includes the deployed application and all site assets. Override `REMOTE_HOST`, `REMOTE_CONTAINER`, `REMOTE_APP`, or `SERVER_COPY` when needed.

## Configuration

`.env.example` contains the variables used by Compose. Copy it to `.env` and replace the development secret and database password before using the stack anywhere shared or public.

Django reads the following container variables in `core/settings.py`:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

The existing `make deploy` target still describes the legacy SSH/systemd deployment. This Compose setup is intentionally local/portable; switching the production server to Compose should be done as a separate deployment change after validating the data and reverse-proxy strategy.
