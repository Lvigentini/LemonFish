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
echo "│  1) OpenRouter (free models available)          │"
echo "│  2) OpenAI                                      │"
echo "│  3) Google Gemini (generous free tier)          │"
echo "│  4) Groq (fast free tier, renewable daily)      │"
echo "│  5) DeepSeek (very cheap paid)                  │"
echo "│  6) Anthropic Claude                            │"
echo "│  7) Grok (xAI)                                  │"
echo "│  8) Alibaba DashScope / Qwen                    │"
echo "│  9) Kimi / Moonshot                             │"
echo "│ 10) Ollama (local, no API key needed)           │"
echo "│ 11) Custom (enter your own base URL)            │"
echo "└─────────────────────────────────────────────────┘"
printf "Select provider [1]: "
read -r PROVIDER_CHOICE
PROVIDER_CHOICE=${PROVIDER_CHOICE:-1}

case "$PROVIDER_CHOICE" in
    1)
        LLM_BASE_URL="https://openrouter.ai/api/v1"
        DEFAULT_MODEL="meta-llama/llama-3.3-70b-instruct:free"
        FALLBACK_MODELS="nousresearch/hermes-3-llama-3.1-405b:free,qwen/qwen3-235b-a22b:free,deepseek/deepseek-chat:free,openrouter/free"
        echo ""
        echo "  OpenRouter selected. Free models available."
        echo "  Get your API key at: https://openrouter.ai/keys"
        ;;
    2)
        LLM_BASE_URL="https://api.openai.com/v1"
        DEFAULT_MODEL="gpt-5-nano"
        FALLBACK_MODELS=""
        echo ""
        echo "  OpenAI selected (default: gpt-5-nano, cheapest tier)."
        echo "  Get your API key at: https://platform.openai.com/api-keys"
        ;;
    3)
        LLM_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"
        DEFAULT_MODEL="gemini-3-flash-preview"
        FALLBACK_MODELS=""
        echo ""
        echo "  Google Gemini selected (default: gemini-3-flash-preview, 1M context)."
        echo "  Get your API key at: https://aistudio.google.com/apikey"
        ;;
    4)
        LLM_BASE_URL="https://api.groq.com/openai/v1"
        DEFAULT_MODEL="llama-3.1-8b-instant"
        FALLBACK_MODELS="qwen/qwen3-32b,moonshotai/kimi-k2-instruct,openai/gpt-oss-20b,openai/gpt-oss-120b"
        echo ""
        echo "  Groq selected (default: llama-3.1-8b-instant, 500K tokens/day free)."
        echo "  Get your API key at: https://console.groq.com/keys"
        ;;
    5)
        LLM_BASE_URL="https://api.deepseek.com/v1"
        DEFAULT_MODEL="deepseek-chat"
        FALLBACK_MODELS=""
        echo ""
        echo "  DeepSeek selected (\$0.28/M input, \$0.42/M output)."
        echo "  Get your API key at: https://platform.deepseek.com/api_keys"
        ;;
    6)
        LLM_BASE_URL="https://api.anthropic.com/v1/"
        DEFAULT_MODEL="claude-sonnet-4-6"
        FALLBACK_MODELS=""
        echo ""
        echo "  Anthropic Claude selected (default: claude-sonnet-4-6)."
        echo "  Note: may not support response_format (JSON mode)."
        echo "  Get your API key at: https://console.anthropic.com/settings/keys"
        ;;
    7)
        LLM_BASE_URL="https://api.x.ai/v1"
        DEFAULT_MODEL="grok-4-1-fast-non-reasoning"
        FALLBACK_MODELS=""
        echo ""
        echo "  Grok (xAI) selected."
        echo "  Get your API key at: https://console.x.ai"
        ;;
    8)
        LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
        DEFAULT_MODEL="qwen-flash"
        FALLBACK_MODELS=""
        echo ""
        echo "  Alibaba DashScope selected (default: qwen-flash, \$0.05/M input)."
        echo "  Get your API key at: https://bailian.console.aliyun.com/"
        ;;
    9)
        LLM_BASE_URL="https://api.moonshot.cn/v1"
        DEFAULT_MODEL="moonshot-v1-8k"
        FALLBACK_MODELS=""
        echo ""
        echo "  Kimi / Moonshot selected."
        echo "  Get your API key at: https://platform.moonshot.cn/console/api-keys"
        ;;
    10)
        LLM_BASE_URL="http://host.docker.internal:11434/v1"
        DEFAULT_MODEL="llama3.2"
        FALLBACK_MODELS=""
        echo ""
        echo "  Ollama selected. Make sure Ollama is running on the host with at least one model pulled."
        echo "  Install Ollama: https://ollama.com/download"
        echo "  Pull a model:  ollama pull llama3.2 (or gemma2:9b, qwen2.5, etc.)"
        echo "  Note: API key will be set to 'ollama' (Ollama does not require one)."
        ;;
    11)
        printf "  Enter base URL: "
        read -r LLM_BASE_URL
        DEFAULT_MODEL=""
        FALLBACK_MODELS=""
        ;;
    *)
        echo "Invalid choice. Defaulting to OpenRouter."
        LLM_BASE_URL="https://openrouter.ai/api/v1"
        DEFAULT_MODEL="meta-llama/llama-3.3-70b-instruct:free"
        FALLBACK_MODELS="nousresearch/hermes-3-llama-3.1-405b:free,qwen/qwen3-235b-a22b:free,deepseek/deepseek-chat:free,openrouter/free"
        ;;
esac

echo ""
if [ "$PROVIDER_CHOICE" = "10" ]; then
    LLM_API_KEY="ollama"
    echo "Using 'ollama' as API key placeholder (Ollama does not require one)."
else
    printf "Enter your LLM API key: "
    read -r LLM_API_KEY

    if [ -z "$LLM_API_KEY" ]; then
        echo "ERROR: API key is required."
        exit 1
    fi
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

# --- Optional: Phase 8 research-from-prompt module ---
echo ""
echo "┌─────────────────────────────────────────────────┐"
echo "│ Step 3: Research module (optional)              │"
echo "├─────────────────────────────────────────────────┤"
echo "│ Enables Step 0 'research from prompt' as an     │"
echo "│ alternative to uploading documents. Uses CLI    │"
echo "│ tools (claude/codex/kimi) or an API fallback.   │"
echo "│ Default: API fallback only.                     │"
echo "└─────────────────────────────────────────────────┘"
printf "Enable research module? [y/N]: "
read -r RESEARCH_CHOICE
case "$RESEARCH_CHOICE" in
    [yY]|[yY][eE][sS])
        RESEARCH_ENABLED="true"
        echo ""
        echo "  Research module enabled."
        echo "  To use the local CLI runners (claude/codex/kimi) instead of the API"
        echo "  fallback, launch with the research compose overlay:"
        echo "    docker compose -f docker-compose.slim.yml -f docker-compose.research.yml up -d"
        echo "  This mounts your ~/.claude, ~/.codex, ~/.config/kimi config dirs into"
        echo "  the container so the CLIs can find their cached OAuth tokens."
        ;;
    *)
        RESEARCH_ENABLED="false"
        ;;
esac

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

# Phase 8 — Research-from-prompt module (opt-in)
RESEARCH_ENABLED=${RESEARCH_ENABLED}
RESEARCH_RUNNERS=api
RESEARCH_DEFAULT_RUNNER=api
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
