#!/bin/bash

ENV=$( ( [ "command -v pyenv" ] && echo PYENV_VERSION=system pyenv exec ) || echo )
eval $ENV python3 sync.py sync_host
