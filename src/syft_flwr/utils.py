from flwr.common import Context
from flwr.common.record import RecordSet
from flwr.common.typing import UserConfig


def create_empty_context(run_id: int) -> Context:
    return Context(
        run_id=run_id,
        node_id=0,
        node_config=UserConfig(),
        state=RecordSet(),
        run_config=UserConfig(),
    )
