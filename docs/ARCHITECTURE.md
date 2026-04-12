# MiroFish Architecture Deep-Dive

## 1. Architecture Overview

MiroFish is a **social media opinion simulation platform** that takes domain-specific documents, builds a knowledge graph from them, generates realistic social media agent personas, runs multi-platform simulations, and produces predictive "future forecast" reports.

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend Framework | Flask (Python) with Blueprints |
| Knowledge Graph | Zep Cloud (Standalone Graph API) |
| LLM Interface | OpenAI-compatible API (via `openai` Python SDK) |
| Simulation Engine | OASIS (`oasis-ai`) + camel-ai |
| Process Isolation | Python `subprocess` for simulation scripts |
| IPC | File-system based (JSON files in commands/responses dirs) |
| Storage | File-system (JSON, JSONL, SQLite for simulation DBs) |
| Frontend Communication | REST API with CORS |

### Application Factory (`app/__init__.py`)

Flask app created via factory pattern (`create_app()`). Key setup:
- CORS enabled for `/api/*`
- Three blueprints registered:
  - `graph_bp` at `/api/graph` - ontology & graph management
  - `simulation_bp` at `/api/simulation` - simulation lifecycle
  - `report_bp` at `/api/report` - report generation
- Simulation process cleanup registered via `SimulationRunner.register_cleanup()` at startup
- Request/response logging middleware

### Directory Structure

```
backend/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── config.py            # Centralized configuration (from .env)
│   ├── api/
│   │   ├── graph.py         # Graph/ontology endpoints
│   │   ├── simulation.py    # Simulation lifecycle endpoints
│   │   └── report.py        # Report generation endpoints
│   ├── services/
│   │   ├── ontology_generator.py       # Step 1: LLM-based ontology design
│   │   ├── graph_builder.py            # Step 2: Zep graph construction
│   │   ├── zep_entity_reader.py        # Entity extraction from graph
│   │   ├── oasis_profile_generator.py  # Step 3: Agent persona generation
│   │   ├── simulation_config_generator.py  # LLM-generated sim config
│   │   ├── simulation_manager.py       # Simulation preparation orchestrator
│   │   ├── simulation_runner.py        # Subprocess management & monitoring
│   │   ├── simulation_ipc.py           # IPC via filesystem
│   │   ├── zep_graph_memory_updater.py # Write sim activity back to graph
│   │   ├── report_agent.py             # ReACT-based report generation
│   │   ├── zep_tools.py               # Report retrieval tools
│   │   └── text_processor.py          # Text chunking/preprocessing
│   ├── models/
│   │   ├── project.py       # Project state model
│   │   └── task.py          # Async task tracking
│   └── utils/
│       ├── llm_client.py    # OpenAI client with retry/fallback
│       ├── file_parser.py   # PDF/MD/TXT extraction
│       ├── zep_paging.py    # Paginated Zep API fetching
│       ├── locale.py        # i18n support
│       ├── logger.py        # Logging setup
│       └── retry.py         # Generic retry utilities
├── scripts/
│   ├── run_reddit_simulation.py     # Reddit OASIS runner
│   ├── run_twitter_simulation.py    # Twitter OASIS runner
│   ├── run_parallel_simulation.py   # Dual-platform runner
│   └── action_logger.py            # JSONL action logging
└── uploads/
    ├── projects/       # Uploaded files & extracted text
    ├── simulations/    # Simulation state, profiles, configs, DBs
    └── reports/        # Generated reports & agent logs
```

---

## 2. Step-by-Step Workflow

### Step 1: Ontology Generation

**Endpoint:** `POST /api/graph/ontology/generate` (`app/api/graph.py:123`)

**Input:** Multipart form with:
- `files`: PDF/MD/TXT documents
- `simulation_requirement`: Description of what to simulate
- `project_name`, `additional_context` (optional)

**Technical Flow:**

1. **File Upload & Text Extraction** (`app/api/graph.py:184-201`)
   - Files saved to `uploads/projects/{project_id}/`
   - Text extracted via `FileParser.extract_text()` (supports PDF, MD, TXT)
   - Text preprocessed via `TextProcessor.preprocess_text()` (normalize whitespace)

2. **Project Creation** (`app/models/project.py`)
   - `ProjectManager.create_project()` assigns `proj_{uuid}` ID
   - Project state serialized to `uploads/projects/{project_id}/project.json`

3. **LLM Ontology Generation** (`app/services/ontology_generator.py:185-226`)
   - Combined document text truncated to 50,000 characters for LLM
   - System prompt defines strict schema: exactly 10 entity types (8 specific + 2 fallback: `Person`, `Organization`), 6-10 edge types
   - Entity types must be PascalCase, edges UPPER_SNAKE_CASE
   - Calls `LLMClient.chat_json()` with temperature=0.3
   - Post-processing: name normalization, deduplication, fallback type injection, Zep limits enforcement (max 10 entities, 10 edges)

