"""
LLM client wrapper
统一使用OpenAI格式调用，带重试、退避和备用模型支持
"""

import json
import logging
import re
import time
from typing import Optional, Dict, Any, List
from openai import OpenAI, RateLimitError, APIStatusError, APITimeoutError, APIConnectionError

from ..config import Config
from .locale import t
from .token_tracker import TokenTracker
from .capability_detector import supports_json_mode

logger = logging.getLogger(__name__)

# Transient errors worth retrying
_RETRYABLE_EXCEPTIONS = (RateLimitError, APITimeoutError, APIConnectionError)
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class LLMClient:
    """LLM client with retry, backoff, and fallback model support"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        self.max_retries = Config.LLM_MAX_RETRIES
        self.retry_base_delay = Config.LLM_RETRY_BASE_DELAY
        self.fallback_models = Config.LLM_FALLBACK_MODELS

        if not self.api_key:
            raise ValueError(t('backend.llmApiKeyMissing'))

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def _is_retryable(self, error: Exception) -> bool:
        """Check if an error is transient and worth retrying."""
        if isinstance(error, _RETRYABLE_EXCEPTIONS):
            return True
        if isinstance(error, APIStatusError) and error.status_code in _RETRYABLE_STATUS_CODES:
            return True
        return False

    def _call_with_retry(self, model: str, kwargs: dict) -> Any:
        """Call the API with exponential backoff retries for a single model."""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                kwargs["model"] = model
                response = self.client.chat.completions.create(**kwargs)
                if attempt > 0:
                    logger.info(t('backend.llmRetrySuccess', attempt=attempt + 1, model=model))
                # Record token usage if available (OpenAI-compatible responses include .usage)
                try:
                    usage = getattr(response, 'usage', None)
                    if usage is not None:
                        input_tokens = getattr(usage, 'prompt_tokens', 0) or 0
                        output_tokens = getattr(usage, 'completion_tokens', 0) or 0
                        TokenTracker.record_usage(
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            model=model,
                            base_url=self.base_url,
                        )
                except Exception as track_err:
                    logger.debug(f"Token tracking failed (non-fatal): {track_err}")
                return response
            except Exception as e:
                last_error = e
                if not self._is_retryable(e):
                    logger.warning(t('backend.llmNonRetryableError', model=model, error=f"{type(e).__name__}: {e}"))
                    raise
                delay = self.retry_base_delay * (2 ** attempt)
                logger.warning(
                    t('backend.llmRetryableError', model=model, attempt=attempt + 1, max=self.max_retries,
                      error=f"{type(e).__name__}: {e}", delay=f"{delay:.1f}")
                )
                time.sleep(delay)
        raise last_error

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        发送聊天请求，带重试和备用模型支持

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            response_format: 响应格式（如JSON模式）

        Returns:
            模型响应文本
        """
        kwargs = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            kwargs["response_format"] = response_format

        # Build model list: primary first, then fallbacks
        models_to_try = [self.model] + [m for m in self.fallback_models if m != self.model]

        last_error = None
        for model in models_to_try:
            try:
                response = self._call_with_retry(model, kwargs)
                content = response.choices[0].message.content
                # Some models (e.g. MiniMax M2.5) include <think> blocks in content
                content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
                return content
            except Exception as e:
                last_error = e
                if len(models_to_try) > 1:
                    logger.warning(t('backend.llmModelFailed', model=model, error=f"{type(e).__name__}: {e}"))
                continue

        logger.error(t('backend.llmAllModelsFailed', error=str(last_error)))
        raise last_error

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Send a chat request and return parsed JSON.

        Automatically detects whether the provider supports OpenAI's
        response_format=json_object parameter. If not (Anthropic, some
        Grok models, etc.), falls back to a prompt-based JSON extraction
        that appends a "respond in JSON only" instruction to the system
        message.

        Args:
            messages: message list
            temperature: sampling temperature
            max_tokens: max output tokens

        Returns:
            Parsed JSON object
        """
        use_native_json = supports_json_mode(self.api_key, self.base_url, self.model)

        if use_native_json:
            response = self.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
        else:
            # Prompt-based JSON extraction for providers without response_format support
            logger.info(f"Provider {self.base_url} does not support response_format; using prompt-based JSON")
            augmented_messages = _augment_messages_for_json(messages)
            response = self.chat(
                messages=augmented_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=None,
            )

        # Clean markdown code block markers (even native JSON mode sometimes wraps in fences)
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        # If the response contains text around JSON, try to extract the first {...} block
        if not cleaned_response.startswith('{') and not cleaned_response.startswith('['):
            json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', cleaned_response)
            if json_match:
                cleaned_response = json_match.group(1)

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            logger.error(f"LLM returned invalid JSON: {cleaned_response[:500]}")
            raise ValueError(t('backend.llmInvalidJson', response=cleaned_response))


def _augment_messages_for_json(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Add a JSON instruction to the system message (or prepend one if absent)."""
    suffix = (
        "\n\nIMPORTANT: Respond with ONLY valid JSON. No prose, no markdown fences, "
        "no explanations. Start your response with { and end with }."
    )
    augmented = []
    system_found = False
    for msg in messages:
        if msg.get('role') == 'system' and not system_found:
            augmented.append({**msg, 'content': msg.get('content', '') + suffix})
            system_found = True
        else:
            augmented.append(msg)
    if not system_found:
        augmented.insert(0, {
            'role': 'system',
            'content': 'Respond with ONLY valid JSON. Start with { and end with }.'
        })
    return augmented
