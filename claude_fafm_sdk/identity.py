"""Hosted identity — the namepoint + write key, stored locally so writes "just work".

**A-for-first-touch, B-for-keepers** (the namepoint doctrine):

- **A — anonymous (zero-config):** the first write with no identity auto-provisions
  an anonymous namepoint + key (`POST /api/voice/issue/anonymous`) and saves it.
  Live instantly — but *session-like*: lose this file and the handle orphans. That
  lose-ability is deliberate, a reminder of the statelessness memory is meant to cure.
- **B — recoverable (keepers):** `claim --email` provisions a named, recoverable
  namepoint (`POST /api/voice/issue`) you keep.

Mirrors grok-faf-voice's identity model — one format, never a fork. Uses stdlib
`urllib` (the issue endpoints are plain REST), so this carries no extra dependency.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:  # explicit UA — the WAF bans the default "Python-urllib/x" signature (CF 1010)
    _USER_AGENT = f"claude-fafm-sdk/{importlib.metadata.version('claude-fafm-sdk')}"
except importlib.metadata.PackageNotFoundError:  # pragma: no cover - editable/uninstalled
    _USER_AGENT = "claude-fafm-sdk"

MEMORY_ENDPOINT = "https://mcpaas.live"
ANON_ISSUE_URL = f"{MEMORY_ENDPOINT}/api/voice/issue/anonymous"
EMAIL_ISSUE_URL = f"{MEMORY_ENDPOINT}/api/voice/issue"
IDENTITY_PATH = Path.home() / ".claude-fafm-sdk" / "identity.json"
SCHEMA_VERSION = 1


class IdentityError(RuntimeError):
    """Provisioning or identity-file problem — always carries an actionable message."""


@dataclass
class Identity:
    namepoint: str
    api_key: str
    source: str  # "anonymous-issue" | "email-issue" | "env"

    @property
    def recoverable(self) -> bool:
        return self.source == "email-issue"

    @property
    def url(self) -> str:
        return f"{MEMORY_ENDPOINT}/{self.namepoint}"


def load_identity(path: Path | None = None) -> Identity | None:
    """Load the saved identity, or None if absent. Raises on a malformed file —
    fail loud rather than silently re-provision and orphan an existing namepoint."""
    path = path or IDENTITY_PATH
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise IdentityError(f"identity file at {path} is unreadable ({e}); delete it to re-provision") from e
    if data.get("version") != SCHEMA_VERSION:
        raise IdentityError(
            f"identity file at {path} has unsupported schema {data.get('version')!r} "
            f"(expected {SCHEMA_VERSION}); delete it to re-provision"
        )
    np, key = data.get("namepoint"), data.get("api_key")
    if not (isinstance(np, str) and isinstance(key, str)):
        raise IdentityError(f"identity file at {path} is missing namepoint/api_key; delete it to re-provision")
    return Identity(np, key, data.get("source", "anonymous-issue"))


def save_identity(identity: Identity, path: Path | None = None) -> None:
    """Persist the identity 0600 (the key is a secret)."""
    path = path or IDENTITY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": SCHEMA_VERSION,
                "namepoint": identity.namepoint,
                "api_key": identity.api_key,
                "source": identity.source,
                "created": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        path.chmod(0o600)
    except OSError:  # pragma: no cover - Windows/FUSE don't honor chmod
        pass


def _post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": _USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 - fixed https mcpaas endpoints
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise IdentityError(f"{url} returned HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise IdentityError(f"could not reach {url} ({e.reason}); check your network") from e


def _identity_from_issue(data: dict, source: str) -> Identity:
    if data.get("error"):
        raise IdentityError(str(data["error"]))
    np, key = data.get("namepoint"), data.get("key")
    if not (isinstance(np, str) and isinstance(key, str)):
        raise IdentityError(f"issue endpoint returned an unexpected shape: {data!r}")
    return Identity(np, key, source)


def provision_anonymous() -> Identity:
    """Mint an anonymous namepoint + key (zero-config, no email). Path A."""
    return _identity_from_issue(_post(ANON_ISSUE_URL, {}), "anonymous-issue")


def claim_email(email: str) -> Identity:
    """Claim a recoverable, named namepoint + key for an email. Path B."""
    return _identity_from_issue(_post(EMAIL_ISSUE_URL, {"email": email}), "email-issue")


def resolve() -> Identity | None:
    """Read the active identity without provisioning: env → saved file. Returns None
    if neither is present (the caller decides whether to auto-provision)."""
    env_key, env_np = os.environ.get("MCPAAS_API_KEY"), os.environ.get("FAF_SOUL")
    if env_key and env_np:
        return Identity(env_np, env_key, "env")
    return load_identity()
