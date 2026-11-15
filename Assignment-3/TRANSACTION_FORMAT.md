# Byte-level transaction format (version 1)

This is a **toy protocol**, not Bitcoin or Ethereum. All transaction fields are mandatory; extra fields are rejected. All integer values must be JSON integers (not booleans or floating-point values). The exact byte string is constructed in the fixed order below, independent of JSON whitespace and object key order. No JSON bytes are signed.

| Order | Field | Encoding | Size |
|---|---|---|---|
| 1 | Domain separator | ASCII `TOYTX` followed by `00` | 6 bytes |
| 2 | Version | unsigned 8-bit integer, exactly `01` | 1 byte |
| 3 | Network ID length | unsigned 8-bit integer | 1 byte |
| 4 | Network ID | ASCII `course-testnet` | 14 bytes |
| 5 | Sender address | Base58Check-decode to `version (1) || SHA256(pubkey)[0:20] || checksum (4)` | 25 bytes |
| 6 | Recipient address | Same as sender | 25 bytes |
| 7 | Amount | unsigned 64-bit integer, big-endian, positive | 8 bytes |
| 8 | Nonce | unsigned 64-bit integer, big-endian | 8 bytes |
| 9 | Memo hash | exactly 32 raw bytes, decoded from 64 lowercase hexadecimal characters | 32 bytes |

**Total:** 120 bytes (6 + 1 + 1 + 14 + 25 + 25 + 8 + 8 + 32).

Address derivation: Ed25519 raw public key (32 bytes) -> SHA-256 -> first 20 bytes -> prepend version byte `0x6f` -> append first 4 bytes of double SHA-256 of the 21-byte payload -> Base58 encode preserving leading zero bytes. Checksum and version are validated before use. The public key is **not** recovered from an address; the signed envelope includes it.

Memo: UTF-8 text -> SHA-256 -> 32 bytes. Empty memo is SHA-256 of empty bytes. Memo text is not included in the signed transaction, only its hash.

Signature: Ed25519 over the **exact 120-byte transaction**, output exactly 64 bytes, encoded as **128 lowercase hex characters**. The signed JSON envelope contains exactly `transaction`, `algorithm` (`Ed25519`), `public_key` (32-byte lowercase hex), and `signature` (64-byte lowercase hex). Ed25519's fixed-width encoding avoids DER ambiguity; malformed/noncanonical hex lengths or characters and invalid Ed25519 signatures are rejected by the cryptographic library.

Verification: validate transaction and network; decode and checksum addresses; derive sender address from the supplied public key and compare; verify Ed25519 signature over canonical bytes. Stateful nonce checking uses the tuple `(network_id, sender, nonce)`; each accepted nonce may appear only once in the supplied nonce database. Signature verification alone cannot detect a previously seen transaction without replay state.

`generate_deliverables.py` uses **publicly known deterministic test seeds** solely to make repeatable examples. `keygen` uses the cryptography library's OS-backed secure randomness instead.
