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

# reproduce the bug:
CONNECTION_STRING="Endpoint=sb://..." QUEUE_NAME="test-queue" make docker-run

# verify the fix:
CONNECTION_STRING="Endpoint=sb://..." QUEUE_NAME="test-queue" APPLY_PATCH=1 make docker-run
```

## What the tests do

| # | Test | Transport | Expected in container |
|---|------|-----------|----------------------|
| 1 | sync send/receive | pure-python AMQP | PASS |
| 2 | async send/receive | pure-python AMQP | **FAIL** |

Set `APPLY_PATCH=1` to apply a monkey-patch that wraps `setsockopt` calls
with error handling for `EINVAL`/`ENOPROTOOPT`. With the patch, both tests pass.

## Cleanup

```bash
make clean      # removes docker image
```
