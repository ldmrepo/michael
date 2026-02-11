#!/bin/bash
# Vast.ai Serverless Setup for Wan 2.2 I2V (Custom Docker Image)
# Run this after Cloud Build completes successfully
#
# Prerequisites:
#   - Vast.ai credit >= $5
#   - HF_TOKEN set in Vast.ai env vars
#   - S3 credentials set in Vast.ai env vars

set -euo pipefail

# Configuration
VAST_API_KEY="${VAST_API_KEY:-$(cat ~/.config/vastai/vast_api_key 2>/dev/null)}"
DOCKER_IMAGE="us-central1-docker.pkg.dev/gen-lang-client-0072871637/comfyui-wan22/wan22-i2v-14b:latest"
ENDPOINT_NAME="comfyui-json"
TEMPLATE_NAME="Wan 2.2 14B I2V Custom"

if [ -z "$VAST_API_KEY" ]; then
    echo "ERROR: VAST_API_KEY not set"
    exit 1
fi

echo "=== Step 1: Create Template ==="
# Onstart script: run provisioning script (writes benchmark), start ComfyUI, start PyWorker
ONSTART='export SERVERLESS=true
export BACKEND=comfyui-json
export COMFYUI_API_BASE="http://localhost:18188"
export MODEL_LOG=/var/log/portal/comfyui.log
/opt/provision-i2v.sh &
entrypoint.sh &
wget -O - "https://raw.githubusercontent.com/vast-ai/pyworker/main/start_server.sh" | bash'

TEMPLATE_ID=$(vastai create template \
    --name "$TEMPLATE_NAME" \
    --image "$DOCKER_IMAGE" \
    --onstart-cmd "$ONSTART" \
    --disk_space 72 \
    --ssh --direct \
    --api-key "$VAST_API_KEY" \
    --raw 2>&1 | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))")

echo "Template created: ID=$TEMPLATE_ID"

echo ""
echo "=== Step 2: Create Endpoint ==="
ENDPOINT_RESULT=$(vastai create endpoint \
    --endpoint_name "$ENDPOINT_NAME" \
    --cold_workers 1 \
    --max_workers 1 \
    --api-key "$VAST_API_KEY" \
    --raw 2>&1)

ENDPOINT_ID=$(echo "$ENDPOINT_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))")
echo "Endpoint created: ID=$ENDPOINT_ID"

echo ""
echo "=== Step 3: Create Workergroup ==="
WORKERGROUP_RESULT=$(vastai create workergroup \
    --endpoint_id "$ENDPOINT_ID" \
    --template_id "$TEMPLATE_ID" \
    --gpu_ram 32 \
    --cold_workers 1 \
    --max_workers 1 \
    --search_params "gpu_ram>=24 cuda_max_good>=12.4 disk_space>=72 verified=true rentable=true rented=false" \
    --api-key "$VAST_API_KEY" \
    --raw 2>&1)

WORKERGROUP_ID=$(echo "$WORKERGROUP_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('new_contract',''))")
echo "Workergroup created: ID=$WORKERGROUP_ID"

echo ""
echo "=== Setup Complete ==="
echo "Docker Image: $DOCKER_IMAGE"
echo "Template ID:  $TEMPLATE_ID"
echo "Endpoint ID:  $ENDPOINT_ID"
echo "Workergroup:  $WORKERGROUP_ID"
echo ""
echo "Monitor with:"
echo "  vastai show instances --api-key $VAST_API_KEY"
echo "  vastai get endpt-logs $ENDPOINT_ID --api-key $VAST_API_KEY"
echo ""
echo "Suspend when done:"
echo "  curl -X PUT 'https://console.vast.ai/api/v0/endptjobs/$ENDPOINT_ID/?api_key=$VAST_API_KEY' -H 'Content-Type: application/json' -d '{\"endpoint_state\": \"suspended\"}'"
