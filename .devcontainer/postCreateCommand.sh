#!/bin/bash
set -e

# Update package lists
sudo apt-get update

# Install required packages
sudo apt-get install -y trash-cli tree libgtk2.0-0 libgtk-3-0 libgbm-dev libnotify-dev libnss3 libxss1 libasound2 libxtst6 xauth xvfb

# Download and extract jujutsu
curl -L https://github.com/jj-vcs/jj/releases/download/v0.29.0/jj-v0.29.0-x86_64-unknown-linux-musl.tar.gz | sudo tar xz -C /usr/local/bin

# Make the workspace folder the current directory
cd ${WORKSPACE_FOLDER}

# Install Poetry if not already installed
poetry config virtualenvs.in-project true
poetry install --with dev

# Ensure .bashrc sources .bash_aliases
if ! grep -q "bash_aliases" /home/vscode/.bashrc; then
    echo -e "\n# Source user aliases\nif [ -f ~/.bash_aliases ]; then\n  . ~/.bash_aliases\nfi" >> /home/vscode/.bashrc
fi
