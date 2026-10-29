# One image for the dashboard and the ingest service - they differ only in their `command`
# (see compose.yaml). `config.yml` is not baked in: compose mounts it read-only (NFR-08).
# There is no .dockerignore: this COPY list is the filter, so docs/, node_modules/ and the
# deploy files never reach the image. **Every file under assets/ that the browser loads has to be
# listed here** (the beer favicon, the cursor image, the bubble script) - a file that is only
# committed is served by a host-side run and 404s in the container. `input.pcss` stays out on
# purpose: it is the Tailwind source, not something the browser may fetch.
# Fully qualified image name (docker.io/library/...), so a Podman host never needs a short-name
# alias from its /etc/containers/registries.conf - see the note at `db` in compose.yaml.
FROM docker.io/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/repo

WORKDIR /repo

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py ./
COPY components/ components/
COPY services/ services/
COPY tools/ tools/
COPY assets/tailwind.css assets/card_state.js assets/bubbles.js assets/
COPY assets/favicon-beer.svg assets/cursor-beer.svg assets/cursor-beer.png assets/
COPY assets/cursor-beer-hover.svg assets/cursor-beer-hover.png assets/
COPY assets/fonts/ assets/fonts/

EXPOSE 8080

# gunicorn, not the development server of main.py.
CMD ["gunicorn", "main:server", \
     "-b", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "120"]
