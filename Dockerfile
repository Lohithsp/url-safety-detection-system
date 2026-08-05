# Use the official lightweight Python image
FROM python:3.9-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED=True

# Set the working directory in the container
WORKDIR /app

# Copy local code to the container image
COPY . ./

# Install system dependencies (libgomp1 is required for XGBoost OpenMP execution)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Run the web service on container startup
# We use gunicorn with 1 worker and 8 threads for serverless execution.
# Timeout is set to 0 to disable worker timeouts, letting Cloud Run manage scaling.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 server:app
