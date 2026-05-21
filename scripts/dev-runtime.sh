#!/usr/bin/env bash
#
# dev-runtime.sh - Repo-scoped runtime governance for local DeerFlow services.
#
# Usage:
#   ./scripts/dev-runtime.sh status [--gateway]
#   ./scripts/dev-runtime.sh preflight [--gateway] [--startup-guard]
#   ./scripts/dev-runtime.sh stop

set -euo pipefail

REPO_ROOT="$(builtin cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd -P)"
CANONICAL_BUSINESS_URL="http://localhost:2026/workspace/cer"
DEVELOPMENT_URL="http://localhost:3000/workspace/cer"
FRONTEND_DIR="$REPO_ROOT/frontend"
TRACKED_PORTS=(2026 3000 8001 2024)

COMMAND="status"
GATEWAY_MODE=false
STARTUP_GUARD=false

usage() {
    cat <<EOF
Usage:
  $0 status [--gateway]
  $0 preflight [--gateway] [--startup-guard]
  $0 stop
EOF
}

for arg in "$@"; do
    case "$arg" in
        status|preflight|stop)
            COMMAND="$arg"
            ;;
        --gateway)
            GATEWAY_MODE=true
            ;;
        --startup-guard)
            STARTUP_GUARD=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            usage >&2
            exit 1
            ;;
    esac
done

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

service_label_for_port() {
    case "$1" in
        2026) echo "Canonical proxy" ;;
        3000) echo "Frontend dev/prod" ;;
        8001) echo "Gateway API" ;;
        2024) echo "LangGraph" ;;
        *) echo "Port $1" ;;
    esac
}

get_required_ports() {
    if $GATEWAY_MODE; then
        echo "2026 3000 8001"
    else
        echo "2026 3000 8001 2024"
    fi
}

get_listen_pids() {
    local port="$1"

    if command_exists lsof; then
        lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | sort -u || true
        return
    fi

    if command_exists ss; then
        ss -ltnp "( sport = :$port )" 2>/dev/null | awk '
            NR > 1 {
                while (match($0, /pid=[0-9]+/)) {
                    pid = substr($0, RSTART + 4, RLENGTH - 4)
                    print pid
                    $0 = substr($0, RSTART + RLENGTH)
                }
            }
        ' | sort -u || true
        return
    fi

    if command_exists netstat; then
        netstat -ltnp 2>/dev/null | awk -v port="$port" '
            $4 ~ ("(^|:)" port "$") {
                split($7, parts, "/")
                if (parts[1] ~ /^[0-9]+$/) {
                    print parts[1]
                }
            }
        ' | sort -u || true
    fi
}

get_ps_field() {
    local pid="$1"
    local field="$2"

    ps -p "$pid" -o "${field}=" 2>/dev/null | sed 's/^ *//'
}

get_command() {
    get_ps_field "$1" command
}

get_ppid() {
    get_ps_field "$1" ppid | tr -d ' '
}

get_rss_mb() {
    local rss_kb
    rss_kb="$(get_ps_field "$1" rss | tr -d ' ')"
    if [[ "$rss_kb" =~ ^[0-9]+$ ]]; then
        echo $(((rss_kb + 1023) / 1024))
    else
        echo "?"
    fi
}

get_cwd() {
    local pid="$1"

    if command_exists lsof; then
        lsof -a -d cwd -p "$pid" -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1
        return
    fi

    if command_exists pwdx; then
        pwdx "$pid" 2>/dev/null | awk '{print $2}'
        return
    fi
}

