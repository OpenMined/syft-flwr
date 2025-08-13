# RPC Message Flow in Syft-FLWR:

1. Server (grid.py): `flower_message_to_bytes() → rpc.send() → filesystem`
2. Client (flower_client.py): `Filesystem → bytes_to_flower_message() → Flower processing`
3. Response (flower_client.py): `Process → _handle_normal_message() → response`

## Filesystem
"Filesystem" in SyftBox context means SyftBox's peer-to-peer file synchronization network that enables distributed communication without direct connections between parties.

1. Server Side (`grid.py`):
`future = rpc.send(url=url, body=msg_bytes, client=self._client)`
2. `rpc.send()` (`rpc.py`): `syft_request.dump(req_path)`  # Writes to local filesystem
3. File Location (`rpc.py`):
```python
local_path = syft_request.url.to_local_path(client.workspace.datasites)
req_path = local_path / f"{syft_request.id}.request"
```
Concrete Example:

- URL: `syft://user@domain.com/app_data/flwr/flwr_app_name/rpc/messages`
- File Path:
`~/SyftBox/datasites/user@domain.com/app_data/flwr/app_name/rpc/messages/{uuid}.request`

### Request / Response Flow
1. Write: Server creates `.request` file in target user's datasite directory
2. Sync: SyftBox daemon (installed with the SyftBox client via https://syftbox.net) syncs file across network to recipient's machine
3. Watch: Recipient's `SyftEvents` watches filesystem and triggers on new `.request` files
4. Process: Handler processes request and writes `.response` file
5. Sync Back: Response file syncs back to sender
