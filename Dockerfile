FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

RUN pip install --no-cache-dir -e .

RUN useradd -m botuser && chown -R botuser:botuser /app
USER botuser

CMD ["python", "-m", "betbot.main"]
