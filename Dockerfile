# PriceSense production image. Local dev doesn't need this at all --
# `python manage.py runserver` on SQLite is the zero-setup path (see
# README). This is for running the full stack (app + Postgres + Redis +
# Celery) via docker-compose.yml, or deploying anywhere that speaks
# Docker.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=pricesense.settings

# build-essential: Prophet's CmdStan backend needs a C++ compiler to build.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bakes CmdStan into the image at build time (a multi-minute compile)
# instead of paying that cost lazily on the first real request.
RUN python -c "import cmdstanpy; cmdstanpy.install_cmdstan()"

COPY . .

RUN SECRET_KEY=build-only python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "pricesense.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
