"""
Pytest configuration and fixtures for Chess Master tests.

Sets up shared test environment including database manager.
"""

import pytest
import tempfile
from pathlib import Path

import db.database as db_module


@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    """
    Auto-use fixture to set up a temporary database for each test.

    This ensures that the global database manager is initialized for tests
    that rely on module-level functions like get_player().
    """
    # Create temp database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_chess_club.db"
        db_url = f"sqlite:///{db_path}"

        # Create and initialize manager
        manager = db_module.DatabaseManager(database_url=db_url)
        manager.initialize()

        # Store original manager
        old_manager = db_module._db_manager

        # Set global manager
        db_module._db_manager = manager

        yield manager

        # Restore original manager
        db_module._db_manager = old_manager
        manager.close()
