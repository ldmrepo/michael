#!/bin/bash

set -euo pipefail

### Configuration ###
WORKSPACE_DIR="${WORKSPACE:-/workspace}"
COMFYUI_DIR="${WORKSPACE_DIR}/ComfyUI"
MODELS_DIR="${COMFYUI_DIR}/models"
INPUTS_DIR="${COMFYUI_DIR}/input"
MODEL_LOG="${MODEL_LOG:-/var/log/portal/comfyui.log}"

### End Configuration ###

mkdir -p "$(dirname "$MODEL_LOG")"

log() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$message" | tee -a "$MODEL_LOG"
}

script_error() {
    local exit_code=$?
    local line_number=$1
    log "[ERROR] Provisioning Script failed at line $line_number with exit code $exit_code"
    exit "$exit_code"
}

trap 'script_error $LINENO' ERR

# Verify all required models are accessible (symlinks from /opt/comfyui-models/)
verify_models() {
    log "Verifying I2V model accessibility..."
    local models_ok=true
    for model in \
        "$MODELS_DIR/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" \
        "$MODELS_DIR/vae/wan_2.1_vae.safetensors" \
        "$MODELS_DIR/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors" \
        "$MODELS_DIR/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors" \
        "$MODELS_DIR/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors" \
        "$MODELS_DIR/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors"; do
        if [[ -f "$model" ]] || [[ -L "$model" ]]; then
            log "  OK: $(basename "$model")"
        else
            log "[ERROR] Missing: $model"
            models_ok=false
        fi
    done

    if [[ "$models_ok" = false ]]; then
        log "[ERROR] Required models missing!"
        exit 1
    fi
    log "All 6 I2V models verified."
}

# Write the I2V benchmark workflow
write_benchmark() {
    local workflow_json
    read -r -d '' workflow_json << 'WORKFLOW_JSON' || true
{
    "90": {
        "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"},
        "class_type": "CLIPLoader"
    },
    "91": {
        "inputs": {"text": "low quality, blurry, static", "clip": ["90", 0]},
        "class_type": "CLIPTextEncode"
    },
    "92": {
        "inputs": {"vae_name": "wan_2.1_vae.safetensors"},
        "class_type": "VAELoader"
    },
    "93": {
        "inputs": {"shift": 8.0, "model": ["101", 0]},
        "class_type": "ModelSamplingSD3"
    },
    "94": {
        "inputs": {"shift": 8, "model": ["102", 0]},
        "class_type": "ModelSamplingSD3"
    },
    "95": {
        "inputs": {"add_noise": "disable", "noise_seed": 0, "steps": 4, "cfg": 3.5, "sampler_name": "euler", "scheduler": "simple", "start_at_step": 2, "end_at_step": 4, "return_with_leftover_noise": "disable", "model": ["94", 0], "positive": ["99", 0], "negative": ["91", 0], "latent_image": ["96", 0]},
        "class_type": "KSamplerAdvanced"
    },
    "96": {
        "inputs": {"add_noise": "enable", "noise_seed": 42, "steps": 4, "cfg": 3.5, "sampler_name": "euler", "scheduler": "simple", "start_at_step": 0, "end_at_step": 2, "return_with_leftover_noise": "enable", "model": ["93", 0], "positive": ["99", 0], "negative": ["91", 0], "latent_image": ["104", 0]},
        "class_type": "KSamplerAdvanced"
    },
    "97": {
        "inputs": {"samples": ["95", 0], "vae": ["92", 0]},
        "class_type": "VAEDecode"
    },
    "98": {
        "inputs": {"filename_prefix": "video/ComfyUI", "format": "auto", "codec": "auto", "video": ["100", 0]},
        "class_type": "SaveVideo"
    },
    "99": {
        "inputs": {"text": "A gentle slow zoom into a beautiful landscape with soft lighting.", "clip": ["90", 0]},
        "class_type": "CLIPTextEncode"
    },
    "100": {
        "inputs": {"fps": 16, "images": ["97", 0]},
        "class_type": "CreateVideo"
    },
    "101": {
        "inputs": {"unet_name": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", "weight_dtype": "default"},
        "class_type": "UNETLoader"
    },
    "102": {
        "inputs": {"unet_name": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors", "weight_dtype": "default"},
        "class_type": "UNETLoader"
    },
    "103": {
        "inputs": {"image": "benchmark_test.png", "upload": "image"},
        "class_type": "LoadImage"
    },
    "104": {
        "inputs": {"length": 17, "image": ["103", 0], "vae": ["92", 0]},
        "class_type": "Wan2.2ImageToVideoLatent"
    }
}
WORKFLOW_JSON

    # Write payload for comfyui-api-wrapper
    mkdir -p /opt/comfyui-api-wrapper/payloads
    cat > /opt/comfyui-api-wrapper/payloads/wan_2.2_i2v.json << EOF
{
    "input": {
        "request_id": "",
        "workflow_json": ${workflow_json}
    }
}
EOF

    # Wait for pyworker benchmark dir, then write benchmark
    local benchmark_dir="$WORKSPACE_DIR/vast-pyworker/workers/comfyui-json/misc"
    log "Waiting for pyworker benchmark dir..."
    local waited=0
    while [[ ! -d "$benchmark_dir" ]]; do
        sleep 2
        waited=$((waited + 2))
        if [[ $waited -ge 300 ]]; then
            log "[WARN] PyWorker dir not found after 300s, creating it"
            mkdir -p "$benchmark_dir"
            break
        fi
    done

    echo "$workflow_json" > "$benchmark_dir/benchmark.json"
    log "Benchmark written to $benchmark_dir/benchmark.json"
}

# Cleanup cron
set_cleanup_job() {
    local script_path="/opt/instance-tools/bin/clean-output.sh"
    mkdir -p "$(dirname "$script_path")"
    if [[ ! -f "$script_path" ]]; then
        cat > "$script_path" << 'EOF'
#!/bin/bash
output_dir="${WORKSPACE:-/workspace}/ComfyUI/output/"
available_space=$(df -m "${output_dir}" | awk 'NR==2 {print $4}')
if [[ "$available_space" -lt 512 ]]; then
    find "${output_dir}" -mindepth 1 -type f -mtime +1 -delete 2>/dev/null
    find "${output_dir}" -mindepth 1 -type d -empty -delete 2>/dev/null
fi
EOF
        chmod +x "$script_path"
    fi
    if ! crontab -l 2>/dev/null | grep -qF 'clean-output.sh'; then
        (crontab -l 2>/dev/null || true; echo "*/10 * * * * $script_path") | crontab -
    fi
}

main() {
    log "=== I2V Provisioning Start (models pre-baked via symlinks) ==="

    if [ -f /venv/main/bin/activate ]; then
        . /venv/main/bin/activate
    fi

    verify_models
    write_benchmark
    set_cleanup_job

    log "=== I2V Provisioning Complete ==="
}

main
