# Personality Frameworks in LemonFish

How LemonFish models agent personality, and why we moved away from MBTI.

**Status:** shipped in Phase 7.16 (v0.9.3)
**Implementation:** `backend/app/services/personality_frameworks.py`
**Related:** [`oasis_dev.md`](./oasis_dev.md) Parts 1.2 and 5 for the audit that led to this change.

---

## TL;DR

| Audience | Framework | Dimensions |
|----------|-----------|------------|
| **Individual humans** | Big Five / Five Factor Model (FFM) | Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism (each 0-100) |
| **Institutions / organisations** | Pragmatic archetype taxonomy + behavioural traits | 8 archetypes + 5 behavioural dimensions (0-100) |
| **Legacy (display only)** | MBTI | Kept for backwards compatibility, not used behaviourally |

LLM-generated persona narratives now include the structured scores as prose, so the agent's system prompt reflects the empirical personality framework.

---

## Why not MBTI?

MBTI (Myers-Briggs Type Indicator) was the original choice in MiroFish/camel-oasis. We replaced it in Phase 7.16 after an audit revealed several problems:

### The scientific problem

The Myers-Briggs Type Indicator is **not recognised as valid by academic personality psychology**. Specific issues:

- **Poor test-retest reliability**: about half of test-takers are assigned a different type on re-test within 5 weeks (Pittenger, 1993)
- **Dichotomised dimensions that are actually continuous**: MBTI forces each person into one of two camps per axis (E/I, S/N, etc.) but empirical personality distributions are unimodal and continuous — there's no statistical justification for the cut
- **No predictive validity**: MBTI types correlate weakly with job performance, relationship outcomes, or actual behaviour
- **Not grounded in factor analysis**: the four axes aren't supported by factor-analytic studies of personality traits

Academic personality research has converged on the **Five Factor Model (Big Five)**, which is supported by factor analysis across languages and cultures (Goldberg 1981, Costa & McCrae 1992, John & Srivastava 1999). HEXACO adds a sixth factor (Honesty-Humility) and has similar backing.

### The implementation problem

On top of the scientific issue, our audit found that MBTI was doing very little work in LemonFish:

1. **Only injected into the Reddit agent system prompt** — one sentence: "You are a male, 42 years old, with an MBTI personality type of INTJ from Australia." Twitter ignored it entirely.
2. **Institutions were all locked to ISTJ** — rule-based fallback hardcoded `"mbti": "ISTJ"` for every organisation, making MBTI completely useless for differentiating institutions.
3. **The persona narrative did the real work** — the 2000-character LLM-generated persona paragraph already carried behavioural detail; MBTI added noise, not signal.
4. **Non-reproducible at T=0.7** — regenerating a persona for the same entity produced different MBTI types, so the field wasn't even stable across runs.

### The design problem

MBTI is fundamentally an **individual personality framework**. Using it for organisations (central banks, NGOs, universities) is a category error. Organisations don't have cognition, emotion, or personality in the way individuals do. Forcing organisations into MBTI slots was a clear signal that the model was wrong.

---

## Framework 1 — Big Five / FFM for individuals

### Definitions

Five dimensions, each scored 0-100, based on the factor-analytic tradition in personality psychology. LemonFish stores these in `big_five: Dict[str, int]` on each individual profile.

| Dimension | Low (0-35) | Mid (36-64) | High (65-100) |
|-----------|-----------|-------------|---------------|
| **Openness** | Conventional, prefers routine, sceptical of change | Balanced between familiar routines and new experiences | Curious, inventive, drawn to novelty and abstract ideas |
| **Conscientiousness** | Spontaneous, casual about deadlines and structure | Reasonably organised but flexible | Organised, disciplined, reliable, goal-directed |
| **Extraversion** | Reserved, drained by heavy social interaction, measured | Comfortable in both social and solitary settings | Outgoing, energised by social interaction, assertive |
| **Agreeableness** | Skeptical, competitive, willing to challenge and argue | Balanced between cooperation and self-interest | Cooperative, empathetic, conflict-averse, trusting |
| **Neuroticism** | Emotionally stable, calm under pressure, unshakeable | Generally stable with occasional volatility | Emotionally reactive, anxious, sensitive to stress |

### Why Big Five works for social simulation

- **Empirically validated**: each dimension predicts actual behaviours (e.g., high conscientiousness → goal attainment, high neuroticism → emotional reactivity in conflict)
- **Continuous scores**: captures that people aren't binary categories
- **Independent axes**: someone can be high openness AND low agreeableness AND high neuroticism without contradiction
- **Cultural transferability**: the factor structure holds up across many languages

