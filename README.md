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

## Teable import

The `import_to_teable` Django management command creates the Teable tables and imports the current local PostgreSQL data. It also uploads referenced images and every file found in the supplied server asset directories into the `Assets` table.

When `TEABLE_ENABLED=True` and the Teable credentials are configured, public therapist/journal views and the therapist JSON API use Teable as their source of truth. PostgreSQL remains available for migrations and for importing/synchronizing legacy data.

Set the token through the environment; it is intentionally not stored in Git:

```sh
export TEABLE_API_TOKEN='your-token'
make import-to-teable
```

The default `TEABLE_ASSET_APP` points to the downloaded server snapshot. To use another snapshot:

```sh
TEABLE_ASSET_APP=server-copy/another-snapshot/app make import-to-teable
```

The import clears and replaces records in the managed Teable tables by default. Use `--no-clear` with the Django command only when you explicitly want to retain existing records. Relationships are preserved with the original PostgreSQL source IDs so they remain inspectable and repeatable in Teable.

In the `Therapists` table, `Languages` is a multi-select of lowercase two-letter language codes (`fr`, `en`, `de`, etc.). `Agreements` is a multi-select whose values are normalized to uppercase ASCII letters only; for example, `Visana` becomes `VISANA` and `Diplôme Fédéral` becomes `DIPLOMEFEDERAL`. In the `Symptoms` table, `Parent Source ID` is a one-way many-to-one relation to another record in `Symptoms`; `Source ID` remains available as the stable import identifier.

## Therapist account

Therapists can use <http://localhost:8000/account/> to request a passwordless login link by email. The link is signed, expires after 15 minutes by default, and stores only the therapist source ID in the Django session after verification. The profile form updates editable public fields, including primary and additional practices, and uploads replacement photos directly to the Teable attachment field.

For local development, login emails use Django's console backend and are visible in the web container logs. For delivery by email, configure `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `DEFAULT_FROM_EMAIL`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `EMAIL_USE_TLS` in `.env`.

## Configuration

`.env.example` contains the variables used by Compose. Copy it to `.env` and replace the development secret and database password before using the stack anywhere shared or public.

Django reads the following container variables in `core/settings.py`:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS` (for example, `http://localhost:8000,http://127.0.0.1:8000` locally)
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `TEABLE_API_URL`
- `TEABLE_BASE_ID`
- `TEABLE_API_TOKEN`
- `TEABLE_CACHE_SECONDS` (`0` disables cross-request caching)
- `TEABLE_ENABLED`
- `EMAIL_BACKEND` (defaults to Django's console backend for local development)
- `DEFAULT_FROM_EMAIL`
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`
- `ACCOUNT_MAGIC_LINK_MAX_AGE` (seconds, default 900)
- `ACCOUNT_MAGIC_LINK_COOLDOWN_SECONDS` (default 60)

The local example uses `TEABLE_CACHE_SECONDS=0` so edits made in Teable appear on the next request. A positive value can be used in production to reduce API traffic. Configure the SMTP variables and set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` to deliver account login links by email; otherwise links are printed by the console backend.

The existing `make deploy` target still describes the legacy SSH/systemd deployment. This Compose setup is intentionally local/portable; switching the production server to Compose should be done as a separate deployment change after validating the data and reverse-proxy strategy.
