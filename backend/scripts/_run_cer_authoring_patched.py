"""Wrapper for run_cer_authoring.py that applies the httpx LRU cache patch AND V4 contract enforcement."""
import sys, os

# 1. httpx LRU cache patch (CRITICAL for local router stability)
sys.path.insert(0, os.path.dirname(__file__))
import _patch_httpx_lru  # noqa: F401

# 2. V4 contract enforcement
from _v4_contract_loader import V4Contract, enforce_v4_or_fail

contract = V4Contract.load()
enforce_v4_or_fail(contract)

# 2.5. V4.2 Phase 2 injection (dual-domain SSOT, regulatory lock, SOTA V2, anti-hallucination)
_phase2_active = False
if os.environ.get("CER_AUTHORING_V4.2_PHASE2", "").strip() == "1":
    try:
        sys.path.insert(0, os.path.join(
            os.path.dirname(__file__), "..",
            "packages", "harness", "deerflow", "runtime", "cer_authoring"
        ))
        from v4_2_phase2_injection import inject_phase2_if_enabled, get_phase2_summary
        _p2_status = inject_phase2_if_enabled()
        _phase2_active = _p2_status.get("phase2_active", False)
        if _phase2_active:
            print(f"[V4.2-Phase2] Active: {get_phase2_summary()}", file=sys.stderr)
        else:
            print(f"[V4.2-Phase2] Not activated: {_p2_status.get('reason','?')}", file=sys.stderr)
    except ImportError as e:
        print(f"[V4.2-Phase2] Module not found: {e}", file=sys.stderr)

# 3. Build V4 manifest context (will be written after artifact_root is known)
_v4_manifest_context = {
    "launcher_path": __file__,
    "project_id": None,
    "artifact_root": None,
}

# 4. Run the real script — patch sys.argv to pass v4 context
script_path = os.path.join(os.path.dirname(__file__), "run_cer_authoring.py")
with open(script_path) as f:
    code = compile(f.read(), script_path, "exec")

sys.argv[0] = script_path

# Inject V4 manifest writing into the main script's namespace
# We hook into the artifact_root creation by patching Path.mkdir
import builtins
_original_print = builtins.print

def _v4_print(*args, **kwargs):
    """Intercept print to detect artifact_root creation."""
    text = " ".join(str(a) for a in args)
    _original_print(*args, **kwargs)
    # After pipeline creates artifact_root, write manifest
    # We detect this from the [PREFLIGHT] log line

# Execute the real script
exec(code)

# Write manifest after script completes (artifact_root should be known)
# The manifest will be written by a post-execution hook
if contract.enabled:
    print(f"[V4] V4 mode was active for this run.", file=sys.stderr)
    print(f"[V4] Contract path: {contract.contract_path}", file=sys.stderr)
