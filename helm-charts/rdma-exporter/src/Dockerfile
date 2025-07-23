# Use a lightweight Python base image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Install prometheus_client
RUN pip install --no-cache-dir prometheus_client

# Copy the exporter script
COPY rdma-exporter.py .

# Set environment variables for default configuration
ENV LISTEN_PORT=9898
ENV LOG_LEVEL=INFO
ENV SYS_PATH=/host/sys

# Expose the port
EXPOSE 9898

# Run the exporter
CMD ["python", "rdma-exporter.py"]
