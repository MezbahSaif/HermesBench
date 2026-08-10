from urllib.parse import parse_qs


def parse_query(url: str) -> dict:
    """Return decoded query parameters; values may repeat (as lists)."""
    if "?" not in url:
        return {}
    _, _, qs = url.partition("?")
    return {k: v[0] for k, v in parse_qs(qs).items()}


def path_of(url: str) -> str:
    path = url.partition("?")[0]
    return path.split("://", 1)[-1].partition("/")[2].rstrip("/") or "/"
