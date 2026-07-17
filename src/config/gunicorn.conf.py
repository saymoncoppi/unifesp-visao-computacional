"""Gunicorn configuration for the label inspector web chat (FastAPI/ASGI).

Run command (from the src/ directory):

    uv run gunicorn -c config/gunicorn.conf.py app.api:app

The server then binds to 0.0.0.0:8000, so it is reachable from other machines on
the LAN at http://<your-ip-on-the-network>:8000 (same idea as Django's
`runserver 0.0.0.0:8000`).

WHY workers = 1 (important):
    The free-tier Gemini rate limit (5 requests/minute) is enforced by an
    in-memory, per-process RPM counter in config/inspector/ratelimit.py. Each
    Gunicorn worker is a separate OS process with its OWN copy of that counter.
    Running more than one worker would fragment the count across processes, so
    the global request rate could exceed the free-tier quota (each worker
    thinking it is under the limit). Keeping workers = 1 makes the counter
    globally correct. The bottleneck here is the Gemini quota / network I/O,
    NOT CPU, so a single worker with a few threads is the right shape.
"""

import multiprocessing  # noqa: F401  (kept for parity/reference; workers is fixed at 1 on purpose)
import os

# Run from the src/ dir so `app.api:app` imports and the relative app/static
# path resolve, no matter where gunicorn is launched:
chdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # -> the src/ directory

bind = "0.0.0.0:8000"   # reachable from other machines on the LAN, like Django 0.0.0.0:8000
worker_class = "uvicorn.workers.UvicornWorker"   # ASGI worker for FastAPI
workers = 1     # keep the in-memory free-tier RPM counter (config/inspector/ratelimit.py) globally correct; the Gemini free key (5 req/min) is the bottleneck, not CPU
threads = 4     # I/O concurrency for the LLM/network calls
timeout = 30
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
preload_app = True
accesslog = "-"
errorlog = "-"
loglevel = "info"
