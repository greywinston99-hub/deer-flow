# ADR-001: LangGraph Scope Decision for CER/RMF Workspace

**Date**: 2026-04-19
**Status**: ACCEPTED
**Deciders**: CER/RMF Engineering Team

---

## Context

The second independent review identified that `localhost:2024` (LangGraph server) is not running, causing 502/404 errors in the RMF Workbench. We must decide whether to:
- A) Start LangGraph and ensure it runs
- B) Explicitly scope LangGraph as NOT required for CER/RMF main链路

## Decision

**LangGraph is NOT required for CER/RMF评审主链路 (CER/RMF Review Main Path)**

CER workspace operates in **Gateway mode** using:
- Gateway API (`localhost:8001`) - REST endpoints
- Harness runtime (`deerflow.*` packages) - direct LLM invocation
- No LangGraph SDK or LangGraph server dependency

### LangGraph Dependency Map

| Component | LangGraph Required? | Notes |
|-----------|-------------------|-------|
| CER Intake Pipeline | NO | Gateway API + harness |
| CER Review Runner | NO | Gateway API + harness |
| Knowledge Container | NO | Gateway API + harness |
| RMF Workbench (CER views) | NO | Gateway API only |
| Chat/Agent Demo | YES | Standard chat threads |
| MCP Tools | YES | Some tools use LangGraph |

### Boundary

```
CER/RMF评审链路:
  Frontend → Gateway (:8001) → Harness + LLM → Artifact Storage
  (No LangGraph dependency)

Chat/Agent Demo:
  Frontend → LangGraph (:2024) → Agent Runtime
  (Requires LangGraph)
```

## Consequences

### Positive
- CER/RMF workspace functions with `make dev-pro` (Gateway mode only)
- No dependency on LangGraph health for critical review paths
- Simpler deployment for CER-specific workflows

### Negative
- Chat/Agent Demo requires full `make dev` with LangGraph
- Two modes of operation instead of one
- Potential confusion if users expect unified experience

## Frontend Handling

For `/api/langgraph/*` calls in RMF Workbench contexts, the frontend should gracefully handle LangGraph unavailability:

```typescript
// In API client or page components
async function safeLangGraphFetch(url: string, options?: RequestInit) {
  try {
    return await fetch(url, options);
  } catch (error) {
    if (isCERWorkspaceContext()) {
      // Graceful degradation for CER workspace
      return null;
    }
    throw error; // Re-throw for chat/agent contexts
  }
}
```

## Startup Commands

| Mode | Command | CER Workspace | Chat/Agent |
|------|---------|--------------|------------|
| Gateway only | `make dev-pro` | WORKS | DOES NOT WORK |
| Full stack | `make dev` | WORKS | WORKS |

## Verification

```bash
# Check LangGraph health (if running)
curl http://localhost:2024/ok

# Check Gateway health (always required)
curl http://localhost:8001/health

# CER workspace should work with Gateway only
curl http://localhost:8001/api/cer-review/projects
```

## Review History

- 2026-04-19: Initial decision - LangGraph not required for CER/RMF main链路
