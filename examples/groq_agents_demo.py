#!/usr/bin/env python3
"""
Two Groq-Powered Agents Communicating via CACP

This demo runs two AI agents (powered by Groq's LLM) that coordinate
on implementing a feature across frontend and backend repositories.

The agents use the CACP protocol to:
1. Create and join a project
2. Propose and negotiate API contracts
3. Share context and make decisions
4. Track implementation progress

In production, agents discover each other via ADP (Agent Discovery Protocol)
through the Metis Agentic Exchange. This demo uses in-memory TestClients
for simplicity, but shows how ADP would be integrated.

Usage:
    export GROQ_API_KEY=your_key_here
    python examples/groq_agents_demo.py

ADP Integration (Production):
    1. Agents register with https://agentic-exchange.metisos.co on startup
    2. Agents discover peers via ADP search: adp.search_cacp_agents(role="frontend")
    3. Agents verify peer identities via ADP before coordination
    4. See src/adp/client.py and config/agent-config.yaml for details
"""

import asyncio
import json
import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

sys.path.insert(0, ".")

from groq import Groq
from src.store import MemoryStore
from src.transport import create_app, CACPClient
from fastapi.testclient import TestClient


# Configure logging - both console and file
import os
import re
log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "cacp_demo.log")

# Custom formatter that strips ANSI codes for file output
class StripAnsiFormatter(logging.Formatter):
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')

    def format(self, record):
        msg = super().format(record)
        return self.ansi_escape.sub('', msg)

# Create logger
logger = logging.getLogger("cacp_demo")
logger.setLevel(logging.INFO)

# Console handler (with colors)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S"))

