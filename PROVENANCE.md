# Verifiable Provenance — signing a Soul-Packet (1.4)

A Soul-Packet (`SPK1`, see [PACKET.md](PACKET.md)) travels a `.fafm` soul as
CRC-sealed bytes. **CRC proves the payload wasn't corrupted — not who sent it.**
1.4 adds an **optional** layer that answers the second question: an **Ed25519
signature** over the same payload bytes.

Integrity (CRC) and provenance (signature) are **separate**, on purpose. A packet
can be unsigned (CRC only, byte-identical to 1.2/1.3) or signed (CRC **and** a
signature). Signing is opt-in behind the `[sign]` extra — the base SDK and the
Provable Receipt stay zero-crypto.

## What a signature does — and does not — mean

**It proves:** *this key signed these exact payload bytes.* Verify with the
matching public key and you know the payload is unmodified **and** was sealed by
the holder of that private key.

It is **not**:

- **authentication branding / "authenticated memory"** — it's a key binding, nothing more.
- **a human identity** — a key is not a person. There is no name, email, or account in it.
- **encryption** — the payload is plaintext `.fafm`; anyone can read it.
- **a PKI** — no CA, no CRL, no revocation, no trust chain. You bring the public key.
- **tamper-*proof* transport.** A signature does **not** prevent a **strip-downgrade**:
  anyone can drop the 64-byte trailer and clear the `SIGNED` flag to recover an
  equivalent *unsigned* packet of the same payload. The flag is not signed. Verify
  proves *this key signed these bytes* — never *this content can only travel signed.*
  If you require provenance, **demand a signed packet and verify it** — don't assume
  an unsigned one was never signed.

## Wire format

Header layout is unchanged from 1.2/1.3 (16-byte little-endian). Signing sets one
flag bit and appends a fixed trailer:

```
offset size field
0      4    magic    b"SPK1"
4      2    version  u16 = 1
6      2    flags    u16    bit 0 = SIGNED (0x0001)
8      4    crc32    u32    CRC-32 of PAYLOAD ONLY
12     4    length   u32    payload byte length (N) — trailer NOT counted
16     N    payload  UTF-8 canonical .fafm YAML
16+N   64   sig      Ed25519 signature over payload[16:16+N]   (only iff SIGNED)
```

- The signature covers the **same bytes CRC covers** — the raw canonical payload.
- The trailer is **exactly 64 bytes**: the Ed25519 signature, nothing else. No
  `key_id`, no embedded public key (both deferred to a later release).
- An **unsigned** seal (`flags = 0`, no trailer) is **byte-identical** to 1.2/1.3.
- `SIGNED` is **SPK1-local** — it is *not* the project `FAFB` binary's flag. `SPK1` ≠ `FAFB`.

## Reading rules (fail closed)

- `from_packet` / CLI `open` open **unsigned** packets only. Handed a signed
  packet, they reject it with a pointer to `verify` — they never CRC-open it as unsigned.
- `verify_packet(data, public_key)` / CLI `verify` open a **signed** packet, and
  only after the signature verifies. Any of *not-signed · truncated · length
  mismatch · CRC mismatch · bad signature* raises `PacketError` — no partial soul.
- `merge_packet(local, data, public_key=…)` **verifies** a signed peer before
  ingest. Given a signed packet and no key, it rejects — a signed peer is never
  merged unverified.
- **Old 1.2/1.3 readers reject** a signed packet: the trailer makes the byte
  length disagree with the header's payload length (length-exact check).

## Use it

```sh
pip install 'claude-fafm-sdk[sign]'

claude-fafm-sdk keygen                                   # sign.pem (0600) + sign.pub.pem
claude-fafm-sdk seal -f soul.fafm -o soul.fafmp --sign --key sign.pem
claude-fafm-sdk verify soul.fafmp -k sign.pub.pem        # exit 0 good / 1 bad
```

Library:

```python
from claude_fafm_sdk import Soul, sign_packet, verify_packet, generate_keypair

priv_pem, pub_pem = generate_keypair()          # or load your own PEM
soul = Soul.load("soul.fafm")
packet = sign_packet(soul, priv_pem)            # bytes: header + payload + 64-byte sig
back = verify_packet(packet, pub_pem)           # Soul, or PacketError on any failure
```

Keep the private key secret (`keygen` writes it `0600`) and **never commit it**.
Share only the public PEM. Ed25519 signing is deterministic (RFC 8032), so signing
identical payload bytes with the same key yields identical bytes — a signed packet
is a reproducible artifact.
