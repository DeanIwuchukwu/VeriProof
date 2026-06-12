"""Shared test fixtures. The real COLA records live in /ColaData at the repo root."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COLA_DIR = REPO_ROOT / "ColaData"


@pytest.fixture(scope="session")
def cola_dir() -> Path:
    assert COLA_DIR.is_dir(), f"ColaData not found at {COLA_DIR}"
    return COLA_DIR
