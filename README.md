# Foodiet

Outlet-specific nutrition for Indian restaurants. Built to the "Restaurant Nutrition Platform (India): Web App Build Spec".
The product name is read from `APP_NAME` in `.env`.

## Layout

- `backend/` FastAPI modular monolith. One folder per service under `app/services/`, each with
  `router.py`, `schemas.py`, `service.py`, `repository.py`. Tables live in `app/models/`.
- `frontend/` React 18 + TypeScript + Vite. Display only: `src/api/` is the only code that calls the backend.
- `design-notes/` earlier design exploration (uncertainty engine prototype). Not used by the app.

## Run locally

Needs Docker, Python 3.12 and Node.

```bash
docker compose up -d
```

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
```

```bash
cd backend && ../.venv/bin/alembic upgrade head
```

```bash
cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

Load the reference data (placeholder nutrient values; see `backend/seed/README.md`):

```bash
cd backend && ../.venv/bin/python -m jobs.seed_reference
```

To try publishing locally, mark the placeholder data as cleared (refuses to run outside development):

```bash
cd backend && ../.venv/bin/python -m jobs.dev_clear_placeholders
```

Give someone the admin role (admin is never self-assigned in the app):

```bash
cd backend && ../.venv/bin/python -m jobs.make_admin person@example.com
```

Open http://localhost:5173 (diners), http://localhost:5173/admin (admin) or http://localhost:5173/business (restaurants). With no email provider set, sign-in codes are not sent; in development the
fixed code in `.env` (`TEST_FIXED_OTP`) works for any address. The component gallery is at `/ui` in development.

The test database must be migrated once:

```bash
cd backend && ALEMBIC_DATABASE_URL=$(grep ^TEST_DATABASE_URL ../.env | cut -d= -f2-) ../.venv/bin/alembic upgrade head
```

```bash
cd backend && ../.venv/bin/python -m pytest -q
```
