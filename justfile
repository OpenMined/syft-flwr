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

dump-sim-config email:
    #!/bin/bash
    mkdir -p .sim/.config
    mkdir -p .sim/SyftBox
    CONFIG_NAME={{email}}.json
    cat > .sim/.config/$CONFIG_NAME <<EOF
    {
        "data_dir": "$(realpath .sim/SyftBox)",
        "server_url": "https://syftbox.openmined.org/",
        "client_url": "http://127.0.0.1:8080/",
        "email": "{{email}}",
        "token": "0",
        "access_token": "",
        "client_timeout": 5.0
    }
    EOF
    echo $(realpath .sim/.config/$CONFIG_NAME)

run-sim-client project_path email data_dir:
    #!/bin/bash
    export SYFTBOX_CLIENT_CONFIG_PATH=$(just dump-sim-config {{email}})
    echo $SYFTBOX_CLIENT_CONFIG_PATH
    export DATA_DIR=$(realpath {{data_dir}})

    cd {{project_path}}
    uv sync
    uv run main.py

run-sim-server project_path email:
    #!/bin/bash
    export SYFTBOX_CLIENT_CONFIG_PATH=$(just dump-sim-config {{email}})
    echo $SYFTBOX_CLIENT_CONFIG_PATH

    cd {{project_path}}
    uv sync
    uv run main.py

reset-sim:
    #!/bin/bash
    rm -rf .sim

# Ref: https://github.com/adap/flower/blob/main/examples/embedded-devices/README.md
setup-embedded-devices:
    #!/bin/bash
    cd examples/embedded-devices
    uv sync
    if [ ! -d "datasets" ]; then
        uv run generate_dataset.py --num-supernodes=2
    else
        echo "${_yellow}datasets directory already exists, skipping dataset generation${_nc}"
    fi
