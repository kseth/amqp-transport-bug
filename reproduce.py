#!/usr/bin/env python3
"""Minimal reproduction for https://github.com/Azure/azure-sdk-for-python/issues/45394

Azure ServiceBus async client fails with:
    [Errno 22] Invalid argument Error condition: amqp:socket-error
when running inside containers (Docker / Kubernetes Kind), while the
synchronous client works fine in the same environment.

Expects a session-enabled queue. A random session ID is generated per run
so that each invocation is isolated.

Usage:
    export CONNECTION_STRING="Endpoint=sb://..."
    export QUEUE_NAME="test-queue"          # must have sessions enabled
    uv run reproduce.py
"""

import asyncio
import os
import platform
import socket
import sys
import traceback

import uuid

from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient as AsyncServiceBusClient

NUM_MESSAGES = int(os.environ.get("NUM_MESSAGES", "1"))
SESSION_ID = f"test-{uuid.uuid4().hex[:8]}"


def env():
    conn_str = os.environ.get("CONNECTION_STRING", "")
    queue_name = os.environ.get("QUEUE_NAME", "")
    if not conn_str or not queue_name:
        print("ERROR: CONNECTION_STRING and QUEUE_NAME must be set")
        sys.exit(1)
    return conn_str, queue_name


def print_env_info():
    import azure.servicebus as sb

    print("=" * 60)
    print("ENVIRONMENT")
    print("=" * 60)
    print(f"  Python          : {sys.version}")
    print(f"  azure-servicebus: {sb.__version__}")
    print(f"  Platform        : {sys.platform}")
    print(f"  Architecture    : {platform.machine()}")
    print(f"  Hostname        : {socket.gethostname()}")
    in_container = os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")
    print(f"  In container    : {in_container}")
    print(f"  Messages/test   : {NUM_MESSAGES}")
    print(f"  Session ID      : {SESSION_ID}")
    print()


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_sync(conn_str, queue_name):
    """Sync send+receive — expected to work everywhere."""
    print(f"--- Test 1: sync send/receive x{NUM_MESSAGES} (pure-python AMQP) ---")
    try:
        with ServiceBusClient.from_connection_string(conn_str) as client:
            sender = client.get_queue_sender(queue_name)
            receiver = client.get_queue_receiver(
                queue_name, session_id=SESSION_ID, max_wait_time=5
            )
            with sender, receiver:
                for i in range(NUM_MESSAGES):
                    body = f"sync-{i}"
                    msg = ServiceBusMessage(body)
                    msg.session_id = SESSION_ID
                    sender.send_messages(msg)
                    msgs = receiver.receive_messages(
                        max_message_count=1, max_wait_time=5
                    )
                    if not msgs:
                        raise RuntimeError(f"no message received for '{body}'")
                    received = str(msgs[0])
                    if received != body:
                        raise RuntimeError(
                            f"body mismatch: sent '{body}', got '{received}'"
                        )
                    receiver.complete_message(msgs[0])
                    print(f"  [{i + 1}/{NUM_MESSAGES}] ok")
        print("RESULT: PASS\n")
        return True
    except Exception as exc:
        print(f"RESULT: FAIL — {exc}\n")
        traceback.print_exc()
        return False


async def test_async(conn_str, queue_name):
    """Async send+receive — triggers the bug in containers."""
    print(f"--- Test 2: async send/receive x{NUM_MESSAGES} (pure-python AMQP) ---")
    try:
        async with AsyncServiceBusClient.from_connection_string(conn_str) as client:
            sender = client.get_queue_sender(queue_name)
            receiver = client.get_queue_receiver(
                queue_name, session_id=SESSION_ID, max_wait_time=5
            )
            async with sender, receiver:
                for i in range(NUM_MESSAGES):
                    body = f"async-{i}"
                    msg = ServiceBusMessage(body)
                    msg.session_id = SESSION_ID
                    await sender.send_messages(msg)
                    msgs = await receiver.receive_messages(
                        max_message_count=1, max_wait_time=5
                    )
                    if not msgs:
                        raise RuntimeError(f"no message received for '{body}'")
                    received = str(msgs[0])
                    if received != body:
                        raise RuntimeError(
                            f"body mismatch: sent '{body}', got '{received}'"
                        )
                    await receiver.complete_message(msgs[0])
                    print(f"  [{i + 1}/{NUM_MESSAGES}] ok")
        print("RESULT: PASS\n")
        return True
    except Exception as exc:
        print(f"RESULT: FAIL — {exc}\n")
        traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    conn_str, queue_name = env()
    print_env_info()

    results = {}

    results["sync"] = test_sync(conn_str, queue_name)
    results["async"] = asyncio.run(test_async(conn_str, queue_name))

    # --- summary ---
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results.items():
        tag = "PASS" if passed else "FAIL"
        print(f"  {name:20s} {tag}")

    if results["sync"] and not results["async"]:
        print()
        print(">>> BUG CONFIRMED: sync works, async fails <<<")
        print(
            ">>> Reproduces https://github.com/Azure/azure-sdk-for-python/issues/45394"
        )
        sys.exit(1)
    elif not results["sync"]:
        print()
        print(
            "Sync also failed — likely a connectivity / credential issue, not the bug."
        )
        sys.exit(2)
    else:
        print()
        print("Bug NOT reproduced in this environment.")
        sys.exit(0)


if __name__ == "__main__":
    main()
