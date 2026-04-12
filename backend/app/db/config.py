import os
from urllib.parse import urlsplit, urlunsplit


DEFAULT_DATABASE_URL_EXAMPLE = "postgresql://<user>:<password>@localhost:5432/portfolio_diversification"


def get_database_url(explicit_url: str | None = None) -> str:
    raw = (explicit_url or os.getenv("DATABASE_URL") or "").strip()
    if not raw:
        raise ValueError(
            "DATABASE_URL is not set. Example: "
            f"{DEFAULT_DATABASE_URL_EXAMPLE}"
        )

    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]

    if not raw.startswith("postgresql://"):
        raise ValueError("DATABASE_URL must use postgresql:// (or postgres://)")
    return raw


def redact_database_url(database_url: str) -> str:
    parsed = urlsplit(database_url)
    if "@" not in parsed.netloc:
        return database_url

    userinfo, hostinfo = parsed.netloc.rsplit("@", maxsplit=1)
    if ":" in userinfo:
        username, _password = userinfo.split(":", maxsplit=1)
        safe_userinfo = f"{username}:***"
    else:
        safe_userinfo = userinfo

    safe_netloc = f"{safe_userinfo}@{hostinfo}"
    return urlunsplit((parsed.scheme, safe_netloc, parsed.path, parsed.query, parsed.fragment))
