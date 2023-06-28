#!/bin/bash

PYTHON_VERSION=3.11

# activate pyenv to use specific python versoin
if [ -e "/home/linuxbrew/.linuxbrew/bin/brew" ]; then
    eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
fi

if [ -x "$(command -v pyenv)" ]; then
    export PYENV_ROOT="$HOME/.pyenv"
    command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"

    if [ -x "$(command -v pyenv-virtualenvwrapper)" ]; then
        export PYENV_VIRTUALENVWRAPPER_PREFER_PYVENV="true"
        pyenv virtualenvwrapper
    fi
fi

ENV=$( ( [ "command -v pyenv" ] && echo PYENV_VERSION=${PYTHON_VERSION} pyenv exec ) || echo )

pushd $(dirname -- "$0")

eval $ENV pip3 install -r config/requirements.txt
eval $ENV python3 config/sync.py sync_host

popd
