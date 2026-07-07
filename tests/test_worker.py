"""Tests for the worker module."""
from unittest.mock import MagicMock, ANY

import pytest
from worker import check_job


class TestCheckJob:
    """Tests for check_job()."""

    def test_check_job_active(self, monkeypatch):
        """Active target → calls check_url and returns the result."""
        target = MagicMock(spec=[])
        target.id = 1
        target.is_active = True
        target.url = "https://example.com"

        mock_result = MagicMock()
        mock_result.is_up = True
        mock_result.latency_ms = 100.0

        monkeypatch.setattr("worker.db.session.get", lambda model, tid: target if tid == 1 else None)
        monkeypatch.setattr("worker.check_url", lambda t: mock_result)

        # Mock create_app to provide a working app context
        mock_app = MagicMock()
        mock_app.app_context.return_value.__enter__.return_value = None
        mock_app.app_context.return_value.__exit__.return_value = None
        monkeypatch.setattr("worker.create_app", lambda: mock_app)

        result = check_job(1)

        assert result == mock_result

    def test_check_job_inactive(self, monkeypatch):
        """Inactive target → skips check_url."""
        target = MagicMock(spec=[])
        target.id = 2
        target.is_active = False
        target.url = "https://example.com"

        mock_check_url = MagicMock()
        monkeypatch.setattr("worker.check_url", mock_check_url)
        monkeypatch.setattr("worker.db.session.get", lambda model, tid: target if tid == 2 else None)

        mock_app = MagicMock()
        mock_app.app_context.return_value.__enter__.return_value = None
        mock_app.app_context.return_value.__exit__.return_value = None
        monkeypatch.setattr("worker.create_app", lambda: mock_app)

        result = check_job(2)

        mock_check_url.assert_not_called()
        assert result is None

    def test_check_job_not_found(self, monkeypatch):
        """Missing target → skips, no crash."""
        mock_check_url = MagicMock()
        monkeypatch.setattr("worker.check_url", mock_check_url)
        monkeypatch.setattr("worker.db.session.get", lambda model, tid: None)

        mock_app = MagicMock()
        mock_app.app_context.return_value.__enter__.return_value = None
        mock_app.app_context.return_value.__exit__.return_value = None
        monkeypatch.setattr("worker.create_app", lambda: mock_app)

        result = check_job(999)

        mock_check_url.assert_not_called()
        assert result is None
