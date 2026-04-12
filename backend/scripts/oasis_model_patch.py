"""
OASIS Per-Agent Model Patch (Phase 6)

Monkey-patches `oasis.social_agent.agents_generator` so that each
SocialAgent gets its own BaseModelBackend instance drawn from an
agent-to-provider assignment written by the parent process.

Activated by setting env var:
    MIROFISH_AGENT_MODEL_ASSIGNMENTS=/path/to/agent_model_assignments.json

No-op if the env var is not set — in that case OASIS falls back to
single-model behaviour (the original design).

The patch wraps two functions:
    - oasis.social_agent.agents_generator.generate_reddit_agent_graph
    - oasis.social_agent.agents_generator.generate_twitter_agent_graph

Both functions build a SocialAgent per row of profile data. The wrapped
version checks the assignment map for each agent_id and, if found,
creates a fresh camel-ai OpenAI model backend keyed to that agent's
provider config. The original function is then called with per-agent
`model_factory` replacement.

Note: this touches camel-ai / openai internals. It has been designed
defensively — if anything goes wrong, the patch logs an error and
falls through to the original (single-model) behaviour so the
simulation never fails because of multi-provider mode.
"""

import json
import logging
import os
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_installed = False
_assignments: Dict[str, Dict[str, Any]] = {}
_provider_models: Dict[str, Any] = {}  # cache: provider_name -> model backend


def _load_assignments(path: str) -> Dict[str, Dict[str, Any]]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            doc = json.load(f)
        return doc.get('assignments', {})
    except Exception as e:
        print(f'[oasis_model_patch] failed to load assignments: {e}', file=sys.stderr)
        return {}


def _build_model_for_provider(entry: Dict[str, Any]):
    """Create a camel-ai OpenAI-compatible model backend for a provider entry.

    Uses caching so agents sharing a provider share a model backend
    instance (saves memory; harmless because ChatAgent state is per-agent).
    """
    key = f"{entry.get('base_url')}||{entry.get('model')}"
    if key in _provider_models:
        return _provider_models[key]

    from camel.models import ModelFactory
    from camel.types import ModelPlatformType

    # Set env vars that camel-ai reads
    os.environ['OPENAI_API_KEY'] = entry['api_key']
    os.environ['OPENAI_API_BASE_URL'] = entry['base_url']

    model_backend = ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI,
        model_type=entry['model'],
    )
    _provider_models[key] = model_backend
    return model_backend


def _make_reddit_wrapper(original):
    """Wraps generate_reddit_agent_graph.

    Reads the profile JSON itself, builds per-agent model backends, and
    manually constructs the AgentGraph bypassing the original's single-model
    loop. Falls back to the original function on any error.
    """
    async def wrapped(
        profile_path,
        model=None,
        available_actions=None,
    ):
        if not _assignments:
            return await original(profile_path, model, available_actions)
        try:
            import json as _json
            from oasis.social_agent import AgentGraph, SocialAgent
            from oasis.social_platform.config import UserInfo

            with open(profile_path, 'r') as f:
                agent_info = _json.load(f)

            agent_graph = AgentGraph()

            for i in range(len(agent_info)):
                assignment = _assignments.get(str(i))
                if assignment:
                    per_agent_model = _build_model_for_provider(assignment)
                else:
                    per_agent_model = model  # fall back to shared

                # Phase 7.16: the persona string already includes the Big Five /
                # org archetype narrative appended by OasisProfileGenerator, so it
                # reaches the agent via the existing user_profile injection path
                # in oasis.social_platform.config.user.UserInfo.to_reddit_system_message.
                # The mbti/age/gender/country fields below are legacy display
                # fields that OASIS's built-in Reddit template also consumes —
                # kept for compatibility.
                profile = {
                    'nodes': [],
                    'edges': [],
                    'other_info': {
                        'user_profile': agent_info[i]['persona'],
                        'mbti': agent_info[i].get('mbti', 'ISTJ'),
                        'gender': agent_info[i].get('gender', 'other'),
                        'age': agent_info[i].get('age', 30),
                        'country': agent_info[i].get('country', 'Australia'),
                    },
                }
                user_info = UserInfo(
                    name=agent_info[i]['username'],
                    description=agent_info[i]['bio'],
                    profile=profile,
                    recsys_type='reddit',
                )
                agent = SocialAgent(
                    agent_id=i,
                    user_info=user_info,
                    agent_graph=agent_graph,
                    model=per_agent_model,
                    available_actions=available_actions,
                )
                agent_graph.add_agent(agent)

            print(
                f'[oasis_model_patch] generate_reddit_agent_graph: assigned per-agent '
                f'models for {len(agent_info)} agents'
            )
            return agent_graph
        except Exception as e:
            print(f'[oasis_model_patch] reddit wrapper failed, falling back: {e}', file=sys.stderr)
            return await original(profile_path, model, available_actions)

    return wrapped


