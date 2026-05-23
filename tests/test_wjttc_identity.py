"""WJTTC — hosted identity (the namepoint + key store).

ENGINE: save/load/resolve do what they say. BRAKE: a malformed identity file
fails LOUD (never silently re-provision and orphan a real namepoint). No network,
no fakes — pure file + precedence logic.
"""

import pytest

import claude_fafm_sdk.identity as idmod
from claude_fafm_sdk.identity import Identity, IdentityError, load_identity, resolve, save_identity


def test_engine_identity_save_load_roundtrip(tmp_path):
    p = tmp_path / "identity.json"
    save_identity(Identity("you26", "mcp_voice_abc", "email-issue"), p)
    back = load_identity(p)
    assert back.namepoint == "you26"
    assert back.api_key == "mcp_voice_abc"
    assert back.recoverable is True
    assert back.url == "https://mcpaas.live/you26"


def test_engine_identity_key_file_is_0600(tmp_path):
    # The api_key is a secret — file must not be world/group readable.
    p = tmp_path / "identity.json"
    save_identity(Identity("anonabc12", "k", "anonymous-issue"), p)
    assert oct(p.stat().st_mode & 0o077) == "0o0"


def test_engine_identity_anonymous_is_not_recoverable():
    anon = Identity("anonabc12", "k", "anonymous-issue")
    assert anon.recoverable is False


def test_engine_identity_missing_returns_none(tmp_path):
    assert load_identity(tmp_path / "nope.json") is None


def test_brake_identity_malformed_raises(tmp_path):
    p = tmp_path / "identity.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(IdentityError):
        load_identity(p)


def test_brake_identity_bad_schema_raises(tmp_path):
    p = tmp_path / "identity.json"
    p.write_text('{"version": 999, "namepoint": "x", "api_key": "k"}', encoding="utf-8")
    with pytest.raises(IdentityError):
        load_identity(p)


def test_engine_identity_resolve_env_wins(tmp_path, monkeypatch):
    # env (MCPAAS_API_KEY + FAF_SOUL) is the power path — beats any saved file.
    monkeypatch.setattr(idmod, "IDENTITY_PATH", tmp_path / "identity.json")
    save_identity(Identity("filehandle10", "filekey", "anonymous-issue"))
    monkeypatch.setenv("MCPAAS_API_KEY", "envkey")
    monkeypatch.setenv("FAF_SOUL", "envhandle")
    ident = resolve()
    assert (ident.namepoint, ident.api_key, ident.source) == ("envhandle", "envkey", "env")


def test_engine_identity_resolve_file_when_no_env(tmp_path, monkeypatch):
    monkeypatch.setattr(idmod, "IDENTITY_PATH", tmp_path / "identity.json")
    monkeypatch.delenv("MCPAAS_API_KEY", raising=False)
    monkeypatch.delenv("FAF_SOUL", raising=False)
    save_identity(Identity("filehandle10", "filekey", "email-issue"))
    ident = resolve()
    assert ident.namepoint == "filehandle10" and ident.source == "email-issue"


def test_engine_identity_resolve_none_when_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(idmod, "IDENTITY_PATH", tmp_path / "identity.json")
    monkeypatch.delenv("MCPAAS_API_KEY", raising=False)
    monkeypatch.delenv("FAF_SOUL", raising=False)
    assert resolve() is None
