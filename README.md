# Azure ServiceBus Async AMQP Socket Bug

Minimal reproduction for [azure-sdk-for-python#45394](https://github.com/Azure/azure-sdk-for-python/issues/45394).

The async `ServiceBusClient` fails with `[Errno 22] Invalid argument` (socket error)
when running inside Docker on macOS, while the synchronous client works fine in the
same container.

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Docker
- An Azure Service Bus namespace with a **session-enabled** queue. Create one with `az`:

```bash
az servicebus namespace create -n my-sb-ns -g my-rg --sku Standard
az servicebus queue create -n test-queue --namespace-name my-sb-ns -g my-rg \
  --enable-session true
# grab the connection string:
az servicebus namespace authorization-rule keys list \
  --namespace-name my-sb-ns -g my-rg \
  --name RootManageSharedAccessKey \
  --query primaryConnectionString -o tsv
```

## Run — native

```bash
uv venv
uv pip install -r requirements.txt
CONNECTION_STRING="Endpoint=sb://..." QUEUE_NAME="test-queue" uv run reproduce.py
```

Expected: all tests pass (bug does **not** reproduce outside containers).

## Run — Docker

```bash
make docker-build

# reproduce the bug (no patch):
CONNECTION_STRING="..." QUEUE_NAME="..." make docker-run
```

Expected: sync passes, async fails with `[Errno 22] Invalid argument`.

## Patches

Two patches are available via the `APPLY_PATCH` environment variable.

### `APPLY_PATCH=1` — resilient setsockopt

Wraps every `setsockopt` call in `_set_socket_options` with a try/except that
catches `EINVAL` and `ENOPROTOOPT`, logging the skipped option instead of crashing.
This is the safer, more general fix — it handles any unsupported socket option.

```bash
CONNECTION_STRING="..." QUEUE_NAME="..." APPLY_PATCH=1 make docker-run
```

### `APPLY_PATCH=2` — remove TCP_MAXSEG

Removes `TCP_MAXSEG` from the SDK's `KNOWN_TCP_OPTS` set before any client is
created. This is the more targeted fix — it prevents the specific option that
fails from ever being set.

```bash
CONNECTION_STRING="..." QUEUE_NAME="..." APPLY_PATCH=2 make docker-run
```

### Results

| | Native | Docker (no patch) | Docker `APPLY_PATCH=1` | Docker `APPLY_PATCH=2` |
|---|---|---|---|---|
| sync | PASS | PASS | PASS | PASS |
| async | PASS | **FAIL** | PASS | PASS |

## Cleanup

```bash
make clean      # removes docker image
```