is_pid_alive() {
    local pid="$1"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

is_repo_owned_pid() {
    local pid="$1"
    local depth=0
    local command_line=""
    local cwd=""
    local parent=""

    while [ "$depth" -lt 6 ] && is_pid_alive "$pid"; do
        command_line="$(get_command "$pid")"
        cwd="$(get_cwd "$pid")"

        if [[ "$command_line" == *"$REPO_ROOT"* ]]; then
            return 0
        fi

        if [ -n "$cwd" ] && [[ "$cwd" == "$REPO_ROOT"* ]]; then
            return 0
        fi

        parent="$(get_ppid "$pid")"
        if [ -z "$parent" ] || [ "$parent" = "$pid" ] || [ "$parent" = "1" ]; then
            break
        fi

        pid="$parent"
        depth=$((depth + 1))
    done

    return 1
}

collect_pattern_pids() {
    local pattern="$1"

    if command_exists pgrep; then
        pgrep -f "$pattern" 2>/dev/null | sort -u || true
        return
    fi

    ps -ax -o pid= -o command= 2>/dev/null | awk -v pattern="$pattern" '$0 ~ pattern {print $1}' | sort -u || true
}

collect_frontend_dev_instance_pids() {
    local pid=""
    local command_line=""
    local cwd=""

    while IFS= read -r pid; do
        [ -z "$pid" ] && continue
        is_repo_owned_pid "$pid" || continue
        command_line="$(get_command "$pid")"
        cwd="$(get_cwd "$pid")"

        if [[ "$command_line" == *"next/dist/bin/next dev"* ]] || [[ "$command_line" == *" next dev"* ]]; then
            if [[ "$command_line" == *"$REPO_ROOT/frontend/"* ]] || [[ "$cwd" == "$FRONTEND_DIR"* ]]; then
                echo "$pid"
            fi
        fi
    done < <(collect_pattern_pids "next dev")
}

collect_repo_runtime_pids() {
    local patterns=(
        "langgraph dev"
        "uvicorn app.gateway.app:app"
        "next dev"
        "next start"
        "next-server"
        "nginx.*nginx.local.conf"
        "pnpm dev"
        "pnpm run dev"
        "npm run dev"
        "yarn dev"
    )
    local pattern=""
    local pid=""
    local port=""

    for port in "${TRACKED_PORTS[@]}"; do
        while IFS= read -r pid; do
            [ -z "$pid" ] && continue
            is_repo_owned_pid "$pid" || continue
            echo "$pid"
        done < <(get_listen_pids "$port")
    done

    for pattern in "${patterns[@]}"; do
        while IFS= read -r pid; do
            [ -z "$pid" ] && continue
            is_repo_owned_pid "$pid" || continue
            echo "$pid"
        done < <(collect_pattern_pids "$pattern")
    done | sort -u
}

get_http_code() {
    local url="$1"
    local code=""

    if ! command_exists curl; then
        echo "n/a"
        return
    fi

    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 2 "$url" 2>/dev/null || true)"
    if [ -z "$code" ]; then
        echo "000"
    else
        echo "$code"
    fi
}

print_process_line() {
    local pid="$1"
    local owner="external"
    local command_line=""
    local cwd=""
    local rss_mb=""

    if is_repo_owned_pid "$pid"; then
        owner="repo"
    fi

    command_line="$(get_command "$pid")"
    cwd="$(get_cwd "$pid")"
    rss_mb="$(get_rss_mb "$pid")"

    printf "    - pid=%s owner=%s rss=%sMB" "$pid" "$owner" "$rss_mb"
    if [ -n "$cwd" ]; then
        printf " cwd=%s" "$cwd"
    fi
    printf "\n"
    printf "      cmd=%s\n" "$command_line"
}

print_port_status() {
    local port="$1"
    local label=""
    local found=false
    local pid=""
    local repo_count=0
    local external_count=0

    label="$(service_label_for_port "$port")"
    echo "  ${label} (${port}):"

    while IFS= read -r pid; do
        [ -z "$pid" ] && continue
        found=true
        if is_repo_owned_pid "$pid"; then
            repo_count=$((repo_count + 1))
        else
            external_count=$((external_count + 1))
        fi
        print_process_line "$pid"
    done < <(get_listen_pids "$port")

    if ! $found; then
        echo "    - not listening"
        return
    fi

    if [ "$repo_count" -gt 0 ] && [ "$external_count" -gt 0 ]; then
        echo "    summary: mixed ownership"
    elif [ "$repo_count" -gt 0 ]; then
        echo "    summary: repo-owned"
    else
        echo "    summary: external"
    fi
}

print_health_summary() {
    local proxy_code=""
    local gateway_code=""
    local frontend_code=""
    local langgraph_code=""

    proxy_code="$(get_http_code "http://127.0.0.1:2026/health")"
    gateway_code="$(get_http_code "http://127.0.0.1:8001/health")"
    frontend_code="$(get_http_code "http://127.0.0.1:3000/")"
    langgraph_code="$(get_http_code "http://127.0.0.1:2024")"

    echo ""
    echo "Health:"
    echo "  proxy_health = $proxy_code"
    echo "  gateway_health = $gateway_code"
    echo "  frontend_route = $frontend_code"
    if $GATEWAY_MODE; then
        echo "  langgraph_health = skipped (gateway mode)"
    else
        echo "  langgraph_health = $langgraph_code"
    fi
}

print_runtime_summary() {
    local frontend_count=0
    local frontend_pid=""
    local required_port=""
    local next_cache_size="missing"
    local node_modules_size="missing"

    while IFS= read -r frontend_pid; do
        [ -z "$frontend_pid" ] && continue
        frontend_count=$((frontend_count + 1))
    done < <(collect_frontend_dev_instance_pids)

    if [ -d "$FRONTEND_DIR/.next" ]; then
        next_cache_size="$(du -sh "$FRONTEND_DIR/.next" 2>/dev/null | awk '{print $1}')"
    fi
    if [ -d "$FRONTEND_DIR/node_modules" ]; then
        node_modules_size="$(du -sh "$FRONTEND_DIR/node_modules" 2>/dev/null | awk '{print $1}')"
    fi

    echo "=========================================="
    echo "  DeerFlow Dev Runtime Preflight"
    echo "=========================================="
    echo ""
    echo "Repository: $REPO_ROOT"
    echo "Canonical business URL: $CANONICAL_BUSINESS_URL"
    echo "Development URL: $DEVELOPMENT_URL"
    echo "Mode: $(if $GATEWAY_MODE; then echo "gateway"; else echo "standard"; fi)"
    echo ""
    echo "Runtime summary:"
    echo "  frontend_dev_instances = $frontend_count"
    echo "  frontend_next_cache = $next_cache_size"
    echo "  frontend_node_modules = $node_modules_size"
    echo ""
    echo "Ports:"
    for required_port in "${TRACKED_PORTS[@]}"; do
        print_port_status "$required_port"
    done
    print_health_summary
}

