"""HTTP helpers for evidence retrieval."""

import httpx

_REDIRECT_TIMEOUT = 5.0


def resolve_redirect(url):
    """GET url, follow redirects, and return the final URL.

    Raises if the request fails or does not complete within 5 seconds.
    """
    try:
        response = httpx.get(url, timeout=_REDIRECT_TIMEOUT, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError("redirect failed") from exc
    return str(response.url)