### How LemonFish generates Big Five scores

1. The individual persona prompt asks the LLM to ground each score in the entity's background, statements, and actions from the source document:
   > "an expert in a contested field should score high in conscientiousness and low in agreeableness"
   > "a local community organiser should score high in extraversion and agreeableness"
2. `validate_big_five()` coerces the LLM output to integers in 0-100 (falls back to 50 for missing dimensions)
3. `big_five_narrative()` renders the scores as a natural-language paragraph that gets appended to the `persona` string
4. The agent's OASIS system prompt therefore contains something like:
   > "Personality profile (Big Five): high openness (82/100) — curious, inventive, drawn to novelty and abstract ideas; low agreeableness (30/100) — skeptical, competitive, willing to challenge and argue; mid extraversion (50/100); high conscientiousness (78/100) — organised, disciplined, reliable, goal-directed; low neuroticism (25/100) — emotionally stable, calm under pressure."

### Rule-based fallback

If the LLM call fails for an individual, `random_big_five()` generates a triangular-distributed random profile (peaking at 50, clipped 0-100) so agents don't cluster at the extremes. Role-specific fallbacks bias scores realistically — e.g., experts get `conscientiousness 65-90, agreeableness 25-55`.

### What Big Five doesn't capture

- **Values and ideology** — a Big Five profile doesn't say *what* someone believes, only *how* they express it. The `persona` narrative still carries position/stance information.
- **Cultural context** — Big Five is trait-level; cultural dimensions are orthogonal. For cross-cultural simulations a future enhancement could add Hofstede scores at the simulation level.
- **Situational variance** — people behave differently in different contexts. LemonFish treats Big Five as a stable baseline.

---

## Framework 2 — Institutional archetypes + behavioural traits

The Big Five is designed for individual humans and doesn't transfer cleanly to organisations. We use a two-layer model:

### Layer A — Organisational archetype

Pick ONE of 8 archetypes that matches how the institution presents on social media. These are informed by Mintzberg's organisational configurations and Miles & Snow's strategic typology, but simplified to what's observable in public communication rather than full organisational theory.

| Archetype | Description | Typical examples |
|-----------|-------------|------------------|
| **authoritative** | Formal register, cautious, slow-moving, high authority signalling. Responses are measured and often deferred to official channels. Rarely engages in direct argument; prefers statements and press releases. | government ministry, regulator, central bank, police force |
| **technocratic** | Evidence-based, measured, cites data and research. Speaks from methodological authority rather than political authority. Corrects misinformation with citations; uncomfortable with emotional appeals. | medical association, scientific society, engineering institute |
| **advocacy** | Passionate, confrontational, morally framed messaging. Willing to escalate disputes publicly. High ideological intensity; polarises audiences to drive engagement. | environmental NGO, civil rights group, union, campaign group |
| **commercial** | Polished, customer-focused, deflective on controversy. Speaks in brand voice; avoids political positions unless forced. Responses optimised for reputation management. | startup, retail chain, tech company, consumer brand |
| **community** | Personal, colloquial, member-driven. Voice is closer to an individual than an institution. Quick to engage, low formality, strong local identity markers. | local sports club, neighbourhood group, fan community |
| **media** | Editorial, headline-driven, appears neutral but often has implicit stance. Fast-moving, prioritises engagement and attention. Comfortable with controversy as content. | newspaper, broadcaster, online publication |
| **academic** | Intellectual, nuanced, slow-burn. Extensive hedging and qualification. High credibility but low reach; often frustrated by simplified public discourse. | university, research institute, think tank |
| **populist** | Emotional, simplified messaging, us-vs-them framing. Low formality, high ideological intensity, high virality potential. Dismisses expert authority. | protest movement, populist party account, insurgent campaign |

### Layer B — Behavioural traits

5 dimensions scored 0-100, analogous to Big Five but scoped to institutional public communication:

| Dimension | Low (0-35) | Mid (36-64) | High (65-100) |
|-----------|-----------|-------------|---------------|
| **Formality** | Casual, colloquial, uses first names and informal language | Conversational but professional | Formal register, press-release style, uses titles and full names |
| **Risk tolerance** | Avoids controversy, retreats to neutral language when pressed | Engages selectively, weighs reputational cost | Willing to engage controversy head-on, takes clear stances |
| **Transparency** | Opaque, uses boilerplate, refers questions to spokespersons | Explains major decisions but withholds detail | Open about internal processes, admits uncertainty and errors |
| **Responsiveness** | Slow to respond, often ignores @-mentions, posts on schedule | Responds within a day or two to direct engagement | Replies quickly, engages in real time, joins live discussions |
| **Ideological intensity** | Position-neutral, describes rather than argues | Stated positions but avoids rhetorical escalation | Strong, repeated public stances, unambiguous values language |

