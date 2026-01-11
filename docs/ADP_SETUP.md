# ADP Setup Guide

**Agent Discovery Protocol (ADP)** is required for CACP agents to discover and coordinate with each other. This guide explains how to set up ADP for your CACP agents.

---

## What is ADP?

ADP (Agent Discovery Protocol) is a registry service that allows AI agents to:

1. **Register** - Publish your agent's capabilities and endpoint
2. **Discover** - Find other compatible agents to coordinate with
3. **Verify** - Confirm agent identities before trusting them

CACP uses the **Metis Agentic Exchange** as its ADP registry:
- URL: `https://agentic-exchange.metisos.co`
- Docs: [ADP Specification](https://github.com/metisos/adp)

---

## Why ADP is Required

Without ADP, CACP agents cannot:

- **Find each other** - How does a frontend agent find a backend agent?
- **Verify identity** - How do you trust incoming coordination requests?
- **Get endpoints** - Where should messages be sent?

```
                    ┌─────────────────────────────┐
                    │   Metis Agentic Exchange    │
                    │         (ADP)               │
                    │                             │
                    │  ┌─────────────────────┐    │
                    │  │  Agent Registry     │    │
                    │  │                     │    │
                    │  │  - Backend Agent    │    │
                    │  │  - Frontend Agent   │    │
                    │  │  - Mobile Agent     │    │
                    │  └─────────────────────┘    │
                    └──────────┬──────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
       ┌────────────┐   ┌────────────┐   ┌────────────┐
       │  Backend   │   │  Frontend  │   │   Mobile   │
       │   Agent    │◄──┤   Agent    │◄──┤   Agent    │
       └────────────┘   └────────────┘   └────────────┘
```

---

## Step 1: Get an Agent ID (AID)

Every agent needs a unique identifier in AID format:

```
aid://your-domain.com/agent-name@version
```

**Examples:**
- `aid://mycompany.com/backend-api@1.0.0`
- `aid://example.io/frontend-react@2.1.0`
- `aid://startup.dev/mobile-agent@1.0.0`

**Requirements:**
- Domain you control (for verification)
- Unique agent name within your domain
- Semantic version number

---

## Step 2: Configure Your Agent

Create a config file (e.g., `config/my-agent.yaml`):

```yaml
agent:
  # Your unique Agent ID (required)
  aid: "aid://your-domain.com/your-agent@1.0.0"
  name: "My Backend Agent"
  description: "Python backend agent for API development"
  owner:
    name: "Your Company"
    site: "https://your-domain.com"
    contact: "agents@your-domain.com"

server:
  host: "0.0.0.0"
  port: 8080

# ADP Configuration (required)
adp:
  exchange_url: "https://agentic-exchange.metisos.co"
  auto_register: true

cacp:
  repo: "backend-api"
  role: "backend"  # backend | frontend | mobile | devops | shared
  languages:
    - "python"
  supported_contract_types:
    - "api_endpoint"
    - "event_schema"
    - "data_model"

mode: "development"  # or "production"
```

---

## Step 3: Register with ADP

### Option A: Auto-Registration (Recommended)

Set `auto_register: true` in your config and start the agent:

```bash
python -m src.main --config config/my-agent.yaml
```

The agent will automatically register with the Agentic Exchange on startup.

### Option B: Manual Registration

Start without auto-register:

```bash
python -m src.main --config config/my-agent.yaml
```

Then register manually:

```bash
python -m src.main --config config/my-agent.yaml --register-adp
```

### Option C: Programmatic Registration

```python
from src.adp import ADPClient

adp = ADPClient("https://agentic-exchange.metisos.co")

manifest = adp.build_manifest(
    aid="aid://your-domain.com/backend@1.0.0",
    name="Backend Agent",
    description="Python backend for API development",
    endpoint="http://your-server:8080",
    role="backend",
    languages=["python"],
    owner={"name": "Your Company", "contact": "you@example.com"}
)

result = await adp.register(manifest)
print(f"Registered: {result}")
```

---

## Step 4: Discover Other Agents

Once registered, you can find other CACP agents:

### Using the ADPClient

```python
from src.adp import ADPClient

adp = ADPClient("https://agentic-exchange.metisos.co")

# Find frontend agents
frontends = await adp.search_cacp_agents(
    role="frontend",
    languages=["typescript", "javascript"]
)

for agent in frontends:
    print(f"Found: {agent.name}")
    print(f"  AID: {agent.aid}")
    print(f"  Endpoint: {agent.endpoint}")
    print(f"  Verified: {agent.verified}")
```

### Using curl

```bash
# Search for CACP agents
curl -X POST https://agentic-exchange.metisos.co/v1/search/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "frontend typescript cacp",
    "filters": {"protocols": ["cacp"]},
    "limit": 10
  }'
```

### Browse All Agents

```bash
curl https://agentic-exchange.metisos.co/v1/agents/
```

---

## Step 5: Connect to Discovered Agents

Once you find agents, register them as peers:

### Automatic (via ADP search)

```python
from src.adp import ADPClient
from src.transport import PeerRegistry

adp = ADPClient()
peers = PeerRegistry(adp_client=adp)

# Search and auto-register peers
await peers.search_adp(role="frontend")

# Now they're registered for broadcasting
```

### Manual Peer Registration

```bash
# Tell your agent about a peer
curl -X POST http://localhost:8080/peers/register \
  -H "Content-Type: application/json" \
  -d '{
    "agentId": "aid://other-domain.com/frontend@1.0.0",
    "endpoint": "http://frontend-server:8081",
    "repoName": "frontend-app"
  }'
```

---

## ADP Manifest Structure

When you register, this is the manifest structure sent to ADP:

```json
{
  "aid": "aid://your-domain.com/backend@1.0.0",
  "name": "Backend Agent",
  "description": "Python backend for API development",
  "owner": {
    "name": "Your Company",
    "site": "https://your-domain.com",
    "contact": "agents@your-domain.com"
  },
  "capabilities": [
    {
      "id": "cacp.coordinate",
      "description": "Cross-repository coordination via CACP v2 protocol"
    }
  ],
  "invocation": {
    "protocols": [
      {
        "type": "cacp",
        "version": "2.0",
        "endpoint": "http://your-server:8080",
        "transportType": "http"
      }
    ],
    "authentication": ["api_key"]
  },
  "metadata": {
    "cacp": {
      "role": "backend",
      "languages": ["python"],
      "supported_contract_types": ["api_endpoint", "data_model"],
      "max_concurrent_projects": 5
    }
  }
}
```

---

## Verification and Trust

ADP provides verification status for agents:

| Status | Meaning | Trust Level |
|--------|---------|-------------|
| `verified: true` | Domain ownership confirmed | Full trust |
| `verified: false` | Not yet verified | Limited trust |

**Best Practice:** Only coordinate with verified agents in production.

```python
agents = await adp.search_cacp_agents(role="frontend")

for agent in agents:
    if agent.verified:
        # Safe to coordinate
        await peers.register_peer(agent.aid, agent.endpoint)
    else:
        # Log warning, require manual approval
        logger.warning(f"Unverified agent: {agent.aid}")
```

---

## Production Checklist

Before deploying to production:

- [ ] Register a real domain for your AID
- [ ] Set `mode: "production"` in config
- [ ] Enable `auto_register: true`
- [ ] Verify your agent gets `verified: true` status
- [ ] Only accept connections from verified agents
- [ ] Use HTTPS for your agent endpoint
- [ ] Set up API key authentication

---

## Troubleshooting

### "ADP registration failed"

1. Check your AID format: `aid://domain.com/name@version`
2. Ensure endpoint is publicly accessible
3. Check network connectivity to exchange

```bash
curl https://agentic-exchange.metisos.co/health
```

### "Agent not found in ADP"

Wait a few seconds after registration, then retry:

```bash
curl https://agentic-exchange.metisos.co/v1/agents/aid%3A%2F%2Fyour-domain.com%2Fagent%401.0.0
```

### "No CACP agents found"

The exchange may have few agents registered. Try:

```bash
# Browse all agents
curl https://agentic-exchange.metisos.co/v1/agents/

# Search without filters
curl -X POST https://agentic-exchange.metisos.co/v1/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "cacp", "limit": 50}'
```

### "Peer not syncing"

1. Check peer registration: `curl http://localhost:8080/peers`
2. Verify peer endpoint is reachable
3. Check peer's health: `curl http://peer-endpoint/health`

---

## API Reference

### ADPClient Methods

| Method | Description |
|--------|-------------|
| `search(query, filters)` | Search for agents |
| `get_agent(aid)` | Get agent by AID |
| `register(manifest)` | Register your agent |
| `browse(limit, offset)` | List all agents |
| `search_cacp_agents(role, languages)` | Find CACP agents |
| `build_manifest(...)` | Build registration manifest |

### ADP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/search/` | POST | Search agents |
| `/v1/agents/` | GET | Browse all agents |
| `/v1/agents/{aid}` | GET | Get specific agent |
| `/v1/register/` | POST | Register agent |

---

## Next Steps

- [Quickstart Guide](QUICKSTART.md) - Get started in 5 minutes
- [Protocol Specification](PROTOCOL.md) - Full CACP reference
- [Agent Guide](AGENT_GUIDE.md) - For AI agents using CACP

---

## Links

- [Metis Agentic Exchange](https://agentic-exchange.metisos.co) - ADP Registry
- [ADP Specification](https://github.com/metisos/adp) - Protocol details
- [CACP Repository](https://github.com/metisos/CACP) - Source code
