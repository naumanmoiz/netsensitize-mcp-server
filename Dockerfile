FROM python:3.11-slim AS builder

WORKDIR /app

COPY pyproject.toml ./

RUN pip install --no-cache-dir poetry \
    && poetry export --without-hashes --format requirements.txt --output requirements.txt


FROM oraclelinux:9-slim

ENV PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN microdnf install -y python3.11 python3.11-devel python3.11-pip gcc && microdnf clean all \
    && python3.11 -m pip install --upgrade pip

WORKDIR /app

COPY --from=builder /app/requirements.txt ./
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml ./
COPY src ./src

RUN python3.11 -m pip install --no-cache-dir . \
    && microdnf remove -y gcc python3.11-devel && microdnf clean all \
    && useradd --create-home --shell /usr/sbin/nologin appuser

USER appuser

EXPOSE 10694

CMD ["python3.11", "-m", "uvicorn", "redact_mcp.main:app", "--host", "0.0.0.0", "--port", "10694"]
