#!/bin/bash

sudo apt update
sudo apt install -y git zsh zsh-antigen autossh build-essential curl python3 python3-pip gcc

curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh | bash
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"

brew install pyenv pyenv-virtualenv
eval "$(pyenv init -)"
pyenv install 3.11
pyenv global 3.11

brew install tmux

brew install neovim
git clone https://github.com/wbthomason/packer.nvim "$env:LOCALAPPDATA\nvim-data\site\pack\packer\start\packer.nvim"

source config/install.bash
