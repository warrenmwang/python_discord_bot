#!/bin/bash

# Friendship ended with github actions, now we are
# using plain old bash scripts.

set -a
source .env_deploy
set +a

SERVER_ALIAS="server"

SCRIPT="
cd /home/wang/deployment_repos/python_discord_bot

# stop the old container
docker compose down

# fast forward to new code
git pull origin main

# Setup env vars
export DISCORD_TOKEN=${DISCORD_TOKEN}
export OPENAI_API_KEY=${OPENAI_API_KEY}
export APP_DATA_DIR=${APP_DATA_DIR}
export CHATGPT_CHANNEL=${CHATGPT_CHANNEL}
export PERSONAL_ASSISTANT_CHANNEL=${PERSONAL_ASSISTANT_CHANNEL}

# build and start new container
docker compose build
docker compose up -d --remove-orphans
"

ssh ${SERVER_ALIAS} "${SCRIPT}"