# File handler (without ANSI colors)
file_handler = logging.FileHandler(log_file, mode='w')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(StripAnsiFormatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S"))

logger.addHandler(console_handler)
logger.addHandler(file_handler)

logger.info(f"Logging to file: {log_file}")

# Colors for terminal output
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def log_llm_request(agent_name: str, prompt: str):
    """Log an LLM request."""
    logger.info(f"{Colors.YELLOW}[LLM REQUEST]{Colors.ENDC} {Colors.BOLD}{agent_name}{Colors.ENDC}")
    logger.info(f"{Colors.YELLOW}Prompt:{Colors.ENDC}\n{prompt[:500]}{'...' if len(prompt) > 500 else ''}\n")


def log_llm_response(agent_name: str, response: str, tokens_used: int = 0):
    """Log an LLM response."""
    logger.info(f"{Colors.GREEN}[LLM RESPONSE]{Colors.ENDC} {Colors.BOLD}{agent_name}{Colors.ENDC}")
    if tokens_used:
        logger.info(f"{Colors.GREEN}Tokens used:{Colors.ENDC} {tokens_used}")
    logger.info(f"{Colors.GREEN}Response:{Colors.ENDC}\n{response}\n")


def log_cacp_request(method: str, params: Dict[str, Any]):
    """Log a CACP JSON-RPC request."""
    logger.info(f"{Colors.CYAN}[CACP REQUEST]{Colors.ENDC} {Colors.BOLD}{method}{Colors.ENDC}")
    # Truncate large content for readability
    params_str = json.dumps(params, indent=2, default=str)
    if len(params_str) > 1000:
        params_str = params_str[:1000] + "\n... (truncated)"
    logger.info(f"{Colors.CYAN}Params:{Colors.ENDC}\n{params_str}\n")


def log_cacp_response(method: str, result: Dict[str, Any]):
    """Log a CACP JSON-RPC response."""
    logger.info(f"{Colors.BLUE}[CACP RESPONSE]{Colors.ENDC} {Colors.BOLD}{method}{Colors.ENDC}")
    result_str = json.dumps(result, indent=2, default=str)
    if len(result_str) > 1000:
        result_str = result_str[:1000] + "\n... (truncated)"
    logger.info(f"{Colors.BLUE}Result:{Colors.ENDC}\n{result_str}\n")


def log_step(step_num: int, description: str):
    """Log a major step in the demo."""
    logger.info(f"\n{Colors.HEADER}{'='*70}")
    logger.info(f"STEP {step_num}: {description}")
    logger.info(f"{'='*70}{Colors.ENDC}\n")


def log_event(event_type: str, message: str):
    """Log a general event."""
    logger.info(f"{Colors.BOLD}[{event_type}]{Colors.ENDC} {message}")


# Load Groq API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    # Try loading from .env.local
    env_path = "/root/share/.env.local"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("GROQ_API_KEY="):
                    GROQ_API_KEY = line.strip().split("=", 1)[1]
                    break

if not GROQ_API_KEY:
    print("ERROR: GROQ_API_KEY not set")
    sys.exit(1)


class GroqAgent:
    """An AI agent powered by Groq that communicates via CACP."""

    def __init__(
        self,
        name: str,
        role: str,
        language: str,
        repo_name: str,
        cacp_client: Any,
        system_prompt: str,
    ):
        self.name = name
        self.role = role
        self.language = language
        self.repo_name = repo_name
        self.cacp = cacp_client
        self.groq = Groq(api_key=GROQ_API_KEY)
        self.system_prompt = system_prompt
        self.conversation_history: List[Dict[str, str]] = []

    def think(self, prompt: str, context: str = "") -> str:
        """Use Groq LLM to think about a problem and generate a response."""
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]

        # Add conversation history
        messages.extend(self.conversation_history[-10:])  # Last 10 messages

        # Add current prompt
        full_prompt = prompt
        if context:
            full_prompt = f"Context:\n{context}\n\nTask:\n{prompt}"

        messages.append({"role": "user", "content": full_prompt})

        # Log the request
        log_llm_request(self.name, full_prompt)

        response = self.groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )

        answer = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else 0

        # Log the response
        log_llm_response(self.name, answer, tokens_used)

        # Update conversation history
        self.conversation_history.append({"role": "user", "content": full_prompt})
        self.conversation_history.append({"role": "assistant", "content": answer})

        return answer

    def decide_contract_response(self, contract: Dict[str, Any]) -> tuple[str, str]:
        """Use LLM to decide how to respond to a contract proposal."""
        prompt = f"""
You are reviewing an API contract proposal. Analyze it and decide your response.

Contract Name: {contract.get('name')}
Contract Type: {contract.get('type')}
Content:
{json.dumps(contract.get('content', {}), indent=2)}

As a {self.role} developer working with {self.language}, evaluate this contract.

Respond with EXACTLY one of these formats:
1. AGREE: <brief reason why you agree>
2. REQUEST_CHANGE: <specific change you want and why>
3. REJECT: <reason for rejection>

Be constructive and practical. Consider what your {self.role} needs.
"""
        response = self.think(prompt)

        # Parse response
        response_upper = response.upper()
        if response_upper.startswith("AGREE"):
            return "agree", response.split(":", 1)[-1].strip()
        elif response_upper.startswith("REQUEST_CHANGE"):
            return "request_change", response.split(":", 1)[-1].strip()
        elif response_upper.startswith("REJECT"):
            return "reject", response.split(":", 1)[-1].strip()
        else:
            # Default to agree if parsing fails
            return "agree", response

    def generate_contract_proposal(self, feature_description: str) -> Dict[str, Any]:
        """Use LLM to generate an API contract proposal."""
        prompt = f"""
You need to propose an API contract for this feature: {feature_description}

You are the {self.role} developer. Generate a REST API endpoint contract.

Respond with a JSON object containing:
{{
    "name": "descriptive endpoint name",
    "method": "GET/POST/PUT/DELETE",
    "path": "/api/...",
    "requestBody": {{ JSON Schema for request body or null }},
    "responseBody": {{ JSON Schema for response }},
    "errors": [{{ "code": number, "name": "ErrorName", "description": "..." }}]
}}

Only output the JSON, no other text.
"""
        response = self.think(prompt)

        # Try to parse JSON from response
        try:
            # Find JSON in response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

        # Fallback contract
        return {
            "method": "POST",
            "path": "/api/feature",
            "requestBody": {"type": "object"},
            "responseBody": {"type": "object"},
        }

    def generate_question(self, topic: str) -> str:
        """Generate a clarifying question about the implementation."""
        prompt = f"""
You're implementing a feature and need clarification from the other team.
Topic: {topic}

As a {self.role} developer, ask ONE specific technical question that would help
you implement your part correctly. Keep it concise.
"""
        return self.think(prompt)

    def generate_decision(self, question: str, options: List[str]) -> tuple[str, str]:
        """Make a decision given options."""
        prompt = f"""
Question: {question}

Options:
{chr(10).join(f'- {opt}' for opt in options)}

As a {self.role} developer, choose the best option and explain why in 1-2 sentences.

Format your response as:
CHOICE: <exact option text>
REASON: <brief explanation>
"""
        response = self.think(prompt)

        # Parse response
        choice = options[0]  # Default
        reason = response

        for line in response.split("\n"):
            if line.upper().startswith("CHOICE:"):
                choice_text = line.split(":", 1)[-1].strip()
                # Find closest matching option
                for opt in options:
                    if opt.lower() in choice_text.lower() or choice_text.lower() in opt.lower():
                        choice = opt
                        break
            elif line.upper().startswith("REASON:"):
                reason = line.split(":", 1)[-1].strip()

        return choice, reason


