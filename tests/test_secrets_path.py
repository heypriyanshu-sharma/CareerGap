"""Tests for the configurable secrets-file path (Item 4e).

The secrets file location must come only from the
CAREERGAP_SECRETS_PATH environment variable, with the
project-root .env as the fallback. No personal filesystem path
may be baked into the source. No secret values are read here:
these tests assert the resolution wiring only.
"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AUTH_PY = ROOT / "auth.py"
BACKEND_PY = ROOT / "backend.py"
AI_ADVISOR_PY = ROOT / "ai_advisor.py"

FILES = (BACKEND_PY, AUTH_PY, AI_ADVISOR_PY)

ENV_VAR = "CAREERGAP_SECRETS_PATH"

LOADING_BLOCK = re.compile(
    r"# Load the external secrets file.*?load_dotenv\(\)",
    re.S,
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _compact(source):
    return re.sub(r"\s+", "", source)


class TestSecretsPath:

    def test_every_module_exists_and_reads_the_override(self):
        for path in FILES:
            assert path.is_file()
            assert ENV_VAR in _read(path), path.name

    def test_no_module_hardcodes_a_personal_path(self):
        """The leak this item fixes: no drive letter, home
        directory, OneDrive path or old default constant."""

        for path in FILES:
            source = _read(path)

            assert not re.search(r"[A-Za-z]:\\", source), path.name
            assert "OneDrive" not in source, path.name
            assert "careergap_secrets" not in source, path.name
            assert "DEFAULT_SECRETS_PATH" not in source, path.name

    def test_resolution_is_env_only(self):
        """The env lookup must not carry a second argument
        that would restore a built-in default path."""

        expected = (
            "SECRETS_PATH="
            'os.environ.get("CAREERGAP_SECRETS_PATH")'
        )

        for path in FILES:
            assert expected in _compact(_read(path)), path.name

    def test_missing_file_or_unset_override_falls_back_to_root_env(self):
        """An unset variable or a missing file still loads the
        project-root .env through bare load_dotenv()."""

        for path in FILES:
            compact = _compact(_read(path))

            assert (
                "ifSECRETS_PATHandPath(SECRETS_PATH).exists():"
                in compact
            )
            assert "load_dotenv(SECRETS_PATH)" in compact
            assert "else:load_dotenv()" in compact

    def test_all_modules_share_the_same_loading_block(self):
        """One copy of the logic, so a change to one module
        cannot silently drift from the others."""

        blocks = []

        for path in FILES:
            match = LOADING_BLOCK.search(_read(path))

            assert match, path.name
            blocks.append(_compact(match.group(0)))

        assert len(set(blocks)) == 1

    def test_backend_loads_secrets_before_importing_auth(self):
        """backend.py's env must be ready before the
        module-level client in auth.py is created."""

        compact = _compact(_read(BACKEND_PY))

        dots = compact.index("load_dotenv")
        auth_import = compact.index("fromauthimport")

        assert dots < auth_import

    def test_fallback_still_calls_bare_load_dotenv(self):
        """The root .env is discovered by python-dotenv rather
        than by reimplementing its lookup here."""

        for path in FILES:
            source = _read(path)

            assert "    load_dotenv()" in source
            assert "find_dotenv" not in source
