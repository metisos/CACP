# CACP v2.0 - Claude Code Instructions

## Rosetta Protocol

This project uses Rosetta for persistent AI context.

**On session start:**
1. Read ROSETTA.md immediately for project context
2. Check `<!-- rosetta:last-updated:DATE -->` for staleness (>30 days = review needed)
3. Load relevant .rosetta/modules/ files based on your task
4. Review .rosetta/notes.md for recent discoveries

**During work:**
- Follow conventions documented in ROSETTA.md
- Check Gotchas before modifying unfamiliar areas
- Reference Key Patterns for consistent code style

**Before session end:**
- Append valuable discoveries to .rosetta/notes.md
- Format: ### YYYY-MM-DD | claude
- Keep notes actionable and non-obvious

**If ROSETTA.md doesn't exist:**
- Create it by analyzing the codebase
- See: https://github.com/metisos/Rosetta_Open_Source

## Project-Specific Notes

### Running the Project

```bash
# Install dependencies
pip install -r requirements.txt

# Run with config file (recommended)
python -m src.main --config config/agent-config.yaml

# Run with CLI args
python -m src.main --repo backend-api --role backend --port 8080

# Run tests
python -m pytest tests/ -v
```

### Key Files to Know

- `src/main.py` - Entry point
- `src/transport/server.py` - FastAPI app setup
- `src/handlers/` - All JSON-RPC method implementations
- `docs/PROTOCOL.md` - Full protocol specification
- `docs/AGENT_GUIDE.md` - Usage guide for AI agents

### Code Style

- Async/await for all I/O operations
- Pydantic models for data validation
- JSON-RPC 2.0 method naming: `cacp/{domain}/{action}`
- Type hints required on all functions
