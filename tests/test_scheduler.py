"""Tests for the scheduler module."""
from unittest.mock import ANY, MagicMock
from datetime import datetime, timezone, timedelta

import pytest

from uptime.database import db
from scheduler import get_due_targets, enqueue_checks


class TestGetDueTargets:
    """Tests for get_due_targets()."""

    def test_get_due_targets_new_target(self, tmp_path, monkeypatch):
        """Target with no checks → should be due."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

        from uptime.app import create_app as _create_app
        app = _create_app()
        with app.app_context():
            from uptime.models import Target
            target = Target(name="Test", url="https://example.com", is_active=True)
            db.session.add(target)
            db.session.commit()
            target_id = target.id

        due = get_due_targets()
        assert len(due) == 1

        # Verify via fresh query (returned objects are detached)
        app2 = _create_app()
        with app2.app_context():
            t = db.session.get(Target, target_id)
            assert t is not None

    def test_get_due_targets_not_due(self, tmp_path, monkeypatch):
        """Target with recent check (within interval_seconds) → NOT due."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

        from uptime.app import create_app as _create_app
        app = _create_app()
        with app.app_context():
            from uptime.models import Target, Check
            target = Target(
                name="Test",
                url="https://example.com",
                is_active=True,
                interval_seconds=60,
            )
            db.session.add(target)
            db.session.commit()
            check = Check(
                target_id=target.id,
                status_code=200,
                latency_ms=100,
                is_up=True,
                created_at=datetime.now(timezone.utc) - timedelta(seconds=10),
            )
            db.session.add(check)
            db.session.commit()

        due = get_due_targets()
        assert len(due) == 0

    def test_get_due_targets_due(self, tmp_path, monkeypatch):
        """Target with old check (past interval_seconds) → due."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

        from uptime.app import create_app as _create_app
        app = _create_app()
        with app.app_context():
            from uptime.models import Target, Check
            target = Target(
                name="Test",
                url="https://example.com",
                is_active=True,
                interval_seconds=30,
            )
            db.session.add(target)
            db.session.commit()
            check = Check(
                target_id=target.id,
                status_code=200,
                latency_ms=100,
                is_up=True,
                created_at=datetime.now(timezone.utc) - timedelta(seconds=60),
            )
            db.session.add(check)
            db.session.commit()

        due = get_due_targets()
        assert len(due) == 1


class TestEnqueueChecks:
    """Tests for enqueue_checks()."""

    def test_enqueue_checks(self, monkeypatch):
        """Calls enqueue for each target with correct args."""
        mock_enqueue = MagicMock()
        monkeypatch.setattr("scheduler.check_queue.enqueue", mock_enqueue)

        target = MagicMock(spec=[])
        target.id = 1
        target.interval_seconds = 30
        target.url = "https://example.com"

        enqueue_checks([target])

        mock_enqueue.assert_called_once_with(
            "uptime.jobs.check_job", 1,
            job_timeout=30,
            description="check:1:https://example.com",
        )

    def test_enqueue_checks_multiple(self, monkeypatch):
        """Multiple targets → multiple enqueue calls."""
        mock_enqueue = MagicMock()
        monkeypatch.setattr("scheduler.check_queue.enqueue", mock_enqueue)

        targets = []
        for i in range(3):
            t = MagicMock(spec=[])
            t.id = i + 1
            t.interval_seconds = 30
            t.url = f"https://example{i}.com"
            targets.append(t)

        enqueue_checks(targets)

        assert mock_enqueue.call_count == 3
        for i in range(3):
            args, kwargs = mock_enqueue.call_args_list[i]
            assert args[0] == "uptime.jobs.check_job"
            assert args[1] == i + 1
            assert kwargs["job_timeout"] == 30
            assert kwargs["description"] == f"check:{i + 1}:https://example{i}.com"
