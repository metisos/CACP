# CACP - Coding Agent Coordination Protocol

**Enable AI coding agents to collaborate across repositories.**

CACP is an open protocol that allows AI coding agents running on different servers to coordinate on features spanning multiple codebases. Unlike A2A (task delegation) or MCP (tool access), CACP focuses specifically on **cross-repository coordination** through shared contracts and context passing.

## Why CACP?

When AI agents work on features that span multiple repositories (frontend + backend, mobile + API, microservices), they need to:

- **Agree on interfaces** - API contracts, data schemas, event formats
- **Share context** - Type definitions, error codes, implementation decisions
- **Track progress** - Who's implementing what, verification status
- **Discover each other** - Find compatible agents via ADP registry

CACP provides a standardized protocol for all of this.

## Quick Example

```python
from src.adp import ADPClient
from src.transport import CACPClient

# 1. Discover frontend agents via ADP
adp = ADPClient("https://agentic-exchange.metisos.co")
peers = await adp.search_cacp_agents(role="frontend", languages=["typescript"])

# 2. Create a coordination project
client = CACPClient("http://localhost:8080")
project = await client.call("cacp/project/create", {
    "name": "User Auth Feature",
    "objective": "Implement OAuth 2.0 login",
    "repos": [
        {"name": "backend-api", "role": "backend", "language": "python"},
        {"name": "frontend-app", "role": "frontend", "language": "typescript"}
    ]
})

# 3. Propose an API contract
contract = await client.call("cacp/contract/propose", {
    "projectId": project["projectId"],
    "type": "api_endpoint",
    "name": "Login Endpoint",
    "content": {
        "method": "POST",
        "path": "/api/auth/login",
        "requestBody": {"email": "string", "password": "string"},
        "responseBody": {"token": "string", "user": "object"}
    }
})

# 4. Frontend agent reviews and agrees
await frontend_client.call("cacp/contract/respond", {
    "projectId": project["projectId"],
    "contractId": contract["contractId"],
    "action": "agree"
})
```

## Features

| Feature | Description |
|---------|-------------|
| **Contract Negotiation** | Propose, review, and agree on API contracts |
| **Context Sharing** | Share code snippets, type definitions, decisions |
| **Implementation Tracking** | Track who's building what, verify integration |
| **Peer-to-Peer Sync** | Each agent has local state, synced via protocol |
| **ADP Discovery** | Find agents via Metis Agentic Exchange |
| **LLM Agnostic** | Works with any LLM (Groq, OpenAI, Claude, etc.) |

## Installation

```bash
git clone https://github.com/metisos/CACP.git
cd CACP
pip install -r requirements.txt
```

## Running an Agent

```bash
# With config file (recommended)
python -m src.main --config config/agent-config.yaml

# With CLI arguments
python -m src.main \
    --repo backend-api \
    --role backend \
    --language python \
    --port 8080

# With ADP registration
python -m src.main --config config/agent-config.yaml --register-adp
```

## Documentation

| Document | Description |
|----------|-------------|
| [Quickstart](docs/QUICKSTART.md) | Get started in 5 minutes |
| [Protocol Specification](docs/PROTOCOL.md) | Full protocol reference |
| [Agent Guide](docs/AGENT_GUIDE.md) | For AI agents using CACP |
| [Implementation Report](docs/IMPLEMENTATION_REPORT.md) | Architecture details |

## Protocol Overview

### Contract Lifecycle

```
PROPOSED → NEGOTIATING → AGREED → IMPLEMENTED → VERIFIED
    │           │                      │
    └───────────┴──────────────────────┘
              (on rejection/failure)
```

### JSON-RPC Methods

```
cacp/project/create     - Create coordination project
cacp/project/join       - Join a project
cacp/contract/propose   - Propose interface contract
cacp/contract/respond   - Agree, request changes, or reject
cacp/context/share      - Share context (code, types, decisions)
cacp/implementation/*   - Track implementation progress
```

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Metis Agentic Exchange (ADP)               │
│                    Agent Registry                       │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
   ┌────────────┐  ┌────────────┐  ┌────────────┐
   │  Backend   │  │  Frontend  │  │   Mobile   │
   │   Agent    │◄─┼─►  Agent   │◄─┼─►  Agent   │
   │            │  │            │  │            │
   │ Local Store│  │ Local Store│  │ Local Store│
   └────────────┘  └────────────┘  └────────────┘
        │               │               │
        ▼               ▼               ▼
   backend-api/    frontend-app/   mobile-app/
```

Each agent maintains its own local state. State synchronizes via JSON-RPC broadcast messages - no shared database required.

## Demo

Run two Groq-powered agents coordinating on a feature:

```bash
export GROQ_API_KEY=your_key
python examples/groq_agents_demo.py
```

Output:
```
SUMMARY:
  Project: User Profile Feature
  Contract 'Get User Profile' status: verified
  Context packets exchanged: 2
  Implementations: 2

Two Groq-powered agents successfully coordinated!
```

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Results: 12 passed
```

## Contributing

We welcome contributions! Please see our contributing guidelines.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `python -m pytest tests/ -v`
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [GitHub Repository](https://github.com/metisos/CACP) - Source code
- [Metis Agentic Exchange](https://agentic-exchange.metisos.co) - Agent discovery
- [ADP Specification](https://github.com/metisos/adp) - Agent Discovery Protocol
