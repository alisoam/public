#!/bin/bash

temp_dir=$(mktemp -d)

git clone https://github.com/alisoam/public.git $temp_dir

pushd $temp_dir
source install_local.bash
popd
