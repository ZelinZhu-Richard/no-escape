"""Load private, project-local settings without echoing credentials.

Only clearway/.env is considered by default. Existing process variables win;
shell commands and ${...} expansion are never evaluated.
"""

from collections.abc import MutableMapping
import os
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
LOCAL_ENV_PATH = ROOT / ".env"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULTS = {"GEMINI_MODEL": DEFAULT_MODEL, "GEMINI_MODEL_VERSION": DEFAULT_MODEL}
ALLOWED_VARIABLES = frozenset({
    "GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_MODEL_VERSION",
    "CLEARWAY_DATA_DIR", "PUBLIC_BASE_URL",
})


class ConfigurationError(ValueError):
    """A safe, authored configuration message; never includes file contents."""


def load_local_environment(
    path: Path | None = None,
    *,
    environ: MutableMapping[str, str] | None = None,
) -> bool:
    """Apply allowlisted settings, returning only whether the file exists.

    Pass a temporary path/mapping in tests. This function does not create files,
    contact a provider, authorize billing, or change existing process values.
    """
    source = Path(path) if path is not None else LOCAL_ENV_PATH
    target = os.environ if environ is None else environ
    try:
        if source.is_symlink():
            raise ConfigurationError("Private configuration must be a regular local .env file.")
        if not source.exists():
            for key, value in DEFAULTS.items():
                target.setdefault(key, value)
            return False
        if not source.is_file():
            raise ConfigurationError("Private configuration must be a regular local .env file.")
        if source.stat().st_size > 32_768:
            raise ConfigurationError("Private configuration exceeds the supported file size.")
        settings = dotenv_values(source, interpolate=False, encoding="utf-8")
        updates = {key: value for key, value in settings.items()
                   if key in ALLOWED_VARIABLES and value is not None and key not in target}
        if any("\x00" in value for value in updates.values()):
            raise ConfigurationError("Private configuration contains an invalid value.")
        for key, value in updates.items():
            target[key] = value
        for key, value in DEFAULTS.items():
            target.setdefault(key, value)
        return True
    except ConfigurationError:
        raise
    except (OSError, UnicodeError, ValueError):
        raise ConfigurationError("Could not read private configuration; check clearway/.env locally.") from None
