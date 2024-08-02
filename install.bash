#!/bin/bash

sudo apt update
sudo apt install -y git zsh zsh-antigen autossh build-essential curl python3 python3-pip python3-virtualenvwrapper python3-colorama gcc powerline kitty-terminfo kitty-terminfo

curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh | bash
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"

brew install jq yq
source install_ssh_keys.bash

brew install pyenv pyenv-virtualenv
eval "$(pyenv init -)"
pyenv install 3.12
pyenv global 3.12

brew install neovim

git clone https://github.com/alisoam/public.git
pushd public/config
source install.bash
popd
