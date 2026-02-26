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
import errno
import os
import platform
import socket
import sys
import traceback

import uuid

from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient as AsyncServiceBusClient
from azure.servicebus._pyamqp._transport import (
    SOL_TCP,
    _AbstractTransport,
)
from azure.servicebus._pyamqp.aio._transport_async import AsyncTransport

SESSION_ID = f"test-{uuid.uuid4().hex[:8]}"
APPLY_PATCH = os.environ.get("APPLY_PATCH", "").lower() in ("1", "true", "yes")


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
    print(f"  Session ID      : {SESSION_ID}")
    print(f"  Patch applied   : {APPLY_PATCH}")
    print()


# ---------------------------------------------------------------------------
# Monkey-patch: make setsockopt resilient to EINVAL / ENOPROTOOPT
# ---------------------------------------------------------------------------


def _resilient_setsockopt(sock, opt, val):
    try:
        sock.setsockopt(SOL_TCP, opt, val)
    except OSError as e:
        if e.errno in (errno.EINVAL, errno.ENOPROTOOPT):
            print(f"  [patch] skipping setsockopt({opt}, {val}): {e}")
        else:
            raise


def _patched_sync_set_socket_options(self, socket_settings):
    tcp_opts = self._get_tcp_socket_defaults(self.sock)
    if socket_settings:
        tcp_opts.update(socket_settings)
    for opt, val in tcp_opts.items():
        _resilient_setsockopt(self.sock, opt, val)


def _patched_async_set_socket_options(self, sock, socket_settings):
    tcp_opts = self._get_tcp_socket_defaults(sock)
    if socket_settings:
        tcp_opts.update(socket_settings)
    for opt, val in tcp_opts.items():
        _resilient_setsockopt(sock, opt, val)


if APPLY_PATCH:
    _AbstractTransport._set_socket_options = _patched_sync_set_socket_options
    AsyncTransport._set_socket_options = _patched_async_set_socket_options


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_sync(conn_str, queue_name):
    """Sync send+receive — expected to work everywhere."""
    print("--- Test 1: sync send/receive (pure-python AMQP) ---")
    try:
        body = f"sync-{SESSION_ID}"
        with ServiceBusClient.from_connection_string(conn_str) as client:
            sender = client.get_queue_sender(queue_name)
            receiver = client.get_queue_receiver(
                queue_name, session_id=SESSION_ID, max_wait_time=5
            )
            with sender, receiver:
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
        print("RESULT: PASS\n")
        return True
    except Exception as exc:
        print(f"RESULT: FAIL — {exc}\n")
        traceback.print_exc()
        return False


async def test_async(conn_str, queue_name):
    """Async send+receive — triggers the bug in containers."""
    print("--- Test 2: async send/receive (pure-python AMQP) ---")
    try:
        body = f"async-{SESSION_ID}"
        async with AsyncServiceBusClient.from_connection_string(conn_str) as client:
            sender = client.get_queue_sender(queue_name)
            receiver = client.get_queue_receiver(
                queue_name, session_id=SESSION_ID, max_wait_time=5
            )
            async with sender, receiver:
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

    sync_ok = test_sync(conn_str, queue_name)
    async_ok = asyncio.run(test_async(conn_str, queue_name))

    sys.exit(0 if sync_ok and async_ok else 1)


if __name__ == "__main__":
    main()
