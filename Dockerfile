FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=7860
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY manifest.webmanifest .
COPY static ./static
RUN mkdir -p /app/data && useradd --system --uid 10001 appuser && chown -R appuser:appuser /app
ENV DATABASE_PATH=/app/data/omidwar.db
EXPOSE 7860
USER 10001
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
