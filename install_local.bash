#!/bin/bash

source install_apt.bash

source install_brew.bash

pushd config
source install.bash
popd
