# Build stage
FROM python:3.9-slim as builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.9-slim

WORKDIR /app

COPY --from=builder /root/.local /root/.local
COPY . .

ENV PATH=/root/.local/bin:$PATH
ENV NEXO_ENV production

USER 1000:1000

CMD ["uvicorn", "nexo.api.main:app --host 0.0.0.0 --port 8000"]
