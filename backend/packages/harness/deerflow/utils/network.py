"""Thread-safe network utilities."""

import os
import socket
import threading
import urllib.request
from contextlib import contextmanager


_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
_NO_PROXY_ENV_KEYS = ("NO_PROXY", "no_proxy")


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _proxy_env_present() -> bool:
    return any(os.getenv(key, "").strip() for key in _PROXY_ENV_KEYS)


def deerflow_network_mode() -> str:
    """Return the effective DeerFlow network policy.

    Modes:
    - direct: default. Remove proxy env vars and install an empty urllib ProxyHandler.
    - preserve/proxy: keep shell/macOS proxy settings.
    - auto: preserve explicit proxy env vars, otherwise direct. Kept only for diagnostics.

    `DEERFLOW_ALLOW_PROXY=1` is kept as a legacy alias for preserve/proxy.
    """
    if _truthy(os.getenv("DEERFLOW_ALLOW_PROXY")):
        return "preserve"
    raw = os.getenv("DEERFLOW_NETWORK_MODE", "direct").strip().lower()
    aliases = {
        "proxy": "preserve",
        "proxies": "preserve",
        "preserve_proxy": "preserve",
        "allow_proxy": "preserve",
        "bypass": "direct",
        "no_proxy": "direct",
        "force_direct": "direct",
    }
    mode = aliases.get(raw, raw)
    if mode not in {"auto", "preserve", "direct"}:
        mode = "direct"
    if mode == "auto":
        return "preserve" if _proxy_env_present() else "direct"
    return mode


def api_network_uses_proxy() -> bool:
    return deerflow_network_mode() == "preserve"


def build_api_url_opener() -> urllib.request.OpenerDirector:
    """Build a urllib opener matching the active DeerFlow API network policy."""
    if api_network_uses_proxy():
        return urllib.request.build_opener()
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def force_direct_api_network() -> None:
    """Apply DeerFlow's API network policy.

    The default behavior forces direct networking to keep model/API calls off
    Clash/Clash Pro system proxies. Set `DEERFLOW_NETWORK_MODE=preserve` only
    for explicit diagnostics or provider-router proxy tests.
    """

    if api_network_uses_proxy():
        for key in _NO_PROXY_ENV_KEYS:
            if os.getenv(key, "").strip() == "*":
                os.environ.pop(key, None)
        urllib.request.install_opener(build_api_url_opener())
        return

    for key in _PROXY_ENV_KEYS:
        os.environ.pop(key, None)
    for key in _NO_PROXY_ENV_KEYS:
        os.environ[key] = "*"
    urllib.request.install_opener(build_api_url_opener())


class PortAllocator:
    """Thread-safe port allocator that prevents port conflicts in concurrent environments.

    This class maintains a set of reserved ports and uses a lock to ensure that
    port allocation is atomic. Once a port is allocated, it remains reserved until
    explicitly released.

    Usage:
        allocator = PortAllocator()

        # Option 1: Manual allocation and release
        port = allocator.allocate(start_port=8080)
        try:
            # Use the port...
        finally:
            allocator.release(port)

        # Option 2: Context manager (recommended)
        with allocator.allocate_context(start_port=8080) as port:
            # Use the port...
            # Port is automatically released when exiting the context
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._reserved_ports: set[int] = set()

    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available for binding.

        Args:
            port: The port number to check.

        Returns:
            True if the port is available, False otherwise.
        """
        if port in self._reserved_ports:
            return False

        # Bind to 0.0.0.0 (wildcard) rather than localhost so that the check
        # mirrors exactly what Docker does.  Docker binds to 0.0.0.0:PORT;
        # checking only 127.0.0.1 can falsely report a port as available even
        # when Docker already occupies it on the wildcard address.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return True
            except OSError:
                return False

    def allocate(self, start_port: int = 8080, max_range: int = 100) -> int:
        """Allocate an available port in a thread-safe manner.

        This method is thread-safe. It finds an available port, marks it as reserved,
        and returns it. The port remains reserved until release() is called.

        Args:
            start_port: The port number to start searching from.
            max_range: Maximum number of ports to search.

        Returns:
            An available port number.

        Raises:
            RuntimeError: If no available port is found in the specified range.
        """
        with self._lock:
            for port in range(start_port, start_port + max_range):
                if self._is_port_available(port):
                    self._reserved_ports.add(port)
                    return port

            raise RuntimeError(f"No available port found in range {start_port}-{start_port + max_range}")

    def release(self, port: int) -> None:
        """Release a previously allocated port.

        Args:
            port: The port number to release.
        """
        with self._lock:
            self._reserved_ports.discard(port)

    @contextmanager
    def allocate_context(self, start_port: int = 8080, max_range: int = 100):
        """Context manager for port allocation with automatic release.

        Args:
            start_port: The port number to start searching from.
            max_range: Maximum number of ports to search.

        Yields:
            An available port number.
        """
        port = self.allocate(start_port, max_range)
        try:
            yield port
        finally:
            self.release(port)


# Global port allocator instance for shared use across the application
_global_port_allocator = PortAllocator()


def get_free_port(start_port: int = 8080, max_range: int = 100) -> int:
    """Get a free port in a thread-safe manner.

    This function uses a global port allocator to ensure that concurrent calls
    don't return the same port. The port is marked as reserved until release_port()
    is called.

    Args:
        start_port: The port number to start searching from.
        max_range: Maximum number of ports to search.

    Returns:
        An available port number.

    Raises:
        RuntimeError: If no available port is found in the specified range.
    """
    return _global_port_allocator.allocate(start_port, max_range)


def release_port(port: int) -> None:
    """Release a previously allocated port.

    Args:
        port: The port number to release.
    """
    _global_port_allocator.release(port)
