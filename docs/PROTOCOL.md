# CACP Protocol Specification

**Version:** 2.0
**Status:** Stable
**Transport:** JSON-RPC 2.0 over HTTP

---

## Overview

CACP (Coding Agent Coordination Protocol) enables AI coding agents to coordinate on cross-repository features. Agents communicate via JSON-RPC 2.0 over HTTP, with state synchronized peer-to-peer.

## Transport

### Endpoint

All JSON-RPC calls go to the root endpoint:

```
POST /
Content-Type: application/json
```

### Request Format

```json
{
  "jsonrpc": "2.0",
  "method": "cacp/project/create",
  "params": {
    "name": "Feature Name",
    "objective": "What we're building"
  },
  "id": "request-123"
}
```

### Response Format

**Success:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "projectId": "uuid-here",
    "status": "created"
  },
  "id": "request-123"
}
```

**Error:**
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params: projectId required"
  },
  "id": "request-123"
}
```

### Error Codes

| Code | Meaning |
|------|---------|
| -32700 | Parse error |
| -32600 | Invalid request |
| -32601 | Method not found |
| -32602 | Invalid params |
| -32000 | Server error |

---

## Data Types

### Project

```typescript
interface Project {
  project_id: string;      // UUID
  name: string;            // Human-readable name
  objective: string;       // What we're building
  status: ProjectStatus;   // planning | implementing | integrating | complete
  repos: RepoContext[];    // Participating repositories
  contracts: Contract[];   // Interface agreements
  context_history: ContextPacket[];
  created_at: string;      // ISO 8601
  updated_at: string;
}

interface RepoContext {
  repo_id: string;         // UUID
  name: string;            // e.g., "backend-api"
  role: string;            // backend | frontend | mobile | shared | infra
  language: string;        // python | typescript | go | etc.
  agent_id?: string;       // Assigned agent (AID format)
  agent_endpoint?: string; // Agent's HTTP endpoint
}
```

### Contract

```typescript
interface Contract {
  contract_id: string;     // UUID
  type: ContractType;      // api_endpoint | event_schema | data_model | etc.
  name: string;            // Descriptive name
  version: number;         // Increments on update
  status: ContractStatus;  // proposed | negotiating | agreed | implemented | verified
  content: object;         // Type-specific schema
  proposed_by: string;     // repo_id
  implementations: Implementation[];
  history: ContractVersion[];
  created_at: string;
  updated_at: string;
}

type ContractType =
  | "api_endpoint"
  | "event_schema"
  | "data_model"
  | "config_spec"
  | "rpc_interface"
  | "custom";

type ContractStatus =
  | "proposed"
  | "negotiating"
  | "agreed"
  | "implemented"
  | "verified";
```

### ContextPacket

```typescript
interface ContextPacket {
  packet_id: string;       // UUID
  from_repo: string;       // repo_id
  from_agent: string;      // agent_id (AID format)
  timestamp: string;       // ISO 8601
  type: ContextType;
  content: object;         // Type-specific content
  related_contracts: string[];  // contract_ids
  reply_to?: string;       // packet_id for threading
}

type ContextType =
  | "code_snippet"
  | "type_definition"
  | "api_spec"
  | "error_catalog"
  | "env_config"
  | "test_case"
  | "dependency_info"
  | "implementation_status"
  | "question"
  | "decision";
```

### Agent ID (AID)

Agents are identified using ADP Agent ID format:

```
aid://domain.com/agent-name@version
```

Examples:
- `aid://example.com/backend-agent@1.0.0`
- `aid://mycompany.io/frontend-react@2.1.0`

---

## Methods

### Project Methods

#### cacp/project/create

Create a new coordination project.

**Params:**
```json
{
  "name": "User Auth Feature",
  "objective": "Implement OAuth 2.0 login across frontend and backend",
  "repos": [
    {"name": "backend-api", "role": "backend", "language": "python"},
    {"name": "frontend-app", "role": "frontend", "language": "typescript"}
  ]
}
```

**Result:**
```json
{
  "projectId": "f0ebc7e6-3b58-4d02-abb1-b63e1e0ba7ac",
  "status": "created",
  "repoCount": 2
}
```

**Broadcasts:** `cacp/project/sync` to all peers

---

#### cacp/project/join

Join a project and claim a repository.

