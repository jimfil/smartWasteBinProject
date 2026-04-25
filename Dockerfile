FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/pirlib/ pirlib/
COPY src/models/ models/
COPY src/producer.py .
COPY src/consumer.py .
COPY src/dashboard.py .
COPY src/archiver.py .

CMD ["python", "--help"]
