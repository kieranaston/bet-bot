FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

RUN pip install --no-cache-dir -e .

RUN useradd -m botuser && chown -R botuser:botuser /app
USER botuser

# Loops continuously so Telegram commands are picked up within ~20s instead of waiting for
# the next scheduled tick. Each iteration is a fresh one-shot `run()` -- cheap (Python
# startup is well under a second) -- and betbot.main's own scan-window + last_scan_window
# dedup logic (see scheduler.current_scan_window_key) ensures the actual Odds API scan still
# only fires once per 3-hour window, not once per loop iteration. For a one-shot invocation
# (e.g. GitHub Actions or a manual `docker run`), override with `docker run ... bet-bot
# python -m betbot.main` instead of using this default CMD.
CMD ["sh", "-c", "while true; do python -m betbot.main; sleep 20; done"]
