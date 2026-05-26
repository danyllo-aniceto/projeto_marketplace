# Docker development

This project includes simple Docker development artifacts: `Dockerfile`, `docker-compose.yml`, and `Makefile`.

Quick start (requires Docker & Docker Compose):

1. Copy or create a `.env` file based on `.env.example` and set database credentials.

2. Build and start services:

```sh
make up
```

3. Run migrations and create a superuser:

```sh
make migrate
make createsuperuser
```

4. View logs or stop services:

```sh
make logs
make down
```

Notes:
- The `web` service mounts the project directory for quick development.
- The `db` service exposes port `5432` to the host; credentials are read from `.env`.
- For production, replace the `runserver` command with a production WSGI server and adjust static files handling.

Git tracking note:
- If you accidentally committed ` .env ` to the repo, remove it from the index (this keeps the file locally but untracks it):

```sh
git rm --cached .env
git commit -m "remove env from repo"
```

Ensure `.env` is listed in `.gitignore` (this repo already adds it).
