# CACP Quickstart

Get two AI agents coordinating in 5 minutes.

---

## Prerequisites

- Python 3.10+
- Groq API key (for the demo)
- Understanding of ADP (see [ADP Setup Guide](ADP_SETUP.md))

---

## Step 1: Install

```bash
git clone https://github.com/metisos/CACP.git
cd CACP
pip install -r requirements.txt
```

---

## Step 2: Set API Key

```bash
export GROQ_API_KEY=your_groq_api_key_here
```

Or create `.env.local`:
```
GROQ_API_KEY=your_groq_api_key_here
```

---

## Step 3: Run the Demo

```bash
python examples/groq_agents_demo.py
```

You'll see two LLM-powered agents:
1. **Backend Agent** - Creates project, proposes API contract
2. **Frontend Agent** - Reviews contract, asks questions, implements

Output:
```
STEP 1: Backend Agent creates project
[LLM REQUEST] Backend Agent
[LLM RESPONSE] Backend Agent - Tokens used: 271

STEP 2: Frontend Agent joins
[LLM REQUEST] Frontend Agent
...

SUMMARY:
  Project: User Profile Feature
  Contract 'Get User Profile' status: verified
  Context packets exchanged: 2
  Implementations: 2

Two Groq-powered agents successfully coordinated!
```

Check `logs/cacp_demo.log` for full details.

---

## Step 4: Run Tests

```bash
python -m pytest tests/ -v
```

All 12 tests should pass.

---

## Step 5: Configure ADP (Required for Multi-Agent)

CACP agents discover each other through **ADP (Agent Discovery Protocol)**. Skip this for local testing, but it's required for real coordination.

### Get an Agent ID (AID)

Create a unique identifier for your agent:
```
aid://your-domain.com/agent-name@version
```

Example: `aid://mycompany.com/backend-api@1.0.0`

### Configure ADP Registration

In your config file, set:
```yaml
adp:
  exchange_url: "https://agentic-exchange.metisos.co"
  auto_register: true  # Registers on startup
```

When you start the agent, it automatically registers with the Metis Agentic Exchange.

See [ADP Setup Guide](ADP_SETUP.md) for complete details.

---

## Step 6: Start Your Own Agent

### Option A: CLI Arguments (Local Testing)

```bash
python -m src.main \
    --repo my-backend \
    --role backend \
    --language python \
    --port 8080
```

### Option B: Config File (Recommended)

Create `config/my-agent.yaml`:
```yaml
agent:
  aid: "aid://mycompany.com/backend-agent@1.0.0"
  name: "My Backend Agent"
  description: "Python backend agent with CACP coordination"

server:
  host: "0.0.0.0"
  port: 8080

adp:
  exchange_url: "https://agentic-exchange.metisos.co"
  auto_register: true

cacp:
  repo: "my-backend"
  role: "backend"
  languages: ["python"]
  supported_contract_types:
    - "api_endpoint"
    - "data_model"

mode: "development"
```

Run:
```bash
python -m src.main --config config/my-agent.yaml
```

---

## Step 7: Connect Two Agents

Terminal 1 (Backend):
```bash
python -m src.main --repo backend-api --role backend --port 8080
```

Terminal 2 (Frontend):
```bash
python -m src.main --repo frontend-app --role frontend --port 8081
```

### Option A: Discover via ADP (Production)

If both agents registered with ADP, they can discover each other:

```python
from src.adp import ADPClient

adp = ADPClient("https://agentic-exchange.metisos.co")
frontends = await adp.search_cacp_agents(role="frontend")
# Returns list of registered frontend agents with endpoints
```

### Option B: Manual Peer Registration (Local Testing)

```bash
# Tell backend about frontend
curl -X POST http://localhost:8080/peers/register \
  -H "Content-Type: application/json" \
  -d '{"agentId": "agent-frontend-app", "endpoint": "http://localhost:8081"}'

# Tell frontend about backend
curl -X POST http://localhost:8081/peers/register \
  -H "Content-Type: application/json" \
  -d '{"agentId": "agent-backend-api", "endpoint": "http://localhost:8080"}'
```

---

## Step 8: Make Your First API Call

Create a project:
```bash
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "cacp/project/create",
    "params": {
      "name": "My Feature",
      "objective": "Build something cool",
      "repos": [
        {"name": "backend-api", "role": "backend", "language": "python"},
        {"name": "frontend-app", "role": "frontend", "language": "typescript"}
      ]
    },
    "id": "1"
  }'
```

Response:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "projectId": "abc123...",
    "status": "created",
    "repoCount": 2
  },
  "id": "1"
}
```

---

## Next Steps

- Read the [ADP Setup Guide](ADP_SETUP.md) for agent discovery configuration
- Read the [Protocol Specification](PROTOCOL.md) for all methods
- Read the [Agent Guide](AGENT_GUIDE.md) for AI agent usage
- Check [examples/](../examples/) for more demos

---

## Troubleshooting

### "GROQ_API_KEY not set"

Set the environment variable:
```bash
export GROQ_API_KEY=your_key
```

### "Connection refused"

Agent not running. Start it:
```bash
python -m src.main --repo my-repo --port 8080
```

### "Method not found"

Check method name. List available methods:
```bash
curl http://localhost:8080/methods
```

### Peer not syncing

Check peer registration:
```bash
curl http://localhost:8080/peers
```

---

## Quick Reference

| Action | Method |
|--------|--------|
| Create project | `cacp/project/create` |
| Join project | `cacp/project/join` |
| Propose contract | `cacp/contract/propose` |
| Agree to contract | `cacp/contract/respond` (action: "agree") |
| Share context | `cacp/context/share` |
| Start implementing | `cacp/implementation/start` |
| Complete implementation | `cacp/implementation/complete` |
| Verify integration | `cacp/implementation/verify` |
