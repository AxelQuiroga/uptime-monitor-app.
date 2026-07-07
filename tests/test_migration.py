"""Tests for migration script (integration tests, need PostgreSQL)."""
import pytest
from unittest.mock import patch, MagicMock


def test_migration_imports():
    """Verify migration module can be imported."""
    import migrate
    assert hasattr(migrate, 'run_migration')


class TestMigration:
    @pytest.fixture
    def mock_conn(self):
        with patch('psycopg2.connect') as mock:
            conn = MagicMock()
            mock.return_value = conn
            yield conn

    def test_creates_extension(self, mock_conn):
        from migrate import run_migration
        run_migration()
        calls = [str(c) for c in mock_conn.cursor.return_value.execute.call_args_list]
        assert any('CREATE EXTENSION' in c for c in calls)

    def test_creates_hypertable(self, mock_conn):
        from migrate import run_migration
        run_migration()
        calls = [str(c) for c in mock_conn.cursor.return_value.execute.call_args_list]
        assert any('create_hypertable' in c for c in calls)

    def test_sets_retention(self, mock_conn):
        from migrate import run_migration
        run_migration()
        calls = [str(c) for c in mock_conn.cursor.return_value.execute.call_args_list]
        assert any('add_retention_policy' in c for c in calls)

    def test_creates_continuous_aggregate(self, mock_conn):
        from migrate import run_migration
        run_migration()
        calls = [str(c) for c in mock_conn.cursor.return_value.execute.call_args_list]
        assert any('hourly_checks' in c for c in calls)
