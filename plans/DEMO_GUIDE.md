# DevAgent Demo Guide

This guide provides comprehensive instructions for testing and demonstrating DevAgent end-to-end, including setup commands, testing procedures, and demo scenarios that showcase the product's capabilities.

## Table of Contents

1. [Quick Setup](#quick-setup)
2. [Testing Commands](#testing-commands)
3. [End-to-End Demo Scenarios](#end-to-end-demo-scenarios)
4. [Demo Presentation Tips](#demo-presentation-tips)
5. [Troubleshooting](#troubleshooting)

---

## Quick Setup

### Prerequisites

- Python 3.12 or 3.13
- Git
- (Optional) Ollama for offline LLM support
- (Optional) GitHub Personal Access Token for GitHub features

### Installation

```bash
# Option 1: Install with pipx (recommended for isolation)
pipx install devagent

# Option 2: Install in virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install devagent
```

### Development Installation

For development/testing from the current directory:

```bash
# Install in development mode with test dependencies
pip install -e ".[dev]"

# Install Ollama (for offline demos)
# Download from https://ollama.com
ollama pull qwen2.5-coder:7b
```

### Initial Configuration

```bash
# Run the setup wizard
devagent init

# This will prompt for:
# - LLM provider (Ollama recommended for demos)
# - Model name
# - GitHub token (optional but recommended for full feature demo)
# - Search provider (SearchX is free)
```

---

## Testing Commands

### Unit Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_config.py

# Run with coverage
pytest --cov=devagent

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_github_tools.py::test_parse_issue_url
```

### Linting and Code Quality

```bash
# Run ruff linter
ruff check devagent/

# Format code with ruff
ruff format devagent/

# Check both linting and formatting
ruff check devagent/ && ruff format --check devagent/
```

### Integration Testing

```bash
# Test configuration loading
devagent config --show

# Test Ollama connectivity
devagent doctor

# Test indexing on a sample project
cd tests/fixtures/sample_project
devagent index
devagent index --status
```

### Component-Specific Tests

```bash
# Test GitHub tools (requires mock or real token)
pytest tests/test_github_tools.py -v

# Test URL parsing
pytest tests/test_url_parser.py -v

# Test configuration management
pytest tests/test_config.py -v

# Test chat context and session management
pytest tests/test_chat_context.py -v

# Test security gate functionality
pytest tests/test_security_gate.py -v
```

---

## End-to-End Demo Scenarios

### Scenario 1: Basic Code Understanding (5 minutes)

**Purpose**: Demonstrate DevAgent's ability to understand and explain code.

```bash
# Navigate to a sample project
cd tests/fixtures/sample_project

# Index the codebase
devagent index

# Start interactive session
devagent

# In the session, ask:
> explain what app.py does
> what are the main classes in this project?
> how does the main function work?
```

**Demo Points**:
- Shows indexing process
- Demonstrates natural language understanding
- Highlights CodePrism knowledge graph integration

### Scenario 2: GitHub Issue Implementation (10 minutes)

**Purpose**: Demonstrate end-to-end GitHub integration.

**Prerequisites**: GitHub token configured, test repository available

```bash
# Navigate to your project
cd /path/to/your/project

# Index the codebase
devagent index

# Implement a GitHub issue
devagent implement https://github.com/owner/repo/issues/42

# The agent will:
# 1. Fetch the issue details
# 2. Analyze affected code using CodePrism
# 3. Make necessary code changes
# 4. Run tests
# 5. Report changes made
```

**Demo Points**:
- Shows GitHub API integration
- Demonstrates automated code analysis
- Highlights multi-step task execution
- Shows session persistence

### Scenario 3: Code Review Automation (8 minutes)

**Purpose**: Demonstrate PR review capabilities.

```bash
# Review a pull request
devagent review https://github.com/owner/repo/pull/17

# The agent will:
# 1. Fetch PR diff and files
# 2. Analyze changes using code graph
# 3. Generate review comments
# 4. Post comments to GitHub (if configured)
```

**Demo Points**:
- Shows automated code review
- Demonstrates understanding of code changes
- Highlights integration with GitHub PR workflow

### Scenario 4: CI Failure Analysis (7 minutes)

**Purpose**: Demonstrate CI debugging capabilities.

```bash
# Analyze a failed CI run
devagent fix-ci https://github.com/owner/repo/actions/runs/987654321

# The agent will:
# 1. Fetch failed workflow logs
# 2. Parse error messages
# 3. Locate problematic code
# 4. Propose fixes
# 5. Apply fixes if confirmed
```

**Demo Points**:
- Shows CI/CD integration
- Demonstrates log analysis
- Highlights automated debugging

### Scenario 5: Issue Triage (6 minutes)

**Purpose**: Demonstrate backlog management capabilities.

```bash
# Triage open issues
devagent triage owner/repo

# The agent will:
# 1. Fetch open issues
# 2. Analyze complexity using CodePrism
# 3. Estimate effort required
# 4. Suggest labels
# 5. Post triage comments
```

**Demo Points**:
- Shows batch processing capabilities
- Demonstrates complexity analysis
- Highlights project management integration

### Scenario 6: Offline-First Demo (5 minutes)

**Purpose**: Demonstrate privacy and offline capabilities.

```bash
# Ensure Ollama is running
ollama serve

# Configure to use Ollama
devagent config --set llm.provider=ollama
devagent config --set llm.model=qwen2.5-coder:7b

# Verify offline capability
devagent doctor

# Run a task completely offline
devagent
> analyze the current codebase and suggest improvements
```

**Demo Points**:
- Shows offline-first architecture
- Demonstrates privacy benefits
- Highlights local LLM integration

### Scenario 7: Session Management (4 minutes)

**Purpose**: Demonstrate session persistence and resumption.

```bash
# Start a session
devagent
> implement feature X
# (Ctrl+C to exit)

# List sessions
devagent session list

# Resume previous session
devagent session resume <session-id>

# Continue the conversation
> add error handling to the feature
```

**Demo Points**:
- Shows session persistence
- Demonstrates context retention
- Highlights long-running task support

### Scenario 8: Background Watcher (6 minutes)

**Purpose**: Demonstrate continuous monitoring capabilities.

```bash
# Start background watcher
devagent watcher start owner/repo

# Check watcher status
devagent watcher status

# Let it run for a while, then check again
devagent watcher status

# Stop watcher when done
devagent watcher stop
```

**Demo Points**:
- Shows background processing
- Demonstrates continuous integration
- Highlights automated monitoring

---

## Demo Presentation Tips

### Preparation Checklist

1. **Environment Setup**
   - [ ] DevAgent installed and configured
   - [ ] Ollama running with model pulled
   - [ ] GitHub token configured (if using GitHub features)
   - [ ] Test repository with sample issues/PRs available
   - [ ] Sample project code ready for indexing

2. **Demo Scenarios Ready**
   - [ ] Basic code understanding scenario tested
   - [ ] GitHub issue URL ready for implementation demo
   - [ ] PR URL ready for review demo
   - [ ] Failed CI run URL ready for debugging demo
   - [ ] Repository ready for triage demo

3. **System Health Check**
   - [ ] Run `devagent doctor` to verify all systems
   - [ ] Test Ollama connectivity
   - [ ] Verify GitHub token authentication
   - [ ] Check indexing works on sample project

### Presentation Flow (20-30 minutes)

**Introduction (2 minutes)**
- Brief overview of DevAgent's purpose
- Key differentiators: offline-first, GitHub-native, token-efficient

**Live Demo Scenarios (15-25 minutes)**
- Choose 2-3 scenarios based on audience:
  - For developers: Scenarios 1, 2, 7
  - For DevOps: Scenarios 3, 4, 8
  - For managers: Scenarios 2, 5, 6
  - Full demo: All scenarios

**Q&A (3-5 minutes)**
- Address questions about specific features
- Discuss integration possibilities
- Cover deployment options

### Key Talking Points

1. **Privacy & Security**
   - "DevAgent runs offline by default using Ollama"
   - "Your code never leaves your network unless you configure cloud providers"
   - "GitHub tokens are stored securely in user config directory"

2. **Efficiency**
   - "CodePrism integration reduces token usage by 60-80%"
   - "Incremental indexing means fast updates"
   - "Session persistence avoids re-explaining context"

3. **Integration**
   - "Works alongside your existing AI tools (Claude, Copilot, etc.)"
   - "GitHub-native workflows for issues, PRs, and CI"
   - "MCP server integration for IDE support"

4. **Flexibility**
   - "Multiple LLM providers supported"
   - "Multi-model routing for cost optimization"
   - "Custom tools through plugin registry"

### Common Demo Questions & Answers

**Q: How does this compare to GitHub Copilot?**
A: Copilot provides inline code completion while you type. DevAgent handles multi-step tasks like implementing entire features, running tests, and managing GitHub workflows. They complement each other.

**Q: Is my code sent to external servers?**
A: By default, no. DevAgent uses Ollama which runs entirely on your machine. Cloud providers (Anthropic, OpenAI, etc.) are opt-in only.

**Q: How do you handle large codebases?**
A: We use CodePrism, a knowledge graph built from your code's AST and import structure. This lets us query for only the relevant functions and classes, reducing context by 60-80%.

**Q: Can I use this with my existing CI/CD pipeline?**
A: Yes, DevAgent can analyze failed CI runs and propose fixes. It integrates with GitHub Actions and other CI systems through GitHub API.

---

## Troubleshooting

### Common Issues

**Issue: "Ollama is not reachable"**
```bash
# Start Ollama
ollama serve

# Verify it's running
curl http://localhost:11434/api/tags

# Check DevAgent configuration
devagent config --show
```

**Issue: "GitHub token appears invalid"**
```bash
# Re-run setup to update token
devagent init

# Or update directly
devagent config --set github.token=your_new_token
```

**Issue: "Project not indexed"**
```bash
# Index the project
devagent index

# Check index status
devagent index --status

# Force re-index if needed
devagent index --full
```

**Issue: Tests failing**
```bash
# Ensure dev dependencies are installed
pip install -e ".[dev]"

# Run tests with verbose output
pytest -v

# Check for specific test failures
pytest tests/test_config.py -v
```

**Issue: Import errors during development**
```bash
# Ensure package is installed in development mode
pip install -e .

# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

### Performance Tips

1. **Indexing Speed**
   - Use incremental indexing (`devagent index`) instead of full re-index
   - Exclude large directories (node_modules, .venv) via .gitignore

2. **LLM Performance**
   - Use smaller models for quick tasks (qwen2.5-coder:7b)
   - Reserve larger models for complex reasoning
   - Consider multi-model routing for cost optimization

3. **Session Management**
   - Clean up old sessions regularly: `devagent session delete <id>`
   - Use session resume for long-running tasks
   - Monitor token usage with `devagent session list`

### Getting Help

- Check documentation: `devagent --help`
- Run diagnostics: `devagent doctor`
- View configuration: `devagent config --show`
- Check logs in your user config directory
- Report issues at: https://github.com/yourusername/DevAgent/issues

---

## Quick Reference Card

### Essential Commands

```bash
# Setup
devagent init              # Initial configuration
devagent config --show     # View configuration
devagent doctor            # System health check

# Codebase
devagent index             # Build/update knowledge graph
devagent index --status    # Check index statistics

# Core functionality
devagent                   # Start interactive session
devagent implement <url>   # Implement GitHub issue
devagent review <url>      # Review pull request
devagent triage <repo>     # Triage open issues
devagent fix-ci <url>      # Fix failed CI run

# Sessions
devagent session list      # List all sessions
devagent session resume <id>  # Resume session
devagent session delete <id>  # Delete session

# Advanced
devagent watcher start <repo>  # Start background monitoring
devagent watcher status        # Check watcher status
devagent watcher stop          # Stop watcher
devagent serve                 # Start REST API server
```

### Testing Commands

```bash
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest --cov             # With coverage
ruff check devagent/     # Lint code
ruff format devagent/    # Format code
```

---

## Demo Environment Reset

To reset your demo environment between sessions:

```bash
# Clear DevAgent sessions
devagent session list
devagent session delete <id>  # Repeat for each session

# Reset configuration (optional)
devagent init  # Re-run setup wizard

# Clear test artifacts
rm -rf .pytest_cache
rm -rf .ruff_cache
rm -rf .coverage

# Re-install in development mode
pip install -e ".[dev]"
```

---

## Additional Resources

- Main README: Full documentation and feature list
- CONTRIBUTING.md: Development guidelines
- PROJECT.md: Detailed project architecture (gitignored)
- FEATURE_F3.md: Watcher feature documentation
- DEVAGENT_ROADMAP.md: Future plans and roadmap

---

**Last Updated**: 2026-08-23
**DevAgent Version**: 0.4.0-dev