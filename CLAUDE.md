# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Deployment

- The app is deployed on **Railway**, automatically from the **`main`** branch of this GitHub repo.
- Every push to `main` triggers a new Railway deployment. There is no manual deploy step.
- The app does **not** run on the developer's computer. Do not try to start a local server.

## Stack

- Python 3.12
- FastAPI
- Jinja2 templates
- SQLAlchemy 2 + Alembic
- PostgreSQL

## Database

- The database is a **Railway PostgreSQL** database, reachable only through the `DATABASE_URL`
  environment variable on Railway.
- **Do not set up a local database** and **do not start a local server**. There is no local
  PostgreSQL instance, and none should be created.
- Alembic migrations run against the Railway database; they are not run locally against a real DB.

## Secrets and configuration

- All secrets come **only** from environment variables: `DATABASE_URL`, `ANTHROPIC_API_KEY`,
  `APP_PASSWORD`.
- **Never hard-code secrets** in code, tests, templates, configs, or commit messages.
- `.env` must be listed in `.gitignore` and must never be committed.

## Before every push

Run all of the following, and only push once they pass:

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Run the tests:
   ```
   pytest
   ```
3. Check that the app imports cleanly:
   ```
   python -c "import app.main"
   ```

Tests must **not** require a real database or a real API key:

- Use **SQLite in-memory** for database-backed tests.
- Use the **mock converter** instead of calling the Anthropic API.

## Workflow

- After each finished task, **commit and push to GitHub** so that Railway deploys the new version.
- Keep commits scoped to one finished task where practical.

## Data policy

- Only **fictional or sanitised** data is ever used.
- **Never add real MMR/TK documents** to the repo — not as fixtures, test data, examples, or
  attachments.
