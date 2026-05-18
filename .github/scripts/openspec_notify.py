#!/usr/bin/env python3
"""
openspec_notify.py

Reads the list of changed files from a git diff, categorizes them by
openspec path pattern, generates an AI summary, and posts to Slack.

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
MAX_FILES_PER_CALL = 5  # cap to keep prompt size reasonable


def md_to_mrkdwn(text: str) -> str:
    """Convert markdown formatting to Slack mrkdwn."""
    # Bold: **text** → *text*
    text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
    # Markdown list items: lines starting with "* " or "- " → bullet
    text = re.sub(r'^[\*\-]\s+', '• ', text, flags=re.MULTILINE)
    # Ensure TL;DR: is bolded if not already
    text = re.sub(r'^(?!\*)TL;DR:', '*TL;DR:*', text, flags=re.MULTILINE)
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
        "max_tokens": 400,
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
        "max_tokens": 400,
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


# ── Category detection ────────────────────────────────────────────────────────

PROPOSAL_DOC_NAMES = {"proposal.md", "design.md", "tasks.md"}


def categorize(files: list[str]) -> dict[str, list[str]]:
    """
    Returns a dict with keys: 'proposals', 'specs', 'other'.
    'proposals' = changes/<change>/(proposal|design|tasks).md only.
                  Excludes changes/<change>/specs/** and changes/archive/**.
    'specs'     = specs/** (acknowledged only, content not sent to AI).
    """
    result: dict[str, list[str]] = {
        "proposals": [],
        "specs": [],
        "other": [],
    }
    for f in files:
        if f.startswith("changes/archive/"):
            continue
        if f.startswith("changes/"):
            parts = f.split("/")
            # changes/<change>/<file> — exactly 3 segments, and not under .../specs/
            if len(parts) == 3 and parts[2] in PROPOSAL_DOC_NAMES:
                result["proposals"].append(f)
            continue
        if f.startswith("specs/"):
            result["specs"].append(f)
        else:
            result["other"].append(f)
    return result


# ── AI summary generation ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You write stakeholder updates in CAVEMAN STYLE for non-technical readers. Rules:
- Short sentences. Simple words. No jargon, no acronyms, no tech terms.
- If a technical concept is unavoidable, translate it into an everyday analogy.
- Lead with the conclusion. Talk about OUTCOMES (what changes for people), never files or code.
- Format: TL;DR first, then 2–4 short bullets.
- Total output under 120 words.
- Use bold (*word*) for key terms. Use bullet points for lists.
- If there is a risk or blocker, say it first.
- Write in Russian, in caveman style (короткие фразы, простые слова, как для ребёнка)."""


def summarize_proposals(files: list[str]) -> str:
    contents = "\n\n---\n\n".join(
        f"File: {f}\n\n{Path(f).read_text(encoding='utf-8', errors='replace')}" for f in files
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "A development proposal was updated. It is not finalized — it represents "
                "a direction being considered. Generate a stakeholder update using this format:\n"
                "*TL;DR:* [one sentence — the most important thing to know about this proposal]\n"
                "• [What outcome or goal this proposal serves]\n"
                "• [Key decision or tradeoff involved, if any]\n"
                "• [What happens next / what still needs to be decided]\n\n"
                "Do not describe the file. Focus on the product impact. "
                "Write your entire response in Russian.\n\n"
                f"{contents}"
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
    all_files = [f for f in all_files if Path(f).name != ".openspec.yaml"]
    cats = categorize(all_files)

    sections: list[dict] = []

    if cats["specs"]:
        sections.append({
            "emoji": "📐",
            "title": "Spec Integrated",
            "summary": "Новое правило теперь в силе. Команда договорилась — так и делаем.",
            "files": cats["specs"],
        })

    if cats["proposals"]:
        summary = summarize_proposals(cats["proposals"])
        sections.append({
            "emoji": "💡",
            "title": "Proposal in Progress",
            "summary": summary or "_Summary unavailable — see linked files._",
            "files": cats["proposals"],
        })

    if not sections:
        print("No openspec-relevant changes — skipping notification.")
        return

    blocks = build_blocks(sections)
    post_to_slack(blocks)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: openspec_notify.py <changed-files-list>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
