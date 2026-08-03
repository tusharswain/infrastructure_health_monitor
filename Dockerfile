FROM python:3.11-slim

WORKDIR /app

# Install system dependencies useful for SSH and metric collection
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    procps \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Mount config/credentials.yaml at runtime
CMD ["python", "run.py", "monitor"]
