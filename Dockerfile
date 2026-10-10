# Public live demo of the Signal web UI — Hugging Face Spaces (Docker SDK), or any container host.
# Demo / heuristic mode with NO secrets: bundled fixtures + the deterministic heuristic scorer.
# Missing keys never raise — every keyed source shows as "skipped" in the source-health panel.
#
#   docker build -t signal-demo . && docker run -p 7860:7860 signal-demo   →  http://localhost:7860
FROM python:3.12-slim

# HF Spaces runs the container as uid 1000; own the app dir so out/ (digests, memos) is writable.
RUN useradd -m -u 1000 user
WORKDIR /home/user/app
RUN pip install --no-cache-dir "pyyaml>=6.0"
COPY --chown=user . .
USER user

ENV PYTHONPATH=src \
    PYTHONUNBUFFERED=1 \
    SIGNAL_LLM_PROVIDER=heuristic \
    PORT=7860

# Pre-bake the demo digest + backtest so the first visitor sees a populated dashboard.
RUN python -m signalfund --demo && python -m signalfund.backtest --demo

EXPOSE 7860
CMD ["python", "-u", "-m", "signalfund.webapp", "--host", "0.0.0.0", "--port", "7860", "--no-open"]
