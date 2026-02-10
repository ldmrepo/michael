---
name: claude-docs
description: |
  Claude Code 공식 문서 레퍼런스. 스킬 생성/개선, hooks, subagents, agent teams, MCP, plugins, permissions, memory, CLI 설정 참조.
  Use when: creating skills, improving SKILL.md, writing hooks, configuring subagents, building agent teams, setting up MCP, reviewing permissions.
  Keywords: "스킬 만들", "skill 만들", "SKILL.md", "hook 설정", "hook 만들", "subagent", "sub-agent", "agent team", "MCP 설정", "plugin", "permission", "allowed-tools", "frontmatter"
argument-hint: "[topic: skills|hooks|subagents|teams|mcp|plugins|permissions|memory|settings|cli|best-practices|create|workflows|overview|monitoring]"
allowed-tools: Bash(bash:*), Read, Grep, Glob
---

# Claude Code Documentation Reference

## Dynamic Documentation Loading

!`bash "$CLAUDE_PROJECT_DIR/.claude/skills/claude-docs/scripts/load-docs.sh" $ARGUMENTS`

## Document Index

39 official docs available in `claude-docs/`. Full index at `.claude/skills/claude-docs/references/doc-index.md`.

### Key Documents by Topic

| Topic | Primary Doc | Lines | Secondary |
|-------|-------------|-------|-----------|
| Skills | `skills.md` | 678 | `best-practices.md` (599) |
| Hooks | `hooks-guide.md` | 633 | `hooks.md` (1553) |
| Sub-agents | `sub-agents.md` | 811 | |
| Agent Teams | `agent-teams.md` | 387 | |
| MCP | `mcp.md` | 1198 | |
| Plugins | `plugins.md` | 410 | `plugins-reference.md` (743) |
| Permissions | `permissions.md` | 258 | `andboxing.md` (261) |
| Memory | `memory.md` | 299 | |
| Settings | `settings.md` | 936 | |
| CLI | `cli-reference.md` | 161 | `headless.md` (171) |

## SKILL.md Frontmatter Quick Reference

```yaml
---
name: skill-name                    # Required. Matches directory name.
description: |                      # Required. Multi-line. Triggers auto-invocation.
  What this skill does.
  Use when: [trigger conditions]
  Keywords: "keyword1", "keyword2"  # Auto-trigger keywords
argument-hint: "[args description]" # Shown in /skill-name help
allowed-tools: Tool1, Tool2        # Tools the skill can use
  # Bash(command:pattern)           # Restrict bash to specific commands
  # Bash(bash:*)                    # Allow all bash
  # Read, Write, Edit, Glob, Grep  # File tools
  # WebFetch, WebSearch             # Web tools
  # Task(agent-name)                # Specific subagent
context: fork                       # Optional. Forks context (no conversation history)
---
```

### Dynamic Context Syntax

```markdown
# Static content here...

## Dynamic Section
!`bash "command" $ARGUMENTS`

# More static content...
!`bash "another-command"`
```

- `$ARGUMENTS`: User's arguments after `/skill-name`
- Commands run at skill load time, output replaces the line
- Use `$CLAUDE_PROJECT_DIR` for project-relative paths

## Skill Creation Checklist

When creating or improving a skill:

1. **Choose pattern**: Simple (static text) | Script (dynamic `!`cmd``) | Reference (doc loading) | Protocol (multi-step)
2. **Write frontmatter**:
   - `name` matches directory name
   - `description` includes trigger keywords for auto-invocation
   - `allowed-tools` is minimal (principle of least privilege)
   - `argument-hint` if skill accepts arguments
3. **Write body**: Instructions, templates, examples
4. **Test**: `/skill-name` runs without errors, arguments work

## This Project's Skill Patterns

### Simple Pattern (static instructions)
`weather/`, `calendar/`, `maps/` - API calls + response format templates

### Script Pattern (dynamic data)
`finance/` - `!`bash "script.sh"`` loads live data at skill invocation

### Reference Pattern (doc loading)
`agui/`, `a2ui/`, `a2a-protocol/` - Large reference docs with examples

### Protocol Pattern (multi-step workflows)
`youtube-shorts/`, `x-to-shorts/` - Sequential steps with intermediate outputs

## Loading Additional Documents

If the loaded topic doesn't cover what you need:

```bash
# Read any doc directly
Read claude-docs/FILENAME.md

# Search across all docs
Grep "pattern" claude-docs/
```