### Archetype defaults

Each archetype has a default trait profile that serves as the baseline. The LLM can deviate from defaults if the source material justifies it — e.g., an `advocacy` NGO that happens to be known for measured, technocratic communication can have `formality=70, ideological_intensity=60` instead of the archetype defaults.

Default profiles (see `ARCHETYPE_DEFAULT_TRAITS` in `personality_frameworks.py`):

| Archetype | Formality | Risk tol. | Transparency | Responsiveness | Ideological intensity |
|-----------|-----------|-----------|--------------|----------------|----------------------|
| authoritative | 90 | 20 | 40 | 25 | 30 |
| technocratic | 75 | 45 | 75 | 55 | 40 |
| advocacy | 40 | 85 | 70 | 80 | 90 |
| commercial | 70 | 30 | 40 | 70 | 20 |
| community | 25 | 55 | 80 | 85 | 50 |
| media | 55 | 75 | 60 | 90 | 50 |
| academic | 80 | 40 | 75 | 35 | 50 |
| populist | 20 | 90 | 45 | 85 | 95 |

### Why not Mintzberg's full taxonomy

Mintzberg (1979) identifies configurations like Simple Structure, Machine Bureaucracy, Professional Bureaucracy, Divisionalized Form, Adhocracy. These are about *internal organisational structure* (centralisation, formalisation, specialisation), not about how an organisation communicates externally. For social media simulation we care about the **public voice**, which is only loosely coupled to internal structure. A Machine Bureaucracy can still run a populist Twitter account (many governments do).

Our 8 archetypes are pragmatically chosen to differentiate real social-media voices, not to match a formal org-theory taxonomy. This is our own synthesis — organisational personality research is less mature than individual trait research, and we don't claim direct empirical backing for this specific 8-category split. It's a useful abstraction for generating differentiated LLM prompts.

### Why not Hofstede's cultural dimensions per-organisation

Hofstede's six dimensions (power distance, individualism, masculinity, uncertainty avoidance, long-term orientation, indulgence) describe **national cultures**, not individual organisations. Applying them per-org would be a category error similar to the MBTI problem. If cultural context becomes important, the right place is a simulation-level config (one set of Hofstede scores per simulation, reflecting the country/region), not per-profile. We've deferred this — for a Wollongong simulation all organisations share the same Australian cultural context, so per-org Hofstede would just add noise.

---

## How the frameworks reach the agent

Both frameworks reach the agent via the **persona string**. We don't modify OASIS's system-prompt templates — instead, the personality narrative is appended to the `persona` field during profile generation, so it flows through the existing `user_profile` injection path in `UserInfo.to_*_system_message()`.

Flow:

```
LLM generates profile_data:
  {
    bio, persona, age, gender, country, profession, interested_topics,
    mbti (legacy),
    big_five: { openness: 82, conscientiousness: 78, ... },      # or
    org_archetype: 'advocacy',
    org_traits: { formality: 40, risk_tolerance: 85, ... }
  }

OasisProfileGenerator.create_profile():
  narrative = big_five_narrative(big_five)
            # OR
            = org_traits_narrative(archetype, org_traits)
  full_persona = profile_data['persona'] + '\n\n' + narrative

OasisAgentProfile stored with:
  - big_five / org_archetype / org_traits as structured fields (for UI + analytics)
  - persona = full_persona (narrative included)

Saved to reddit_profiles.json / twitter_profiles.csv with all structured fields plus persona.

Simulation subprocess reads profile, builds SocialAgent:
  user_info.profile['other_info']['user_profile'] = persona  # narrative inside

OASIS UserInfo.to_*_system_message() renders:
  "Your have profile: [persona text including the Big Five / archetype narrative]"

Agent's LLM receives the structured personality info as natural language.
```

**Consequence:** both Twitter and Reddit agents now receive personality information (previously only Reddit did, via the MBTI sentence). The structured fields are also available in the profile JSON for UI display, analytics, and any future custom OASIS templates.

---

## JSON schema

### Individual profile (new fields)

