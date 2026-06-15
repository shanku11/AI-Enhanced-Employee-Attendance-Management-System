FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY Backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY Backend ./Backend
COPY ML ./ML

# Make Backend importable
ENV PYTHONPATH=/app/Backend
EXPOSE 10000
CMD ["sh", "-c", "cd /app/Backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
