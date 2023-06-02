#!/bin/sh

BASE_DIR=./
alias CP="cp"
alias SUDOCP="sudo cp"
alias MKDIR="mkdir"
alias SUDOMKDIR="sudo mkdir"

echo tmux
CP ${BASE_DIR}/tmux/tmux.conf ~/.tmux.conf

echo shell
CP ${BASE_DIR}/shell/zshrc ~/.zshrc
CP ${BASE_DIR}/shell/bashrc ~/.bashrc
CP ${BASE_DIR}/shell/profile ~/.profile

echo nvim
MKDIR -p ~/.config/nvim/lua
CP ${BASE_DIR}/nvim/init.lua ~/.config/nvim/init.lua
CP ${BASE_DIR}/nvim/lua/lsp-cfg.lua ~/.config/nvim/lua/lsp-cfg.lua

echo ssh
MKDIR -p ~/.ssh/
CP ${BASE_DIR}/ssh/config ~/.ssh/config
CP ${BASE_DIR}/ssh/authorized_keys ~/.ssh/authorized_keys

echo git
CP ${BASE_DIR}/git/gitconfig ~/.gitconfig
CP ${BASE_DIR}/git/gitignore ~/.gitignore

echo i3
MKDIR -p ~/.config/i3/
MKDIR -p ~/.config/i3status
CP ${BASE_DIR}/i3/i3 ~/.config/i3/config
CP ${BASE_DIR}/i3/i3status ~/.config/i3status/confi

echo kitty
MKDIR -p ~/.config/kitty/
CP ${BASE_DIR}/kitty/kitty.conf ~/.config/kitty/kitty.conf
CP ${BASE_DIR}/kitty/theme.conf ~/.config/kitty/theme.conf


echo kitty
MKDIR -p ~/.config/kitty/
CP ${BASE_DIR}/kitty/kitty.conf ~/.config/kitty/kitty.conf
CP ${BASE_DIR}/kitty/theme.conf ~/.config/kitty/theme.conf

echo docker
SUDOMKDIR -p /etc/docker/
SUDOMKDIR -p /etc/systemd/system/docker.service.d/
SUDOCP ${BASE_DIR}/docker/daemon.json /etc/docker/daemon.json
SUDOCP ${BASE_DIR}/docker/proxy.conf /etc/systemd/system/docker.service.d/proxy.conf
systemctl daemon-reload
systemctl restart docker

