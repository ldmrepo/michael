#!/usr/bin/env bash
# load-docs.sh - Topic-based Claude Code documentation loader
# Usage: load-docs.sh [topic1] [topic2] ...
# Topics: skills, hooks, subagents, teams, mcp, plugins, permissions, memory,
#         settings, cli, best-practices, create, all-topics

set -euo pipefail

DOCS_DIR="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}/claude-docs"
MAX_LINES=800
total_lines=0

if [ ! -d "$DOCS_DIR" ]; then
  echo "ERROR: claude-docs/ directory not found at $DOCS_DIR"
  exit 1
fi

# Print doc with line budget
print_doc() {
  local file="$1"
  local basename
  basename=$(basename "$file")

  if [ ! -f "$file" ]; then
    echo "  [NOT FOUND: $basename]"
    return
  fi

  local lines
  lines=$(wc -l < "$file" | tr -d ' ')
  local remaining=$((MAX_LINES - total_lines))

  if [ "$remaining" -le 0 ]; then
    echo "  [TRUNCATED: $basename ($lines lines) - Read claude-docs/$basename for full content]"
    return
  fi

  echo "=== $basename ($lines lines) ==="
  if [ "$lines" -le "$remaining" ]; then
    cat "$file"
    total_lines=$((total_lines + lines))
  else
    head -n "$remaining" "$file"
    total_lines=$((total_lines + remaining))
    echo ""
    echo "... [TRUNCATED at $remaining/$lines lines - Read claude-docs/$basename for full content]"
  fi
  echo ""
}

# Show available topics
show_topics() {
  cat <<'TOPICS'
# Claude Code Documentation Topics

Usage: /claude-docs [topic]

| Topic | Documents | Description |
|-------|-----------|-------------|
| `skills` | skills.md | Skill system: frontmatter, dynamic context, fork, arguments |
| `hooks` | hooks-guide.md, hooks.md | Hook system: events, matchers, commands |
| `subagents` | sub-agents.md | Sub-agents: Task tool, custom agents |
| `teams` | agent-teams.md | Agent teams: TeamCreate, coordination |
| `mcp` | mcp.md | MCP server integration |
| `plugins` | plugins.md, plugins-reference.md | Plugin system |
| `permissions` | permissions.md, andboxing.md | Permissions and sandboxing |
| `memory` | memory.md | Memory system: CLAUDE.md, project memory |
| `settings` | settings.md | Configuration: .claude/settings.json |
| `cli` | cli-reference.md, headless.md | CLI flags and headless mode |
| `best-practices` | best-practices.md | Coding patterns and tips |
| `create` | skills.md, best-practices.md | Skill creation combo |
| `workflows` | common-workflows.md | Common workflow patterns |
| `overview` | overview.md, features-overview.md | Architecture and features |
| `monitoring` | monitoring-usage.md, costs.md, analytics.md | Usage and cost tracking |

Tip: Combine topics - `/claude-docs skills hooks` loads both.
For full doc index: Read .claude/skills/claude-docs/references/doc-index.md
TOPICS
}

# Map topic to files
get_files_for_topic() {
  local topic="$1"
  case "$topic" in
    skill|skills)
      echo "$DOCS_DIR/skills.md"
      ;;
    hook|hooks)
      echo "$DOCS_DIR/hooks-guide.md"
      echo "$DOCS_DIR/hooks.md"
      ;;
    subagent|subagents|sub-agent|sub-agents)
      echo "$DOCS_DIR/sub-agents.md"
      ;;
    team|teams|agent-team|agent-teams)
      echo "$DOCS_DIR/agent-teams.md"
      ;;
    mcp)
      echo "$DOCS_DIR/mcp.md"
      ;;
    plugin|plugins)
      echo "$DOCS_DIR/plugins.md"
      echo "$DOCS_DIR/plugins-reference.md"
      ;;
    permission|permissions)
      echo "$DOCS_DIR/permissions.md"
      echo "$DOCS_DIR/andboxing.md"
      ;;
    memory)
      echo "$DOCS_DIR/memory.md"
      ;;
    setting|settings)
      echo "$DOCS_DIR/settings.md"
      ;;
    cli)
      echo "$DOCS_DIR/cli-reference.md"
      echo "$DOCS_DIR/headless.md"
      ;;
    best-practice|best-practices)
      echo "$DOCS_DIR/best-practices.md"
      ;;
    create)
      echo "$DOCS_DIR/skills.md"
      echo "$DOCS_DIR/best-practices.md"
      ;;
    workflow|workflows)
      echo "$DOCS_DIR/common-workflows.md"
      ;;
    overview)
      echo "$DOCS_DIR/overview.md"
      echo "$DOCS_DIR/features-overview.md"
      ;;
    monitor|monitoring)
      echo "$DOCS_DIR/monitoring-usage.md"
      echo "$DOCS_DIR/costs.md"
      echo "$DOCS_DIR/analytics.md"
      ;;
    interactive)
      echo "$DOCS_DIR/nteractive-mode.md"
      ;;
    headless)
      echo "$DOCS_DIR/headless.md"
      ;;
    troubleshoot|troubleshooting)
      echo "$DOCS_DIR/troubleshooting.md"
      ;;
    statusline)
      echo "$DOCS_DIR/statusline.md"
      ;;
    model|model-config)
      echo "$DOCS_DIR/model-config.md"
      ;;
    *)
      # Try direct filename match
      if [ -f "$DOCS_DIR/${topic}.md" ]; then
        echo "$DOCS_DIR/${topic}.md"
      else
        echo "UNKNOWN:$topic" >&2
      fi
      ;;
  esac
}

# Main
if [ $# -eq 0 ] || [ "${1:-}" = "help" ] || [ "${1:-}" = "--help" ]; then
  show_topics
  exit 0
fi

# Collect all files from all topics
declare -a all_files=()
for topic in "$@"; do
  topic_lower=$(echo "$topic" | tr '[:upper:]' '[:lower:]')
  while IFS= read -r file; do
    if [ -n "$file" ]; then
      # Deduplicate
      already_added=false
      for existing in "${all_files[@]+"${all_files[@]}"}"; do
        if [ "$existing" = "$file" ]; then
          already_added=true
          break
        fi
      done
      if [ "$already_added" = false ]; then
        all_files+=("$file")
      fi
    fi
  done < <(get_files_for_topic "$topic_lower")
done

if [ ${#all_files[@]} -eq 0 ]; then
  echo "No documents found for: $*"
  echo ""
  show_topics
  exit 1
fi

echo "# Loading ${#all_files[@]} document(s) for: $*"
echo ""

for file in "${all_files[@]}"; do
  print_doc "$file"
done

if [ $total_lines -ge $MAX_LINES ]; then
  echo "---"
  echo "Line budget reached ($MAX_LINES lines). Use Read tool for remaining content."
fi
