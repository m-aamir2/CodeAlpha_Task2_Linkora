import os
from urllib.parse import unquote, urlsplit


def is_user_blob_url(value, user_id, allowed_categories=None):
    """Only accept HTTPS Vercel Blob URLs stored in the uploader's own folder."""
    allowed_categories = allowed_categories or {"posts", "profiles"}
    try:
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").lower()
        segments = [unquote(segment) for segment in parsed.path.split("/") if segment]
    except (TypeError, ValueError):
        return False

    configured_hosts = {
        host.strip().lower().removeprefix("https://").removeprefix("http://").split("/")[0]
        for host in os.getenv("BLOB_PUBLIC_HOSTNAMES", "").split(",")
        if host.strip()
    }
    known_vercel_blob_host = hostname.endswith(".public.blob.vercel-storage.com")
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        return False
    if not (known_vercel_blob_host or hostname in configured_hosts):
        return False
    return (
        len(segments) >= 4
        and segments[:2] == ["users", str(user_id)]
        and segments[2] in allowed_categories
        and all(segment not in {".", ".."} for segment in segments)
    )
