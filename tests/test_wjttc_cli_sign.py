"""WJTTC — CLI provenance glue (1.4): keygen · seal --sign · verify · open-refuses-signed.

Thin shell tests over ``cli.main([...])`` (the exit-code contract). Crypto
correctness lives in ``test_wjttc_sign.py``; this file guards the CLI wiring and
its fail-closed exits.
"""
from __future__ import annotations

import stat
from pathlib import Path

import pytest

# Signing needs the optional [sign] extra. Skip in the zero-crypto base config
# (base `pip install` / base CI job); the `sign` CI job installs [sign] and runs these.
pytest.importorskip("cryptography")

from claude_fafm_sdk.cli import main
from claude_fafm_sdk.soul import Soul

NP = "cli-sign-test"


def _init(path: Path) -> None:
    assert main(["init", "-f", str(path), "-n", NP, "--force"]) == 0


def _keygen(tmp: Path) -> tuple[Path, Path]:
    assert main(["keygen", "--out", str(tmp)]) == 0
    return tmp / "sign.pem", tmp / "sign.pub.pem"


def test_keygen_writes_keypair_private_0600(tmp_path: Path) -> None:
    priv, pub = _keygen(tmp_path)
    assert priv.is_file() and pub.is_file()
    assert stat.S_IMODE(priv.stat().st_mode) == 0o600  # private key locked down
    assert priv.read_bytes().startswith(b"-----BEGIN PRIVATE KEY-----")
    assert pub.read_bytes().startswith(b"-----BEGIN PUBLIC KEY-----")


def test_keygen_no_clobber_without_force(tmp_path: Path) -> None:
    _keygen(tmp_path)
    assert main(["keygen", "--out", str(tmp_path)]) == 1  # would destroy the key
    assert main(["keygen", "--out", str(tmp_path), "--force"]) == 0


def test_s9_seal_sign_then_verify_roundtrip(tmp_path: Path) -> None:
    priv, pub = _keygen(tmp_path)
    soul = tmp_path / "s.fafm"
    pkt = tmp_path / "s.fafmp"
    out = tmp_path / "opened.fafm"
    _init(soul)
    assert main(["etch", "-f", str(soul), "signed-fact", "--id", "sf"]) == 0
    assert main(["seal", "-f", str(soul), "-o", str(pkt), "--sign", "--key", str(priv)]) == 0
    # S9 good → 0, and -o writes the verified soul
    assert main(["verify", str(pkt), "-k", str(pub), "-o", str(out)]) == 0
    assert Soul.load(out).get_fact("sf") is not None


def test_s9_verify_wrong_key_exit_1(tmp_path: Path) -> None:
    priv, _pub = _keygen(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    assert main(["keygen", "--out", str(other)]) == 0
    wrong_pub = other / "sign.pub.pem"
    soul = tmp_path / "s.fafm"
    pkt = tmp_path / "s.fafmp"
    _init(soul)
    assert main(["seal", "-f", str(soul), "-o", str(pkt), "--sign", "--key", str(priv)]) == 0
    assert main(["verify", str(pkt), "-k", str(wrong_pub)]) == 1  # falsifier: non-zero


def test_s9_verify_tampered_exit_1(tmp_path: Path) -> None:
    priv, pub = _keygen(tmp_path)
    soul = tmp_path / "s.fafm"
    pkt = tmp_path / "s.fafmp"
    _init(soul)
    assert main(["seal", "-f", str(soul), "-o", str(pkt), "--sign", "--key", str(priv)]) == 0
    b = bytearray(pkt.read_bytes())
    b[-1] ^= 0xFF  # flip a signature byte
    pkt.write_bytes(bytes(b))
    assert main(["verify", str(pkt), "-k", str(pub)]) == 1


def test_s8_open_refuses_signed_packet(tmp_path: Path) -> None:
    priv, _pub = _keygen(tmp_path)
    soul = tmp_path / "s.fafm"
    pkt = tmp_path / "s.fafmp"
    _init(soul)
    assert main(["seal", "-f", str(soul), "-o", str(pkt), "--sign", "--key", str(priv)]) == 0
    # `open` is unsigned-only → exit 1, pointing at verify (fail closed)
    assert main(["open", str(pkt)]) == 1


def test_seal_sign_without_key_exit_1(tmp_path: Path) -> None:
    soul = tmp_path / "s.fafm"
    _init(soul)
    assert main(["seal", "-f", str(soul), "--sign"]) == 1  # --sign needs --key


def test_verify_on_unsigned_exit_1(tmp_path: Path) -> None:
    _priv, pub = _keygen(tmp_path)
    soul = tmp_path / "s.fafm"
    pkt = tmp_path / "s.fafmp"
    _init(soul)
    assert main(["seal", "-f", str(soul), "-o", str(pkt)]) == 0  # unsigned
    assert main(["verify", str(pkt), "-k", str(pub)]) == 1  # not signed → fail closed


def test_cli_merge_signed_packet_fails_closed_no_clobber(tmp_path: Path) -> None:
    priv, _pub = _keygen(tmp_path)
    a = tmp_path / "a.fafm"
    b = tmp_path / "b.fafm"
    pkt = tmp_path / "a.fafmp"
    _init(a)
    assert main(["etch", "-f", str(a), "from-a", "--id", "fa"]) == 0
    assert main(["seal", "-f", str(a), "-o", str(pkt), "--sign", "--key", str(priv)]) == 0
    _init(b)
    assert main(["etch", "-f", str(b), "local-only", "--id", "loc"]) == 0
    before = b.read_bytes()
    # CLI merge is unsigned-only (like open) — a signed packet fails closed, no clobber.
    assert main(["merge", "-f", str(b), str(pkt)]) == 1
    assert b.read_bytes() == before
    assert [f.id for f in Soul.load(b).facts] == ["loc"]