**Output:** JSON ontology with `entity_types[]`, `edge_types[]`, `analysis_summary`

**State Created:**
- `uploads/projects/{project_id}/project.json` (status: `ontology_generated`)
- `uploads/projects/{project_id}/extracted_text.txt`

---

### Step 2: Graph Building

**Endpoint:** `POST /api/graph/build` (`app/api/graph.py:261`)

**Input:** `{"project_id": "proj_xxx", "chunk_size": 500, "chunk_overlap": 50}`

**Technical Flow (runs in background thread):**

1. **Text Chunking** (`app/services/text_processor.py:18-34`)
   - Character-level splitting with configurable overlap
   - Default: 500 chars per chunk, 50 char overlap

2. **Zep Graph Creation** (`app/services/graph_builder.py:196-206`)
   - Creates standalone graph with ID `mirofish_{uuid_hex[:16]}`
   - `client.graph.create(graph_id, name, description)`

3. **Ontology Registration** (`app/services/graph_builder.py:208-295`)
   - Dynamically creates Python classes inheriting from `EntityModel` and `EdgeModel` (Zep SDK)
   - Uses `type()` metaclass to build Pydantic models at runtime
   - Handles reserved attribute names (uuid, name, group_id, etc.) by prefixing with `entity_`
   - `client.graph.set_ontology(graph_ids=[graph_id], entities=..., edges=...)`

4. **Batch Episode Ingestion** (`app/services/graph_builder.py:297-371`)
   - Chunks sent in batches of 3 as `EpisodeData(data=chunk, type="text")`
   - Per-batch retry with exponential backoff (2s, 4s, 8s)
   - 1-second delay between batches to avoid rate limiting
   - Returns list of episode UUIDs

5. **Wait for Processing** (`app/services/graph_builder.py:373-428`)
   - Polls each episode's `processed` status via `client.graph.episode.get(uuid_=...)`
   - 3-second polling interval, 600-second timeout
   - Zep asynchronously extracts entities and relationships from episodes

6. **Graph Data Retrieval** (`app/services/graph_builder.py:452-527`)
   - Fetches all nodes and edges via paginated API (`utils/zep_paging.py`)
   - Returns node/edge counts, entity type distribution

**External Dependencies:** Zep Cloud API (graph create, set_ontology, add_batch, episode.get, graph.search)

**State Created:**
- Zep Cloud graph (persistent, external)
- Project updated with `graph_id`, status `graph_completed`

---

### Step 3: Agent Persona Generation (within Simulation Preparation)

**Endpoint:** `POST /api/simulation/prepare` (triggers `SimulationManager.prepare_simulation()`)

**Technical Flow:**

1. **Entity Reading & Filtering** (`app/services/zep_entity_reader.py`)
   - `ZepEntityReader.filter_defined_entities()` fetches all nodes from Zep graph
   - Filters nodes that have labels beyond just "Entity"/"Node" (i.e., typed entities)
   - Optionally enriches with edge data (related relationships)

2. **Profile Generation** (`app/services/oasis_profile_generator.py:212-274`)
   - For each entity, determines type: individual vs. group/institutional
   - **Zep Context Enrichment** (`_search_zep_for_entity`, line 286-346):
     - Parallel search for edges and nodes related to the entity
     - Uses `graph.search()` with `scope="edges"` and RRF reranker
     - Retries up to 3 times with exponential backoff
   - **LLM Profile Generation** (`_generate_profile_with_llm`):
     - Builds prompt with entity name, type, summary, attributes, and Zep context
     - Generates: bio, persona (detailed character description), age, gender, MBTI, country, profession, interested_topics
     - Distinguishes individual entities (generate personal profile) from group entities (generate spokesperson profile)
   - **Parallel Generation**: Configurable `parallel_count` (default 3) for concurrent profile generation
   - **Real-time Save**: Profiles saved incrementally to avoid data loss

3. **Output Formats:**
   - Reddit: JSON array (`reddit_profiles.json`)
   - Twitter: CSV format (`twitter_profiles.csv`)
   - Each profile includes: user_id, username, name, bio, persona, karma/followers, demographic data, source entity UUID

**Key Data Structure - `OasisAgentProfile`:**
```python
@dataclass
class OasisAgentProfile:
    user_id: int
    user_name: str
    name: str
    bio: str           # Short description
    persona: str       # Detailed character description (drives LLM behavior in simulation)
    karma: int         # Reddit metric
    friend_count: int  # Twitter metric
    follower_count: int
    age, gender, mbti, country, profession: Optional
    interested_topics: List[str]
    source_entity_uuid: str  # Traceability back to knowledge graph
```

---

### Step 3b: Simulation Configuration Generation

**Service:** `SimulationConfigGenerator` (`app/services/simulation_config_generator.py`)

**Strategy: Multi-step LLM generation** (avoids single-prompt token overflow):

