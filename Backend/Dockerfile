FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/Backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY Backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and ML directories
COPY Backend ./Backend
COPY ML ./ML

EXPOSE 5000

CMD ["uvicorn", "Backend.main:app", "--host", "0.0.0.0", "--port", "5000", "--app-dir", "/app/Backend"]
