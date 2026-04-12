"""
Token Usage Estimator
Predicts LLM token consumption for a simulation before it runs.

Based on the formula in docs/llm_budget_planning.md, derived from
measuring actual prompt templates in the codebase.

Formula:
    Total ~ 1,160 * R * N  +  2,700 * N  +  41,400 * S  +  D/2  +  18,400

Where:
    N = number of agents
    R = simulation rounds
    D = document characters (used in ontology step)
    S = report sections
"""

import math
from typing import Dict, Any


# Per-step coefficients (empirically derived — see docs/llm_budget_planning.md)
ONTOLOGY_BASE = 2800
ONTOLOGY_PER_CHAR = 0.5  # half a token per input char (rough Chinese+English avg)
ONTOLOGY_OUTPUT = 2000

PROFILES_PER_AGENT = 2700  # ~1200 input + ~1500 output per persona

CONFIG_BASE = 10300
CONFIG_PER_BATCH = 3580  # one batch per 15 agents

SIMULATION_PER_ACTION = 2900  # ~2700 input + ~200 output
SIMULATION_ACTIVE_RATIO = 0.4  # average fraction of agents active per round

REPORT_OUTLINE = 2300
REPORT_PER_SECTION = 41400  # ReACT loop with tool calls


def estimate(
    agents: int,
    rounds: int,
    document_chars: int,
    report_sections: int = 4,
) -> Dict[str, Any]:
    """Estimate token consumption for a simulation run.

    Args:
        agents: number of AI agents (N)
        rounds: simulation rounds (R)
        document_chars: total characters in seed documents (D)
        report_sections: sections in final report (S, default 4)

    Returns:
        dict with per-step estimates and grand total, plus human-readable summary.
    """
    # Cap document_chars at the ontology truncation limit
    effective_doc_chars = min(document_chars, 50000)

    # Step 1: Ontology
    ontology_tokens = int(ONTOLOGY_BASE + effective_doc_chars * ONTOLOGY_PER_CHAR + ONTOLOGY_OUTPUT)

    # Step 2: Profiles
    profile_tokens = agents * PROFILES_PER_AGENT

    # Step 3: Config
    config_batches = math.ceil(agents / 15)
    config_tokens = CONFIG_BASE + config_batches * CONFIG_PER_BATCH

    # Step 4: Simulation (dominant cost)
    avg_active = int(round(agents * SIMULATION_ACTIVE_RATIO))
    simulation_calls = rounds * avg_active
    simulation_tokens = simulation_calls * SIMULATION_PER_ACTION

    # Step 5: Report
    report_tokens = REPORT_OUTLINE + report_sections * REPORT_PER_SECTION + 3000  # interview overhead

    total = ontology_tokens + profile_tokens + config_tokens + simulation_tokens + report_tokens

    return {
        'inputs': {
            'agents': agents,
            'rounds': rounds,
            'document_chars': document_chars,
            'effective_document_chars': effective_doc_chars,
            'report_sections': report_sections,
        },
        'per_step': {
            'ontology': {
                'tokens': ontology_tokens,
                'calls': 1,
                'notes': f'Document capped at {effective_doc_chars:,} chars for input',
            },
            'profiles': {
                'tokens': profile_tokens,
                'calls': agents,
                'notes': f'One call per agent',
            },
            'config': {
                'tokens': config_tokens,
                'calls': 2 + config_batches,
                'notes': f'2 base calls + {config_batches} agent config batches',
            },
            'simulation': {
                'tokens': simulation_tokens,
                'calls': simulation_calls,
                'notes': f'{avg_active} active agents/round × {rounds} rounds (avg 40% active)',
            },
            'report': {
                'tokens': report_tokens,
                'calls': report_sections * 5,  # ~5 ReACT iterations per section
                'notes': f'{report_sections} sections via ReACT loop',
            },
        },
        'total': {
            'tokens': total,
            'tokens_formatted': _format_tokens(total),
            'approx_cost_usd': _estimate_cost(total),
            'dominant_step': 'simulation',
            'dominant_step_percent': round(100 * simulation_tokens / max(total, 1), 1),
        },
    }


def _format_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f'{n / 1_000_000:.1f}M'
    if n >= 1_000:
        return f'{n / 1_000:.0f}K'
    return str(n)


def _estimate_cost(total_tokens: int) -> Dict[str, float]:
    """Rough cost estimates across pricing tiers.

    Assumes 80% input / 20% output split (simulation-heavy workloads).
    """
    input_tokens = total_tokens * 0.8
    output_tokens = total_tokens * 0.2

    # Representative pricing per 1M tokens (input, output)
    tiers = {
        'free_openrouter': (0.0, 0.0),
        'cheap_groq_llama8b': (0.05, 0.08),
        'cheap_deepseek_chat': (0.28, 0.42),
        'mid_gemini_flash': (0.10, 0.40),
        'premium_gpt5_nano': (0.05, 0.40),
        'premium_claude_sonnet': (3.0, 15.0),
    }

    return {
        name: round((input_tokens * inp + output_tokens * out) / 1_000_000, 4)
        for name, (inp, out) in tiers.items()
    }