1. **Time Configuration** - Total simulation hours, minutes per round, active agent counts by time period
   - Hardcoded Chinese timezone activity patterns (peak 19-22, dead 0-5)
   - Default: 72 hours simulated time, 60 min/round

2. **Event Configuration** - Initial posts, scheduled events, hot topics, narrative direction
   - LLM decides what "seed" content triggers the simulation

3. **Agent Configurations** (batched, 15 per batch) - Per-agent:
   - `activity_level` (0-1): Overall posting frequency
   - `posts_per_hour`, `comments_per_hour`
   - `active_hours`: When this agent is "awake"
   - `response_delay_min/max`: Reaction speed to events
   - `sentiment_bias` (-1 to 1)
   - `stance`: supportive/opposing/neutral/observer
   - `influence_weight`: Visibility multiplier

4. **Platform Configuration** - Recommendation weights, viral thresholds, echo chamber strength

5. **Post-Agent Assignment** - Matches initial seed posts to appropriate agent personas

**Output:** `simulation_config.json` (full `SimulationParameters` serialization)

---

### Step 4: Simulation Execution

**Endpoint:** `POST /api/simulation/start` (triggers `SimulationRunner.start_simulation()`)

**Technical Flow:**

1. **Process Launch** (`app/services/simulation_runner.py:388-478`)
   - Selects script: `run_twitter_simulation.py`, `run_reddit_simulation.py`, or `run_parallel_simulation.py`
   - Launches as `subprocess.Popen` with:
     - `start_new_session=True` (new process group for clean termination)
     - `cwd=simulation_dir` (SQLite DB written here)
     - Environment: `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`
     - stdout/stderr redirected to `simulation.log`
   - Command: `python {script} --config {config_path} [--max-rounds N]`

2. **OASIS Environment Setup** (`scripts/run_reddit_simulation.py:385-588`)
   - Creates LLM model via `camel-ai`'s `ModelFactory.create()` (OpenAI platform type)
   - Loads agent profiles: `generate_reddit_agent_graph(profile_path, model, available_actions)`
   - Creates OASIS environment: `oasis.make(agent_graph, platform, database_path, semaphore=30)`
   - Executes initial events (seed posts from config)

3. **Simulation Loop** (per round):
   - Calculates `current_hour` from round number and `minutes_per_round`
   - Selects active agents based on:
     - Time-of-day activity multipliers (peak/off-peak)
     - Per-agent `active_hours` and `activity_level`
     - Random sampling within target count
   - Creates `LLMAction` for each active agent
   - Calls `env.step(actions)` - OASIS handles LLM calls for each agent's decision
   - Logs actions to `{platform}/actions.jsonl` (JSONL format)

4. **Monitoring Thread** (`SimulationRunner._monitor_simulation`, line 482-548)
   - Runs in Flask process, tails `actions.jsonl` files every 2 seconds
   - Parses action events, updates `SimulationRunState`
   - Detects process termination, sets final status

5. **Post-Simulation IPC** (`IPCHandler` in simulation scripts)
   - After simulation completes, script enters "wait for commands" mode
   - Polls `ipc_commands/` directory for JSON command files
   - Supports: `INTERVIEW` (single agent), `BATCH_INTERVIEW`, `CLOSE_ENV`
   - Writes responses to `ipc_responses/` directory

6. **Optional: Graph Memory Update** (`ZepGraphMemoryManager`)
   - If enabled, converts agent actions to natural language episodes
   - Sends back to Zep graph, updating the knowledge graph with simulation results

**Action Types:**
- Twitter: CREATE_POST, LIKE_POST, REPOST, FOLLOW, DO_NOTHING, QUOTE_POST
- Reddit: LIKE_POST, DISLIKE_POST, CREATE_POST, CREATE_COMMENT, LIKE/DISLIKE_COMMENT, SEARCH_POSTS, SEARCH_USER, TREND, REFRESH, DO_NOTHING, FOLLOW, MUTE

**State Created:**
- `{simulation_dir}/reddit_simulation.db` (SQLite - OASIS internal state)
- `{simulation_dir}/twitter/actions.jsonl`, `reddit/actions.jsonl`
- `{simulation_dir}/simulation.log`
- `{simulation_dir}/run_state.json`

---

### Step 5: Report Generation

**Endpoint:** `POST /api/report/generate` (triggers `ReportAgent.generate_report()`)

**Technical Flow:**

1. **Planning Phase** (`app/services/report_agent.py:552-611`)
   - Fetches graph statistics (node/edge counts, entity types)
   - Samples facts from the graph for context
   - Sends planning prompt to LLM asking for 2-5 section outline
   - LLM returns JSON: `{title, summary, sections: [{title, description}]}`

