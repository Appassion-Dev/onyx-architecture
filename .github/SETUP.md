# OpenSpec CI Notification — Setup

Sends an AI-generated Slack message whenever commits are pushed to `main`.

## How it works

1. `git diff HEAD~1 HEAD` finds changed files
2. Files are categorized by path:
   - `changes/archive/**` → **Change Finalized** (a proposal was shipped)
   - `specs/**` → **Spec Updated** (requirements changed)
   - `changes/**` (non-archive) → **Proposal in Progress** (idea stage)
3. Changed file contents are sent to the **GitHub Models API** (`gpt-4o-mini`) using the automatic `GITHUB_TOKEN` — no extra API key needed
4. The AI summary + file links are posted to Slack

## Required secrets

Add these in **Settings → Secrets and variables → Actions**:

| Secret | Value |
|--------|-------|
| `SLACK_OPENSPEC_WEBHOOK` | Slack Incoming Webhook URL for the target channel |

`GITHUB_TOKEN` is provided automatically by Actions — nothing to add.

## GitHub Models availability

The workflow uses the [GitHub Models](https://github.com/marketplace/models) API (`models.inference.ai.azure.com`) authenticated via `GITHUB_TOKEN`.

- **Free accounts**: rate-limited (low RPM/RPD) but sufficient for commit-based triggers
- **GitHub Copilot subscribers / GitHub Teams+**: higher limits

If the API returns an error (rate limit or access), the script falls back to posting the Slack message with _"Summary unavailable — see linked files"_ rather than failing the workflow.

## Slack setup

1. Go to your Slack workspace → **Apps → Incoming Webhooks**
2. Add a new webhook pointing at the channel you want (e.g. `#dev-specs`)
3. Copy the webhook URL
4. Add it as `SLACK_OPENSPEC_WEBHOOK` in GitHub repo secrets

## Local testing

```bash
# Set env vars
export GITHUB_TOKEN=ghp_...
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
export GH_REPO=myorg/openspec
export GH_SHA=abc1234
export GH_REF=main
export COMMIT_MESSAGE="feat: add tighten-gclid-attribution-window proposal"
export COMMIT_AUTHOR="Art"
export COMMIT_URL=https://github.com/myorg/openspec/commit/abc1234

# Create a test file list
echo "changes/tighten-gclid-attribution-window/proposal.md" > /tmp/test_files.txt

# Run
python3 .github/scripts/openspec_notify.py /tmp/test_files.txt
```