def _make_twitter_wrapper(original):
    """Wraps generate_twitter_agent_graph similarly."""
    async def wrapped(
        profile_path,
        model=None,
        available_actions=None,
    ):
        if not _assignments:
            return await original(profile_path, model, available_actions)
        try:
            import pandas as pd
            from oasis.social_agent import AgentGraph, SocialAgent
            from oasis.social_platform.config import UserInfo

            agent_info = pd.read_csv(profile_path)
            agent_graph = AgentGraph()

            for agent_id in range(len(agent_info)):
                assignment = _assignments.get(str(agent_id))
                if assignment:
                    per_agent_model = _build_model_for_provider(assignment)
                else:
                    per_agent_model = model

                profile = {
                    'nodes': [],
                    'edges': [],
                    'other_info': {
                        'user_profile': agent_info['user_char'][agent_id],
                    },
                }
                user_info = UserInfo(
                    name=agent_info['username'][agent_id],
                    description=agent_info['description'][agent_id],
                    profile=profile,
                    recsys_type='twitter',
                )
                agent = SocialAgent(
                    agent_id=agent_id,
                    user_info=user_info,
                    model=per_agent_model,
                    agent_graph=agent_graph,
                    available_actions=available_actions,
                )
                agent_graph.add_agent(agent)

            print(
                f'[oasis_model_patch] generate_twitter_agent_graph: assigned per-agent '
                f'models for {len(agent_info)} agents'
            )
            return agent_graph
        except Exception as e:
            print(f'[oasis_model_patch] twitter wrapper failed, falling back: {e}', file=sys.stderr)
            return await original(profile_path, model, available_actions)

    return wrapped


def install() -> None:
    """Install the per-agent model patch. Safe to call multiple times."""
    global _installed, _assignments

    if _installed:
        return

    assignments_path = os.environ.get('MIROFISH_AGENT_MODEL_ASSIGNMENTS')
    if not assignments_path:
        return

    _assignments = _load_assignments(assignments_path)
    if not _assignments:
        print('[oasis_model_patch] no assignments loaded; patch not installed', file=sys.stderr)
        return

    try:
        import oasis.social_agent.agents_generator as gen_module
    except ImportError:
        print('[oasis_model_patch] oasis package not available; skipping', file=sys.stderr)
        return

    original_reddit = gen_module.generate_reddit_agent_graph
    original_twitter = gen_module.generate_twitter_agent_graph

    gen_module.generate_reddit_agent_graph = _make_reddit_wrapper(original_reddit)
    gen_module.generate_twitter_agent_graph = _make_twitter_wrapper(original_twitter)

    # Also patch the oasis module-level re-exports if they exist
    try:
        import oasis
        if hasattr(oasis, 'generate_reddit_agent_graph'):
            oasis.generate_reddit_agent_graph = gen_module.generate_reddit_agent_graph
        if hasattr(oasis, 'generate_twitter_agent_graph'):
            oasis.generate_twitter_agent_graph = gen_module.generate_twitter_agent_graph
    except ImportError:
        pass

    providers_used = set(a.get('provider') for a in _assignments.values())
    print(
        f'[oasis_model_patch] installed; {len(_assignments)} agents routed '
        f'across {len(providers_used)} providers: {sorted(providers_used)}',
        file=sys.stderr,
    )
    _installed = True
