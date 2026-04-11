#!/bin/sh
# MiroFish Setup Wizard
# Creates .env configuration and launches Docker

set -e

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║          MiroFish Setup Wizard                   ║"
echo "║  Multi-Agent Prediction & Simulation Engine      ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Check Docker is available
if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: Docker is not installed or not in PATH."
    echo "Install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "ERROR: Docker daemon is not running. Please start Docker."
    exit 1
fi

echo "Docker detected. Let's configure your LLM and memory providers."
echo ""

# --- LLM Provider ---
echo "┌─────────────────────────────────────────────────┐"
echo "│ Step 1: LLM Provider                            │"
echo "├─────────────────────────────────────────────────┤"
echo "│ 1) OpenRouter (free models available)           │"
echo "│ 2) OpenAI                                       │"
echo "│ 3) Google Gemini (generous free tier)           │"
echo "│ 4) DeepSeek (cheapest paid)                     │"
echo "│ 5) Anthropic Claude                             │"
echo "│ 6) Grok (xAI)                                  │"
echo "│ 7) Alibaba DashScope / Qwen                    │"
echo "│ 8) Kimi / Moonshot                             │"
echo "│ 9) Custom (enter your own base URL)             │"
echo "└─────────────────────────────────────────────────┘"
printf "Select provider [1]: "
read -r PROVIDER_CHOICE
PROVIDER_CHOICE=${PROVIDER_CHOICE:-1}

case "$PROVIDER_CHOICE" in
    1)
        LLM_BASE_URL="https://openrouter.ai/api/v1"
        DEFAULT_MODEL="google/gemma-4-31b-it:free"
        FALLBACK_MODELS="meta-llama/llama-3.3-70b-instruct:free,nousresearch/hermes-3-llama-3.1-405b:free,nvidia/nemotron-3-super-120b-a12b:free,openrouter/free"
        echo ""
        echo "  OpenRouter selected. Free models available."
        echo "  Get your API key at: https://openrouter.ai/keys"
        ;;
    2)
        LLM_BASE_URL="https://api.openai.com/v1"
        DEFAULT_MODEL="gpt-4o-mini"
        FALLBACK_MODELS=""
        echo ""
        echo "  OpenAI selected."
        echo "  Get your API key at: https://platform.openai.com/api-keys"
        ;;
    3)
        LLM_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"
        DEFAULT_MODEL="gemini-2.5-flash"
        FALLBACK_MODELS=""
        echo ""
        echo "  Google Gemini selected."
        echo "  Get your API key at: https://aistudio.google.com/apikey"
        ;;
    4)
        LLM_BASE_URL="https://api.deepseek.com/v1"
        DEFAULT_MODEL="deepseek-chat"
        FALLBACK_MODELS=""
        echo ""
        echo "  DeepSeek selected."
        echo "  Get your API key at: https://platform.deepseek.com/api_keys"
        ;;
    5)
        LLM_BASE_URL="https://api.anthropic.com/v1/"
        DEFAULT_MODEL="claude-sonnet-4-20250514"
        FALLBACK_MODELS=""
        echo ""
        echo "  Anthropic Claude selected."
        echo "  Note: may not support response_format (JSON mode)."
        echo "  Get your API key at: https://console.anthropic.com/settings/keys"
        ;;
    6)
        LLM_BASE_URL="https://api.x.ai/v1"
        DEFAULT_MODEL="grok-3-mini"
        FALLBACK_MODELS=""
        echo ""
        echo "  Grok (xAI) selected."
        echo "  Get your API key at: https://console.x.ai"
        ;;
    7)
        LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
        DEFAULT_MODEL="qwen-plus"
        FALLBACK_MODELS=""
        echo ""
        echo "  Alibaba DashScope selected."
        echo "  Get your API key at: https://bailian.console.aliyun.com/"
        ;;
    8)
        LLM_BASE_URL="https://api.moonshot.cn/v1"
        DEFAULT_MODEL="moonshot-v1-8k"
        FALLBACK_MODELS=""
        echo ""
        echo "  Kimi / Moonshot selected."
        echo "  Get your API key at: https://platform.moonshot.cn/console/api-keys"
        ;;
    9)
        printf "  Enter base URL: "
        read -r LLM_BASE_URL
        DEFAULT_MODEL=""
        FALLBACK_MODELS=""
        ;;
    *)
        echo "Invalid choice. Defaulting to OpenRouter."
        LLM_BASE_URL="https://openrouter.ai/api/v1"
        DEFAULT_MODEL="google/gemma-4-31b-it:free"
        FALLBACK_MODELS="meta-llama/llama-3.3-70b-instruct:free,nousresearch/hermes-3-llama-3.1-405b:free,nvidia/nemotron-3-super-120b-a12b:free,openrouter/free"
        ;;
esac

echo ""
printf "Enter your LLM API key: "
read -r LLM_API_KEY

if [ -z "$LLM_API_KEY" ]; then
    echo "ERROR: API key is required."
    exit 1
fi

printf "Model name [%s]: " "$DEFAULT_MODEL"
read -r LLM_MODEL_NAME
LLM_MODEL_NAME=${LLM_MODEL_NAME:-$DEFAULT_MODEL}

# --- Zep Cloud ---
echo ""
echo "┌─────────────────────────────────────────────────┐"
echo "│ Step 2: Zep Cloud (Memory / Knowledge Graph)    │"
echo "├─────────────────────────────────────────────────┤"
echo "│ Free tier is sufficient for basic usage.        │"
echo "│ Sign up at: https://app.getzep.com/             │"
echo "└─────────────────────────────────────────────────┘"
printf "Enter your Zep API key: "
read -r ZEP_API_KEY

if [ -z "$ZEP_API_KEY" ]; then
    echo "ERROR: Zep API key is required."
    exit 1
fi

# --- Write .env ---
echo ""
echo "Writing .env configuration..."

cat > .env << ENVEOF
# MiroFish Configuration (generated by setup wizard)
LLM_API_KEY=${LLM_API_KEY}
LLM_BASE_URL=${LLM_BASE_URL}
LLM_MODEL_NAME=${LLM_MODEL_NAME}

# Fallback models (OpenRouter only)
LLM_FALLBACK_MODELS=${FALLBACK_MODELS}

# Resilience
LLM_MAX_RETRIES=3
LLM_RETRY_BASE_DELAY=2.0

# Zep Cloud
ZEP_API_KEY=${ZEP_API_KEY}
ENVEOF

echo "  .env written successfully."

# --- Build and launch ---
echo ""
echo "┌─────────────────────────────────────────────────┐"
echo "│ Step 3: Build & Launch                          │"
echo "├─────────────────────────────────────────────────┤"
echo "│ Building optimised Docker image (first time     │"
echo "│ takes 3-5 minutes, subsequent starts are fast)  │"
echo "└─────────────────────────────────────────────────┘"
echo ""

docker compose -f docker-compose.slim.yml up -d --build

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  MiroFish is ready!                              ║"
echo "║                                                  ║"
echo "║  Open in browser: http://localhost:3000           ║"
echo "║                                                  ║"
echo "║  Commands:                                       ║"
echo "║    Stop:    docker compose -f docker-compose.slim.yml down    ║"
echo "║    Logs:    docker compose -f docker-compose.slim.yml logs -f ║"
echo "║    Restart: docker compose -f docker-compose.slim.yml restart ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
