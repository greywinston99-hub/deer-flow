"""Check the local DeerFlow/Claude Code LLM stack.

This script is intentionally narrow: it verifies that the production LLM path
uses only DeepSeek, Kimi API, and MiniMax M3, that DeerFlow defaults to direct networking, and
that optional live checks fail with a clear network/model diagnosis.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

import httpx
from langchain_core.messages import HumanMessage

from deerflow.config.app_config import AppConfig
from deerflow.models.factory import create_chat_model
from deerflow.utils.network import deerflow_network_mode, force_direct_api_network


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config.yaml"
CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"
ROUTER_ENV = Path.home() / ".claude" / "provider-router.env"
ROUTER_BASE_URL = "http://127.0.0.1:18765"

ALLOWED_DEERFLOW_MODELS = {
    "kimi-k2.6": ("kimi-k2.6", "https://api.moonshot.cn/v1"),
    "kimi-k2.6-api": ("kimi-k2.6", "https://api.moonshot.cn/v1"),
    "deepseek-v4-pro": ("deepseek-v4-pro", "https://api.deepseek.com/v1"),
}
FORBIDDEN_RUNTIME_MODEL_STRINGS = ("openai", "gpt-", "claude-sonnet", "claude-opus", "minimax", "kimi-for-coding")


def _result(name: str, status: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"check": name, "status": status, "details": details or {}}


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def check_deerflow_config() -> list[dict[str, Any]]:
    config = AppConfig.from_file(str(CONFIG_PATH))
    checks: list[dict[str, Any]] = []
    active = {model.name: model for model in config.models}

    unexpected = sorted(set(active) - set(ALLOWED_DEERFLOW_MODELS))
    if unexpected:
        checks.append(_result("deerflow.allowed_model_names", "FAIL", {"unexpected": unexpected}))
    else:
        checks.append(_result("deerflow.allowed_model_names", "PASS", {"models": sorted(active)}))

    mismatches = []
    for name, (expected_model, expected_base) in ALLOWED_DEERFLOW_MODELS.items():
        model = active.get(name)
        if model is None:
            mismatches.append({"name": name, "issue": "missing"})
            continue
        actual_base = getattr(model, "api_base", None) or getattr(model, "anthropic_api_url", None)
        if model.model != expected_model or actual_base != expected_base:
            mismatches.append(
                {
                    "name": name,
                    "model": model.model,
                    "expected_model": expected_model,
                    "base": actual_base,
                    "expected_base": expected_base,
                }
            )
    checks.append(
        _result(
            "deerflow.model_targets",
            "PASS" if not mismatches else "FAIL",
            {"mismatches": mismatches},
        )
    )

    active_runtime_text = json.dumps(
        [
            {
                "name": model.name,
                "use": model.use,
                "model": model.model,
                "api_base": getattr(model, "api_base", None),
                "anthropic_api_url": getattr(model, "anthropic_api_url", None),
            }
            for model in config.models
        ],
        ensure_ascii=False,
    ).lower()
    forbidden_hits = sorted({token for token in FORBIDDEN_RUNTIME_MODEL_STRINGS if token in active_runtime_text})
    checks.append(
        _result(
            "deerflow.no_forbidden_runtime_model_strings",
            "PASS" if not forbidden_hits else "FAIL",
            {"hits": forbidden_hits},
        )
    )
    return checks


def check_deerflow_network_policy() -> list[dict[str, Any]]:
    before = {key: os.environ.get(key) for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "no_proxy")}
    mode_before = deerflow_network_mode()
    force_direct_api_network()
    after = {key: os.environ.get(key) for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "no_proxy")}
    proxy_clean = not any(after.get(key) for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"))
    no_proxy_forced = after.get("NO_PROXY") == "*" and after.get("no_proxy") == "*"
    return [
        _result(
            "deerflow.default_network_mode",
            "PASS" if mode_before == "direct" else "FAIL",
            {"mode": mode_before, "before": before, "after": after},
        ),
        _result(
            "deerflow.proxy_env_cleared",
            "PASS" if proxy_clean and no_proxy_forced else "FAIL",
            {"after": after},
        ),
    ]


def check_claude_config() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    settings = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8"))
    env = settings.get("env") or {}
    router_env = _load_env_file(ROUTER_ENV)

    expected = {
        "ANTHROPIC_BASE_URL": "http://127.0.0.1:18765/anthropic",
        "ANTHROPIC_MODEL": "deepseek-v4-pro[1m]",
        "ANTHROPIC_SMALL_FAST_MODEL": "MiniMax-M3",
        "CLAUDE_CODE_SUBAGENT_MODEL": "MiniMax-M3",
    }
    mismatches = {key: {"actual": env.get(key), "expected": value} for key, value in expected.items() if env.get(key) != value}
    checks.append(_result("claude.settings_model_route", "PASS" if not mismatches else "FAIL", {"mismatches": mismatches}))

    forbidden_env = sorted(key for key in router_env if key.startswith("KIMI_CODE") or key.startswith("OPENAI"))
    checks.append(
        _result(
            "claude.router_env_no_kimi_code",
            "PASS" if not forbidden_env else "FAIL",
            {"forbidden_env_keys": forbidden_env},
        )
    )
    return checks


def check_router_live() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    try:
        health = httpx.get(f"{ROUTER_BASE_URL}/health", timeout=5).json()
        providers = sorted(health.get("providers") or [])
        checks.append(_result("claude.router_health", "PASS" if providers == ["deepseek", "minimax"] else "FAIL", health))
    except Exception as exc:
        return [_result("claude.router_health", "FAIL", {"error": f"{type(exc).__name__}: {exc}"})]

    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
        "x-api-key": "router-local",
    }
    for model in ("deepseek-v4-pro[1m]", "MiniMax-M3"):
        try:
            response = httpx.post(
                f"{ROUTER_BASE_URL}/anthropic/v1/messages",
                headers=headers,
                json={"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": "Reply exactly OK"}]},
                timeout=30,
            )
            payload = response.json()
            text = "".join(part.get("text", "") for part in payload.get("content", []) if part.get("type") == "text")
            checks.append(
                _result(
                    f"claude.router_message.{model}",
                    "PASS" if response.status_code == 200 and text.strip() == "OK" else "FAIL",
                    {"status_code": response.status_code, "model": payload.get("model"), "text": text[:80]},
                )
            )
        except Exception as exc:
            checks.append(_result(f"claude.router_message.{model}", "FAIL", {"error": f"{type(exc).__name__}: {exc}"}))
    return checks


def check_direct_dns() -> list[dict[str, Any]]:
    hosts = ("api.deepseek.com", "api.moonshot.cn", "api.minimaxi.com")
    checks: list[dict[str, Any]] = []
    for host in hosts:
        try:
            address = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)[0][4][0]
            checks.append(_result(f"direct_dns.{host}", "PASS", {"address": address}))
        except Exception as exc:
            checks.append(_result(f"direct_dns.{host}", "FAIL", {"error": f"{type(exc).__name__}: {exc}"}))
    return checks


def check_deerflow_live() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    force_direct_api_network()
    for model in ("kimi-k2.6-api", "deepseek-v4-pro"):
        try:
            response = create_chat_model(model).invoke([HumanMessage(content="Reply exactly: OK")])
            text = str(response.content).strip()
            checks.append(_result(f"deerflow.live_model.{model}", "PASS" if text == "OK" else "FAIL", {"text": text[:80]}))
        except Exception as exc:
            checks.append(_result(f"deerflow.live_model.{model}", "FAIL", {"error": f"{type(exc).__name__}: {exc}"}))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Check DeerFlow and Claude Code LLM routing.")
    parser.add_argument("--live-router", action="store_true", help="Call the local Claude provider router.")
    parser.add_argument("--live-direct", action="store_true", help="Check direct DNS and call DeerFlow models directly.")
    args = parser.parse_args()

    checks: list[dict[str, Any]] = []
    checks.extend(check_deerflow_config())
    checks.extend(check_deerflow_network_policy())
    checks.extend(check_claude_config())
    if args.live_router:
        checks.extend(check_router_live())
    if args.live_direct:
        checks.extend(check_direct_dns())
        checks.extend(check_deerflow_live())

    summary = {
        "status": "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL",
        "checks": checks,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
