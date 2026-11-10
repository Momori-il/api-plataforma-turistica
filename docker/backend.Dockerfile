FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=UTC
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl unixodbc \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb -o /tmp/microsoft.deb \
    && dpkg -i /tmp/microsoft.deb \
    && apt-get update && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18=18.7.1.1-1 \
    && rm -rf /var/lib/apt/lists/* /tmp/microsoft.deb
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd -g 10001 app && useradd -u 10001 -g app -M -s /usr/sbin/nologin app
COPY backend/ /app/
COPY docker/init_sql.py /app/scripts/init_container_sql.py
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=10s --start-period=60s --retries=3 CMD ["python","-c","import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=8)"]
CMD ["python","-m","uvicorn","main:app","--host","0.0.0.0","--port","8000","--no-access-log"]
