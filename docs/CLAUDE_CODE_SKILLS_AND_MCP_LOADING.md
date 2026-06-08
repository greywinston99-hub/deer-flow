# Claude Code Skills And MCP Loading

## Added Skills

- `source-package-integrity-audit`
- `browser-evidence-collector`
- `actionable-gap-drafting`
- `review-copilot-batch-drafting`
- `shadow-backtest-reporter`
- `experience-draft-recorder`
- `regulatory-boundary-guard`

## Skill purposes

- `source-package-integrity-audit`
  - Builds a physical source-package register, identifies large or unreadable files, and prevents fake-read claims.
- `browser-evidence-collector`
  - Captures screenshot, console, network, and trace or HAR evidence for UI validation.
- `actionable-gap-drafting`
  - Converts G-Points into actionable gap paths with evidence, impact, owner, and next-step framing.
- `review-copilot-batch-drafting`
  - Produces staged recommendations, blocking-gap views, limited-review explanations, and open-file-check drafts.
- `shadow-backtest-reporter`
  - Reports before and after recommendation changes, confidence-band shifts, and drift risk in sandbox-only form.
- `experience-draft-recorder`
  - Stores human feedback as repo-local draft experience events without backflow.
- `regulatory-boundary-guard`
  - Prevents project-specific, NB-specific, or confidence-based signals from being misrepresented as approved regulatory basis.

## Workflow to skill mapping

- Source package intake
  - `source-package-integrity-audit`
  - `regulatory-boundary-guard`
- Gap analysis
  - `actionable-gap-drafting`
  - `regulatory-boundary-guard`
- Review copilot
  - `review-copilot-batch-drafting`
  - `regulatory-boundary-guard`
- UI or browser validation
  - `browser-evidence-collector`
- Shadow validation
  - `shadow-backtest-reporter`
  - `regulatory-boundary-guard`
- Human feedback capture
  - `experience-draft-recorder`
  - `regulatory-boundary-guard`

## MCP template enablement

- This patch adds only `.mcp.json.template`.
- No real MCP credentials, tokens, or write permissions are enabled by default.
- To enable MCP later, a human should review the template, copy it to `.mcp.json`, fill only safe local placeholders, and explicitly approve any project MCP server.

## Recommended MCP

- `playwright`
  - Recommended when UI or browser evidence is required.

## Optional MCP

- `document-extraction-optional`
  - Optional when document extraction is needed and a read-only implementation is available.

## Not recommended by default

- Unrestricted filesystem MCP
- Obsidian write MCP
- Issue-tracker write MCP
- Any external write-enabled MCP

## Human gate rules

- Gate before external publication
- Gate before Obsidian backflow
- Gate before upgrading candidate to active
- Gate before claiming regulatory approval
- Gate before closing major findings

## No-backflow rules

- No automatic Obsidian backflow
- No automatic knowledge-base sync
- No automatic promotion from candidate or draft to approved or active

## Obsidian rule

- Obsidian must not be written automatically by any skill or MCP path added in this patch.

## UI evidence rule

- No screenshot, trace, console, or network evidence means no UI PASS.

## Source package integrity rule

- Filenames are not content evidence.
- Metadata scan comes first.
- Open-file evidence is required before claiming file content was read.
- Large-file hashing must be on-demand rather than full-package by default.

## Using these additions without interrupting the current task

- Skills are project-local definitions under `.claude/skills/` and do not require restarting Claude Code to exist on disk.
- MCP remains template-only until a human explicitly reviews and enables a real `.mcp.json`.
- Existing `.claude/settings.local.json` remains untouched.
- Existing `.claude/settings.json` hooks remain untouched.
