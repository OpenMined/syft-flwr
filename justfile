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
alias rcs := run-client-with-syftbox
alias rss := run-server-with-syftbox

# ---------------------------------------------------------------------------------------------------------------------

@default:
    just --list

[group('utils')]
run-jupyter jupyter_args="":
    # uv sync

    uv run --frozen --with "jupyterlab" \
        jupyter lab {{ jupyter_args }}

# sb_conf_path: path to the SyftBox Config file
[group('client')]
run-client sb_conf_path="":
    uv run python -m examples.basic.client_syft --sb_conf_path "{{ sb_conf_path }}"

[group('client')]
run-client-with-syftbox flower-toml-path="" sb-conf-path="":
    uv run python -m src.syft_flwr.runner --flower-toml-path "{{ flower-toml-path }}" --sb-conf-path "{{ sb-conf-path }}" --client

# sb_conf_path: path to the SyftBox Config file
[group('server')]
run-server sb_conf_path="":
    uv run python -m examples.basic.server_syft --sb_conf_path "{{ sb_conf_path }}"

[group('server')]
run-server-with-syftbox flower-toml-path="" sb-conf-path="":
    uv run python -m src.syft_flwr.runner --flower-toml-path "{{ flower-toml-path }}" --sb-conf-path "{{ sb-conf-path }}" --aggregator

[group('test')]
test:
    uv run pytest tests/e2e/basic_test.py