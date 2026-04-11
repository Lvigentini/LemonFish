# LemonFish — Seed Document & Ontology Guide

## How Ontology Generation Works

### The Pipeline

1. User uploads documents (PDF/MD/TXT) + writes a simulation requirement in natural language
2. Documents are parsed and text is extracted
3. Text is **truncated to 50,000 characters** (current hard limit)
4. A single LLM call analyses the text and outputs a JSON ontology:
   - Exactly 10 entity types (8 specific + Person + Organization fallback)
   - 6-10 relationship types
   - 1-3 attributes per entity type
5. The ontology is validated, names are normalised (PascalCase entities, UPPER_SNAKE_CASE edges)
6. The ontology is set as the schema for the Zep knowledge graph
7. The full document text (not truncated) is chunked and ingested into Zep
8. Zep extracts actual entities matching the schema

### The 50K Character Truncation Problem

The ontology LLM call caps input at `MAX_TEXT_LENGTH_FOR_LLM = 50000` characters (`ontology_generator.py:229`). This is roughly 25,000 tokens. Anything beyond is silently dropped.

However, the **graph building step** (Step 1b) sends the **full document** to Zep in chunks with no truncation. So the knowledge graph contains everything, but the ontology schema was designed from only the first 50K chars. If entity types relevant to later sections were not mentioned in the first 50K chars, those entities get forced into the Person/Organization fallback types, losing specificity.

---

## What Makes a Good Seed Document

### The system needs named, interactive entities

The ontology prompt explicitly requires entities that are "real-world subjects that can speak and interact on social media" not abstract concepts, not topics, not attitudes.

### Quality Tiers

**Excellent document** (produces rich ontology + many well-differentiated agents):
- Named individuals with roles (e.g., "Dr Jane Smith, Head of Wollongong Planning")
- Named organisations with functions (e.g., "Game4Padel, UK-based operator backed by Andy Murray")
- Explicit relationships (e.g., "Tennis Australia oversees padel through its padel department led by Callum Beale")
- Multiple stakeholder perspectives (supporters, critics, regulators, media, public)
- Enough role diversity to fill 8 specific entity types naturally
- 10K-50K characters

**Good document** (produces adequate ontology):
- Mix of named and generic entities
- Some relationships implied but not stated
- Clear stakeholder groups even if not individually named
- Statistical data mixed with narrative
- 5K-30K characters

**Poor document** (produces weak ontology, simulation suffers):
- Mostly statistics and charts (no text to extract entities from)
- No named actors only categories ("consumers", "businesses")
- Single-perspective (e.g., only market data, no community voices)
- Very short (<2K characters) LLM fills gaps with hallucinated types
- Very long (>100K chars) but important actors appear after the 50K truncation point

### Document Structure Recommendations

For best results, organise seed documents with the most important information first:

```
1. Key Stakeholders & Actors (named people, organisations, agencies)
2. Relationships & Power Dynamics (who influences whom, who regulates whom)
3. Positions & Perspectives (what each stakeholder thinks/wants)
4. Background Context (demographics, market data, trends)
5. Supporting Evidence (statistics, reports, studies)
```

This front-loads the entity-rich content before the 50K truncation point.

### Enrichment Strategies

If your source material is data-heavy (statistics, market reports), enrich it with:

- **Stakeholder profiles**: Write 2-3 paragraphs per key actor describing who they are, what they want, and how they relate to others
- **Scenario narratives**: Frame the prediction question as a story ("If company X announces plan Y, how would stakeholder Z react?")
- **Media excerpts**: Include quotes, press releases, social media posts from relevant actors
- **Opposition/support briefs**: Explicitly state who supports and opposes the proposal, and why

The LLM generates richer ontologies from narrative text than from tabular data.

---

## Using Gemini for Ontology Generation

### The Case For It

Gemini 2.5 Flash has a **1M token context window** (roughly 2M characters). This eliminates the 50K character truncation entirely. Benefits:

1. **No information loss**: The LLM sees the entire document, not just the first quarter
2. **Better entity coverage**: Types mentioned only in later sections are captured
3. **Better relationship mapping**: Cross-references between distant sections are preserved
4. **Free tier**: Google AI Studio offers generous free access
5. **JSON mode support**: Gemini supports response_format json_object

### The Case For Step-Specific Model Selection

Different steps have different requirements:

| Step | Needs | Best model type |
|------|-------|----------------|
| 1. Ontology | Deep document understanding, large context | Gemini (1M context, free) |
| 2. Profiles | Moderate context, creative persona writing | Any good model |
| 3. Config | Small context, JSON output | Any model with JSON mode |
| 4. Simulation | Fast, cheap, many parallel calls | Groq (fast inference), small models |
| 5. Report | Moderate context, analytical writing | Good reasoning model |

The current architecture uses a single LLMClient everywhere. A per-step model override would allow:

```env
# Step-specific model overrides
LLM_ONTOLOGY_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_ONTOLOGY_MODEL=gemini-2.5-flash
LLM_ONTOLOGY_API_KEY=AIza...
LLM_ONTOLOGY_MAX_TEXT_LENGTH=2000000

LLM_SIMULATION_BASE_URL=https://api.groq.com/openai/v1
LLM_SIMULATION_MODEL=llama-3.1-8b-instant
LLM_SIMULATION_API_KEY=gsk_...
```

### Implementation Notes

To lift the 50K cap when using a large-context model:
- `MAX_TEXT_LENGTH_FOR_LLM` in `ontology_generator.py:229` should become configurable
- Or set to a per-provider value based on the model's known context window
- The `max_tokens=4096` on the ontology call output side is fine as the ontology JSON is small regardless of input size

### Risks

- **Gemini may generate different ontology structures** than models MiroFish was tuned for. The prompt is detailed but model-specific behaviours (how strictly it follows the "exactly 10 types" instruction, how it interprets PascalCase requirements) may vary.
- **Latency**: Processing a 500K char document through Gemini takes longer than 50K through a smaller model. For ontology this is acceptable (one-time cost).
- **Rate limits**: Google AI Studio free tier is roughly 15 RPM. For a single ontology call this is irrelevant.

---

## Improving the Padel/Pickleball Seed Document

The current seed document (`backend/uploads/padel-pickleball-wollongong-seed-data.md`) is data-rich but entity-sparse. To improve it for simulation:

### What is strong
- Named venues (Game Point, Complete Tennis, Nordic Padel, etc.)
- Named organisations (Tennis Australia, Pickleball Australia, Wollongong City Council)
- Named operators (Game4Padel, Andy Murray)
- Clear demographic segments
- Council policy context

### What could be stronger
- No named individuals beyond Andy Murray. The simulation would benefit from fictional but realistic local stakeholders:
  - A council sports planning officer
  - A local tennis club president sceptical of padel
  - A padel enthusiast who played in Sydney
  - A pickleball group organiser
  - A local business owner near the proposed site
  - A university sports coordinator
  - A retiree active in community sports
- No explicit conflict or tension. Who would oppose this? Neighbours? Competing venues?
- No media voices. What would the Illawarra Mercury editorial position be?

Adding 3-5 paragraphs of stakeholder narrative would significantly improve the ontology and resulting agent diversity.

---

## Open Questions

- Should we auto-detect document language and select the ontology model accordingly?
- Should there be a "document quality score" that estimates how good the ontology will be before running the LLM call?
- Should we support structured input (CSV of stakeholders) alongside unstructured documents?
- Could we run ontology generation twice with different models and merge/compare results?
