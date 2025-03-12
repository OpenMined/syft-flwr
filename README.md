# flwr

## Run Flower with the Deployment Engine using `GrpcDriver`

- [Source tutorial](https://flower.ai/docs/framework/how-to-run-flower-with-deployment-engine.html)

Steps and inner working:

1. Setting up a project
```bash
flwr new my-project --framework PyTorch --username flower
cd my-project
uv pip install -e .
```

2. If run `flower-superlink --insecure` which `run_superlink`, that does
	- calls `run_exec_api_grpc` that returns `exec_server: grpc.Server`
	- calls `run_serverappio_api_grpc()` that returns a `serverappio_server: grpc.Server`
	- start Fleet API where `fleet_api_type = 'grpc-rere'` and calls `_run_fleet_api_grpc_rere()` that returns `fleet_server: grpc.Server`
	- spawning `_flwr_scheduler` thread
	- calls `_flwr_scheduler` in a thread

3. Then launch two `SuperNodes` and connect them to the `SuperLink`. Run
```bash
flflower-supernode \
     --insecure \
     --superlink 127.0.0.1:9092 \
     --clientappio-api-address 127.0.0.1:9094 \
     --node-config "partition-id=0 num-partitions=2"
```
and
```bash
 flflower-supernode \
     --insecure \
     --superlink 127.0.0.1:9092 \
     --clientappio-api-address 127.0.0.1:9095 \
     --node-config "partition-id=1 num-partitions=2"
```
in 2 different terminals, which calls `start_client_internal`, which does
- does `_clientappio_grpc_server, clientappio_servicer = run_clientappio_api_grpc(...)`
- then it calls `_init_connection` that calls `grpc_request_response` that creates primitive methods (e.g. `receive, send, create_node, delete_node, get_run, get_fab`) for request / response-based interaction with a server using gRPC
- the client also has `state: InMemoryNodeState`


4. Then append
```toml
[tool.flwr.federations.local-deployment]
address = "127.0.0.1:9093"
insecure = true
```
to `pyproject.toml` to define a federation and run your Flower App through the federation using
```bash
flwr run . local-deployment --stream
```
Running `flwr run . local-deployment --stream` will actually start
- the `flwr-serverapp` process in the `superlink` and the `flwr run` processes with stack trace `_run_flwr_command` -> `flwr_serverapp()` -> `run_serverapp()` -> Initializing the `GrpcDriver`
- start `flwr-clientapp` subprocess that runs `_run_flwr_clientapp`, which calls `flwr_clientapp` -> `run_clientapp` that creates the `ClientApp` class and then runs the client side's computation with `reply_message: Message = client_app(message=message, context=context)` (by invoking `ClientApp.__call__` function). Client then send the `reply_message` with with `grpc_request_response.send`
