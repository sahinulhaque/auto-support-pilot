FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN useradd -m -u 1000 appuserasp

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

RUN mkdir -p chromaDocuments sqldb chromadb && \
    chown -R appuserasp:appuserasp /app && \
    chmod -R 0755 chromaDocuments sqldb chromadb


COPY . .

USER appuserasp
EXPOSE 8000
CMD ["python", "startServer.py"]