**Params:**
```json
{
  "projectId": "f0ebc7e6-3b58-4d02-abb1-b63e1e0ba7ac",
  "repoName": "frontend-app",
  "agentEndpoint": "http://frontend-agent:8081"
}
```

**Result:**
```json
{
  "repoId": "abc123",
  "status": "joined"
}
```

**Broadcasts:** `cacp/repo/sync` to all peers

---

#### cacp/project/get

Get project details.

**Params:**
```json
{
  "projectId": "f0ebc7e6-3b58-4d02-abb1-b63e1e0ba7ac"
}
```

**Result:** Full Project object

---

#### cacp/project/list

List all projects.

**Params:** `{}` (none required)

**Result:**
```json
{
  "projects": [Project, Project, ...]
}
```

---

### Contract Methods

#### cacp/contract/propose

Propose a new interface contract.

**Params:**
```json
{
  "projectId": "f0ebc7e6-...",
  "type": "api_endpoint",
  "name": "Get User Profile",
  "content": {
    "method": "GET",
    "path": "/api/v1/users/profile",
    "headers": {
      "Authorization": "Bearer {token}"
    },
    "responseBody": {
      "type": "object",
      "properties": {
        "id": {"type": "integer"},
        "email": {"type": "string"},
        "name": {"type": "string"}
      }
    }
  }
}
```

**Result:**
```json
{
  "contractId": "695296cc-d05a-4f43-99cd-ec3b6197461b",
  "version": 1,
  "status": "proposed"
}
```

**Broadcasts:** `cacp/contract/sync` to all peers

---

#### cacp/contract/respond

Respond to a contract proposal.

**Params:**
```json
{
  "projectId": "f0ebc7e6-...",
  "contractId": "695296cc-...",
  "action": "agree",
  "comment": "Looks good!"
}
```

**Actions:**
- `agree` - Accept the contract
- `request_change` - Request modifications (provide comment)
- `reject` - Reject the contract

**Result:**
```json
{
  "status": "agreed",
  "version": 1
}
```

**Broadcasts:** `cacp/contract/sync` to all peers

---

#### cacp/contract/update

Update contract content (when in negotiating state).

**Params:**
```json
{
  "projectId": "f0ebc7e6-...",
  "contractId": "695296cc-...",
  "content": {
    "method": "GET",
    "path": "/api/v1/users/profile",
    "responseBody": { ... }
  },
  "changeNote": "Made avatar field nullable"
}
```

**Result:**
```json
{
  "version": 2,
  "status": "proposed"
}
```

**Broadcasts:** `cacp/contract/sync` to all peers

---

### Context Methods

#### cacp/context/share

Share context with the project.

**Params:**
```json
{
  "projectId": "f0ebc7e6-...",
  "type": "code_snippet",
  "content": {
    "language": "python",
    "file": "auth/jwt.py",
    "snippet": "def verify_token(token: str) -> dict: ...",
    "explanation": "JWT verification function for authentication"
  },
  "relatedContracts": ["695296cc-..."]
}
```

**Result:**
```json
{
  "packetId": "abc123",
  "status": "shared"
}
```

**Broadcasts:** `cacp/context/sync` to all peers

---

#### cacp/context/askQuestion

Convenience method to ask a question.

**Params:**
```json
{
  "projectId": "f0ebc7e6-...",
  "question": "Should we use JWT or session cookies for auth?",
  "options": ["JWT tokens", "Session cookies", "OAuth tokens"],
  "urgent": false,
  "relatedContracts": ["695296cc-..."]
}
```

---

#### cacp/context/recordDecision

Record a technical decision.

**Params:**
```json
{
  "projectId": "f0ebc7e6-...",
  "decision": "Authentication method",
  "chosen": "JWT tokens",
  "rationale": "Better for stateless API, works across services",
  "implications": [
    "Frontend must store token securely",
    "Backend needs token refresh endpoint"
  ],
  "relatedContracts": ["695296cc-..."]
}
```

---

### Implementation Methods

#### cacp/implementation/start

Signal that you're starting implementation.

**Params:**
```json
{
  "projectId": "f0ebc7e6-...",
  "contractId": "695296cc-...",
  "plan": "Will implement GET endpoint with SQLAlchemy ORM"
}
```

---

#### cacp/implementation/complete

Mark your implementation as complete.

**Params:**
```json
{
  "projectId": "f0ebc7e6-...",
  "contractId": "695296cc-...",
  "files": ["src/routes/user.py", "src/models/user.py"]
}
```

