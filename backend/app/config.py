"""
Configuration management.
Loads settings from the project root's .env file.
"""

import os
from dotenv import load_dotenv

# Load .env from the project root.
# Path: MiroFish/.env (relative to backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # Fall back to reading environment variables directly (for production).
    load_dotenv(override=True)


class Config:
    """Flask configuration class"""

    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    # JSON settings: disable ASCII escaping so CJK chars render directly
    # (instead of \uXXXX escape sequences)
    JSON_AS_ASCII = False

    # LLM settings (OpenAI-compatible format)
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')

    # Per-step LLM overrides — each step can optionally use a different provider/model.
    # If not set, the step falls back to the primary LLM_* config above.

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

    # Path to the machine-readable provider catalogue maintained by the
    # /llm-provider-tracker skill. If present, providers listed here can
    # opt into multi-model sub-allocation (one account, many free models).
    LLM_PROVIDER_CATALOGUE_PATH = os.path.join(
        os.path.dirname(__file__), '..', 'data', 'llm_providers.json'
    )

    @classmethod
    def _load_provider_catalogue(cls) -> dict:
        """Load the multi-model catalogue. Returns {} on missing/invalid file."""
        import json
        path = cls.LLM_PROVIDER_CATALOGUE_PATH
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                doc = json.load(f)
            return doc.get('providers', {}) or {}
        except Exception:
            # Deliberately silent — missing/malformed catalogue falls back
            # to single-model behaviour, which is the safe default.
            return {}

    @classmethod
    def get_provider_pool(cls) -> list:
        """Return list of configured multi-provider entries.

        Each entry is a dict with:
            name, api_key, base_url, daily_token_budget (optional)
        PLUS one of:
            model: str                — single-model provider (legacy path)
            models: list[dict]        — multi-model provider. Each sub-dict:
                                        {id, daily_token_budget?, rpd?}
        Provider resolution order (first match wins):
            1. Catalogue (backend/data/llm_providers.json) for providers with
               >1 free_models entry → multi-model entry.
            2. LLM_<NAME>_MODELS env var (comma-separated) → multi-model entry
               with uniform/unknown quotas. Used for local providers (Ollama)
               where the catalogue is machine-specific.
            3. LLM_<NAME>_MODEL env var → single-model entry (legacy / default).

        Returns empty list if LLM_PROVIDERS is not set.
        """
        catalogue = cls._load_provider_catalogue()
        pool = []
        for name in cls.LLM_PROVIDERS:
            prefix = f'LLM_{name.upper()}_'
            api_key = os.environ.get(prefix + 'API_KEY')
            base_url = os.environ.get(prefix + 'BASE_URL')
            if not (api_key and base_url):
                continue

            budget_raw = os.environ.get(prefix + 'DAILY_TOKEN_BUDGET', '')
            try:
                account_budget = int(budget_raw) if budget_raw else None
            except ValueError:
                account_budget = None

            # ---- (1) Catalogue path: provider has a free_models list ----
            cat_entry = catalogue.get(name) or {}
            cat_models = cat_entry.get('free_models') or []
            if len(cat_models) >= 1:
                # Only use the catalogue base_url if the env one is absent;
                # respecting .env lets the user override for e.g. proxies.
                models = [
                    {
                        'id': m.get('id'),
                        'daily_token_budget': m.get('daily_token_budget'),
                        'rpd': m.get('rpd'),
                    }
                    for m in cat_models
                    if m.get('id')
                ]
                if models:
                    pool.append({
                        'name': name,
                        'api_key': api_key,
                        'base_url': base_url,
                        'models': models,
                        # Sum of per-model quotas where known; None if all unknown
                        'daily_token_budget': account_budget or (
                            sum(m['daily_token_budget'] for m in models if m.get('daily_token_budget'))
                            or None
                        ),
                        'source': 'catalogue',
                    })
                    continue

            # ---- (2) Env list path: LLM_<NAME>_MODELS=m1,m2,m3 ----
            models_raw = os.environ.get(prefix + 'MODELS', '')
            model_ids = [m.strip() for m in models_raw.split(',') if m.strip()]
            if len(model_ids) > 1:
                pool.append({
                    'name': name,
                    'api_key': api_key,
                    'base_url': base_url,
                    'models': [{'id': mid, 'daily_token_budget': None, 'rpd': None} for mid in model_ids],
                    'daily_token_budget': account_budget,  # account-level only
                    'source': 'env_list',
                })
                continue

            # ---- (3) Single-model legacy path ----
            model = os.environ.get(prefix + 'MODEL')
            if not model:
                # No models declared at all — skip incomplete block
                continue
            pool.append({
                'name': name,
                'api_key': api_key,
                'base_url': base_url,
                'model': model,
                'daily_token_budget': account_budget,
                'source': 'env_single',
            })
        return pool

    # Zep knowledge graph credentials
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')

    # File upload limits
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown', 'csv'}

    # Text chunking defaults (for the graph builder)
    DEFAULT_CHUNK_SIZE = 500   # default chunk size in characters
    DEFAULT_CHUNK_OVERLAP = 50  # default overlap between chunks

    # OASIS simulation config
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')

    # Platform-specific action sets exposed to OASIS agents
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]

    # Report Agent tuning
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    @classmethod
    def validate(cls):
        """Validate required configuration. Returns a list of error messages."""
        from .utils.locale import t
        errors = []
        if not cls.LLM_API_KEY:
            errors.append(t('backend.llmApiKeyMissing'))
        if not cls.ZEP_API_KEY:
            errors.append(t('backend.zepApiKeyMissing'))
        return errors
