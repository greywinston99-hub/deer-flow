from __future__ import annotations

import os

from deerflow.utils.network import api_network_uses_proxy, deerflow_network_mode, force_direct_api_network


def _clear_network_env(monkeypatch) -> None:
    for key in (
        "DEERFLOW_ALLOW_PROXY",
        "DEERFLOW_NETWORK_MODE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
    ):
        monkeypatch.delenv(key, raising=False)


def test_network_policy_default_direct_clears_explicit_proxy(monkeypatch) -> None:
    _clear_network_env(monkeypatch)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7890")
    monkeypatch.setenv("NO_PROXY", "*")

    assert deerflow_network_mode() == "direct"
    assert api_network_uses_proxy() is False

    force_direct_api_network()

    assert "HTTPS_PROXY" not in os.environ
    assert os.environ["NO_PROXY"] == "*"


def test_network_policy_preserve_mode_keeps_explicit_proxy(monkeypatch) -> None:
    _clear_network_env(monkeypatch)
    monkeypatch.setenv("DEERFLOW_NETWORK_MODE", "preserve")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7890")
    monkeypatch.setenv("NO_PROXY", "*")

    assert deerflow_network_mode() == "preserve"
    assert api_network_uses_proxy() is True

    force_direct_api_network()

    assert os.environ["HTTPS_PROXY"] == "http://127.0.0.1:7890"
    assert os.environ.get("NO_PROXY") is None


def test_network_policy_direct_mode_clears_proxy(monkeypatch) -> None:
    _clear_network_env(monkeypatch)
    monkeypatch.setenv("DEERFLOW_NETWORK_MODE", "direct")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7890")

    assert deerflow_network_mode() == "direct"
    assert api_network_uses_proxy() is False

    force_direct_api_network()

    assert "HTTPS_PROXY" not in os.environ
    assert os.environ["NO_PROXY"] == "*"


def test_network_policy_legacy_allow_proxy_alias(monkeypatch) -> None:
    _clear_network_env(monkeypatch)
    monkeypatch.setenv("DEERFLOW_ALLOW_PROXY", "1")
    monkeypatch.setenv("DEERFLOW_NETWORK_MODE", "direct")

    assert deerflow_network_mode() == "preserve"
    assert api_network_uses_proxy() is True
