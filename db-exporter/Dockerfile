FROM python:3.12-slim AS builder

# pymssql needs freetds headers + a build toolchain to compile its C extension.
# The other three drivers (psycopg2-binary, mysql-connector-python,
# python-oracledb in thin mode) need no system dependencies at all.
RUN apt-get update && apt-get install -y --no-install-recommends \
        freetds-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.12-slim

# freetds-bin (the runtime shared library, not the -dev headers) is needed
# at runtime for pymssql -- freetds-dev/gcc from the builder stage are not
# copied forward, keeping the final image slim.
RUN apt-get update && apt-get install -y --no-install-recommends \
        freetds-bin \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app
COPY main.py .
COPY src/ src/

EXPOSE 9433
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9433/health', timeout=3)" || exit 1

CMD ["python", "main.py"]
