import os


worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "75"))
forwarded_allow_ips = "*"
