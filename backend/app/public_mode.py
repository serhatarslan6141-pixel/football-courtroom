"""Public images have an immutable marker, independent of live AI flags."""
import os
from pathlib import Path
from urllib.parse import urlsplit

PUBLIC_ONLY = (Path(__file__).with_name('PUBLIC_ONLY').is_file()
               or os.environ.get('FOOTBALL_PUBLIC_MODE', '').lower() == 'true')


def cors_origins():
    configured = os.environ.get('CORS_ORIGINS')
    if configured is None:
        return [] if PUBLIC_ONLY else [
            'http://localhost:5173', 'http://127.0.0.1:5173',
            'http://localhost:3000', 'http://127.0.0.1:3000']
    origins = list(dict.fromkeys(value.strip() for value in configured.split(',') if value.strip()))
    for origin in origins:
        url = urlsplit(origin)
        if (url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password
                or url.path or url.query or url.fragment or '*' in origin
                or (PUBLIC_ONLY and url.scheme != 'https' and url.hostname not in ('localhost', '127.0.0.1'))):
            raise ValueError('CORS_ORIGINS must contain exact HTTPS origins (HTTP loopback is allowed locally).')
    return origins