---

#### cacp/implementation/verify

Verify that integration works.

**Params:**
```json
{
  "projectId": "f0ebc7e6-...",
  "contractId": "695296cc-...",
  "result": "success",
  "notes": "Integration tests passing"
}
```

---

### Sync Methods (Peer-to-Peer)

These methods are called automatically when broadcasting state changes.

#### cacp/project/sync

Receive project state from a peer.

**Params:**
```json
{
  "project": { ... full project object ... },
  "source_agent": "aid://example.com/backend@1.0.0"
}
```

---

#### cacp/contract/sync

Receive contract update from a peer.

**Params:**
```json
{
  "projectId": "f0ebc7e6-...",
  "contract": { ... full contract object ... },
  "source_agent": "aid://example.com/backend@1.0.0"
}
```

---

#### cacp/context/sync

Receive context packet from a peer.

**Params:**
```json
{
  "projectId": "f0ebc7e6-...",
  "packet": { ... full packet object ... },
  "source_agent": "aid://example.com/backend@1.0.0"
}
```

---

## Discovery Endpoints

### GET /.well-known/agent.json

Returns agent card for discovery.

```json
{
  "name": "CACP Agent (backend-api)",
  "description": "Coding agent for backend-api repository",
  "version": "2.0.0",
  "url": "http://localhost:8080",
  "protocols": {
    "a2a": "0.3",
    "cacp": "2.0"
  },
  "capabilities": ["python", "backend"],
  "extensions": {
    "cacp": {
      "repo": "backend-api",
      "role": "backend",
      "language": "python",
      "agentId": "aid://example.com/backend@1.0.0",
      "supportedContractTypes": ["api_endpoint", "event_schema", "data_model"]
    }
  }
}
```

### GET /health

Health check endpoint.

```json
{
  "status": "healthy",
  "agentId": "aid://example.com/backend@1.0.0",
  "repo": "backend-api",
  "peerCount": 2
}
```

### GET /methods

List available methods.

```json
{
  "methods": [
    "cacp/project/create",
    "cacp/project/join",
    "cacp/contract/propose",
    ...
  ]
}
```

### POST /peers/register

Register a peer agent.

**Body:**
```json
{
  "agentId": "aid://example.com/frontend@1.0.0",
  "endpoint": "http://frontend-agent:8081",
  "repoName": "frontend-app"
}
```

---

## State Synchronization

### Broadcast Flow

When an agent modifies state, it broadcasts to all peers:

```
Agent A                              Agent B
   │                                    │
   │  1. cacp/contract/propose          │
   │  (modifies local state)            │
   │                                    │
   │  2. cacp/contract/sync ──────────► │
   │     (broadcast to peers)           │
   │                                    │
   │                              (stores locally)
   │                                    │
```

### Conflict Resolution

Currently uses last-write-wins based on:
1. Version number (higher wins)
2. Updated timestamp (newer wins)

---

## ADP Integration

Agents discover each other via ADP (Agent Discovery Protocol):

### Search for Agents

```
POST https://agentic-exchange.metisos.co/v1/search/
{
  "query": "frontend typescript react cacp",
  "filters": {"protocols": ["cacp"]},
  "limit": 10
}
```

### Register Agent

```
POST https://agentic-exchange.metisos.co/v1/register/
{
  "manifest": {
    "aid": "aid://example.com/backend@1.0.0",
    "name": "Backend Agent",
    "invocation": {
      "protocols": [
        {"type": "cacp", "version": "2.0", "endpoint": "http://..."}
      ]
    }
  }
}
```

---

## Security Considerations

### Authentication

Agents should verify peers via:
1. ADP registration (verified flag)
2. API key exchange
3. JWT project tokens

### Headers

```
Authorization: Bearer cacp_sk_live_xxx...
X-Agent-ID: aid://example.com/backend@1.0.0
X-Project-Token: eyJhbGc...
```

### Trust Levels

| Level | Source | Access |
|-------|--------|--------|
| Verified | ADP-registered, key exchanged | Full access |
| Known | ADP-registered, no key | Read-only |
| Unknown | Not in ADP | Rejected |

---

## Versioning

Protocol version is included in agent cards:

```json
{
  "protocols": {
    "cacp": "2.0"
  }
}
```

Breaking changes increment major version. Agents should check compatibility before coordination.
