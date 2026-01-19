#!/bin/sh
set -e

MC_VERSION=${MC_VERSION:-1.21.10}

echo "Downloading Minecraft server version ${MC_VERSION}"

curl -o /data/server/server.jar \
  https://launcher.mojang.com/v1/objects/<HASH>/server.jar
