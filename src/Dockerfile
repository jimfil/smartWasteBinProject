FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pirlib/ pirlib/
COPY models/ models/
COPY producer.py .
COPY consumer.py .
COPY dashboard.py .
COPY archiver.py .

CMD ["python", "pipeline.py", "--device-id", "pir-docker-01", "--pin", "4", "--sample-interval", "0.1", "--cooldown", "5", "--min-high", "0.2", "--queue-size", "50", "--consumer-delay", "0.5", "--duration", "6000", "--out", "motion_pipeline.log", "--verbose"]
