#!/bin/bash

# Configuration
SESSION_NAME="discord_bot"
BOT_DIRECTORY="/root/deployment_repos/python_discord_bot"
START_COMMAND="/root/anaconda3/envs/my_discord_bot/bin/python main.py"

# Navigate to the bot directory
cd "$BOT_DIRECTORY"

# Check if the tmux session exists
tmux has-session -t $SESSION_NAME 2>/dev/null

if [ $? != 0 ]; then
    echo "Session $SESSION_NAME does not exist, creating it"
    tmux new-session -d -s $SESSION_NAME "$START_COMMAND"
else
    echo "Session $SESSION_NAME exists, killing and creating a new one"
    tmux kill-session -t $SESSION_NAME
    tmux new-session -d -s $SESSION_NAME "$START_COMMAND"
fi

echo "Bot restarted in tmux session: $SESSION_NAME"