2. **Section Generation - ReACT Loop** (per section, `report_agent.py:614-850`)
   - System prompt includes: report context, section title, available tools, format rules
   - Multi-turn conversation with LLM:
     - **Thought**: LLM reasons about what information is needed
     - **Action**: LLM outputs `<tool_call>{"name": "...", "parameters": {...}}</tool_call>`
     - **Observation**: System executes tool, injects result as user message
     - **Final Answer**: LLM outputs `Final Answer:` followed by section content
   - Constraints: min 3, max 5 tool calls per section
   - Tool call parsing supports XML tags and bare JSON fallback

3. **Available Tools** (`app/services/zep_tools.py:401-419`):
   - **`insight_forge`** - Most powerful. Auto-decomposes query into sub-questions, performs parallel semantic search + entity analysis + relationship chain tracking
   - **`panorama_search`** - Breadth-first. Gets all nodes/edges including expired ones, distinguishes active vs. historical facts
   - **`quick_search`** - Lightweight semantic search via Zep's `graph.search()` with cross-encoder reranker
   - **`interview_agents`** - Calls the actual OASIS simulation environment's interview API via IPC. Selects relevant agents, generates questions, executes batch interview across both platforms

4. **Report Assembly**
   - Sections concatenated as Markdown
   - Saved to `uploads/reports/{report_id}/report.md`
   - Detailed agent log: `agent_log.jsonl` (every thought, tool call, result, response)
   - Console log: `console_log.txt`

5. **Chat Mode** (post-generation)
   - User can ask follow-up questions
   - Agent has access to the same tools (max 1-2 calls per chat turn)
   - Prioritizes existing report content, falls back to tool retrieval

---

## 3. Key Design Decisions

### 3.1 Zep Cloud for Knowledge Graph

**Why Zep:**
- Provides managed graph infrastructure with **automatic entity/relationship extraction** from raw text (episodes)
- Built-in **semantic search** (hybrid BM25 + embedding) with reranking
- Native **ontology enforcement** - entity types and edge types are first-class
- Temporal edges (valid_at, invalid_at, expired_at) enable tracking state changes
- No need to maintain own embedding pipeline or graph database

**Trade-offs:**
- External dependency with rate limits and latency
- Limited to Zep's processing logic for entity extraction (black box)
- Episode processing is async with polling (adds wait time)
- Zep limits: max 10 entity types, max 10 edge types per ontology
- No fine-grained control over how facts are extracted or merged

**Alternatives:**
- Neo4j + custom NER pipeline: More control, but massive engineering effort
- LangChain's GraphStore: Less mature, no temporal edges
- Custom embedding DB (Pinecone/Weaviate) + LLM extraction: More flexible but requires building graph logic

### 3.2 OASIS/camel-ai for Simulation

**Why OASIS:**
- Purpose-built for **social media simulation** with platform-specific mechanics
- Pre-built platform abstractions (Twitter, Reddit) with realistic action types
- Agent decision-making via LLM (each agent independently decides actions)
- Built-in recommendation algorithms, content feeds, social graphs
- SQLite-based state tracking for reproducibility

**Trade-offs:**
- Heavy dependency on a research library (less stable APIs)
- Each agent action requires an LLM call (expensive at scale)
- Limited to supported platforms (Twitter, Reddit)
- Concurrency bounded by `semaphore` parameter (default 30 parallel LLM calls)
- camel-ai's model factory adds indirection over direct OpenAI calls

**Alternatives:**
- Custom agent loop with simpler rules: Faster, cheaper, but less realistic
- Mesa (ABM framework): Better for mathematical models, worse for LLM-driven behavior
- Concordia (Google DeepMind): Similar concept but less platform-specific

### 3.3 Flask (vs FastAPI)

