"""
Regression tests for production API documentation gating (Item 4a).

The interactive docs enumerate every route, so they must not be reachable
on the production host. Render sets RENDER=true in its runtime; local
development keeps /docs, /redoc and /openapi.json so the documented
workflow still works.

The gate is exercised through the real helper and through real FastAPI
applications built from its output. A source pin keeps the module-level
app wired to the helper instead of hardcoded URLs.
"""

import re
from pathlib import Path

import pytest
from fastapi import FastAPI

import backend

BACKEND_PY = Path(__file__).resolve().parent.parent / "backend.py"


@pytest.fixture(autouse=True)
def no_render_env(monkeypatch):
    """Keep the ambient environment from leaking into these tests."""

    monkeypatch.delenv("RENDER", raising=False)


# ============================================================
# ENVIRONMENT GATE
# ============================================================

def test_docs_stay_enabled_locally():
    assert backend.api_docs_urls() == {
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
    }


def test_docs_are_disabled_in_production(monkeypatch):
    monkeypatch.setenv("RENDER", "true")

    assert backend.api_docs_urls() == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }


# ============================================================
# ROUTE REGISTRATION
# ============================================================

def test_production_app_registers_no_docs_routes(monkeypatch):
    """A production app must expose no docs or schema routes at all."""

    monkeypatch.setenv("RENDER", "true")

    app = FastAPI(**backend.api_docs_urls())
    paths = {route.path for route in app.routes}

    assert "/docs" not in paths
    assert "/redoc" not in paths
    assert "/openapi.json" not in paths


def test_local_app_registers_the_docs_routes():
    app = FastAPI(**backend.api_docs_urls())
    paths = {route.path for route in app.routes}

    assert "/docs" in paths
    assert "/redoc" in paths
    assert "/openapi.json" in paths


# ============================================================
# SOURCE PIN
# ============================================================

def test_module_app_is_built_from_the_environment_gate():
    """The real app must consume the helper, so the gate cannot be
    bypassed by hardcoded documentation URLs."""

    compact = re.sub(
        r"\s+",
        "",
        BACKEND_PY.read_text(encoding="utf-8"),
    )

    assert "app=FastAPI(" in compact
    assert "**api_docs_urls()," in compact
