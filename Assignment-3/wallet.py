"""Educational Ed25519 wallet. Not for real funds."""
import hashlib
import json
import os
import stat
import struct
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

NETWORK = 'course-testnet'
ADDRESS_VERSION = 0x6F
ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
FIELDS = ('version','network_id','sender','recipient','amount_units','nonce','memo_hash')


def sha256(data): return hashlib.sha256(data).digest()


def b58encode(data):
    n = int.from_bytes(data, 'big')
    chars = ''
    while n:
        n, r = divmod(n, 58)
        chars = ALPHABET[r] + chars
    return '1' * (len(data) - len(data.lstrip(b'\x00'))) + chars


def b58decode(text):
    if not isinstance(text, str) or not text: raise ValueError('empty/malformed Base58')
    n = 0
    for ch in text:
        if ch not in ALPHABET: raise ValueError('invalid Base58 character')
        n = n * 58 + ALPHABET.index(ch)
    raw = n.to_bytes((n.bit_length() + 7)//8, 'big') if n else b''
    return b'\x00' * (len(text) - len(text.lstrip('1'))) + raw


def address_from_public(public_bytes):
    if len(public_bytes) != 32: raise ValueError('Ed25519 public key must be 32 bytes')
    payload = bytes([ADDRESS_VERSION]) + sha256(public_bytes)[:20]
    return b58encode(payload + sha256(sha256(payload))[:4])


def validate_address(address):
    raw = b58decode(address)
    if len(raw) != 25 or raw[0] != ADDRESS_VERSION: raise ValueError('invalid address length/version')
    if sha256(sha256(raw[:-4]))[:4] != raw[-4:]: raise ValueError('invalid address checksum')
    if b58encode(raw) != address: raise ValueError('noncanonical Base58 address')
    return True


def private_bytes(key):
    return key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())


def public_bytes(key):
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def generate_keypair(public_path, private_path=None):
    key = Ed25519PrivateKey.generate()  # cryptography uses secure OS-backed randomness
    pub = public_bytes(key)
    Path(public_path).write_text(json.dumps({'algorithm':'Ed25519','public_key':pub.hex(),'address':address_from_public(pub)},indent=2)+'\n')
    if private_path:
        # Exclusive creation, restrictive permissions on POSIX; no overwriting.
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(private_path, flags, 0o600)
        try:
            if os.name == 'posix': os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
            with os.fdopen(fd,'w') as f:
                json.dump({'WARNING':'TEST ONLY - NEVER USE WITH REAL FUNDS; UNENCRYPTED PRIVATE KEY', 'algorithm':'Ed25519', 'private_key':private_bytes(key).hex()}, f, indent=2)
                f.write('\n')
        except BaseException:
            try: os.unlink(private_path)
            except OSError: pass
            raise
    return {'public_key':pub.hex(),'address':address_from_public(pub),'private_file_written':bool(private_path)}


def exact_hex(value, length, name):
    if not isinstance(value,str) or len(value)!=length*2 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError(f'{name} must be {length} bytes of lowercase hex')
    return bytes.fromhex(value)


def uint(value, max_value, name):
    if type(value) is not int or not 0 <= value <= max_value: raise ValueError(f'invalid {name}')
    return value


def canonical_bytes(tx):
    if not isinstance(tx,dict) or set(tx)!=set(FIELDS): raise ValueError('transaction fields missing/extra')
    version = uint(tx['version'],255,'version')
    if version != 1: raise ValueError('unsupported transaction version')
    network = tx['network_id']
    if not isinstance(network,str) or network != NETWORK: raise ValueError('wrong network')
    nb = network.encode('ascii')
    if len(nb)>255: raise ValueError('network too long')
    sender = tx['sender']; recipient = tx['recipient']
    validate_address(sender); validate_address(recipient)
    amount = uint(tx['amount_units'],2**64-1,'amount_units')
    if amount == 0: raise ValueError('amount must be positive')
    nonce = uint(tx['nonce'],2**64-1,'nonce')
    memo = exact_hex(tx['memo_hash'],32,'memo_hash')
    # Domain tag, version, network length + bytes, address raw bytes, uint64 big-endian fields, memo hash.
    return b'TOYTX\x00' + bytes([version,len(nb)]) + nb + b58decode(sender) + b58decode(recipient) + struct.pack('>QQ',amount,nonce) + memo


def sign_transaction(tx, private_hex):
    key = Ed25519PrivateKey.from_private_bytes(exact_hex(private_hex,32,'private_key'))
    pub = public_bytes(key)
    if tx['sender'] != address_from_public(pub): raise ValueError('wrong signer: sender does not match private key')
    payload = canonical_bytes(tx)
    return {'transaction':tx,'algorithm':'Ed25519','public_key':pub.hex(),'signature':key.sign(payload).hex()}


def verify_envelope(envelope, used_nonces=None):
    if not isinstance(envelope,dict) or set(envelope)!= {'transaction','algorithm','public_key','signature'}: raise ValueError('malformed signed envelope')
    if envelope['algorithm']!='Ed25519': raise ValueError('wrong algorithm')
    pub = exact_hex(envelope['public_key'],32,'public_key')
    sig = exact_hex(envelope['signature'],64,'signature')
    tx = envelope['transaction']
    payload = canonical_bytes(tx)
    if tx['sender'] != address_from_public(pub): raise ValueError('wrong signer')
    try: Ed25519PublicKey.from_public_bytes(pub).verify(sig,payload)
    except InvalidSignature as exc: raise ValueError('invalid signature or modified transaction') from exc
    replay_key = (tx['network_id'],tx['sender'],tx['nonce'])
    if used_nonces is not None:
        if replay_key in used_nonces: raise ValueError('replayed nonce')
        used_nonces.add(replay_key)
    return True


def memo_hash(memo): return sha256(memo.encode('utf-8')).hex()
