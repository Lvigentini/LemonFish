"""
Research-backed personality frameworks for agent differentiation.

Replaces the original MBTI-based approach (which is pseudoscientific and
only minimally used by OASIS) with frameworks that have actual empirical
backing for modelling individual and institutional behaviour.

Two framework layers:

  1. Individuals — Big Five / Five Factor Model (FFM)
     ----------------------------------------------------
     The Big Five is the dominant trait taxonomy in academic personality
     psychology, supported by factor-analytic evidence across cultures,
     languages, and decades of empirical research. Five dimensions,
     each scored 0-100:
         Openness           — curiosity, imagination, preference for novelty
         Conscientiousness  — organisation, discipline, goal-directedness
         Extraversion       — sociability, assertiveness, positive affect
         Agreeableness      — cooperation, trust, compassion
         Neuroticism        — emotional volatility, anxiety, negative affect

     References:
       - Costa & McCrae (1992), NEO-PI-R
       - John & Srivastava (1999), Big Five Inventory
       - Soto & John (2017), BFI-2

  2. Institutions — Social Media Archetypes + Behavioural Traits
     -------------------------------------------------------------
     The Big Five is designed for individual humans and doesn't transfer
     cleanly to organisations. Instead we use:

     a) A pragmatic 8-category archetype taxonomy that captures how
        organisations actually present on social media. These archetypes
        are informed by Mintzberg's organisational configurations and
        Miles & Snow's strategic typology, but simplified to what's
        observable in public communication rather than full org theory.

     b) Five behavioural dimensions analogous to Big Five but scoped to
        institutional public communication (0-100 each):
            Formality            — register, tone rigour
            Risk tolerance       — willingness to engage controversy
            Transparency         — openness about internal matters
            Responsiveness       — speed of reaction to external events
            Ideological intensity — strength of stated position

     This layer is our own synthesis, not a direct import of an academic
     framework — organisational personality research is less mature than
     individual trait research. The archetypes are chosen for
     social-media modelling utility, not theoretical purity.

Legacy MBTI fields are kept for backwards compatibility (display only).
See docs/oasis_dev.md Part 1 for the behavioural-impact hierarchy and
docs/personality_frameworks.md for the full rationale.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import random


# ------------------------------------------------------------------
# Individual — Big Five
# ------------------------------------------------------------------

BIG_FIVE_DIMENSIONS = [
    'openness',
    'conscientiousness',
    'extraversion',
    'agreeableness',
    'neuroticism',
]

BIG_FIVE_DESCRIPTIONS = {
    'openness': {
        'high': 'curious, inventive, drawn to novelty and abstract ideas',
        'mid': 'balanced between familiar routines and new experiences',
        'low': 'conventional, prefers routine, sceptical of change',
    },
    'conscientiousness': {
        'high': 'organised, disciplined, reliable, goal-directed',
        'mid': 'reasonably organised but flexible',
        'low': 'spontaneous, casual about deadlines and structure',
    },
    'extraversion': {
        'high': 'outgoing, energised by social interaction, assertive',
        'mid': 'comfortable in both social and solitary settings',
        'low': 'reserved, drained by heavy social interaction, measured',
    },
    'agreeableness': {
        'high': 'cooperative, empathetic, conflict-averse, trusting',
        'mid': 'balanced between cooperation and self-interest',
        'low': 'skeptical, competitive, willing to challenge and argue',
    },
    'neuroticism': {
        'high': 'emotionally reactive, anxious, sensitive to stress',
        'mid': 'generally stable with occasional volatility',
        'low': 'emotionally stable, calm under pressure, unshakeable',
    },
}


def bucket(score: int) -> str:
    """Bucket a 0-100 score into low / mid / high."""
    if score <= 35:
        return 'low'
    if score >= 65:
        return 'high'
    return 'mid'


def big_five_narrative(scores: Dict[str, int]) -> str:
    """Render Big Five scores as a natural-language paragraph for injection
    into the agent's system prompt.

    Example output:
        "Personality profile (Big Five): high openness (82/100) - curious,
        inventive, drawn to novelty and abstract ideas; low agreeableness
        (30/100) - skeptical, competitive, willing to challenge and
        argue; mid extraversion (50/100); high conscientiousness (78/100)
        - organised, disciplined, reliable, goal-directed; low neuroticism
        (25/100) - emotionally stable, calm under pressure."
    """
    if not scores:
        return ''
    parts = []
    for dim in BIG_FIVE_DIMENSIONS:
        score = scores.get(dim)
        if score is None:
            continue
        level = bucket(score)
        desc = BIG_FIVE_DESCRIPTIONS[dim][level]
        parts.append(f"{level} {dim} ({score}/100) — {desc}")
    if not parts:
        return ''
    return 'Personality profile (Big Five): ' + '; '.join(parts) + '.'


def random_big_five() -> Dict[str, int]:
    """Rule-based fallback: generate a plausible random Big Five profile.

    Uses a light bias toward the middle of the distribution (normal-ish)
    so agents don't all sit at the extremes.
    """
    def normal_score() -> int:
        # Triangular distribution peaking around 50, clipped to 0-100
        return max(0, min(100, int(random.triangular(0, 100, 50))))
    return {dim: normal_score() for dim in BIG_FIVE_DIMENSIONS}


def validate_big_five(data: Any) -> Dict[str, int]:
    """Coerce LLM output into a valid Big Five dict with int scores 0-100."""
    if not isinstance(data, dict):
        return random_big_five()
    out: Dict[str, int] = {}
    for dim in BIG_FIVE_DIMENSIONS:
        raw = data.get(dim)
        try:
            score = int(raw)
        except (TypeError, ValueError):
            score = 50
        out[dim] = max(0, min(100, score))
    return out


# ------------------------------------------------------------------
# Institution — Archetypes + Behavioural Traits
# ------------------------------------------------------------------

ORG_ARCHETYPES = {
    'authoritative': {
        'label': 'Authoritative',
        'description': (
            'Government bodies, regulators, central banks. Formal register, '
            'cautious, slow-moving, high authority signalling. Responses are '
            'measured and often deferred to official channels. Rarely engages '
            'in direct argument; prefers statements and press releases.'
        ),
        'examples': ['government ministry', 'regulator', 'central bank', 'police force'],
    },
    'technocratic': {
        'label': 'Technocratic',
        'description': (
            'Expert bodies, professional associations, standards organisations. '
            'Evidence-based, measured, cites data and research. Speaks from '
            'methodological authority rather than political authority. '
            'Corrects misinformation with citations; uncomfortable with emotional appeals.'
        ),
        'examples': ['medical association', 'scientific society', 'engineering institute'],
    },
    'advocacy': {
        'label': 'Advocacy',
        'description': (
            'NGOs, campaigns, pressure groups, unions. Passionate, confrontational, '
            'morally framed messaging. Willing to escalate disputes publicly. '
            'High ideological intensity; polarises audiences to drive engagement.'
        ),
        'examples': ['environmental NGO', 'civil rights group', 'union', 'campaign group'],
    },
    'commercial': {
        'label': 'Commercial',
        'description': (
            'Companies, brands, for-profit operators. Polished, customer-focused, '
            'deflective on controversy. Speaks in brand voice; avoids political '
            'positions unless forced. Responses optimised for reputation management.'
        ),
        'examples': ['startup', 'retail chain', 'tech company', 'consumer brand'],
    },
    'community': {
        'label': 'Community',
        'description': (
            'Local groups, clubs, grassroots organisations. Personal, colloquial, '
            'member-driven. Voice is closer to an individual than an institution. '
            'Quick to engage, low formality, strong local identity markers.'
        ),
        'examples': ['local sports club', 'neighbourhood group', 'fan community'],
    },
    'media': {
        'label': 'Media',
        'description': (
            'News outlets, publishers, broadcasters. Editorial, headline-driven, '
            'appears neutral but often has implicit stance. Fast-moving, prioritises '
            'engagement and attention. Comfortable with controversy as content.'
        ),
        'examples': ['newspaper', 'broadcaster', 'online publication'],
    },
    'academic': {
        'label': 'Academic',
        'description': (
            'Universities, research institutes, think tanks. Intellectual, nuanced, '
            'slow-burn. Extensive hedging and qualification. High credibility but '
            'low reach; often frustrated by simplified public discourse.'
        ),
        'examples': ['university', 'research institute', 'think tank'],
    },
    'populist': {
        'label': 'Populist',
        'description': (
            'Movements, pressure groups, insurgent political actors. Emotional, '
            'simplified messaging, us-vs-them framing. Low formality, high '
            'ideological intensity, high virality potential. Dismisses expert authority.'
        ),
        'examples': ['protest movement', 'populist party account', 'insurgent campaign'],
    },
}


ORG_TRAIT_DIMENSIONS = [
    'formality',
    'risk_tolerance',
    'transparency',
    'responsiveness',
    'ideological_intensity',
]

ORG_TRAIT_DESCRIPTIONS = {
    'formality': {
        'high': 'formal register, press-release style, uses titles and full names',
        'mid': 'conversational but professional',
        'low': 'casual, colloquial, uses first names and informal language',
    },
    'risk_tolerance': {
        'high': 'willing to engage controversy head-on, takes clear stances',
        'mid': 'engages selectively, weighs reputational cost',
        'low': 'avoids controversy, retreats to neutral language when pressed',
    },
    'transparency': {
        'high': 'open about internal processes, admits uncertainty and errors',
        'mid': 'explains major decisions but withholds detail',
        'low': 'opaque, uses boilerplate, refers questions to spokespersons',
    },
    'responsiveness': {
        'high': 'replies quickly, engages in real time, joins live discussions',
        'mid': 'responds within a day or two to direct engagement',
        'low': 'slow to respond, often ignores @-mentions, posts on schedule',
    },
    'ideological_intensity': {
        'high': 'strong, repeated public stances, unambiguous values language',
        'mid': 'stated positions but avoids rhetorical escalation',
        'low': 'position-neutral, describes rather than argues',
    },
}

# Archetype -> default behavioural trait profile (informs LLM baseline,
# not a hard constraint — LLM can deviate based on specific entity context).
ARCHETYPE_DEFAULT_TRAITS: Dict[str, Dict[str, int]] = {
    'authoritative': {
        'formality': 90, 'risk_tolerance': 20, 'transparency': 40,
        'responsiveness': 25, 'ideological_intensity': 30,
    },
    'technocratic': {
        'formality': 75, 'risk_tolerance': 45, 'transparency': 75,
        'responsiveness': 55, 'ideological_intensity': 40,
    },
    'advocacy': {
        'formality': 40, 'risk_tolerance': 85, 'transparency': 70,
        'responsiveness': 80, 'ideological_intensity': 90,
    },
    'commercial': {
        'formality': 70, 'risk_tolerance': 30, 'transparency': 40,
        'responsiveness': 70, 'ideological_intensity': 20,
    },
    'community': {
        'formality': 25, 'risk_tolerance': 55, 'transparency': 80,
        'responsiveness': 85, 'ideological_intensity': 50,
    },
    'media': {
        'formality': 55, 'risk_tolerance': 75, 'transparency': 60,
        'responsiveness': 90, 'ideological_intensity': 50,
    },
    'academic': {
        'formality': 80, 'risk_tolerance': 40, 'transparency': 75,
        'responsiveness': 35, 'ideological_intensity': 50,
    },
    'populist': {
        'formality': 20, 'risk_tolerance': 90, 'transparency': 45,
        'responsiveness': 85, 'ideological_intensity': 95,
    },
}


def org_traits_narrative(archetype: Optional[str], traits: Dict[str, int]) -> str:
    """Render organisational archetype + trait scores as a natural-language
    paragraph for injection into the agent's system prompt.
    """
    parts = []
    if archetype and archetype in ORG_ARCHETYPES:
        label = ORG_ARCHETYPES[archetype]['label']
        desc = ORG_ARCHETYPES[archetype]['description']
        parts.append(f"Organisational archetype: {label}. {desc}")
    if traits:
        trait_parts = []
        for dim in ORG_TRAIT_DIMENSIONS:
            score = traits.get(dim)
            if score is None:
                continue
            level = bucket(score)
            desc = ORG_TRAIT_DESCRIPTIONS[dim][level]
            dim_label = dim.replace('_', ' ')
            trait_parts.append(f"{level} {dim_label} ({score}/100) — {desc}")
        if trait_parts:
            parts.append('Behavioural profile: ' + '; '.join(trait_parts) + '.')
    return ' '.join(parts)


def validate_org_traits(data: Any, archetype: Optional[str] = None) -> Dict[str, int]:
    """Coerce LLM output into valid trait dict with int scores 0-100.

    If the LLM omitted a trait, fall back to the archetype's default.
    """
    defaults = ARCHETYPE_DEFAULT_TRAITS.get(archetype or '', {
        dim: 50 for dim in ORG_TRAIT_DIMENSIONS
    })
    if not isinstance(data, dict):
        return dict(defaults)
    out: Dict[str, int] = {}
    for dim in ORG_TRAIT_DIMENSIONS:
        raw = data.get(dim)
        try:
            score = int(raw)
        except (TypeError, ValueError):
            score = defaults.get(dim, 50)
        out[dim] = max(0, min(100, score))
    return out


def validate_archetype(value: Any) -> str:
    """Coerce LLM archetype string to a valid enum value."""
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ORG_ARCHETYPES:
            return v
        # Try to match label case-insensitively
        for key, data in ORG_ARCHETYPES.items():
            if data['label'].lower() == v:
                return key
    return 'authoritative'  # safe default


def archetype_for_entity_type(entity_type: str) -> str:
    """Heuristic mapping from entity type to default archetype — used as the
    rule-based fallback when the LLM doesn't provide one.
    """
    t = (entity_type or '').lower()
    if any(k in t for k in ['government', 'agency', 'ministry', 'regulator', 'council', 'police']):
        return 'authoritative'
    if any(k in t for k in ['university', 'institute', 'research']):
        return 'academic'
    if any(k in t for k in ['media', 'news', 'press', 'publisher', 'broadcaster']):
        return 'media'
    if any(k in t for k in ['ngo', 'union', 'campaign', 'movement', 'advocacy', 'activist']):
        return 'advocacy'
    if any(k in t for k in ['company', 'corporation', 'corp', 'ltd', 'inc', 'brand', 'startup']):
        return 'commercial'
    if any(k in t for k in ['club', 'community', 'group', 'fan', 'association']):
        return 'community'
    return 'authoritative'
