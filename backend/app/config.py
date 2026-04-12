"""
配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
# 路径: MiroFish/.env (相对于 backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # 如果根目录没有 .env，尝试加载环境变量（用于生产环境）
    load_dotenv(override=True)


class Config:
    """Flask配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON配置 - 禁用ASCII转义，让中文直接显示（而不是 \uXXXX 格式）
    JSON_AS_ASCII = False
    
    # LLM配置（统一使用OpenAI格式）
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')

    # Per-step LLM overrides — each step can optionally use a different provider/model.
    # If not set, the step falls back to the primary LLM_* config above.
    # See docs/implementation_plan.md Phase 2 for rationale.

    # Step 1 — Ontology generation (benefits from large-context models like Gemini)
    LLM_ONTOLOGY_API_KEY = os.environ.get('LLM_ONTOLOGY_API_KEY')
    LLM_ONTOLOGY_BASE_URL = os.environ.get('LLM_ONTOLOGY_BASE_URL')
    LLM_ONTOLOGY_MODEL = os.environ.get('LLM_ONTOLOGY_MODEL')
    LLM_ONTOLOGY_MAX_TEXT_LENGTH = int(os.environ.get('LLM_ONTOLOGY_MAX_TEXT_LENGTH', '0')) or None

    # Step 2 — Agent persona generation (N parallel calls, benefits from cheap/fast JSON-capable models)
    LLM_PROFILES_API_KEY = os.environ.get('LLM_PROFILES_API_KEY')
    LLM_PROFILES_BASE_URL = os.environ.get('LLM_PROFILES_BASE_URL')
    LLM_PROFILES_MODEL = os.environ.get('LLM_PROFILES_MODEL')

    # Step 3 — Simulation config generation (small context, JSON output)
    LLM_CONFIG_API_KEY = os.environ.get('LLM_CONFIG_API_KEY')
    LLM_CONFIG_BASE_URL = os.environ.get('LLM_CONFIG_BASE_URL')
    LLM_CONFIG_MODEL = os.environ.get('LLM_CONFIG_MODEL')

    # Step 4 — Simulation (~90% of total tokens; must be free or near-free)
    # Passed through to the OASIS subprocess via environment variables.
    LLM_SIMULATION_API_KEY = os.environ.get('LLM_SIMULATION_API_KEY')
    LLM_SIMULATION_BASE_URL = os.environ.get('LLM_SIMULATION_BASE_URL')
    LLM_SIMULATION_MODEL = os.environ.get('LLM_SIMULATION_MODEL')

    # Step 5 — Report generation (ReACT loop, benefits from reasoning-capable models)
    LLM_REPORT_API_KEY = os.environ.get('LLM_REPORT_API_KEY')
    LLM_REPORT_BASE_URL = os.environ.get('LLM_REPORT_BASE_URL')
    LLM_REPORT_MODEL = os.environ.get('LLM_REPORT_MODEL')

    @classmethod
    def get_step_llm_config(cls, step: str) -> dict:
        """Return api_key/base_url/model for a pipeline step, falling back to primary LLM_* if any are unset.

        Args:
            step: one of 'ontology', 'profiles', 'config', 'simulation', 'report'

        Returns:
            dict with keys 'api_key', 'base_url', 'model'
        """
        step_upper = step.upper()
        api_key = os.environ.get(f'LLM_{step_upper}_API_KEY') or cls.LLM_API_KEY
        base_url = os.environ.get(f'LLM_{step_upper}_BASE_URL') or cls.LLM_BASE_URL
        model = os.environ.get(f'LLM_{step_upper}_MODEL') or cls.LLM_MODEL_NAME
        return {'api_key': api_key, 'base_url': base_url, 'model': model}

    # LLM resilience settings
    LLM_MAX_RETRIES = int(os.environ.get('LLM_MAX_RETRIES', '3'))
    LLM_RETRY_BASE_DELAY = float(os.environ.get('LLM_RETRY_BASE_DELAY', '2.0'))
    LLM_FALLBACK_MODELS = [
        m.strip() for m in os.environ.get('LLM_FALLBACK_MODELS', '').split(',') if m.strip()
    ]

    # -------------------- Phase 4: Multi-Provider Pool --------------------
    # Enables spreading LLM load across multiple free-tier providers.
    # Set LLM_PROVIDERS=groq,google,ollama then add per-provider blocks:
    #   LLM_GROQ_API_KEY, LLM_GROQ_BASE_URL, LLM_GROQ_MODEL
    #   LLM_GROQ_DAILY_TOKEN_BUDGET (optional, informational)
    # Each provider name is uppercased and looked up at runtime.
    # If unset, the app uses the single LLM_* config above.
    LLM_PROVIDERS = [
        p.strip().lower() for p in os.environ.get('LLM_PROVIDERS', '').split(',') if p.strip()
    ]

    @classmethod
    def get_provider_pool(cls) -> list:
        """Return list of configured multi-provider entries.

        Each entry is a dict with: name, api_key, base_url, model, daily_token_budget (optional).
        Returns empty list if LLM_PROVIDERS is not set.
        """
        pool = []
        for name in cls.LLM_PROVIDERS:
            prefix = f'LLM_{name.upper()}_'
            api_key = os.environ.get(prefix + 'API_KEY')
            base_url = os.environ.get(prefix + 'BASE_URL')
            model = os.environ.get(prefix + 'MODEL')
            if not (api_key and base_url and model):
                # Incomplete provider block — skip with a warning
                continue
            budget_raw = os.environ.get(prefix + 'DAILY_TOKEN_BUDGET', '')
            try:
                daily_budget = int(budget_raw) if budget_raw else None
            except ValueError:
                daily_budget = None
            pool.append({
                'name': name,
                'api_key': api_key,
                'base_url': base_url,
                'model': model,
                'daily_token_budget': daily_budget,
            })
        return pool
    
    # Zep配置
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown', 'csv'}
    
    # 文本处理配置
    DEFAULT_CHUNK_SIZE = 500  # 默认切块大小
    DEFAULT_CHUNK_OVERLAP = 50  # 默认重叠大小
    
    # OASIS模拟配置
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS平台可用动作配置
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent配置
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    @classmethod
    def validate(cls):
        """验证必要配置"""
        from .utils.locale import t
        errors = []
        if not cls.LLM_API_KEY:
            errors.append(t('backend.llmApiKeyMissing'))
        if not cls.ZEP_API_KEY:
            errors.append(t('backend.zepApiKeyMissing'))
        return errors

