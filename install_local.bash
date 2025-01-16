#!/bin/bash

source install_apt.bash

source install_brew.bash

eval "$(pyenv init -)"
pyenv install -s 3.12
pyenv global 3.12

pushd config
source install.bash
popd
