"""Shared test configuration.

DB-dependent tests define their own db_engine and session fixtures locally
because they connect to TEST_DATABASE_URL (port 5433) rather than the
default DATABASE_URL, and manage their own schema lifecycle.

This conftest only sets required environment variables so that app.core.config
can be imported without a real .env file.
"""

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test",
)
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault(
    "SUPABASE_JWT_SECRET",
    "test-jwt-secret-minimum-32-characters!!",
)
os.environ.setdefault("ENVIRONMENT", "development")
