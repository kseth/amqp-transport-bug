# Azure ServiceBus Async AMQP Socket Bug

Minimal reproduction for [azure-sdk-for-python#45394](https://github.com/Azure/azure-sdk-for-python/issues/45394).

The async `ServiceBusClient` fails with `[Errno 22] Invalid argument` (socket error)
when running inside containers, while the synchronous client works fine in the same
environment.

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
CONNECTION_STRING="Endpoint=sb://..." QUEUE_NAME="test-queue" make docker
```

Expected: sync passes, async fails — **bug confirmed**.

## What the tests do

| # | Test | Transport | Expected in container |
|---|------|-----------|----------------------|
| 1 | sync send/receive x25 | pure-python AMQP | PASS |
| 2 | async send/receive x25 | pure-python AMQP | **FAIL** |

## Cleanup

```bash
make clean      # removes docker image
```
