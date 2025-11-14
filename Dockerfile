FROM python:3.12-slim

WORKDIR /app

# Copy all necessary files
COPY requirements.txt .
COPY config.yaml .
COPY packages/ packages/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install local packages in editable mode
RUN pip install -e packages/core && \
    pip install -e packages/network && \
    pip install -e packages/providers/azure/models && \
    pip install -e packages/providers/azure/vectordb

# Expose port 8000 (standard port, Azure will map to 80/443)
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    NLWEB_CONFIG_DIR=/app

# Standard Docker pattern: Use CMD with full command
# Azure App Service will respect this if no startup command is configured
CMD ["python", "-m", "nlweb_network.server"]
