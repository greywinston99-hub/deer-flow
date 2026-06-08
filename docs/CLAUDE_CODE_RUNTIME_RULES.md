# Claude Code Runtime Rules

## Canonical addresses

- 2026 business URL: `http://localhost:2026/workspace/cer`
- 3000 dev URL: `http://localhost:3000/workspace/cer`
- 8001 gateway: `http://127.0.0.1:8001/health`
- 2024 LangGraph: `http://127.0.0.1:2024`

## Runtime modes

- `make pilot` is the default stable mode for real business-loop acceptance.
- `make dev` is only for continuous integration and active debug work.

## Agent restrictions

- Agents must not start or restart DeerFlow unless the main controller explicitly authorizes it.
- `make preflight` is the only default runtime command allowed for agent execution in this operating model.
- If code changes require a restart or reload, agents must report `REQUIRES_MAIN_CONTROLLER_RESTART=YES`.
- Runtime review must not silently learn from current-session feedback or sandbox experiments.
- Sandbox candidates must not affect runtime review decisions until human approval and regression evidence exist.
- Shadow backtesting may inform sandbox evaluation, but it must not be treated as runtime approval.

## Duplicate frontend prevention

- Never start a second DeerFlow runtime while another controlled instance is already in place.
- Never use UI verification language unless runtime ownership is known.
- Runtime guard must inspect ports and process state before any restart recommendation.

## Main controller ownership

- Only the main controller decides whether to run `make dev`, `make pilot`, `pnpm dev`, `npm run dev`, or `next dev`.
- Agent teams may inspect runtime state and report required actions, but they do not execute those actions by default.
