# One image for the dashboard and the ingest service - they differ only in their `command`
# (see compose.yaml). `config.yml` is not baked in: compose mounts it read-only (NFR-08).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/repo

WORKDIR /repo

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# gunicorn, not the development server of main.py.
CMD ["gunicorn", "main:server", \
     "-b", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "120"]
