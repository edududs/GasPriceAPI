# syntax=docker/dockerfile:1
FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY manage.py ./
COPY src ./src
RUN uv sync --locked --no-dev

# The Tailwind binary is downloaded here and stays in this stage; only the built CSS moves on.
RUN DJANGO_DEBUG=1 .venv/bin/python manage.py tailwind build \
 && DJANGO_SECRET_KEY=collectstatic-only .venv/bin/python manage.py collectstatic --noinput


FROM python:3.13-slim
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=build --chown=app /app/.venv ./.venv
COPY --from=build --chown=app /app/src ./src
COPY --from=build --chown=app /app/staticfiles ./staticfiles
COPY --from=build --chown=app /app/manage.py ./
RUN mkdir data && chown app data
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
HEALTHCHECK --interval=1m --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')"
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn gasprice.config.wsgi -b 0.0.0.0:8000 -w 2 --access-logfile -"]
