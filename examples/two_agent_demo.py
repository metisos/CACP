#!/usr/bin/env python3
"""
Two-Agent Communication Demo

This script demonstrates two CACP agents coordinating on an OAuth feature:
1. Backend agent creates a project
2. Frontend agent joins
3. Backend proposes an API contract
4. Frontend responds with agreement
5. Both agents share context
6. Track implementation progress

Run this after starting two agent servers:
    Terminal 1: python -m src.main --port 8080 --repo backend-api --role backend --language python
    Terminal 2: python -m src.main --port 8081 --repo frontend-app --role frontend --language typescript
    Terminal 3: python examples/two_agent_demo.py
"""

import asyncio
import sys
sys.path.insert(0, ".")

from src.transport.client import CACPClient


async def main():
    # Create clients for both agents
    backend_client = CACPClient("http://localhost:8080", agent_id="agent-backend-api")
    frontend_client = CACPClient("http://localhost:8081", agent_id="agent-frontend-app")

    print("=" * 60)
    print("CACP v2 Two-Agent Communication Demo")
    print("=" * 60)

    # Step 1: Check health of both agents
    print("\n[1] Checking agent health...")
    try:
        backend_health = await backend_client.health_check()
        print(f"    Backend agent: {backend_health}")
    except Exception as e:
        print(f"    ERROR: Backend agent not available: {e}")
        print("    Make sure to start: python -m src.main --port 8080 --repo backend-api --role backend")
        return

    try:
        frontend_health = await frontend_client.health_check()
        print(f"    Frontend agent: {frontend_health}")
    except Exception as e:
        print(f"    ERROR: Frontend agent not available: {e}")
        print("    Make sure to start: python -m src.main --port 8081 --repo frontend-app --role frontend")
        return

    # Step 2: Backend agent creates a project
    print("\n[2] Backend agent creating project...")
    project_result = await backend_client.create_project(
        name="User Authentication Feature",
        objective="Implement OAuth 2.0 login with Google and GitHub providers",
        repos=[
            {
                "name": "backend-api",
                "role": "backend",
                "language": "python",
                "relevantPaths": ["src/auth/", "src/api/users/"],
            },
            {
                "name": "frontend-app",
                "role": "frontend",
                "language": "typescript",
                "relevantPaths": ["src/components/auth/", "src/hooks/"],
            },
        ],
    )
    project_id = project_result["projectId"]
    print(f"    Project created: {project_id}")

    # Step 3: Frontend agent joins the project
    print("\n[3] Frontend agent joining project...")
    join_result = await frontend_client.join_project(
        project_id=project_id,
        repo_name="frontend-app",
        agent_endpoint="http://localhost:8081",
    )
    print(f"    Joined: {join_result}")

    # Step 4: Backend proposes an API contract
    print("\n[4] Backend agent proposing OAuth callback endpoint contract...")
    contract_result = await backend_client.propose_contract(
        project_id=project_id,
        contract_type="api_endpoint",
        name="OAuth Callback Endpoint",
        content={
            "method": "POST",
            "path": "/api/auth/oauth/callback",
            "requestBody": {
                "type": "object",
                "properties": {
                    "provider": {"type": "string", "enum": ["google", "github"]},
                    "code": {"type": "string"},
                    "state": {"type": "string"},
                },
                "required": ["provider", "code", "state"],
            },
            "responseBody": {
                "type": "object",
                "properties": {
                    "accessToken": {"type": "string"},
                    "refreshToken": {"type": "string"},
                    "user": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "email": {"type": "string"},
                            "name": {"type": "string"},
                            "avatarUrl": {"type": "string"},
                        },
                    },
                },
            },
            "authentication": "none",
            "errors": [
                {"code": 400, "name": "InvalidCode", "description": "OAuth code is invalid or expired"},
                {"code": 400, "name": "InvalidState", "description": "State mismatch, possible CSRF"},
                {"code": 500, "name": "ProviderError", "description": "OAuth provider returned an error"},
            ],
        },
    )
    contract_id = contract_result["contractId"]
    print(f"    Contract proposed: {contract_id} (v{contract_result['version']})")

    # Step 5: Frontend reviews and agrees to contract
    print("\n[5] Frontend agent responding to contract...")
    response_result = await frontend_client.respond_to_contract(
        project_id=project_id,
        contract_id=contract_id,
        action="agree",
        comment="Looks good! The response schema matches what we need for the auth context.",
    )
    print(f"    Response: {response_result}")

    # Step 6: Backend shares context - a code snippet
    print("\n[6] Backend agent sharing code context...")
    code_result = await backend_client.call("cacp/context/shareCode", {
        "projectId": project_id,
        "language": "python",
        "file": "src/auth/oauth.py",
        "snippet": '''async def oauth_callback(provider: str, code: str, state: str):
    """Handle OAuth callback from provider."""
    # Validate state to prevent CSRF
    if not validate_oauth_state(state):
        raise InvalidStateError()

    # Exchange code for tokens
    tokens = await oauth_providers[provider].exchange_code(code)

    # Get user info from provider
    user_info = await oauth_providers[provider].get_user_info(tokens.access_token)

    # Create or update user in our system
    user = await upsert_user(provider, user_info)

    # Generate our own tokens
    return create_auth_response(user, tokens)''',
        "explanation": "This is the core OAuth callback handler. Frontend will POST to this endpoint after receiving the OAuth redirect.",
        "relatedContracts": [contract_id],
    })
    print(f"    Code shared: {code_result['packetId']}")

    # Step 7: Frontend asks a question
    print("\n[7] Frontend agent asking a question...")
    question_result = await frontend_client.ask_question(
        project_id=project_id,
        question="Should we store the refresh token in localStorage or use httpOnly cookies?",
        options=[
            "localStorage (simpler, but XSS vulnerable)",
            "httpOnly cookies (more secure, requires CORS setup)",
            "Memory only (most secure, but lost on refresh)",
        ],
    )
    print(f"    Question asked: {question_result['packetId']}")

    # Step 8: Backend records a decision
    print("\n[8] Backend agent recording a decision...")
    decision_result = await backend_client.record_decision(
        project_id=project_id,
        decision="Token Storage Strategy",
        chosen="httpOnly cookies",
        rationale="Security is critical for auth tokens. httpOnly cookies prevent XSS attacks and the backend can handle CORS.",
        implications=[
            "Backend: Must set cookies with Secure, HttpOnly, SameSite=Strict flags",
            "Backend: Need to configure CORS to allow credentials",
            "Frontend: Use fetch with credentials: 'include'",
            "Frontend: No need to manually handle token storage",
        ],
    )
    print(f"    Decision recorded: {decision_result['packetId']}")

    # Step 9: Get current context history
    print("\n[9] Fetching context history...")
    context_result = await backend_client.list_context(project_id=project_id)
    print(f"    Total context packets: {len(context_result['packets'])}")
    for packet in context_result["packets"]:
        print(f"      - [{packet['type']}] from {packet['from_agent']} at {packet['timestamp']}")

    # Step 10: Start implementation (backend)
    print("\n[10] Backend agent starting implementation...")
    impl_start = await backend_client.start_implementation(
        project_id=project_id,
        contract_id=contract_id,
        plan="1. Add OAuth provider configs\n2. Implement callback endpoint\n3. Add token generation\n4. Write tests",
        estimated_files=["src/auth/oauth.py", "src/api/auth_routes.py", "tests/test_oauth.py"],
    )
    print(f"    Implementation started: {impl_start}")

    # Step 11: Complete implementation (backend)
    print("\n[11] Backend agent completing implementation...")
    impl_complete = await backend_client.complete_implementation(
        project_id=project_id,
        contract_id=contract_id,
        files=["src/auth/oauth.py", "src/api/auth_routes.py", "tests/test_oauth.py"],
        notes="OAuth callback endpoint implemented with Google and GitHub support. Tests passing.",
        test_endpoint="http://localhost:8000/api/auth/oauth/callback",
    )
    print(f"    Implementation complete: {impl_complete}")

    # Step 12: Frontend starts and completes implementation
    print("\n[12] Frontend agent implementing...")
    await frontend_client.start_implementation(
        project_id=project_id,
        contract_id=contract_id,
        plan="1. Add OAuth buttons\n2. Handle redirect callback\n3. Update auth context",
        estimated_files=["src/components/auth/OAuthButtons.tsx", "src/pages/oauth/callback.tsx"],
    )
    await frontend_client.complete_implementation(
        project_id=project_id,
        contract_id=contract_id,
        files=["src/components/auth/OAuthButtons.tsx", "src/pages/oauth/callback.tsx", "src/hooks/useAuth.ts"],
        notes="OAuth flow implemented. Buttons render correctly, callback page handles the redirect.",
    )
    print(f"    Frontend implementation complete")

    # Step 13: Verify integration
    print("\n[13] Verifying integration...")
    verify_result = await backend_client.verify_implementation(
        project_id=project_id,
        contract_id=contract_id,
        result="success",
        notes="End-to-end OAuth flow tested successfully with both Google and GitHub.",
    )
    print(f"    Verification: {verify_result}")

    # Step 14: Final project state
    print("\n[14] Final project state...")
    project = await backend_client.get_project(project_id)
    print(f"    Project: {project['name']}")
    print(f"    Status: {project['status']}")
    print(f"    Repos: {len(project['repos'])}")
    print(f"    Contracts: {len(project['contracts'])}")
    print(f"    Context packets: {len(project['context_history'])}")

    # Show contract final state
    contract = await backend_client.get_contract(project_id, contract_id, include_history=True)
    print(f"\n    Contract '{contract['name']}':")
    print(f"      Status: {contract['status']}")
    print(f"      Version: {contract['version']}")
    print(f"      Implementations: {len(contract['implementations'])}")
    for impl in contract["implementations"]:
        print(f"        - {impl['repo_id']}: {impl['status']}")

    print("\n" + "=" * 60)
    print("Demo complete! Two agents successfully coordinated.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
