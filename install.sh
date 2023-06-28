#!/bin/sh

sudo apt update
sudo apt install -y git zsh zsh-antigen autossh build-essential curl python3 python3-pip

git clone https://github.com/alisoam/public.git
pip3 install -r config/requirements.txt
python3 config/sync.py sync_host

echo yes | /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install pyenv pyenv-virtualenv
brew install tmux
