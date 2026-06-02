#!/usr/bin/env python3
"""
openspec_notify.py

Reads the list of changed files from a git diff, keeps only the changes
reports (reports/*.md), generates an AI summary of each report, and posts
to Slack.

AI backend (first key found wins):
  AI_API_KEY    - preferred; any OpenAI-compatible provider
  AI_API_URL    - endpoint for the above (default: https://openrouter.ai/api/v1/chat/completions)
  AI_MODEL      - model name to use (default: openai/gpt-4o)
  GITHUB_TOKEN  - fallback; uses GitHub Models API (auto-provided)

Other environment variables required:
  SLACK_WEBHOOK_URL     - Slack Incoming Webhook URL (repo secret)
  GH_REPO               - e.g. "myorg/openspec"
  GH_SHA                - full commit SHA
  GH_REF                - branch name
  COMMIT_MESSAGE        - commit message
  COMMIT_AUTHOR         - committer display name
  COMMIT_URL            - URL to the commit on GitHub
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────

GITHUB_MODELS_API = "https://models.inference.ai.azure.com/chat/completions"
GITHUB_MODEL = "gpt-4o"

DEFAULT_AI_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_AI_MODEL = "openai/gpt-4o"

MAX_FILE_CHARS = 4000   # truncate large files before sending to the model
REPORTS_DIR = "reports/"


def md_to_mrkdwn(text: str) -> str:
    """Convert markdown formatting to Slack mrkdwn."""
    # Bold: **text** → *text*
    text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
    # Markdown list items: lines starting with "* " or "- " → bullet
    text = re.sub(r'^[\*\-]\s+', '• ', text, flags=re.MULTILINE)
    # Ensure Главное: is bolded if not already
    text = re.sub(r'^(?!\*)Главное:', '*Главное:*', text, flags=re.MULTILINE)
    return text

# ── Helpers ──────────────────────────────────────────────────────────────────

def read_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def github_file_url(path: str) -> str:
    repo = read_env("GH_REPO")
    sha = read_env("GH_SHA")
    return f"https://github.com/{repo}/blob/{sha}/{path}"


def read_file_safe(path: str) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8")
        if len(text) > MAX_FILE_CHARS:
            text = text[:MAX_FILE_CHARS] + "\n\n[... truncated ...]"
        return text
    except Exception:
        return "[file unreadable]"


def call_ai(messages: list[dict]) -> str:
    ai_key = read_env("AI_API_KEY")
    if ai_key:
        url = read_env("AI_API_URL") or DEFAULT_AI_API_URL
        model = read_env("AI_MODEL") or DEFAULT_AI_MODEL
        return _call_openai_compatible(messages, ai_key, url, model)
    return _call_github_models(messages)


def _call_openai_compatible(messages: list[dict], api_key: str, url: str, model: str) -> str:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 900,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"[AI] HTTP {e.code}: {body}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[AI] Error: {e}", file=sys.stderr)
        return None


def _call_github_models(messages: list[dict]) -> str:
    token = read_env("GITHUB_TOKEN")
    payload = json.dumps({
        "model": GITHUB_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 900,
    }).encode()

    req = urllib.request.Request(
        GITHUB_MODELS_API,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"[GitHub Models] HTTP {e.code}: {body}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[GitHub Models] Error: {e}", file=sys.stderr)
        return None


def post_to_slack(blocks: list[dict]) -> None:
    webhook = read_env("SLACK_WEBHOOK_URL")
    if not webhook:
        print("[Slack] SLACK_WEBHOOK_URL not set — skipping.", file=sys.stderr)
        return

    payload = json.dumps({"blocks": blocks}).encode()
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[Slack] Posted — HTTP {resp.status}")
    except Exception as e:
        print(f"[Slack] Error: {e}", file=sys.stderr)
        sys.exit(1)


# ── Report detection ──────────────────────────────────────────────────────────

def find_reports(files: list[str]) -> list[str]:
    """Keep only changed report files: reports/*.md."""
    return [f for f in files if f.startswith(REPORTS_DIR) and f.endswith(".md")]


def report_title(path: str) -> str:
    """Use the first H1 heading as the title, falling back to the file name."""
    try:
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except Exception:
        pass
    return Path(path).stem


# ── AI summary generation ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You write stakeholder updates in CLEAR, PLAIN LANGUAGE for a mixed audience
(product, marketing, ops — not engineers). Rules:
- Short sentences. Plain words. Avoid deep engineering jargon, acronyms, and code/file references.
- Common business and product terms are FINE and expected: conversions, platform, dashboard,
  integration, pipeline, campaign, dataset, API, webhook, etc. Don't translate these into analogies.
- Lead with the conclusion. Talk about OUTCOMES — what changes for the team or the product — not activities.
- Follow the exact section structure the user gives you; keep every section label.
- Be concise: each bullet is one short line. Total output under 250 words.
- Use bold (*word*) for key terms. Use bullet points for lists.
- If there is a risk or blocker, say it first.
- Write in Russian."""


def summarize_report(path: str) -> str:
    content = Path(path).read_text(encoding="utf-8", errors="replace")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "A changes report was published. Summarize it for stakeholders using EXACTLY "
                "this structure, keeping every section label and order:\n\n"
                "*Главное:* [one sentence — the single most important thing this report says shipped]\n\n"
                "*Обзор недели:* [2–3 sentences that summarize the report's "
                "\"## High-level overview of the week\" section]\n\n"
                "*База данных:*\n"
                "• [each notable database change — schema, views, functions, migrations — "
                "aggregated across the report's \"### Database\" subsections]\n\n"
                "*Фронтенд:*\n"
                "• [each notable frontend change, aggregated across the \"### Frontend\" subsections]\n\n"
                "*Edge-функции:*\n"
                "• [each notable edge-function change, aggregated across the \"### Edge function\" "
                "subsections; write \"• — без изменений\" if the report has none]\n\n"
                "*Темы недели:*\n"
                "• [each recurring theme from the report's \"## Themes for the week\" section]\n\n"
                "Aggregate across all changes in the report — do not go change-by-change. "
                "Focus on product impact, not file names. Write your entire response in Russian.\n\n"
                f"{content}"
            ),
        },
    ]
    result = call_ai(messages)
    return md_to_mrkdwn(result) if result else None


# ── Slack block builders ──────────────────────────────────────────────────────

def file_links_text(files: list[str], limit: int = 5) -> str:
    shown = files[:limit]
    links = [f"<{github_file_url(f)}|{Path(f).name}>" for f in shown]
    extra = f"  _+{len(files) - limit} more_" if len(files) > limit else ""
    return "  •  " + "\n  •  ".join(links) + extra


def build_blocks(sections: list[dict]) -> list[dict]:
    commit_url = read_env("COMMIT_URL")
    author = read_env("COMMIT_AUTHOR")
    message = read_env("COMMIT_MESSAGE", "").split("\n")[0]  # first line only
    ref = read_env("GH_REF")
    sha = read_env("GH_SHA")[:7]

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📋 OpenSpec Update", "emoji": True},
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"*<{commit_url}|{sha}>*  ·  `{ref}`  ·  "
                        f"{author}  ·  _{message}_"
                    ),
                }
            ],
        },
        {"type": "divider"},
    ]

    for section in sections:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{section['emoji']}  *{section['title']}*\n{section['summary']}",
            },
        })
        if section.get("files"):
            blocks.append({
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": file_links_text(section["files"])}
                ],
            })
        blocks.append({"type": "divider"})

    readme_url = f"https://github.com/{read_env('GH_REPO')}/blob/main/README.md"
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"<{readme_url}|View full OpenSpec index>",
            }
        ],
    })

    return blocks


# ── Main ──────────────────────────────────────────────────────────────────────

def main(changed_files_path: str) -> None:
    raw = Path(changed_files_path).read_text().strip()
    if not raw:
        print("No changed files — nothing to notify.")
        return

    all_files = [f.strip() for f in raw.splitlines() if f.strip()]
    reports = find_reports(all_files)

    if not reports:
        print("No report changes — skipping notification.")
        return

    for f in reports:
        summary = summarize_report(f)
        section = {
            "emoji": "📊",
            "title": report_title(f),
            "summary": summary or "_Summary unavailable — see linked file._",
            "files": [f],
        }
        blocks = build_blocks([section])
        post_to_slack(blocks)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: openspec_notify.py <changed-files-list>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