```json
{
  "user_id": 0,
  "username": "jane_smith_247",
  "name": "Dr Jane Smith",
  "bio": "Council sports planning officer...",
  "persona": "Jane Smith is a 42-year-old council officer...\n\nPersonality profile (Big Five): high conscientiousness (82/100) — organised, disciplined, reliable, goal-directed; mid openness (55/100); low extraversion (30/100) — reserved, drained by heavy social interaction, measured; ...",
  "age": 42,
  "gender": "female",
  "mbti": "ISTJ",
  "country": "Australia",
  "profession": "Council sports planning officer",
  "interested_topics": ["local government", "sports infrastructure"],
  "big_five": {
    "openness": 55,
    "conscientiousness": 82,
    "extraversion": 30,
    "agreeableness": 60,
    "neuroticism": 35
  },
  "karma": 1200,
  "created_at": "2026-04-12"
}
```

### Institutional profile (new fields)

```json
{
  "user_id": 5,
  "username": "wollongong_council_442",
  "name": "Wollongong City Council",
  "bio": "Official account of Wollongong City Council...",
  "persona": "Wollongong City Council is the local government body...\n\nOrganisational archetype: Authoritative. Government bodies, regulators, central banks. Formal register, cautious, slow-moving, high authority signalling. ... Behavioural profile: high formality (90/100) — formal register, press-release style; low risk_tolerance (25/100) — avoids controversy; ...",
  "age": 30,
  "gender": "other",
  "mbti": "ISTJ",
  "country": "Australia",
  "profession": "local government",
  "interested_topics": ["public infrastructure", "community planning"],
  "org_archetype": "authoritative",
  "org_traits": {
    "formality": 90,
    "risk_tolerance": 25,
    "transparency": 45,
    "responsiveness": 30,
    "ideological_intensity": 30
  },
  "karma": 800,
  "created_at": "2026-04-12"
}
```

---

## Open questions and future work

### Should we add reproducibility via seeds?

The persona generator currently runs at `temperature=0.7` with no seed. Regenerating profiles for the same entity produces different Big Five scores. For research publication this would be a problem. Adding a seed to profile generation is straightforward but isn't blocking any current use case.

### Should Hofstede be added at the simulation level?

For multi-region simulations (e.g., comparing how a padel centre would be received in Wollongong vs Bangalore vs Berlin), cultural context matters. A simulation-level Hofstede config that applies to all agents in the run would be the right extension point. Out of scope for Phase 7.16.

### Should we replace the legacy MBTI field entirely?

Currently MBTI is kept for backwards compatibility (display in the UI, existing JSON schema). A future cleanup could remove it, but the risk of breaking third-party tooling or existing `reddit_profiles.json` files isn't worth the cleanup benefit.

### Should the behavioural impact of the frameworks be tested?

Ideally we'd run simulations with the old (MBTI-only) and new (Big Five + archetypes) profile generation against the same seed document and compare agent-output diversity and coherence. This is the live end-to-end test we've been deferring — once we do it, the results should inform whether the framework change materially improves simulation quality.

---

## References

Academic personality psychology:

- Costa, P. T., & McCrae, R. R. (1992). *Revised NEO Personality Inventory (NEO-PI-R) and NEO Five-Factor Inventory (NEO-FFI): Professional Manual.* Psychological Assessment Resources.
- Goldberg, L. R. (1981). Language and individual differences: The search for universals in personality lexicons. In L. Wheeler (Ed.), *Review of personality and social psychology* (Vol. 2, pp. 141-165). Sage.
- John, O. P., & Srivastava, S. (1999). The Big Five trait taxonomy: History, measurement, and theoretical perspectives. In L. A. Pervin & O. P. John (Eds.), *Handbook of personality: Theory and research* (2nd ed., pp. 102-138). Guilford Press.
- Pittenger, D. J. (1993). The utility of the Myers-Briggs Type Indicator. *Review of Educational Research*, 63(4), 467-488.
- Soto, C. J., & John, O. P. (2017). The next Big Five Inventory (BFI-2). *Journal of Personality and Social Psychology*, 113(1), 117-143.

Organisational theory (informing archetype taxonomy):

- Mintzberg, H. (1979). *The Structuring of Organizations.* Prentice-Hall.
- Miles, R. E., & Snow, C. C. (1978). *Organizational Strategy, Structure, and Process.* McGraw-Hill.

Cultural dimensions (deferred as per-simulation future work):

- Hofstede, G. (1980). *Culture's Consequences: International Differences in Work-Related Values.* Sage.
- Hofstede, G., Hofstede, G. J., & Minkov, M. (2010). *Cultures and Organizations: Software of the Mind* (3rd ed.). McGraw-Hill.
