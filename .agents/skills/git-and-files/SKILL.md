---
name: git-and-files
description: Use when you need to locate git repositories, check git status, stage/commit/push changes, or find project files and directories across the filesystem. Trigger when you feel the urge to run git status, find, ls, or locate commands to orient yourself before acting.
---

# Git & Files Orientation

This skill teaches the agent how to find repositories and files without burning turns on exploratory shell commands. Use it whenever you are about to run `git status`, `find`, `ls`, or `locate` to orient yourself — this skill replaces those with structured lookups.

## Core Principle

**Before running any exploratory command, check the three cached sources first.** They were populated during session setup and answer 90% of orientation questions:

1. **`AGENTS.md`** — the project's architecture overview. Always read this first. It lists core modules, reports, conventions, and key findings.
2. **`CLAUDE.md`** — project instructions, build/test commands, architecture overview, conventions.
3. **Memory index** (`MEMORY.md`) — persistent facts about the user, project, and reference material. Located at `.claude/projects/-home-yapilwsl-arthityap-trend/memory/MEMORY.md`.

## Finding Git Repositories

The agent's home directory is `/home/yapilwsl`. The trend project git root is `/home/yapilwsl/arthityap/trend/.git`.

If you need to find other git roots, use these shortcuts instead of `find`:

```bash
# All git repos under a directory (fast, no recursion into submodules):
find /home/yapilwsl -maxdepth 4 -name ".git" -type d 2>/dev/null | grep -v nvm

# The trend repo is always at /home/yapilwsl/arthityap/trend
# Its git root: /home/yapilwsl/arthityap/trend
# Its remote: https://github.com/yapily77/trend.git
```

**Never run `find / -name ".git"`** — it scans the entire filesystem and wastes turns. The known repos under `/home/yapilwsl/arthityap/` are already enumerated in `AGENTS.md` and the memory files.

## Git Workflow (trend repo)

All commands assume the working directory is `/home/yapilwsl/arthityap/trend` unless stated otherwise.

### Status
```bash
git status          # Working tree status
git status --short  # Concise status
git log --oneline -3  # Recent commits
```

### Stage & Commit
```bash
git add <files>
git commit -m "description"
git push
```

### Push
```bash
git push
# If upstream is set: git push origin master
```

### Memory Files (NOT in trend git repo)

Memory files live at `/home/yapilwsl/.claude/projects/-home-yapilwsl-arthityap-trend/memory/` and are **not tracked by the trend git repo**. They are the agent's persistent knowledge base.

To update memory:
1. Read `MEMORY.md` to see the index.
2. Write or update the relevant `.md` file in that directory.
3. Update `MEMORY.md` index if adding a new entry.
4. Do NOT `git add` memory files — they live outside the trend repo.

## File Search Shortcuts (no `find` needed)

Instead of running `find` or `ls`, use these known paths:

| What you need | Path |
|---|---|
| Project root | `/home/yapilwsl/arthityap/trend` |
| Core scripts | `/home/yapilwsl/arthityap/trend/scripts/bt/` |
| Reports | `/home/yapilwsl/arthityap/trend/reports/` |
| JPY research | `/home/yapilwsl/arthityap/trend/JPY/` |
| US research | `/home/yapilwsl/arthityap/trend/US/` |
| Memory index | `/home/yapilwsl/.claude/projects/-home-yapilwsl-arthityap-trend/memory/MEMORY.md` |
| Memory files | `/home/yapilwsl/.claude/projects/-home-yapilwsl-arthityap-trend/memory/` |
| Skills | `/home/yapilwsl/arthityap/trend/.agents/skills/` |
| AGENTS.md | `/home/yapilwsl/arthityap/trend/AGENTS.md` |
| CLAUDE.md | `/home/yapilwsl/arthityap/trend/CLAUDE.md` |
| User memory | `/home/yapilwsl/.claude/projects/-home-yapilwsl-arthityap-trend/memory/user-profile.md` |
| KAMA research | `/home/yapilwsl/.claude/projects/-home-yapilwsl-arthityap-trend/memory/kama-research-results.md` |

## Decision Flow (before acting)

```
1. Read AGENTS.md → know the project structure
2. Read CLAUDE.md → know the instructions
3. Read MEMORY.md → know the user and project context
4. If you still need to find a file, check the table above
5. If you still need to find a git repo, use the find shortcut above
6. Only then run git commands from the known root
```

This eliminates the orientation loop. Most questions are answered by step 1–3 alone.
