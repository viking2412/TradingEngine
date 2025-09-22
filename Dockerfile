FROM ubuntu:latest
LABEL authors="Kuroko"

ENTRYPOINT ["top", "-b"]

FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "trading_engine.main", "--config", "config.json"]
