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
alias rc := run-client
alias rs := run-server
alias rsp := run-server-pytorch
alias rcp := run-client-pytorch

# ---------------------------------------------------------------------------------------------------------------------

@default:
    just --list

[group('utils')]
run-jupyter jupyter_args="":
    # uv sync

    uv run --frozen --with "jupyterlab" \
        jupyter lab {{ jupyter_args }}

[group('client')]
run-client:
    uv run python -m examples.basic.client_syft_event

[group('client')]
run-client-pytorch:
    uv run python -m examples.quickstart-pytorch-syft.pytorch.client_app

[group('server')]
run-server:
    uv run python -m examples.basic.server

[group('server')]
run-server-pytorch:
    uv run python -m examples.quickstart-pytorch-syft.pytorch.server_app

[group('test')]
test:
    uv run pytest tests/e2e/basic_test.py