# Control database migrations

Iteration 1 uses a dependency-light idempotent migration in `backend/dpo/database.py`, so storage health works before optional framework dependencies are installed. The schema is versioned through `schema_meta` and covered by tests.

When SQLAlchemy/Alembic is installed, later schema migrations must mirror the same version and never store heavy artifacts or photographs in SQLite.
