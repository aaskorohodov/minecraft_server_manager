#!/bin/sh
set -e

echo "Starting Minecraft Server Manager..."

# Ensure server directory exists
mkdir -p /data/server

# Downloading server if missing
if [ ! -f /data/server/server.jar ]; then
    echo "Minecraft server not found, downloading..."
    /app/docker/download_server.sh
fi

# Accepting EULA automatically
if [ ! -f /data/server/eula.txt ]; then
    echo "eula=true" > /data/server/eula.txt
fi

# Starting server-manager
exec python -m main
