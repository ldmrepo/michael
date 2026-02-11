FROM vastai/comfy:v0.12.3-cuda-12.9-py312

# Vast.ai boot process: /opt/workspace-internal/ is copied to /workspace/ on first boot.
# Large models go to /opt/comfyui-models/ and we symlink from workspace-internal
# to avoid duplication (symlinks are preserved during the copy).

# Create staging directory for models
RUN mkdir -p /opt/comfyui-models/text_encoders \
    && mkdir -p /opt/comfyui-models/vae \
    && mkdir -p /opt/comfyui-models/diffusion_models \
    && mkdir -p /opt/comfyui-models/loras

# Download text encoder (~4.5GB)
RUN wget -q -O /opt/comfyui-models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors \
    "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"

# Download VAE (~0.3GB)
RUN wget -q -O /opt/comfyui-models/vae/wan_2.1_vae.safetensors \
    "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors"

# Download I2V high noise diffusion model (~14.5GB)
RUN wget -q -O /opt/comfyui-models/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors \
    "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"

# Download I2V low noise diffusion model (~14.5GB)
RUN wget -q -O /opt/comfyui-models/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors \
    "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"

# Download I2V LoRAs (~100MB each)
RUN wget -q -O /opt/comfyui-models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors \
    "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"

RUN wget -q -O /opt/comfyui-models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors \
    "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors"

# Create symlinks in workspace-internal (these get copied to /workspace on boot)
# The model dirs in workspace-internal/ComfyUI/models/ should already exist from base image
RUN for f in /opt/comfyui-models/text_encoders/*.safetensors; do \
        ln -sf "$f" /opt/workspace-internal/ComfyUI/models/text_encoders/$(basename "$f"); \
    done \
    && for f in /opt/comfyui-models/vae/*.safetensors; do \
        ln -sf "$f" /opt/workspace-internal/ComfyUI/models/vae/$(basename "$f"); \
    done \
    && for f in /opt/comfyui-models/diffusion_models/*.safetensors; do \
        ln -sf "$f" /opt/workspace-internal/ComfyUI/models/diffusion_models/$(basename "$f"); \
    done \
    && for f in /opt/comfyui-models/loras/*.safetensors; do \
        ln -sf "$f" /opt/workspace-internal/ComfyUI/models/loras/$(basename "$f"); \
    done

# Generate test image for I2V benchmark
RUN python3 -c "from PIL import Image; img=Image.new('RGB',(640,640),(100,150,200)); img.save('/opt/workspace-internal/ComfyUI/input/benchmark_test.png')"

# Copy provisioning script
COPY provision-i2v.sh /opt/provision-i2v.sh
RUN chmod +x /opt/provision-i2v.sh
