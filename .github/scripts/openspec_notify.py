#!/usr/bin/env python3
"""
openspec_notify.py

Reads the list of changed files from a git diff, categorizes them by
openspec path pattern, generates an AI summary via GitHub Models API
(using GITHUB_TOKEN — no extra secrets), and posts to Slack.

Environment variables required:
  GITHUB_TOKEN          - auto-provided by GitHub Actions
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
import sys
import urllib.request
import urllib.error
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────

MODELS_API = "https://models.inference.ai.azure.com/chat/completions"
MODEL = "gpt-4o-mini"
MAX_FILE_CHARS = 4000   # truncate large files before sending to the model
MAX_FILES_PER_CALL = 5  # cap to keep prompt size reasonable

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


def call_github_models(messages: list[dict]) -> str:
    token = read_env("GITHUB_TOKEN")
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 400,
    }).encode()

    req = urllib.request.Request(
        MODELS_API,
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

def categorize(files: list[str]) -> dict[str, list[str]]:
    """
    Returns a dict with keys: 'proposals', 'specs', 'archive', 'other'.
    'proposals' = changes under changes/ but NOT in changes/archive/
    'archive'   = changes/archive/** (a change was finalized)
    'specs'     = specs/**
    """
    result: dict[str, list[str]] = {
        "proposals": [],
        "specs": [],
        "archive": [],
        "other": [],
    }
    for f in files:
        if f.startswith("changes/archive/"):
            result["archive"].append(f)
        elif f.startswith("changes/"):
            result["proposals"].append(f)
        elif f.startswith("specs/"):
            result["specs"].append(f)
        else:
            result["other"].append(f)
    return result


# ── AI summary generation ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a technical writer summarizing changes to a software specification \
repository for non-technical stakeholders. Be concise (2-4 sentences max \
per summary). Focus on WHAT is changing and WHY it matters to the product, \
not implementation details. Write in plain English."""


def summarize_proposals(files: list[str]) -> str:
    sample = files[:MAX_FILES_PER_CALL]
    contents = "\n\n---\n\n".join(
        f"File: {f}\n\n{read_file_safe(f)}" for f in sample
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "The following specification proposal files were updated in a commit. "
                "These represent a potential development direction — the idea has been "
                "proposed but not yet finalized. Summarize what is being proposed and "
                "why it matters. Do not describe the file format, just the content.\n\n"
                f"{contents}"
            ),
        },
    ]
    return call_github_models(messages)


def summarize_specs(files: list[str]) -> str:
    sample = files[:MAX_FILES_PER_CALL]
    contents = "\n\n---\n\n".join(
        f"File: {f}\n\n{read_file_safe(f)}" for f in sample
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "The following finalized specification files were updated in a commit. "
                "These represent confirmed, production-ready requirements. Summarize "
                "what capability was added or changed and what it means for the product. "
                "Do not describe the file format, just the content.\n\n"
                f"{contents}"
            ),
        },
    ]
    return call_github_models(messages)


def summarize_archive(files: list[str]) -> str:
    # Try to find the proposal.md in the archived change to summarize it
    proposal_files = [f for f in files if f.endswith("proposal.md")]
    target = proposal_files[:1] or files[:1]
    contents = "\n\n---\n\n".join(
        f"File: {f}\n\n{read_file_safe(f)}" for f in target
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "A change proposal has just been archived — meaning it has been fully "
                "implemented and its requirements are now part of the finalized specs. "
                "Summarize what was built and delivered. "
                "Do not describe the file format, just the content.\n\n"
                f"{contents}"
            ),
        },
    ]
    return call_github_models(messages)


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
    cats = categorize(all_files)

    sections: list[dict] = []

    if cats["archive"]:
        summary = summarize_archive(cats["archive"])
        sections.append({
            "emoji": "✅",
            "title": "Change Finalized",
            "summary": summary or "_Summary unavailable — see linked files._",
            "files": cats["archive"],
        })

    if cats["specs"]:
        summary = summarize_specs(cats["specs"])
        sections.append({
            "emoji": "📐",
            "title": "Spec Updated",
            "summary": summary or "_Summary unavailable — see linked files._",
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
