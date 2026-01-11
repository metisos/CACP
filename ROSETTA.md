# Rosetta

> CACP (Coding Agent Coordination Protocol) v2.0 - An open protocol enabling AI coding agents on different servers to coordinate on features spanning multiple codebases.

<!-- rosetta:sections:
overview
tech stack
architecture
directory structure
conventions
entry points
key patterns
module index
gotchas
agent notes
-->

## Overview

CACP enables AI coding agents to coordinate on multi-repo features by agreeing on interface contracts (APIs, data models, events), sharing context (code snippets, type definitions, decisions), and tracking implementation progress. Architecture is peer-to-peer with no shared database - each agent maintains its own local MemoryStore, synchronized via JSON-RPC broadcast messages.

## Tech Stack

- **Python**: 3.10+ (async/await, type hints)
- **FastAPI**: >=0.100.0 (JSON-RPC server)
- **Pydantic**: >=2.0.0 (data validation)
- **httpx/aiohttp**: Async HTTP for peer communication
- **PyJWT**: Project-scoped tokens
- **pytest-asyncio**: Test framework

## Architecture

```
┌─────────────────┐    JSON-RPC     ┌─────────────────┐
│   Agent A       │◄───broadcast───►│   Agent B       │
│  (Backend)      │                 │  (Frontend)     │
├─────────────────┤                 ├─────────────────┤
│  MemoryStore    │                 │  MemoryStore    │
│  (independent)  │                 │  (independent)  │
└────────┬────────┘                 └────────┬────────┘
         │                                   │
         └─────────►  ADP Exchange  ◄────────┘
                   (peer discovery)
```

## Directory Structure

```
src/
├── main.py              # Entry point - agent server startup
├── models/              # Pydantic data models
│   ├── enums.py         # Status enums (Project/Contract/Context)
│   ├── project.py       # Project & RepoContext
│   ├── contract.py      # Contract & Implementation
│   └── context.py       # ContextPacket models
├── store/
│   └── memory_store.py  # In-memory store + JSON persistence
├── handlers/            # JSON-RPC method handlers
│   ├── project_handlers.py
│   ├── contract_handlers.py
│   ├── context_handlers.py
│   ├── implementation_handlers.py
│   ├── sync_handlers.py      # Peer broadcast receivers
│   └── file_handlers.py
├── transport/
│   ├── server.py        # FastAPI + BroadcastingHandlers
│   ├── client.py        # CACPClient for peer calls
│   └── peer_registry.py # Peer discovery & broadcast
├── security/            # API keys, JWT tokens, invites
└── adp/
    └── client.py        # Metis Agentic Exchange integration
```

## Conventions

- **Method naming**: `cacp/{domain}/{action}` (e.g., `cacp/project/create`)
- **All handlers**: Take `(store, agent_id, repo_name)` constructor params
- **Async everywhere**: Handler methods are `async def`, use `await`
- **Pydantic models**: `.model_dump(mode="json")` for serialization
- **UUIDs**: Auto-generated via `Field(default_factory=...)`

## Entry Points

| File | Purpose |
|------|---------|
| `src/main.py` | CLI entry point - starts agent server |
| `src/transport/server.py:create_app()` | Creates FastAPI instance |
| `POST /` | JSON-RPC endpoint for all methods |
| `GET /.well-known/agent.json` | Agent discovery card |
| `GET /health` | Health check endpoint |

## Key Patterns

**JSON-RPC 2.0 Request/Response**:
```json
{"jsonrpc":"2.0","method":"cacp/project/create","params":{...},"id":"1"}
{"jsonrpc":"2.0","result":{...},"id":"1"}
```

**Contract State Machine**:
```
PROPOSED → NEGOTIATING → AGREED → IMPLEMENTED → VERIFIED
```

**Broadcasting Pattern**:
1. Agent calls local handler
2. Handler updates local MemoryStore
3. BroadcastingHandlers wrapper broadcasts to peers
4. Peers receive via sync handlers, update their stores

## Module Index

| Module | Path | Description | Load When |
|--------|------|-------------|-----------|
| handlers | `.rosetta/modules/handlers.md` | Handler method details | Modifying JSON-RPC methods |
| models | `.rosetta/modules/models.md` | Data model schemas | Working with contracts/context |
| transport | `.rosetta/modules/transport.md` | Peer communication | Networking/sync issues |

## Gotchas

- **Agent ID format**: Must be `aid://domain.com/agent@version` for ADP registration
- **Repo name matching**: Agent auto-assigns to repos matching its `--repo` name exactly
- **No shared DB**: Each agent's MemoryStore is independent - sync via broadcasts only
- **Contract transitions**: Follow `VALID_TRANSITIONS` state machine or errors raised
- **Production mode**: If `mode: "production"`, ADP registration is required or server exits
- **Persistence concurrency**: Don't share `persist_path` between multiple agents

## Agent Notes

<!--
  AGENTS: Append learnings below this line.
  Format: ### YYYY-MM-DD | agent-name
-->

### 2026-01-11 | claude
- Initial Rosetta context created from full codebase analysis
- Project has 31 Python files, 25+ JSON-RPC methods, 12 tests passing
- Key docs: `docs/PROTOCOL.md` (full spec), `docs/AGENT_GUIDE.md` (usage)

---

<!-- rosetta:version:1.0 -->
<!-- rosetta:last-updated:2026-01-11 -->
