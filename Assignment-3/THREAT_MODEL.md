# Threat model — educational wallet

| Threat | Risk | Mitigation / remaining limitation |
|---|---|---|
| Key theft | Attacker can authorize transactions | Default keygen exports **public key only**. Optional development private-key file is **unencrypted**, marked TEST ONLY, created with mode `0600` on POSIX, and never overwritten. Windows permissions are not hardened by this demo; use an encrypted keystore/HSM for real use. Never submit development private keys. |
| Weak randomness | Predictable private keys | `Ed25519PrivateKey.generate()` uses the maintained cryptography library and OS-backed CSPRNG; never custom PRNG. Fixed keys in test vectors are public, unsafe for funds. |
| Replay | Valid transaction reused | Verify with `--nonce-db` to reject previously accepted `(network, sender, nonce)`. The demo file-based DB is sequential-use only, not concurrency-safe or crash-atomic; real chains need consensus-backed state and transactional updates. |
| Clipboard replacement | Recipient changed before signing | Show/confirm the recipient and amount through a trusted UI. Signature authenticates the signed recipient but cannot detect a user approving an attacker-supplied address. |
| Phishing | User tricked into sharing secret/signing | Do not paste private keys into websites, verify transaction details, use hardware wallet for real funds. |
| Accidental mainnet use | Real-money loss | Fixed network ID `course-testnet`, fixed address version `0x6f`, explicit `TOYTX\x00` domain separation, and conspicuous TEST ONLY warnings. Not interoperable with real chains. |

**Trust assumptions:** trusted local OS and `cryptography` installation, correct public-key distribution, and an uncompromised verifier. The demo does not implement balances, authorization policies, blockchain consensus, or a production wallet.
