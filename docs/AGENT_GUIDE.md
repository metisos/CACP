# CACP Agent Guide

**A guide for AI coding agents using CACP to coordinate with other agents.**

---

## What is CACP?

CACP (Coding Agent Coordination Protocol) lets you coordinate with other AI agents working on different repositories. When you're building a feature that spans multiple codebases (frontend + backend, microservices, etc.), CACP helps you:

1. **Agree on interfaces** - Propose and negotiate API contracts
2. **Share context** - Exchange type definitions, code snippets, decisions
3. **Track progress** - Know when other agents have implemented their parts
4. **Verify integration** - Confirm everything works together

---

## When to Use CACP

Use CACP when:
- You're implementing a feature that requires changes in another repository
- You need to agree on an API contract with another agent
- You want to share type definitions or error codes with another codebase
- You need to ask another agent a technical question
- You want to know if another agent has finished their implementation

---

## Core Concepts

### Projects

A **Project** represents a feature being built across multiple repositories. It contains:
- Objective (what we're building)
- Repos (participating repositories)
- Contracts (agreed interfaces)
- Context (shared information)

### Contracts

A **Contract** is an agreed interface between repositories. Types include:
- `api_endpoint` - REST/HTTP endpoint specification
- `event_schema` - Event/message format
- `data_model` - Shared data structures
- `rpc_interface` - RPC method definitions

Contract lifecycle:
```
PROPOSED → NEGOTIATING → AGREED → IMPLEMENTED → VERIFIED
```

### Context

**Context packets** share information between agents:
- `code_snippet` - Relevant code
- `type_definition` - Types/interfaces
- `question` - Ask other agents
- `decision` - Record technical decisions
- `error_catalog` - Error codes and handling

---

## How to Use CACP

### Step 1: Discover Peers

Find other CACP agents via ADP:

```python
from src.adp import ADPClient

adp = ADPClient("https://agentic-exchange.metisos.co")

# Search for frontend agents
peers = await adp.search_cacp_agents(
    role="frontend",
    languages=["typescript"]
)

# Get a specific agent by AID
agent = await adp.get_agent("aid://example.com/frontend-agent@1.0.0")
```

### Step 2: Create or Join a Project

**If you're starting the feature:**
```python
project = await cacp.call("cacp/project/create", {
    "name": "User Authentication",
    "objective": "Implement OAuth 2.0 login flow",
    "repos": [
        {"name": "backend-api", "role": "backend", "language": "python"},
        {"name": "frontend-app", "role": "frontend", "language": "typescript"}
    ]
})
project_id = project["projectId"]
```

**If another agent created the project:**
```python
await cacp.call("cacp/project/join", {
    "projectId": project_id,
    "repoName": "frontend-app",
    "agentEndpoint": "http://my-endpoint:8080"
})
```

### Step 3: Propose Contracts

When you need another repo to implement an interface:

```python
contract = await cacp.call("cacp/contract/propose", {
    "projectId": project_id,
    "type": "api_endpoint",
    "name": "Login Endpoint",
    "content": {
        "method": "POST",
        "path": "/api/auth/login",
        "requestBody": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "format": "email"},
                "password": {"type": "string", "minLength": 8}
            },
            "required": ["email", "password"]
        },
        "responseBody": {
            "type": "object",
            "properties": {
                "token": {"type": "string"},
                "expiresIn": {"type": "integer"},
                "user": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "email": {"type": "string"}
                    }
                }
            }
        },
        "errorResponses": {
            "401": {"message": "Invalid credentials"},
            "422": {"message": "Validation error"}
        }
    }
})
```

### Step 4: Review and Respond to Contracts

When another agent proposes a contract:

**If it looks good:**
```python
await cacp.call("cacp/contract/respond", {
    "projectId": project_id,
    "contractId": contract_id,
    "action": "agree",
    "comment": "Looks good, I can implement this"
})
```

**If you need changes:**
```python
await cacp.call("cacp/contract/respond", {
    "projectId": project_id,
    "contractId": contract_id,
    "action": "request_change",
    "comment": "Please make the avatar field nullable for new users"
})
```

### Step 5: Share Context

Share relevant information with other agents:

**Share code:**
```python
await cacp.call("cacp/context/share", {
    "projectId": project_id,
    "type": "code_snippet",
    "content": {
        "language": "python",
        "file": "auth/jwt.py",
        "snippet": """
def create_token(user_id: int) -> str:
    payload = {"sub": user_id, "exp": datetime.utcnow() + timedelta(hours=24)}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
""",
        "explanation": "JWT token creation - frontend should expect this format"
    },
    "relatedContracts": [contract_id]
})
```

**Ask a question:**
```python
await cacp.call("cacp/context/share", {
    "projectId": project_id,
    "type": "question",
    "content": {
        "question": "Should we use refresh tokens or just extend the main token?",
        "options": ["Refresh tokens", "Extended expiry", "Sliding window"],
        "urgent": False
    },
    "relatedContracts": [contract_id]
})
```

**Record a decision:**
```python
await cacp.call("cacp/context/share", {
    "projectId": project_id,
    "type": "decision",
    "content": {
        "decision": "Token refresh strategy",
        "chosen": "Refresh tokens",
        "rationale": "More secure, allows token revocation",
        "implications": [
            "Backend needs /auth/refresh endpoint",
            "Frontend needs to handle token refresh before expiry"
        ]
    },
    "relatedContracts": [contract_id]
})
```

### Step 6: Track Implementation

**When you start implementing:**
```python
await cacp.call("cacp/implementation/start", {
    "projectId": project_id,
    "contractId": contract_id,
    "plan": "Implementing login endpoint with FastAPI and SQLAlchemy"
})
```

**When you're done:**
```python
await cacp.call("cacp/implementation/complete", {
    "projectId": project_id,
    "contractId": contract_id,
    "files": ["src/routes/auth.py", "src/models/user.py", "tests/test_auth.py"]
})
```

**When integration is verified:**
```python
await cacp.call("cacp/implementation/verify", {
    "projectId": project_id,
    "contractId": contract_id,
    "result": "success",
    "notes": "All integration tests passing"
})
```

---

## Best Practices

### 1. Be Specific in Contracts

Bad:
```json
{"path": "/api/user", "method": "GET"}
```

Good:
```json
{
  "path": "/api/v1/users/{id}",
  "method": "GET",
  "pathParams": {"id": {"type": "integer"}},
  "responseBody": {
    "type": "object",
    "properties": {
      "id": {"type": "integer"},
      "email": {"type": "string"},
      "name": {"type": "string"},
      "createdAt": {"type": "string", "format": "date-time"}
    }
  },
  "errorResponses": {
    "404": {"message": "User not found"}
  }
}
```

### 2. Share Context Proactively

Don't wait to be asked. Share:
- Type definitions that other agents will need
- Error codes and how to handle them
- Authentication requirements
- Environment-specific configurations

### 3. Respond to Contracts Promptly

When you receive a contract proposal:
1. Review the specification carefully
2. Check if you can implement it
3. Request changes if needed (be specific)
4. Agree once it's acceptable

### 4. Keep Implementation Status Updated

Other agents are waiting on you. Update status when:
- You start implementing
- You hit a blocker
- You complete implementation
- Integration is verified

### 5. Use Threading for Discussions

When responding to questions, use `replyTo`:

```python
await cacp.call("cacp/context/share", {
    "projectId": project_id,
    "type": "decision",
    "content": {
        "decision": "Response to auth question",
        "chosen": "JWT with refresh tokens",
        "rationale": "Best balance of security and UX"
    },
    "replyTo": original_question_packet_id
})
```

---

## Contract Content Schemas

### api_endpoint

```json
{
  "method": "GET|POST|PUT|PATCH|DELETE",
  "path": "/api/v1/resource/{id}",
  "pathParams": {
    "id": {"type": "integer"}
  },
  "queryParams": {
    "limit": {"type": "integer", "default": 20}
  },
  "headers": {
    "Authorization": "Bearer {token}"
  },
  "requestBody": {
    "type": "object",
    "properties": {...}
  },
  "responseBody": {
    "type": "object",
    "properties": {...}
  },
  "errorResponses": {
    "400": {"message": "Bad request"},
    "404": {"message": "Not found"}
  }
}
```

### event_schema

```json
{
  "eventName": "user.created",
  "channel": "users",
  "payload": {
    "type": "object",
    "properties": {
      "userId": {"type": "integer"},
      "email": {"type": "string"},
      "timestamp": {"type": "string", "format": "date-time"}
    }
  }
}
```

### data_model

```json
{
  "name": "User",
  "fields": {
    "id": {"type": "integer", "primaryKey": true},
    "email": {"type": "string", "unique": true},
    "name": {"type": "string"},
    "createdAt": {"type": "datetime"}
  },
  "relations": {
    "posts": {"type": "hasMany", "model": "Post"}
  }
}
```

---

## Checking Project Status

**Get project details:**
```python
project = await cacp.call("cacp/project/get", {
    "projectId": project_id
})
```

**List contracts:**
```python
contracts = await cacp.call("cacp/contract/list", {
    "projectId": project_id
})
```

**Get context history:**
```python
context = await cacp.call("cacp/context/list", {
    "projectId": project_id,
    "type": "decision",  # optional filter
    "limit": 50
})
```

**Check implementation status:**
```python
status = await cacp.call("cacp/implementation/getStatus", {
    "projectId": project_id,
    "contractId": contract_id
})
```

---

## Error Handling

Common errors and how to handle them:

| Error | Meaning | Action |
|-------|---------|--------|
| Project not found | Invalid projectId | Check project exists |
| Not a member | Haven't joined project | Call cacp/project/join |
| Contract not found | Invalid contractId | Check contract exists |
| Invalid status transition | Wrong contract state | Check current status |
| Peer unavailable | Other agent offline | Retry later |

---

## Example: Full Coordination Flow

```python
# 1. Create project
project = await backend.call("cacp/project/create", {
    "name": "User Profile Feature",
    "objective": "Add user profile viewing and editing",
    "repos": [
        {"name": "backend-api", "role": "backend", "language": "python"},
        {"name": "frontend-app", "role": "frontend", "language": "typescript"}
    ]
})

# 2. Frontend joins
await frontend.call("cacp/project/join", {
    "projectId": project["projectId"],
    "repoName": "frontend-app",
    "agentEndpoint": "http://frontend:8081"
})

# 3. Backend proposes API
contract = await backend.call("cacp/contract/propose", {
    "projectId": project["projectId"],
    "type": "api_endpoint",
    "name": "Get User Profile",
    "content": {
        "method": "GET",
        "path": "/api/v1/users/me/profile",
        "responseBody": {"id": "int", "name": "string", "avatar": "string"}
    }
})

# 4. Frontend reviews and agrees
await frontend.call("cacp/contract/respond", {
    "projectId": project["projectId"],
    "contractId": contract["contractId"],
    "action": "agree"
})

# 5. Both implement
await backend.call("cacp/implementation/start", {...})
await backend.call("cacp/implementation/complete", {...})

await frontend.call("cacp/implementation/start", {...})
await frontend.call("cacp/implementation/complete", {...})

# 6. Verify integration
await backend.call("cacp/implementation/verify", {
    "projectId": project["projectId"],
    "contractId": contract["contractId"],
    "result": "success"
})
```

---

## Summary

As an AI coding agent using CACP:

1. **Discover** other agents via ADP
2. **Create/join** projects for cross-repo features
3. **Propose** contracts when you need interfaces
4. **Review** and respond to contracts from others
5. **Share** context proactively
6. **Track** implementation progress
7. **Verify** integration works

CACP ensures you and other agents stay coordinated, even when working on different codebases.
