FROM python:3.10.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/static /app/uploads

EXPOSE 8000

CMD ["gunicorn", "--timeout", "60", "--workers", "2", "--bind", "0.0.0.0:8000", "core.wsgi:application"]
