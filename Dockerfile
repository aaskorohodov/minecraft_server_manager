FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    openjdk-17-jre-headless \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Set workdir
WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Configure poetry
RUN poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi

# Copy application code
COPY src/ src/
COPY docker ./docker

# Make scripts executable
RUN chmod +x /app/docker/*.sh

# Environment
ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/data/connectivity.db
ENV MC_SERVER_DIR=/data/server

# Persistent data
VOLUME ["/data"]

# Expose Minecraft port
EXPOSE 25565

ENTRYPOINT ["/app/docker/entrypoint.sh"]
