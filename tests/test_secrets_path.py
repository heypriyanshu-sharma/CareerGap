"""Tests for the configurable secrets-file path (Item 4e).

The secrets file location must come from SECRETS_PATH in auth.py
and backend.py, overridable with the CAREERGAP_SECRETS_PATH
environment variable, keeping the original path as the default
and the project-root .env fallback. No secret values are read
here: these tests assert the resolution wiring only.
"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AUTH_PY = ROOT / "auth.py"
BACKEND_PY = ROOT / "backend.py"


def _read(path):
    return path.read_text(encoding="utf-8")


def _compact(source):
    return re.sub(r"\s+", "", source)


FILES = (AUTH_PY, BACKEND_PY)


class TestSecretsPath:

    def test_both_files_exist(self):
        assert AUTH_PY.exists()
        assert BACKEND_PY.exists()

    def test_both_files_expose_the_override_variable(self):
        for path in FILES:
            source = _read(path)

            assert "CAREERGAP_SECRETS_PATH" in source
            assert "DEFAULT_SECRETS_PATH" in source

    def test_secrets_path_resolves_through_the_env_var(self):
        """SECRETS_PATH must be resolved through the env var,
        falling back to DEFAULT_SECRETS_PATH."""

        for path in FILES:
            compact = _compact(_read(path))

            assert (
                "SECRETS_PATH=Path("
                'os.environ.get("'
                'CAREERGAP_SECRETS_PATH",DEFAULT_SECRETS_PATH))'
            ) in compact

    def test_default_path_is_the_original_location(self):
        """Existing local setups keep working: the prior
        hardcoded location stays as the default."""

        for path in FILES:
            compact = _compact(_read(path))

            assert "OneDrive\\Documents\\careergap_secrets\\.env" in compact
            assert "DEFAULT_SECRETS_PATH=r" in compact

    def test_missing_file_falls_back_to_root_env(self):
        """The exists-check and bare load_dotenv() fallback
        must be preserved in both modules."""

        for path in FILES:
            compact = _compact(_read(path))

            assert "ifSECRETS_PATH.exists():" in compact
            assert "load_dotenv(SECRETS_PATH)" in compact
            assert "else:load_dotenv()" in compact

    def test_backend_loads_secrets_before_importing_auth(self):
        """backend.py's env must be ready before the
        module-level client in auth.py is created."""

        compact = _compact(_read(BACKEND_PY))

        dots = compact.index("load_dotenv")
        auth_import = compact.index("fromauthimport")

        assert dots < auth_import

    def test_path_call_consumes_the_env_lookup_not_the_literal(self):
        """The Path(...) call must consume the env lookup,
        never the raw literal directly."""

        for path in FILES:
            compact = _compact(_read(path))

            assert 'Path(r"C:\\Users' not in compact
            assert "os.environ.get" in compact