class InMemoryCACPClient:
    """CACP client that talks to an in-memory TestClient."""

    def __init__(self, test_client: TestClient, agent_id: str):
        self.client = test_client
        self.agent_id = agent_id

    def call(self, method: str, params: dict) -> dict:
        # Log the request
        log_cacp_request(method, params)

        response = self.client.post("/", json={
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": "1",
        })
        data = response.json()

        if "error" in data:
            logger.error(f"{Colors.RED}[CACP ERROR]{Colors.ENDC} {method}: {data['error']['message']}")
            raise Exception(f"RPC Error: {data['error']['message']}")

        result = data.get("result", {})

        # Log the response
        log_cacp_response(method, result)

        return result


async def run_demo():
    """Run the two-agent coordination demo with Groq LLMs."""
    logger.info(f"\n{Colors.HEADER}{'='*70}")
    logger.info(f"CACP v2 - Two Groq-Powered Agents Coordinating")
    logger.info(f"Using Groq LLM: llama-3.3-70b-versatile")
    logger.info(f"ADP Exchange: https://agentic-exchange.metisos.co")
    logger.info(f"{'='*70}{Colors.ENDC}\n")

    # ==========================================================================
    # In production, agents would discover each other via ADP:
    #
    #   from src.adp import ADPClient
    #   adp = ADPClient("https://agentic-exchange.metisos.co")
    #
    #   # Search for frontend agents that support CACP
    #   peers = await adp.search_cacp_agents(role="frontend", languages=["typescript"])
    #
    #   # Register discovered peers
    #   for peer in peers:
    #       peer_registry.register_peer(
    #           agent_id=peer.aid,
    #           endpoint=peer.endpoint,
    #           verified=peer.verified,
    #       )
    #
    # For this demo, we use in-memory TestClients with a shared store.
    # ==========================================================================

    # Create shared store (for demo simplicity - production uses separate stores)
    shared_store = MemoryStore()

    # Agent IDs in AID format (as they would be registered in ADP)
    BACKEND_AID = "aid://demo.cacp.dev/backend-agent@1.0.0"
    FRONTEND_AID = "aid://demo.cacp.dev/frontend-agent@1.0.0"

    # Create CACP apps for both agents
    backend_app = create_app(
        agent_id=BACKEND_AID,
        repo_name="backend-api",
        repo_role="backend",
        language="python",
        store=shared_store,
    )
    frontend_app = create_app(
        agent_id=FRONTEND_AID,
        repo_name="frontend-app",
        repo_role="frontend",
        language="typescript",
        store=shared_store,
    )

    # Create in-memory clients (in production, these would be HTTP clients to discovered endpoints)
    backend_cacp = InMemoryCACPClient(TestClient(backend_app), BACKEND_AID)
    frontend_cacp = InMemoryCACPClient(TestClient(frontend_app), FRONTEND_AID)

    # Create Groq-powered agents
    backend_agent = GroqAgent(
        name="Backend Agent",
        role="backend",
        language="Python/FastAPI",
        repo_name="backend-api",
        cacp_client=backend_cacp,
        system_prompt="""You are a senior backend developer working on a Python/FastAPI application.
You design robust APIs, think about security, error handling, and database interactions.
You communicate clearly with frontend teams about API contracts.
Be concise and technical in your responses.""",
    )

    frontend_agent = GroqAgent(
        name="Frontend Agent",
        role="frontend",
        language="TypeScript/React",
        repo_name="frontend-app",
        cacp_client=frontend_cacp,
        system_prompt="""You are a senior frontend developer working on a TypeScript/React application.
You focus on user experience, type safety, and clean component architecture.
You need clear API contracts to build reliable integrations.
Be concise and technical in your responses.""",
    )

    # === STEP 1: Backend creates project ===
    log_step(1, "Backend Agent creates project")

    feature_desc = "User profile management - users can view and update their profile information"

    log_event("FEATURE", feature_desc)
    log_event("THINKING", "Backend Agent analyzing project requirements...")

    backend_thoughts = backend_agent.think(
        f"We're starting a new feature: {feature_desc}. What are the key API endpoints we'll need?"
    )

    project = backend_cacp.call("cacp/project/create", {
        "name": "User Profile Feature",
        "objective": feature_desc,
        "repos": [
            {"name": "backend-api", "role": "backend", "language": "python"},
            {"name": "frontend-app", "role": "frontend", "language": "typescript"},
        ],
    })
    project_id = project["projectId"]
    log_event("PROJECT CREATED", f"ID: {project_id}")

    # === STEP 2: Frontend joins ===
    log_step(2, "Frontend Agent joins project")

    log_event("THINKING", "Frontend Agent analyzing UI requirements...")
    frontend_thoughts = frontend_agent.think(
        f"I'm joining a project for: {feature_desc}. What UI components will I need to build?"
    )

    frontend_cacp.call("cacp/project/join", {
        "projectId": project_id,
        "repoName": "frontend-app",
        "agentEndpoint": "http://frontend:8081",
    })
    log_event("JOINED", "Frontend agent joined the project")

    # === STEP 3: Backend proposes contract ===
    log_step(3, "Backend Agent proposes API contract")

    log_event("THINKING", "Backend Agent generating contract proposal...")
    contract_content = backend_agent.generate_contract_proposal(
        "Get user profile endpoint - retrieve the current user's profile data including name, email, avatar, and preferences"
    )
    log_event("CONTRACT CONTENT", f"\n{json.dumps(contract_content, indent=2)}")

    contract = backend_cacp.call("cacp/contract/propose", {
        "projectId": project_id,
        "type": "api_endpoint",
        "name": "Get User Profile",
        "content": contract_content,
    })
    contract_id = contract["contractId"]
    log_event("CONTRACT PROPOSED", f"ID: {contract_id}")

    # === STEP 4: Frontend reviews and responds ===
    log_step(4, "Frontend Agent reviews contract")

    # Get the full contract
    full_contract = backend_cacp.call("cacp/contract/get", {
        "projectId": project_id,
        "contractId": contract_id,
    })

    log_event("THINKING", "Frontend Agent analyzing contract...")
    action, comment = frontend_agent.decide_contract_response(full_contract)
    log_event("DECISION", f"{action.upper()}")
    log_event("COMMENT", comment)

    response = frontend_cacp.call("cacp/contract/respond", {
        "projectId": project_id,
        "contractId": contract_id,
        "action": action,
        "comment": comment,
    })
    log_event("CONTRACT STATUS", response['contractStatus'])

    # If change requested, backend updates
    if action == "request_change":
        log_step("4b", "Backend Agent updates contract based on feedback")

        log_event("THINKING", "Backend analyzing feedback and updating contract...")
        update_thoughts = backend_agent.think(
            f"Frontend requested changes: {comment}\n\nHow should I update the contract?"
        )

        # Generate updated contract
        updated_content = backend_agent.generate_contract_proposal(
            f"Updated based on frontend feedback: {comment}"
        )

        backend_cacp.call("cacp/contract/update", {
            "projectId": project_id,
            "contractId": contract_id,
            "content": updated_content,
            "changeNotes": f"Updated based on frontend feedback: {comment}",
        })

        # Frontend reviews again
        log_event("THINKING", "Frontend reviewing updated contract...")
        action2, comment2 = frontend_agent.decide_contract_response({
            **full_contract,
            "content": updated_content
        })
        frontend_cacp.call("cacp/contract/respond", {
            "projectId": project_id,
            "contractId": contract_id,
            "action": "agree",  # Assume agreement after update for demo
        })
        log_event("AGREED", "Frontend agreed to updated contract")

    # === STEP 5: Agents share context ===
    log_step(5, "Agents share implementation context")

    # Frontend asks a question
    log_event("THINKING", "Frontend generating question about implementation...")
    question = frontend_agent.generate_question("authentication and authorization for the profile endpoint")
    log_event("QUESTION", question)

    q_result = frontend_cacp.call("cacp/context/share", {
        "projectId": project_id,
        "type": "question",
        "content": {"question": question, "urgent": False},
        "relatedContracts": [contract_id],
    })

    # Backend answers with a decision
    options = [
        "JWT token in Authorization header",
        "Session cookie with CSRF protection",
        "API key in X-API-Key header",
    ]

    log_event("THINKING", "Backend considering authentication options...")
    choice, reason = backend_agent.generate_decision(question, options)
    log_event("DECISION", f"Choice: {choice}")
    log_event("RATIONALE", reason)

    backend_cacp.call("cacp/context/share", {
        "projectId": project_id,
        "type": "decision",
        "content": {
            "decision": "Authentication method for profile endpoint",
            "chosen": choice,
            "rationale": reason,
            "implications": [
                f"Backend: Implement {choice} validation middleware",
                f"Frontend: Include {choice.split()[0]} in requests",
            ],
        },
        "relatedContracts": [contract_id],
    })

    # === STEP 6: Implementation tracking ===
    log_step(6, "Agents implement the contract")

    # Backend implements
    log_event("THINKING", "Backend planning implementation...")
    backend_plan = backend_agent.think(
        "I need to implement the user profile GET endpoint. What files will I create/modify and what's my plan?"
    )

    backend_cacp.call("cacp/implementation/start", {
        "projectId": project_id,
        "contractId": contract_id,
        "plan": backend_plan,
        "estimatedFiles": ["src/api/routes/users.py", "src/models/user.py"],
    })

    backend_cacp.call("cacp/implementation/complete", {
        "projectId": project_id,
        "contractId": contract_id,
        "files": ["src/api/routes/users.py", "src/models/user.py", "tests/test_users.py"],
        "notes": "Implemented profile endpoint with auth middleware",
    })
    log_event("COMPLETE", "Backend implementation complete")

    # Frontend implements
    log_event("THINKING", "Frontend planning implementation...")
    frontend_plan = frontend_agent.think(
        "I need to implement the profile page that calls this API. What components and hooks will I create?"
    )

    frontend_cacp.call("cacp/implementation/start", {
        "projectId": project_id,
        "contractId": contract_id,
        "plan": frontend_plan,
    })

    frontend_cacp.call("cacp/implementation/complete", {
        "projectId": project_id,
        "contractId": contract_id,
        "files": ["src/pages/Profile.tsx", "src/hooks/useProfile.ts", "src/api/userApi.ts"],
        "notes": "Profile page with data fetching hook",
    })
    log_event("COMPLETE", "Frontend implementation complete")

    # === STEP 7: Verification ===
    log_step(7, "Verify integration")

    backend_cacp.call("cacp/implementation/verify", {
        "projectId": project_id,
        "contractId": contract_id,
        "result": "success",
        "notes": "End-to-end test passed - frontend successfully retrieves profile from backend",
    })

    # === Final Summary ===
    logger.info(f"\n{Colors.HEADER}{'='*70}")
    logger.info("COORDINATION COMPLETE")
    logger.info(f"{'='*70}{Colors.ENDC}\n")

    final_project = backend_cacp.call("cacp/project/get", {"projectId": project_id})
    final_contract = backend_cacp.call("cacp/contract/get", {
        "projectId": project_id,
        "contractId": contract_id,
    })
    context = backend_cacp.call("cacp/context/list", {"projectId": project_id})

    logger.info(f"{Colors.GREEN}SUMMARY:{Colors.ENDC}")
    logger.info(f"  Project: {final_project['name']}")
    logger.info(f"  Contract '{final_contract['name']}' status: {Colors.GREEN}{final_contract['status']}{Colors.ENDC}")
    logger.info(f"  Context packets exchanged: {len(context['packets'])}")
    logger.info(f"  Implementations: {len(final_contract['implementations'])}")

    logger.info(f"\n{Colors.GREEN}{'='*70}")
    logger.info("Two Groq-powered agents successfully coordinated!")
    logger.info(f"{'='*70}{Colors.ENDC}")


if __name__ == "__main__":
    asyncio.run(run_demo())