has_repo_runtime_activity() {
    local pid=""
    local port=""
    local frontend_count=0

    while IFS= read -r pid; do
        [ -z "$pid" ] && continue
        is_repo_owned_pid "$pid" || continue
        return 0
    done < <(collect_frontend_dev_instance_pids)

    for port in "${TRACKED_PORTS[@]}"; do
        while IFS= read -r pid; do
            [ -z "$pid" ] && continue
            is_repo_owned_pid "$pid" || continue
            return 0
        done < <(get_listen_pids "$port")
    done

    return 1
}

has_external_port_conflict() {
    local required_ports=""
    local port=""
    local pid=""

    required_ports="$(get_required_ports)"

    for port in $required_ports; do
        while IFS= read -r pid; do
            [ -z "$pid" ] && continue
            if ! is_repo_owned_pid "$pid"; then
                return 0
            fi
        done < <(get_listen_pids "$port")
    done

    return 1
}

count_frontend_instances() {
    local count=0
    local pid=""

    while IFS= read -r pid; do
        [ -z "$pid" ] && continue
        count=$((count + 1))
    done < <(collect_frontend_dev_instance_pids)

    echo "$count"
}

enforce_startup_guard() {
    local frontend_count=""

    frontend_count="$(count_frontend_instances)"

    if has_external_port_conflict; then
        echo ""
        echo "FAIL startup blocked: one or more required DeerFlow ports are occupied by a non-repo process."
        echo "Inspect the port table above, free the conflicting port, then retry."
        exit 1
    fi

    if [ "$frontend_count" -gt 1 ]; then
        echo ""
        echo "FAIL startup blocked: detected $frontend_count repo-owned frontend dev instances."
        echo "Run 'make stop' to clean the existing runtime before starting again."
        exit 1
    fi

    if has_repo_runtime_activity; then
        echo ""
        echo "FAIL startup blocked: DeerFlow is already running from this repo."
        echo "Use 'make stop' or './scripts/serve.sh --restart ...' instead of starting a second instance."
        exit 1
    fi

    echo ""
    echo "OK startup guard passed"
}

stop_runtime() {
    local pids=()
    local pid=""
    local pid_list=""
    local remaining=()

    echo "Stopping DeerFlow services for repo: $REPO_ROOT"

    while IFS= read -r pid; do
        [ -z "$pid" ] && continue
        pids+=("$pid")
    done < <(collect_repo_runtime_pids)

    if command_exists nginx; then
        nginx -c "$REPO_ROOT/docker/nginx/nginx.local.conf" -p "$REPO_ROOT" -s quit 2>/dev/null || true
    fi

    if [ "${#pids[@]}" -eq 0 ]; then
        ./scripts/cleanup-containers.sh deer-flow-sandbox 2>/dev/null || true
        echo "✓ No repo-owned DeerFlow services were running"
        return
    fi

    pid_list="$(printf "%s\n" "${pids[@]}" | awk 'NF && !seen[$0]++' | sort -nr)"

    echo "  Terminating repo-owned PIDs:"
    while IFS= read -r pid; do
        [ -z "$pid" ] && continue
        echo "    - $pid"
        kill "$pid" 2>/dev/null || true
    done <<< "$pid_list"

    sleep 2

    while IFS= read -r pid; do
        [ -z "$pid" ] && continue
        if is_pid_alive "$pid"; then
            remaining+=("$pid")
        fi
    done <<< "$pid_list"

    if [ "${#remaining[@]}" -gt 0 ]; then
        echo "  Forcing remaining PIDs:"
        for pid in "${remaining[@]}"; do
            echo "    - $pid"
            kill -9 "$pid" 2>/dev/null || true
        done
    fi

    ./scripts/cleanup-containers.sh deer-flow-sandbox 2>/dev/null || true
    echo "✓ DeerFlow services stopped"
}

case "$COMMAND" in
    status|preflight)
        print_runtime_summary
        if $STARTUP_GUARD; then
            enforce_startup_guard
        fi
        ;;
    stop)
        stop_runtime
        ;;
    *)
        echo "Unknown command: $COMMAND" >&2
        usage >&2
        exit 1
        ;;
esac
