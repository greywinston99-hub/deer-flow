#!/bin/bash
# Diff two CER runs — compare CER_draft.md between artifact directories.
# Usage: cer_diff_runs.sh <run1_artifact_root> <run2_artifact_root>

RUN1="${1:-}"
RUN2="${2:-}"

if [ -z "$RUN1" ] || [ -z "$RUN2" ]; then
    echo "Usage: cer_diff_runs.sh <run1_output> <run2_output>"
    echo "Example: cer_diff_runs.sh 02_CER_OUTPUT /tmp/cer_output_v2"
    exit 1
fi

MD1="$RUN1/CER_draft.md"
MD2="$RUN2/CER_draft.md"

if [ ! -f "$MD1" ]; then echo "Missing: $MD1"; exit 1; fi
if [ ! -f "$MD2" ]; then echo "Missing: $MD2"; exit 1; fi

echo "=== Word Count ==="
echo "Run1: $(wc -w < "$MD1") words"
echo "Run2: $(wc -w < "$MD2") words"

echo ""
echo "=== Evidence Count ==="
python3 -c "
import json
for label, path in [('Run1', '$RUN1/evidence_count_funnel.json'), ('Run2', '$RUN2/evidence_count_funnel.json')]:
    try:
        d = json.load(open(path))
        print(f'{label}: {d}')
    except: print(f'{label}: N/A')
"

echo ""
echo "=== Gate Decision ==="
python3 -c "
import json
for label, path in [('Run1', '$RUN1/final_gate_closure_report.json'), ('Run2', '$RUN2/final_gate_closure_report.json')]:
    try:
        d = json.load(open(path))
        print(f'{label}: {d.get(\"decision\", \"?\")}')
    except: print(f'{label}: N/A')
"

echo ""
echo "=== Diff (first 50 changed lines) ==="
diff "$MD1" "$MD2" | head -50
