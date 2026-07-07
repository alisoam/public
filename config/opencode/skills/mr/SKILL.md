---
name: mr
description: Reviews uncommitted changes and commits from the current branch against the base branch, then commits with a proper message, pushes, and extracts the MR/PR URL from git push output. Use when the user asks to commit and push changes, create an MR/PR, or finalize their work.
---

# Review, Commit, Push & Show MR URL

This skill guides the full workflow from reviewing local changes to surfacing the MR URL that the git server returns on push.

## Workflow

### 1. Review Uncommitted Changes

Run these commands to understand the current state:
- `git status` — list staged, unstaged, and untracked files
- `git diff` — show unstaged changes
- `git diff --staged` — show staged changes
- `git branch --show-current` — get current branch name

### 2. Review Commits vs Base Branch

Detect the base branch (typically `main`, `master`, or `develop`):
- `git remote show origin | grep "HEAD branch"` — find default base branch
- `git log <base>..HEAD --oneline` — list commits ahead of base
- `git diff <base>...HEAD` — full diff vs base branch

### 3. Analyze & Report

Present a concise review to the user:
- Summary of files changed (added/modified/deleted)
- Key logical changes grouped by intent
- Any concerns (debug code, secrets, large files, TODOs, failing patterns)
- **Ask the user to confirm before proceeding** unless they explicitly said "go ahead"

### 4. Commit Changes

Only after the user confirms:
- Stage relevant files: `git add <files>` (avoid `git add .` unless intentional)
- Write a commit using Conventional Commits format:

```
<type>(<scope>): <short summary>

<body explaining what and why, not how>
<footer: refs/closes issue, breaking changes>
```

- Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `style`, `build`, `ci`
- Keep subject ≤ 72 chars, imperative mood
- Run: `git commit -m "subject" -m "body"`

### 5. Push Changes & Capture MR URL

Push and capture **both stdout and stderr** (git prints the MR/PR URL to stderr):

```bash
git push -u origin <current-branch> 2>&1
```

The server response will contain a line like one of these:

**GitLab (new MR):**

```
remote: To create a merge request for <branch>, visit:
remote:   https://gitlab.com/<group>/<repo>/-/merge_requests/new?merge_request%5Bsource_branch%5D=<branch>
```

**GitLab (existing MR):**

```
remote: View merge request for <branch>:
remote:   https://gitlab.com/<group>/<repo>/-/merge_requests/<id>
```

**GitHub:**

```
remote: Create a pull request for '<branch>' on GitHub by visiting:
remote:      https://github.com/<owner>/<repo>/pull/new/<branch>
```

Bitbucket / Gitea / others: similar `remote:` lines with a URL.

Extract the URL from the captured output (look for `https://` after `remote:` lines). Do not use `gh`, `glab`, or any other API tool — only rely on what the server returned.

If push is rejected, fetch and rebase: `git pull --rebase origin <base>`, then re-push.

### 6. Report to User

Present a final summary using the URL extracted from push output:

```
## Pushed

**MR/PR URL:** <url from push output>

### What changed in this MR
- <bullet describing change 1>
- <bullet describing change 2>
- <bullet describing change 3>

### Commits pushed
- <hash> <subject>
- <hash> <subject>

### Files
<N> files changed (+<added> / -<removed>)
```

The "What changed" section should describe the MR's purpose and effect at a human level, based on the diff and commit messages — not a raw file list.

### Guardrails

- Never commit secrets, `.env` files, API keys, or credentials — warn and abort
- Never force-push to shared branches (`main`, `master`, `develop`, `release/*`)
- Always confirm with user before committing if changes look risky or unrelated
- Skip commit if working tree is clean — just push if needed and show URL
- If pre-commit hooks fail, surface the error and let the user decide
- Respect existing `.gitignore`; never add ignored files
- If no MR URL appears in push output (e.g., branch already up to date, or server doesn't emit one), tell the user plainly — don't fabricate a URL

## Trigger Phrases

- "commit and push my changes"
- "review my changes and ship them"
- "finalize this work"
- "create an MR"
