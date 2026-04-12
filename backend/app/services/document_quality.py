"""
Document Quality Scoring (Phase 7.1)

Estimates how well a seed document will produce a rich ontology, BEFORE
spending an LLM call on ontology generation. The score is a heuristic, not
a ground truth — it's meant to warn the user about low-quality inputs that
will produce weak simulations.

Signals measured:
  - Named-entity density: count of capitalised proper-noun runs (rough)
  - Relationship verb density: action verbs indicating interactions
    (works at, founded, oversees, criticised, etc.)
  - Quoted speech / direct attribution count
  - Document length (very short = LLM hallucinates entities)
  - Stakeholder diversity: variety of role/title words
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass, asdict
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


# Rough dictionary — tuned for English (other languages will score lower,
# which is a known limitation — the ontology generator handles non-English
# just fine, this scorer is just for UI feedback).
RELATIONSHIP_VERBS = {
    'works', 'founded', 'owns', 'leads', 'runs', 'chairs', 'manages',
    'oversees', 'regulates', 'reports', 'criticised', 'criticized',
    'supports', 'opposes', 'praised', 'announced', 'said', 'told',
    'funds', 'invests', 'represents', 'backed', 'backs', 'sued',
    'partnered', 'collaborated', 'acquired', 'merged', 'appointed',
    'elected', 'resigned', 'fired', 'hired', 'joined', 'left',
    'studies', 'studied', 'teaches', 'taught', 'endorses', 'endorsed',
    'investigated', 'sponsored', 'sponsors', 'developed', 'develops',
}

ROLE_WORDS = {
    'ceo', 'cto', 'cfo', 'founder', 'director', 'manager', 'president',
    'chairman', 'chairwoman', 'chair', 'executive', 'officer',
    'professor', 'doctor', 'dr', 'lecturer', 'student', 'researcher',
    'journalist', 'reporter', 'editor', 'columnist', 'commentator',
    'minister', 'senator', 'mayor', 'governor', 'councillor', 'councilor',
    'spokesperson', 'advocate', 'lawyer', 'attorney',
    'entrepreneur', 'investor', 'analyst', 'consultant',
    'coach', 'captain', 'player', 'athlete',
    'owner', 'operator', 'chief',
}

# Regex for candidate proper-noun runs (simple heuristic)
PROPER_NOUN_RE = re.compile(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b')
# Quoted speech
QUOTE_RE = re.compile(r'["\u201c][^"\u201d]{5,}["\u201d]')


@dataclass
class QualityScore:
    score: int                       # 0-100
    tier: str                        # 'excellent', 'good', 'adequate', 'weak'
    char_count: int
    named_entity_candidates: int     # unique capitalized phrases
    relationship_verbs: int          # count of interaction verbs
    role_words: int                  # count of role/title words
    quoted_statements: int           # "..." attribution count
    warnings: List[str]
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def score_document(text: str) -> QualityScore:
    """Score a document for ontology generation quality.

    Pure function — no side effects, no LLM calls.
    """
    warnings: List[str] = []
    recommendations: List[str] = []

    if not text:
        return QualityScore(
            score=0, tier='weak', char_count=0,
            named_entity_candidates=0, relationship_verbs=0,
            role_words=0, quoted_statements=0,
            warnings=['Empty document'],
            recommendations=['Add at least 2-3 paragraphs describing key stakeholders.'],
        )

    char_count = len(text)
    words = text.split()
    word_count = len(words)
    lowered_words = [w.lower().strip('.,;:!?"()[]') for w in words]

    # Named entity candidates (unique)
    proper_nouns = set(PROPER_NOUN_RE.findall(text))
    # Strip very common starter-of-sentence false positives: single-word all-common
    # Keep multi-word phrases and words that appear multiple times
    proper_noun_counter = Counter(PROPER_NOUN_RE.findall(text))
    entity_count = sum(1 for n, c in proper_noun_counter.items() if ' ' in n or c >= 2)

    # Relationship verb count
    verb_count = sum(1 for w in lowered_words if w in RELATIONSHIP_VERBS)

    # Role words
    role_count = sum(1 for w in lowered_words if w in ROLE_WORDS)

    # Quoted statements
    quote_count = len(QUOTE_RE.findall(text))

    # Scoring logic — weighted combination, capped at 100
    # Length floor: below 2000 chars, heavy penalty
    length_factor = min(char_count / 10000.0, 1.0)  # 0..1, saturates at 10K chars

    # Entity density: target ~1 entity per 500 chars
    entity_density = entity_count / max(char_count / 500, 1)
    entity_score = min(entity_density * 30, 35)

    # Verb score: target ~1 interaction verb per 400 chars
    verb_density = verb_count / max(char_count / 400, 1)
    verb_score = min(verb_density * 30, 30)

    # Role score: target ~1 role word per 600 chars
    role_density = role_count / max(char_count / 600, 1)
    role_score = min(role_density * 20, 20)

    # Quote score: 2-3 quotes is a nice signal of narrative text
    quote_score = min(quote_count * 3, 15)

    raw_score = (entity_score + verb_score + role_score + quote_score) * length_factor
    score = int(max(0, min(100, round(raw_score))))

    # Tier + recommendations
    if score >= 75:
        tier = 'excellent'
    elif score >= 55:
        tier = 'good'
    elif score >= 30:
        tier = 'adequate'
    else:
        tier = 'weak'

    # Specific warnings
    if char_count < 2000:
        warnings.append(f'Document is very short ({char_count} chars). LLMs may invent entity types not grounded in the text.')
        recommendations.append('Aim for at least 5,000 characters (roughly 2-3 pages).')
    elif char_count > 50_000:
        warnings.append(f'Document exceeds the 50K char ontology truncation limit (currently {char_count} chars). Set LLM_ONTOLOGY_MAX_TEXT_LENGTH or use Gemini with 1M context.')
        recommendations.append('Either shorten the document or configure a large-context ontology model.')

    if entity_count < 3:
        warnings.append('Very few named entities detected. The ontology will rely on fallback Person/Organization types.')
        recommendations.append('Name specific individuals and organisations (e.g. "Dr Jane Smith, UOW sport coordinator") rather than generic categories.')
    elif entity_count < 8 and char_count > 5000:
        warnings.append('Entity density is low for the document length.')
        recommendations.append('Add 3-5 more named stakeholders with their roles.')

    if verb_count < 2 and char_count > 3000:
        warnings.append('Few relationship/interaction verbs detected. The simulation will struggle to model stakeholder interactions.')
        recommendations.append('Describe how stakeholders relate (X supports Y, A criticised B, M works at N).')

    if quote_count == 0 and char_count > 5000:
        recommendations.append('Include a few quoted statements or stated positions to give agents clear voices.')

    if not warnings and not recommendations:
        recommendations.append('Document looks good for ontology generation.')

    return QualityScore(
        score=score,
        tier=tier,
        char_count=char_count,
        named_entity_candidates=entity_count,
        relationship_verbs=verb_count,
        role_words=role_count,
        quoted_statements=quote_count,
        warnings=warnings,
        recommendations=recommendations,
    )
