FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FOOTBALL_PUBLIC_MODE=true \
    FOUNDRY_LIVE_ENABLED=false \
    COURTROOM_LIVE_ENABLED=false
WORKDIR /srv
COPY backend/requirements-public.txt /srv/requirements-public.txt
RUN pip install --no-cache-dir -r /srv/requirements-public.txt
COPY backend/app/ /srv/backend/app/
COPY backend/data/courtroom-trials/ /srv/backend/data/courtroom-trials/
# This root-owned marker cannot be disabled by environment flags or API input.
RUN touch /srv/backend/app/PUBLIC_ONLY \
    && chmod -R a=rX /srv/backend
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "/srv/backend", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
