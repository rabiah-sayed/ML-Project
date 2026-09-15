import os

from django.conf import settings


def static_version(request):
    """Cache-busting token for static assets, derived from style.css's
    mtime -- appended as a query string on the stylesheet link so the
    browser re-fetches it after every edit instead of serving a stale
    cached copy (which otherwise silently mismatches newly changed HTML
    class names during development).
    """
    try:
        mtime = int(os.path.getmtime(settings.BASE_DIR / 'static' / 'css' / 'style.css'))
    except OSError:
        mtime = 0
    return {'style_version': mtime}