**Why Flask:**
- Simpler mental model for a research/prototype system
- Background threads for async work (vs FastAPI's native async)
- Well-understood deployment model
- The app is primarily I/O-bound (LLM calls, Zep API), not compute-bound

**Trade-offs:**
- No native async support (uses `threading.Thread` for background work)
- No automatic OpenAPI/Swagger docs
- No native WebSocket support (would need Flask-SocketIO for real-time updates)
- Type hints don't generate request validation

**What would be better:**
- FastAPI: Native async, automatic docs, Pydantic validation, WebSocket support
- The current polling-based status checking (`GET /task/{id}`) could be replaced with SSE/WebSocket

### 3.4 Subprocess Isolation for Simulations

**Why subprocesses:**
- OASIS modifies global state (logging, environment variables, SQLite)
- Prevents OASIS/camel-ai from interfering with Flask's event loop
- Clean termination: `start_new_session=True` + `os.killpg()` kills all children
- Memory isolation: OASIS can be memory-hungry with many agents
- Allows different Python environments (though not currently used)

**Trade-offs:**
- Communication limited to file-based IPC (no shared memory)
- Startup overhead for each simulation
- Debugging is harder (separate process, separate logs)
- No real-time streaming of individual actions to API (polling-based)

**The IPC mechanism** (`simulation_ipc.py`):
- Commands: Flask writes JSON to `ipc_commands/{command_id}.json`
- Responses: Script writes to `ipc_responses/{command_id}.json`
- Polling-based with configurable timeout
- Simple but robust (survives process crashes without corruption)

### 3.5 Agent Persona Generation Approach

**Strategy: Knowledge Graph -> LLM Enhancement -> OASIS Profile**

1. Entities from the graph provide **structural accuracy** (real actors mentioned in documents)
2. Zep search enriches with **relational context** (what facts connect to this entity)
3. LLM generates **behavioral detail** (personality, MBTI, communication style)
4. Distinction between individual and institutional entities ensures appropriate spokesperson personas

**Why this approach:**
- Grounded in source material (not hallucinated personas)
- Consistent with the ontology (types match graph labels)
- Rich enough for LLM-driven simulation (detailed persona drives realistic behavior)

**Limitations:**
- Profile quality depends heavily on graph richness
- Parallel generation can hit rate limits
- No validation that generated personas are internally consistent
- MBTI/demographic attributes are somewhat arbitrary for institutions

### 3.6 Dual-Platform (Twitter + Reddit) Simulation

**Why both:**
- Different platform mechanics produce different discourse patterns
- Twitter: Short-form, repost-driven virality, follower asymmetry
- Reddit: Long-form, comment threads, voting-based visibility
- Comparing platforms reveals how the same event evolves differently

**Implementation:**
- `run_parallel_simulation.py` uses `multiprocessing` to run both platforms concurrently
- Each platform has independent agent graphs, databases, and action logs
- Shared configuration but separate action spaces
- Interview tool queries both platforms for comprehensive perspective

### 3.7 ReportAgent with Tool Use

**Why ReACT pattern:**
- Report must be **grounded in simulation data**, not LLM's training knowledge
- Tool calls force the LLM to actually retrieve and cite evidence
- Multiple tools provide different "lenses" (depth vs breadth vs interviews)
- Minimum tool call enforcement (3 per section) prevents lazy generation

**Design choices:**
- Custom tool-call parsing (XML tags) rather than OpenAI function calling
  - Works with any OpenAI-compatible API (not just OpenAI)
  - Allows the model to "think" before calling tools (visible reasoning)
- `interview_agents` bridges report generation with live simulation
  - Agent is literally asked questions and responds in-character
  - Adds authenticity impossible with pure retrieval

---

## 4. Data Models

### Project State (`uploads/projects/{id}/project.json`)

```json
{
  "project_id": "proj_xxxxx",
  "name": "Project Name",
  "status": "created|ontology_generated|graph_building|graph_completed|failed",
  "files": [{"filename": "doc.pdf", "size": 12345}],
  "total_text_length": 50000,
  "ontology": {
    "entity_types": [{"name": "Professor", "description": "...", "attributes": [...], "examples": [...]}],
    "edge_types": [{"name": "WORKS_FOR", "description": "...", "source_targets": [...]}]
  },
  "graph_id": "mirofish_abc123",
  "simulation_requirement": "Simulate public reaction to...",
  "chunk_size": 500,
  "chunk_overlap": 50
}
```

### Simulation Config (`uploads/simulations/{id}/simulation_config.json`)

```json
{
  "simulation_id": "sim_xxxxx",
  "project_id": "proj_xxxxx",
  "graph_id": "mirofish_xxxxx",
  "simulation_requirement": "...",
  "time_config": {
    "total_simulation_hours": 72,
    "minutes_per_round": 60,
    "agents_per_hour_min": 5,
    "agents_per_hour_max": 20,
    "peak_hours": [19, 20, 21, 22],
    "peak_activity_multiplier": 1.5,
    "off_peak_hours": [0, 1, 2, 3, 4, 5],
    "off_peak_activity_multiplier": 0.05
  },
  "agent_configs": [{
    "agent_id": 0,
    "entity_uuid": "...",
    "entity_name": "Professor Wang",
    "entity_type": "Professor",
    "activity_level": 0.7,
    "posts_per_hour": 1.5,
    "active_hours": [8, 9, 10, 11, 14, 15, 16, 20, 21],
    "response_delay_min": 10,
    "response_delay_max": 120,
    "sentiment_bias": -0.3,
    "stance": "opposing",
    "influence_weight": 2.0
  }],
  "event_config": {
    "initial_posts": [{"content": "Breaking news...", "poster_agent_id": 3}],
    "hot_topics": ["academic fraud", "university response"],
    "narrative_direction": "..."
  },
  "twitter_config": {"recency_weight": 0.4, "popularity_weight": 0.3, ...},
  "reddit_config": {...},
  "llm_model": "gpt-4o-mini",
  "llm_base_url": "https://api.openai.com/v1"
}
```

### Reddit Profile (`uploads/simulations/{id}/reddit_profiles.json`)

```json
[
  {
    "user_id": 0,
    "username": "prof_wang_123",
    "name": "Professor Wang",
    "bio": "Distinguished professor at XYZ University...",
    "persona": "You are Professor Wang, a 55-year-old computer science professor who has been at XYZ University for 20 years. You are known for your rigorous academic standards and have publicly criticized recent trends in...",
    "karma": 3500,
    "created_at": "2025-01-15",
    "age": 55,
    "gender": "male",
    "mbti": "INTJ",
    "country": "China",
    "profession": "Computer Science Professor",
    "interested_topics": ["academic integrity", "AI research", "education reform"]
  }
]
```

### Action Log (`uploads/simulations/{id}/reddit/actions.jsonl`)

```jsonl
{"event":"round_start","round":1,"simulated_hour":8,"timestamp":"2025-01-01T08:00:00"}
{"event":"agent_action","round":1,"platform":"reddit","agent_id":3,"agent_name":"Prof Wang","action_type":"CREATE_POST","action_args":{"content":"I am deeply concerned about..."},"timestamp":"..."}
{"event":"round_end","round":1,"actions_count":5}
{"event":"simulation_end","total_rounds":72,"total_actions":450}
```

### Run State (`uploads/simulations/{id}/run_state.json`)

```json
{
  "simulation_id": "sim_xxxxx",
  "runner_status": "running|completed|failed|stopped",
  "current_round": 15,
  "total_rounds": 72,
  "simulated_hours": 15,
  "total_simulation_hours": 72,
  "twitter_running": true,
  "reddit_running": true,
  "twitter_actions_count": 120,
  "reddit_actions_count": 95,
  "process_pid": 12345,
  "started_at": "...",
  "recent_actions": [...]
}
```

---

## 5. LLM Usage Patterns

### 5.1 Ontology Generation

- **Model:** Configured via `LLM_MODEL_NAME` (default: `gpt-4o-mini`)
- **Temperature:** 0.3 (low creativity, high consistency)
- **Max tokens:** 4096
- **Response format:** JSON mode (`chat_json()`)
- **Prompt structure:** System prompt (2000+ chars of detailed instructions) + User prompt (document text + requirements)
- **Key constraint:** Forces exactly 10 entity types to prevent over/under-specification

### 5.2 Profile Generation

- **Model:** Same as above
- **Temperature:** Likely 0.7 (default in `chat()`)
- **Per-entity:** One LLM call generates full persona JSON
- **Context injection:** Zep search results prepended to prompt for grounding
- **Parallel calls:** Up to `parallel_count` concurrent generations

### 5.3 Simulation Config Generation

- **Multi-step:** 3+ LLM calls (time config, event config, agent configs in batches of 15)
- **Each step:** Receives truncated document context + entity summaries
- **Output:** Structured JSON parsed into dataclasses
- **Reasoning capture:** LLM explains its parameter choices (stored in `generation_reasoning`)

### 5.4 Simulation (OASIS)

- **Per-agent-per-round:** Each active agent makes one LLM call to decide its action
- **Model:** Created via camel-ai's `ModelFactory.create(ModelPlatformType.OPENAI, model_type=...)`
- **Environment variable passthrough:** `OPENAI_API_KEY` and `OPENAI_API_BASE_URL`
- **Concurrency:** `semaphore=30` limits parallel LLM requests within OASIS
- **No temperature control:** OASIS handles this internally

### 5.5 Report Generation

- **Planning:** One LLM call, JSON output
- **Per-section:** 4-8 LLM calls (3-5 tool rounds + reflection)
- **Temperature:** Configurable via `REPORT_AGENT_TEMPERATURE` (default 0.5)
- **Tool results injected as conversation history:** Multi-turn chat format
- **Chat follow-up:** Additional LLM calls with full report as context

### 5.6 LLM Client Resilience (`app/utils/llm_client.py`)

- **Retry:** Exponential backoff (2s, 4s, 8s) for transient errors (429, 500, 502, 503, 504)
- **Fallback models:** Configurable via `LLM_FALLBACK_MODELS` env var (comma-separated)
- **Model cascade:** Primary model retried N times, then each fallback model retried N times
- **JSON extraction:** Handles markdown code fences, strips them before `json.loads()`

---

## 6. Critical Analysis

### 6.1 Zep as Single Point of Failure

**Fragility:** Every step depends on Zep Cloud availability. Graph building, entity reading, profile enrichment, report generation all make Zep API calls. A Zep outage stops the entire pipeline.

**What could be done differently:**
- Cache graph data locally after building (currently only `get_graph_data` is cached implicitly in responses)
- Implement a local graph fallback (NetworkX + embeddings) for report generation when Zep is down
- The `_local_search` fallback in `zep_tools.py` is a start but only covers keyword matching

### 6.2 Simulation Cost and Scale

**Problem:** Each simulation round requires N LLM calls (one per active agent). With 30 agents active per round and 72 rounds, that's 2,160+ LLM calls per platform. Dual-platform doubles it.

**Scaling issues:**
- Cost grows linearly with agents * rounds
- No batching of agent decisions (each is independent)
- No caching of similar decisions (agents with similar profiles in similar contexts)

**Alternatives:**
- Rule-based agents for "background" actors, LLM only for key agents
- Embedding-based action prediction trained on prior simulation data
- Shorter simulations with interpolation for "boring" periods (dead hours)

### 6.3 File-System State Management

**Fragility:** All state is JSON files on disk. No transactions, no locking, no ACID guarantees.

**Risks:**
- Concurrent writes to `state.json` (race condition between monitor thread and API)
- Disk full = data loss
- No migration path for schema changes
- Project listing requires directory scan (`os.listdir`)

**What would scale better:**
- PostgreSQL for project/simulation metadata
- Redis for real-time run state (with pub/sub for live updates)
- S3-compatible storage for large files (profiles, reports)

### 6.4 IPC via Filesystem

**Fragility:** The command/response pattern via JSON files works but has inherent races:
- No guaranteed delivery (file could be partially written when read)
- Polling delay (up to the poll interval before a command is noticed)
- No acknowledgment/retry protocol

**Better alternatives:**
- Unix sockets or named pipes (lower latency, atomic messages)
- ZeroMQ or Redis pub/sub
- gRPC between Flask and simulation process

### 6.5 Report Quality Dependence on Graph Quality

**Chain of dependencies:** Document quality -> Ontology quality -> Graph quality -> Profile quality -> Simulation quality -> Report quality. Each step can degrade signal.

**Weak links:**
- Zep's entity extraction may miss entities or create duplicates
- 50,000 char truncation for ontology generation may lose important context
- 10 entity types is a hard limit that may not capture complex scenarios
- Generated personas may not accurately reflect the source material

### 6.6 No Persistence of Simulation Semantics

**Problem:** The simulation produces rich behavioral data (in SQLite), but only `actions.jsonl` is exposed to the report agent. The report tools query the Zep graph (which may or may not be updated with simulation results depending on `enable_graph_memory_update`).

**Gap:** If graph memory update is disabled, the report agent has limited access to what actually happened in the simulation. It relies on:
- Pre-simulation graph facts (from documents)
- Interview responses (requires live simulation environment)
- Action logs (not directly accessible via tools)

### 6.7 Localization Approach

**Current:** `utils/locale.py` with `t()` function for string translation. Language affects LLM prompts (via `get_language_instruction()`).

**Fragility:** Thread-local locale state must be explicitly propagated to background threads (done via `set_locale(current_locale)` before thread start). Easy to miss when adding new background tasks.

### 6.8 Security Considerations

**Gaps:**
- No authentication on any API endpoint (CORS allows `*`)
- File upload accepts any content within allowed extensions (no malware scanning)
- API keys stored in environment variables (acceptable) but no rotation mechanism
- subprocess execution with user-influenced paths (simulation_dir) - potential for path traversal
- No rate limiting on API endpoints

---

## 7. Configuration Reference

All configuration via environment variables (loaded from `MiroFish/.env`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_API_KEY` | (required) | OpenAI-compatible API key |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | LLM endpoint |
| `LLM_MODEL_NAME` | `gpt-4o-mini` | Model for all LLM tasks |
| `LLM_MAX_RETRIES` | `3` | Retry count for failed LLM calls |
| `LLM_RETRY_BASE_DELAY` | `2.0` | Initial backoff delay (seconds) |
| `LLM_FALLBACK_MODELS` | (empty) | Comma-separated fallback model list |
| `ZEP_API_KEY` | (required) | Zep Cloud API key |
| `OASIS_DEFAULT_MAX_ROUNDS` | `10` | Default simulation round cap |
| `REPORT_AGENT_MAX_TOOL_CALLS` | `5` | Max tools per report section |
| `REPORT_AGENT_MAX_REFLECTION_ROUNDS` | `2` | Max reflection iterations |
| `REPORT_AGENT_TEMPERATURE` | `0.5` | Report LLM temperature |
| `FLASK_DEBUG` | `True` | Debug mode |

---

## 8. Key File Reference

| File | Lines | Purpose |
|------|-------|---------|
| `app/__init__.py` | 80 | App factory, blueprint registration |
| `app/config.py` | 84 | All configuration constants |
| `app/api/graph.py` | 623 | Graph/ontology API (5 endpoints) |
| `app/api/simulation.py` | ~600 | Simulation API (10+ endpoints) |
| `app/services/ontology_generator.py` | 506 | Ontology design with LLM |
| `app/services/graph_builder.py` | 533 | Zep graph construction |
| `app/services/oasis_profile_generator.py` | ~500 | Agent persona generation |
| `app/services/simulation_config_generator.py` | ~400 | LLM-based config generation |
| `app/services/simulation_manager.py` | 530 | Simulation orchestration |
| `app/services/simulation_runner.py` | ~600 | Process management & monitoring |
| `app/services/report_agent.py` | ~1100 | ReACT report generation |
| `app/services/zep_tools.py` | ~600 | Report retrieval tools |
| `scripts/run_parallel_simulation.py` | ~700 | Dual-platform simulation script |
| `scripts/run_reddit_simulation.py` | ~600 | Reddit simulation script |

---

## 9. Research Module (Phase 8, opt-in add-on)

Added in v0.10.0, the research module is an optional add-on that plugs in **before** Step 1. It replaces the "upload documents" entry point with a "research from prompt" flow: the user gives a vague intent, research agents gather material via web search, and the compiled output becomes the same `uploads/projects/{project_id}/extracted_text.txt` that the existing ontology generator already consumes.

**Integration seam:** the module does not modify any existing pipeline code. It writes the compiled document to the project's standard extracted text path and advances the project status so Step 1 picks it up unchanged.

**Conditional registration:** `backend/app/__init__.py` imports the module inside a `try/except ImportError` block and only calls `register_blueprint(app)` when `RESEARCH_ENABLED=true`. With the module absent or disabled, the main app starts with zero behavioural change and no `/api/research/*` routes.

### Module layout

```
backend/research/
  __init__.py                 # is_enabled(), register_blueprint()
  config.py                   # RESEARCH_* env vars
  api.py                      # Flask blueprint with 7 endpoints
  orchestrator.py             # Plan → Research → Synthesise driver
  models.py                   # ResearchTask, SubTopic, ResearchSummary + on-disk persistence
  availability.py             # Cross-runner availability aggregator
  runners/
    base.py                   # CLIRunner ABC, AvailabilityResult
    api_runner.py             # Fallback: LLMClient + duckduckgo-search
    claude_runner.py          # Claude Code CLI subprocess wrapper
    codex_runner.py           # OpenAI Codex CLI subprocess wrapper
    kimi_runner.py            # Moonshot Kimi CLI subprocess wrapper
  search/
    ddg.py                    # duckduckgo-search client wrapper
```

### Three-phase orchestrator

Each research task runs in a daemon thread on the Flask process:

1. **Plan** — 1 LLM call via `Config.get_step_llm_config('research_plan')` decomposes the vague prompt into 3-8 sub-topics with specific research questions
2. **Research** — `ThreadPoolExecutor` fans out sub-topics to the chosen runner (up to `RESEARCH_MAX_PARALLEL` in parallel); each runner returns a `ResearchSummary` with citations
3. **Synthesise** — 1 LLM call via `Config.get_step_llm_config('research_synthesis')` merges the summaries into a single coherent compiled document

State is persisted to `uploads/research/{task_id}/state.json` after every phase transition, so tasks survive restarts and the frontend's polling endpoint (`/api/research/status/<task_id>`) always sees current state.

### Runner pattern

Each runner is a thin subprocess wrapper (CLI runners) or HTTP loop (API runner) implementing `CLIRunner.is_available()` and `CLIRunner.run(sub_topic, system_prompt, timeout)`. The orchestrator does not care which runner is used — it dispatches purely by name. Runners are registered in the orchestrator's registry on module import; missing runner modules fail silently so the API fallback always works.

CLI runners shell out with an **explicit minimal environment** (`PATH`, `HOME`, `USER`, `LANG`, `TERM`, `TMPDIR`, `SHELL`, plus CLI-specific keys like `OPENAI_API_KEY` or `MOONSHOT_API_KEY`). LemonFish secrets like `LLM_API_KEY` and `ZEP_API_KEY` are deliberately stripped before the CLI is invoked so they don't leak into the CLI tool's context or logs.

### Reuses from earlier phases

| Research module needs | Provided by | File |
|-----------------------|-------------|------|
| Per-phase LLM routing | Phase 2 | `Config.get_step_llm_config()` |
| Retry + fallback for LLM calls | Phase 0 | `LLMClient` with exponential backoff |
| JSON mode with prompt-based fallback | Phase 5 | `LLMClient.chat_json` capability auto-detection |
| Task cancellation | Phase 7 | `TaskManager.request_cancel / is_cancelled` |
| Project creation + storage layout | Phase 0 | `ProjectManager.create_project / save_extracted_text` |

### Docker support

Because the CLI runners need the user's host OAuth credentials (`~/.claude`, `~/.codex`, `~/.config/kimi`), the slim Docker image does not enable the research module by default. Users opt in via the research compose overlay:

```bash
docker compose -f docker-compose.slim.yml -f docker-compose.research.yml up -d
```

The overlay sets `RESEARCH_ENABLED=true` and mounts the three CLI config directories read-only into the container. Windows users (or deployments without those CLIs installed) can still use the API fallback runner (`RESEARCH_RUNNERS=api`), which only needs the existing `LLM_API_KEY` and the `ddgs` package.

See **[docs/research_module.md](./research_module.md)** for the full user guide, runner details, API surface, and troubleshooting.
