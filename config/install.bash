#!/bin/bash
#
pushd $(dirname -- "$0")

pip3 install -r config/requirements.txt
python3 config/sync.py sync_host

popd
