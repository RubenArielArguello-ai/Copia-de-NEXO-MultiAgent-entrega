# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /install /usr/local
COPY . .

ENV NEXO_ENV production
ENV OLLAMA_HOST=http://ollama-provider:11434

RUN mkdir -p /data && chown -R 1000:1000 /app /data
USER 1000:1000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
