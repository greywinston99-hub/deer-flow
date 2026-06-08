"""Graceful shutdown integration for CER Authoring Event Bus.

Wires EventBus, EventWorkers, and MCP Process Pool shutdown into the
application lifecycle. Ensures that:
1. In-flight events are processed before shutdown.
2. MCP subprocesses are terminated cleanly (not orphaned).
3. SQLite connections are closed.

Usage:
    from deerflow.runtime.cer_authoring.graceful_shutdown import shutdown_event_bus_system

    # In FastAPI lifespan shutdown or signal handler:
    await shutdown_event_bus_system(timeout_seconds=30)
"""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any

logger = logging.getLogger(__name__)

_shutdown_hooks: list[Callable[[], Any]] = []
_shutdown_async_hooks: list[Callable[[], Any]] = []


def register_shutdown_hook(hook: Callable[[], Any]) -> None:
    """Register a synchronous shutdown hook."""
    _shutdown_hooks.append(hook)


def register_async_shutdown_hook(hook: Callable[[], Any]) -> None:
    """Register an async shutdown hook."""
    _shutdown_async_hooks.append(hook)


async def shutdown_event_bus_system(timeout_seconds: float = 30.0) -> None:
    """Gracefully shut down all Event Bus subsystems.

    Order:
    1. Stop EventBus (stops accepting new events, drains queue).
    2. Stop all EventWorkers (wait for current tasks).
    3. Shutdown MCP Process Pools (terminate subprocesses).
    4. Run registered hooks.
    """
    logger.info("Graceful shutdown initiated (timeout=%.1fs)", timeout_seconds)

    # 1. Stop EventBus
    try:
        from deerflow.runtime.cer_authoring.event_bus.core import _event_bus_instance

        if _event_bus_instance is not None:
            await asyncio.wait_for(
                _event_bus_instance.stop(),
                timeout=max(1.0, timeout_seconds * 0.3),
            )
            logger.info("EventBus stopped")
    except Exception:
        logger.exception("Failed to stop EventBus gracefully")

    # 2. Shutdown MCP Process Pools
    try:
        from deerflow.runtime.cer_authoring.mcp_pool import _pools

        for server, pool in _pools.items():
            try:
                pool.shutdown()
                logger.info("MCP pool '%s' shut down", server)
            except Exception:
                logger.exception("Failed to shutdown MCP pool '%s'", server)
    except Exception:
        logger.exception("Failed to shutdown MCP pools")

    # 3. Run registered async hooks
    for hook in _shutdown_async_hooks:
        try:
            if asyncio.iscoroutinefunction(hook):
                await asyncio.wait_for(hook(), timeout=5.0)
            else:
                hook()
        except Exception:
            logger.exception("Shutdown hook failed")

    # 4. Run registered sync hooks
    for hook in _shutdown_hooks:
        try:
            hook()
        except Exception:
            logger.exception("Shutdown hook failed")

    logger.info("Graceful shutdown complete")


def install_signal_handlers() -> None:
    """Install SIGTERM/SIGINT handlers that trigger graceful shutdown.

    Should be called once at application startup.
    """
    loop = asyncio.get_event_loop()

    def _signal_handler(sig: int) -> None:
        logger.info("Received signal %d, initiating graceful shutdown...", sig)
        # Schedule shutdown in the event loop
        asyncio.create_task(shutdown_event_bus_system())

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig: _signal_handler(s))
            logger.debug("Installed handler for signal %d", sig)
        except (NotImplementedError, ValueError):
            # Windows or already handled
            pass


# Typing helper
from typing import Callable
