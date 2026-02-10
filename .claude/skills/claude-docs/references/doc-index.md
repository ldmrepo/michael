# Claude Code Documentation Index

All documents are in `claude-docs/` relative to project root.
Total: 39 files, ~16,200 lines.

## Core Concepts

| File | Lines | Description |
|------|-------|-------------|
| `overview.md` | 215 | Claude Code architecture and core concepts |
| `how-claude-code-works.md` | 240 | Internal workings: agentic loop, tool use, context |
| `features-overview.md` | 278 | Feature catalog with brief descriptions |
| `quickstart.md` | 335 | Getting started guide |

## Skills & Agents

| File | Lines | Description |
|------|-------|-------------|
| `skills.md` | 678 | **Skill system**: frontmatter fields, dynamic context (`!`cmd``), fork mode, arguments, `$ARGUMENTS`, allowed-tools |
| `sub-agents.md` | 811 | **Sub-agents**: Task tool, custom agent definitions (.claude/agents/), agent types |
| `agent-teams.md` | 387 | **Agent teams**: TeamCreate, task coordination, multi-agent workflows |
| `best-practices.md` | 599 | Coding patterns, CLAUDE.md tips, skill design guidelines |

## Hooks & Automation

| File | Lines | Description |
|------|-------|-------------|
| `hooks-guide.md` | 633 | **Hooks guide**: event types, matchers, command patterns, examples |
| `hooks.md` | 1553 | **Hooks reference**: complete API, all events, configuration schema |
| `common-workflows.md` | 861 | Workflow patterns: PR review, debugging, refactoring |

## Configuration & Settings

| File | Lines | Description |
|------|-------|-------------|
| `settings.md` | 936 | **Settings**: .claude/settings.json, all config options |
| `permissions.md` | 258 | Permission model: allow/deny rules, tool permissions |
| `andboxing.md` | 261 | Sandboxing: macOS sandbox, Docker, filesystem restrictions |
| `memory.md` | 299 | **Memory**: CLAUDE.md, project instructions, auto-memory |
| `model-config.md` | 159 | Model selection and configuration |
| `keybindings.md` | 381 | Keyboard shortcuts customization |
| `output-styles.md` | 112 | Output formatting options |
| `statusline.md` | 850 | Status line configuration and customization |

## MCP & Plugins

| File | Lines | Description |
|------|-------|-------------|
| `mcp.md` | 1198 | **MCP**: Model Context Protocol server setup, configuration |
| `plugins.md` | 410 | **Plugins**: installation, configuration, lifecycle |
| `plugins-reference.md` | 743 | Plugin API reference |
| `plugin-marketplaces.md` | 629 | Plugin discovery and marketplace |
| `discover-plugins.md` | 393 | Finding and evaluating plugins |

## CLI & Deployment

| File | Lines | Description |
|------|-------|-------------|
| `cli-reference.md` | 161 | CLI flags and options |
| `headless.md` | 171 | Headless/non-interactive mode for CI/CD |
| `nteractive-mode.md` | 326 | Interactive mode features |
| `fast-mode.md` | 131 | Fast mode (same model, faster output) |
| `terminal-config.md` | 84 | Terminal setup and compatibility |
| `devcontainer.md` | 81 | Dev container configuration |
| `network-config.md` | 94 | Network and proxy settings |
| `llm-gateway.md` | 174 | LLM gateway/proxy configuration |

## Monitoring & Costs

| File | Lines | Description |
|------|-------|-------------|
| `monitoring-usage.md` | 509 | Usage monitoring and tracking |
| `costs.md` | 202 | Pricing and cost management |
| `analytics.md` | 224 | Analytics and telemetry |
| `data-usage.md` | 96 | Data handling and privacy |

## Troubleshooting

| File | Lines | Description |
|------|-------|-------------|
| `troubleshooting.md` | 424 | Common issues and solutions |
| `checkpointing.md` | 89 | Checkpoint/restore functionality |
| `third-party-integrations.md` | 258 | IDE and third-party tool integration |

## Topic → File Quick Reference

```
skills        → skills.md
hooks         → hooks-guide.md, hooks.md
subagents     → sub-agents.md
teams         → agent-teams.md
mcp           → mcp.md
plugins       → plugins.md, plugins-reference.md
permissions   → permissions.md, andboxing.md
memory        → memory.md
settings      → settings.md
cli           → cli-reference.md, headless.md
best-practices → best-practices.md
create        → skills.md + best-practices.md
workflows     → common-workflows.md
overview      → overview.md, features-overview.md
monitoring    → monitoring-usage.md, costs.md, analytics.md
```
