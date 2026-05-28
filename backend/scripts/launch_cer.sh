#!/bin/bash
# Generic CER launcher — auto-detect project from path.
# Usage: ./launch_cer.sh "/path/to/CER_PILOT_STANDARD_XX/project_name"

PROJECT="$1"
if [ -z "$PROJECT" ] || [ ! -d "$PROJECT" ]; then
    echo "Usage: ./launch_cer.sh '/path/to/project'"
    echo "Available projects:"
    ls -d /Users/winstonwei/CER-RAG/升级\ CCD-3\ 个项目文件/CER_PILOT_STANDARD_*/
    exit 1
fi

PROJECT=$(cd "$PROJECT" && pwd)
NAME=$(basename "$PROJECT")
INPUT="$PROJECT/01_AUTHORING_INPUT_ALLOWED"
OUTPUT="$PROJECT/02_CER_OUTPUT"

if [ ! -d "$INPUT" ]; then
    echo "❌ No 01_AUTHORING_INPUT_ALLOWED in $PROJECT"
    exit 1
fi

# Auto-detect IFU and extract keywords
IFU_FILE=$(find "$INPUT/01_IFU_REQUIRED" -type f \( -name "*.docx" -o -name "*.doc" -o -name "*.pdf" \) 2>/dev/null | head -1)
if [ -z "$IFU_FILE" ]; then
    echo "❌ No IFU file found in $INPUT/01_IFU_REQUIRED/"
    exit 1
fi

IFU_NAME=$(basename "$IFU_FILE")
echo "📄 IFU: $IFU_NAME"

# Extract pilot number from folder name (e.g. "02" from "CER_PILOT_STANDARD_02米道斯")
PILOT_NUM=$(echo "$NAME" | grep -oE 'CER_PILOT_STANDARD_[0-9]+' | grep -oE '[0-9]+$')
PILOT_NUM="${PILOT_NUM:-00}"

# Extract project-id from folder name
PROJECT_ID=$(echo "$NAME" | sed 's/CER_PILOT_STANDARD_[0-9]*//' | sed 's/[[:space:]]*$//' | tr '[:lower:]' '[:upper:]' | tr ' ' '_')
PROJECT_ID="${PROJECT_ID}_001"

# Auto-detect keywords AND ASCII project-id from IFU filename
KEYWORDS=""
ASCII_ID=""
case "$IFU_NAME" in
    *等离子手术设备*|*plasma*surgical*equipment*|*plasma*generator*|*ENT*|*耳鼻喉*)
        KEYWORDS="等离子手术设备,等离子射频治疗仪,耳鼻喉,ENT,otolaryngology,plasma,radiofrequency,soft tissue,resection,ablation,coagulation,hemostasis"
        ASCII_ID="PLASMA_SURGICAL_EQUIPMENT" ;;
    *等离子*|*plasma*|*射频*|*电极*|*手术电极*)
        KEYWORDS="等离子,射频,手术电极,plasma,radiofrequency,electrode,arthroscopy"
        ASCII_ID="PLASMA_ELECTRODE" ;;
    *心脏*|*固定器*|*stabilizer*|*cardiac*|*coronary*|*bypass*)
        KEYWORDS="心脏固定器,cardiac,stabilizer,tissue,coronary,bypass"
        ASCII_ID="CARDIAC_STABILIZER" ;;
    *)
        KEYWORDS="medical device,clinical evaluation"
        ASCII_ID="MEDICAL_DEVICE" ;;
esac

# Sanitize: if PROJECT_ID contains non-ASCII, use keyword-based ASCII fallback
_CLEAN=$(echo "$PROJECT_ID" | sed 's/[a-zA-Z0-9_-]//g')
if [ -n "$_CLEAN" ]; then
    PROJECT_ID="${ASCII_ID}_P${PILOT_NUM}_001"
fi
echo "🆔 Project ID: $PROJECT_ID"
echo "🔑 Keywords: $KEYWORDS"

# Prepare output
rm -f "$OUTPUT/dashboard.json" 2>/dev/null
mkdir -p "$OUTPUT/.human_gate"
cp /Users/winstonwei/Documents/Playground/deer-flow/backend/scripts/cer_dashboard.html "$OUTPUT/" 2>/dev/null

# Clear checkpoint
rm -f /Users/winstonwei/Documents/Playground/deer-flow/backend/packages/harness/checkpoints.db 2>/dev/null

echo ""
echo "🚀 Launching..."
echo ""

cd /Users/winstonwei/Documents/Playground/deer-flow/backend/packages/harness
CER_AUTHORING_STRICT_V7=1 \
CER_AUTHORING_ENABLE_LLM_AGENTS=1 \
CER_AUTHORING_ENABLE_EVENT_BUS=0 \
CER_GRAPH_INVOKE_TIMEOUT=1800 \
CER_AUTHORING_API_MAX_RETRIES=2 \
CER_AUTHORING_API_RETRY_BACKOFF=1.5 \
/Users/winstonwei/Documents/Playground/deer-flow/.venv/bin/python3 \
  ../../scripts/run_cer_authoring.py \
  --project-id "$PROJECT_ID" \
  --input-root "$INPUT" \
  --artifact-root "$OUTPUT" \
  --target-keywords "$KEYWORDS" \
  --strict-v7 --json --auto-confirm
