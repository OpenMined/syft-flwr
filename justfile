# Guidelines for new commands
# - Start with a verb
# - Keep it short (max. 3 words in a command)
# - Group commands by context. Include group name in the command name.
# - Mark things private that are util functions with [private] or _var
# - Don't over-engineer, keep it simple.
# - Don't break existing commands
# - Run just --fmt --unstable after adding new commands

set dotenv-load := true

# ---------------------------------------------------------------------------------------------------------------------
# Private vars

_red := '\033[1;31m'
_cyan := '\033[1;36m'
_green := '\033[1;32m'
_yellow := '\033[1;33m'
_nc := '\033[0m'

# ---------------------------------------------------------------------------------------------------------------------
# Aliases

alias rj := run-jupyter

# ---------------------------------------------------------------------------------------------------------------------

@default:
    just --list


dump-config email:
    #!/bin/bash
    mkdir -p .config
    CONFIG_NAME={{email}}.json
    jq '.email = "{{email}}"' ~/.syftbox/config.json > .config/$CONFIG_NAME
    echo $(realpath .config/$CONFIG_NAME)

run-server project email:
    #!/bin/bash
    export SYFTBOX_CLIENT_CONFIG_PATH=$(just dump-config {{email}})
    echo $SYFTBOX_CLIENT_CONFIG_PATH

    cd examples/{{project}}
    uv sync
    uv run main.py

run-client project email:
    #!/bin/bash
    export SYFTBOX_CLIENT_CONFIG_PATH=$(just dump-config {{email}})
    echo $SYFTBOX_CLIENT_CONFIG_PATH

    cd examples/{{project}}
    uv sync
    uv run main.py

[group('utils')]
run-jupyter jupyter_args="":
    # uv sync

    uv run --frozen --with "jupyterlab" \
        jupyter lab {{ jupyter_args }}
