"""V4 Contract Loader — reads V4 systemization files and enforces V4 mode.

Usage:
    from _v4_contract_loader import V4Contract
    contract = V4Contract.load()
    if not contract.ready:
        raise SystemExit("V4 mode enabled but contract not loaded")
    contract.write_manifest(artifact_root)

Set CER_AUTHORING_V4_MODE=1 to enable V4 enforcement.
"""
from __future__ import annotations

import json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class V4Contract:
    """Represents the V4 execution contract loaded from systemization files."""

    def __init__(self):
        self.enabled: bool = False
        self.contract_path: str = ""
        self.contract_loaded: bool = False
        self.policy_loaded: bool = False
        self.qa_checklist_loaded: bool = False
        self.errors: list[str] = []

    @classmethod
    def load(cls) -> "V4Contract":
        contract = cls()
        contract.enabled = os.environ.get("CER_AUTHORING_V4_MODE", "").strip() == "1"

        if not contract.enabled:
            return contract

        # Find V4 contract root
        repo_root = Path(__file__).resolve().parents[2]
        v4_root = repo_root / ".claude" / "systemization" / "V4"

        if not v4_root.exists():
            contract.errors.append(f"V4 contract root not found: {v4_root}")
            return contract

        contract.contract_path = str(v4_root)

        # Load contract
        contract_file = v4_root / "V4_GLOBAL_EXECUTION_CONTRACT.md"
        if contract_file.exists():
            contract.contract_loaded = True
        else:
            contract.errors.append(f"V4 contract file missing: {contract_file}")

        # Load operator policy
        policy_file = v4_root / "V4_OPERATOR_ASSISTED_WRITING_POLICY.md"
        if policy_file.exists():
            contract.policy_loaded = True
        else:
            contract.errors.append(f"V4 policy file missing: {policy_file}")

        # Load QA checklist
        qa_file = v4_root / "V4_NEXT_PROJECT_READINESS_CHECKLIST.md"
        if qa_file.exists():
            contract.qa_checklist_loaded = True
        else:
            contract.errors.append(f"V4 QA checklist missing: {qa_file}")

        return contract

    @property
    def ready(self) -> bool:
        if not self.enabled:
            return True  # V4 mode not required
        return self.contract_loaded and self.policy_loaded and len(self.errors) == 0

    def write_manifest(self, artifact_root: str, **extra) -> str:
        """Write V4_RUN_MANIFEST.json to artifact root."""
        manifest: dict[str, Any] = {
            "v4_mode_enabled": self.enabled,
            "contract_loaded": self.contract_loaded,
            "policy_loaded": self.policy_loaded,
            "qa_checklist_loaded": self.qa_checklist_loaded,
            "contract_path": self.contract_path,
            "errors": self.errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **extra,
        }

        artifact_dir = Path(artifact_root)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = artifact_dir / "V4_RUN_MANIFEST.json"

        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        return str(manifest_path)


def enforce_v4_or_fail(contract: V4Contract) -> None:
    """Fail fast if V4 mode is enabled but contract not ready."""
    if not contract.enabled:
        print("[V4] V4 mode not enabled — running without V4 contract enforcement", file=sys.stderr)
        return

    if not contract.ready:
        msg = f"[V4] FATAL: V4 mode enabled but contract not ready. Errors: {contract.errors}"
        print(msg, file=sys.stderr)
        raise SystemExit(msg)

    print(f"[V4] V4 mode ACTIVE — contract loaded from {contract.contract_path}", file=sys.stderr)
