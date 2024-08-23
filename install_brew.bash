#!/bin/bash

curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh | bash
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
brew upgrade
xargs brew install <brew.txt
