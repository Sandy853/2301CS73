"""Educational PoW blockchain with branch-aware UTXO validation (not production consensus)."""
from __future__ import annotations
import hashlib, json, struct, time
from dataclasses import dataclass, field
from typing import Optional
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

MAX_MONEY = 2**63 - 1
MAX_HASH = 2**256 - 1
SUBSIDY = 50
ZERO = '00' * 32

def canonical(obj): return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
def sha(data): return hashlib.sha256(data).digest()
def shahex(data): return sha(data).hex()
def keypair():
    sk = Ed25519PrivateKey.generate()
    pk = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    return sk, pk

def address(pk): return shahex(bytes.fromhex(pk))

def output(value, owner): return {'value': value, 'owner': owner}

def txid(tx): return shahex(canonical(tx))

def spend_message(inputs, outputs): return canonical({'inputs': inputs, 'outputs': outputs})

def make_spend(inputs, outputs, keys):
    """inputs: [{txid,index}]; keys: matching private keys."""
    msg = spend_message(inputs, outputs)
    return {'kind': 'spend', 'inputs': inputs, 'outputs': outputs,
            'witnesses': [{'pubkey': sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex(),
                           'signature': sk.sign(msg).hex()} for sk in keys]}

def coinbase(owner, value, height, tag=''):
    return {'kind': 'coinbase', 'height': height, 'tag': tag, 'outputs': [output(value, owner)]}

def merkle(txs):
    if not txs: raise ValueError('block must contain coinbase')
    layer = [bytes.fromhex(txid(tx)) for tx in txs]
    while len(layer) > 1:
        if len(layer) % 2: layer.append(layer[-1])
        layer = [sha(layer[i] + layer[i+1]) for i in range(0, len(layer), 2)]
    return layer[0].hex()

@dataclass
class Header:
    version: int
    previous: str
    merkle_root: str
    timestamp: int
    target: int
    nonce: int = 0
    def encode(self):
        if not (0 <= self.version < 2**32 and 0 <= self.timestamp < 2**64 and
                0 < self.target <= MAX_HASH and 0 <= self.nonce < 2**64):
            raise ValueError('header field out of range')
        if len(bytes.fromhex(self.previous)) != 32 or len(bytes.fromhex(self.merkle_root)) != 32:
            raise ValueError('invalid header hash length')
        return (struct.pack('<I', self.version) + bytes.fromhex(self.previous) +
                bytes.fromhex(self.merkle_root) + struct.pack('<Q', self.timestamp) +
                self.target.to_bytes(32, 'big') + struct.pack('<Q', self.nonce))
    def hash(self): return shahex(self.encode())
    def as_dict(self): return vars(self).copy()

@dataclass
class Block:
    header: Header
    transactions: list
    def hash(self): return self.header.hash()
    def as_dict(self): return {'hash': self.hash(), 'header': self.header.as_dict(), 'transactions': self.transactions}

def work(target): return (1 << 256) // (target + 1)

def mine(previous, transactions, target, timestamp=None, max_attempts=5_000_000):
    h = Header(1, previous, merkle(transactions), int(time.time()) if timestamp is None else timestamp, target)
    start = time.perf_counter()
    for nonce in range(max_attempts):
        h.nonce = nonce
        if int(h.hash(), 16) <= target:
            duration = time.perf_counter() - start
            return Block(h, transactions), {'attempts': nonce+1, 'seconds': duration, 'hashes_per_second': (nonce+1)/max(duration, 1e-12), 'expected_attempts': (1 << 256)/(target+1)}
    raise RuntimeError('nonce search exhausted')

class ValidationError(ValueError): pass

def require(condition, reason):
    if not condition: raise ValidationError(reason)

def valid_output(o):
    return (isinstance(o, dict) and type(o.get('value')) is int and
            0 <= o['value'] <= MAX_MONEY and isinstance(o.get('owner'), str) and
            len(o['owner']) == 64 and all(c in '0123456789abcdef' for c in o['owner']))

def apply_transactions(txs, utxos, height):
    """Copy-on-write validation; never modifies input state."""
    state = dict(utxos)
    require(bool(txs) and txs[0].get('kind') == 'coinbase', 'missing first coinbase')
    require(sum(tx.get('kind') == 'coinbase' for tx in txs) == 1, 'multiple coinbase transactions')
    cb = txs[0]
    require(type(cb.get('height')) is int and cb['height'] == height, 'incorrect coinbase height')
    require(isinstance(cb.get('tag'), str), 'invalid coinbase tag')
    require(isinstance(cb.get('outputs'), list) and len(cb['outputs']) == 1 and valid_output(cb['outputs'][0]), 'invalid coinbase output')
    fees = 0
    seen_txids = set()
    for tx in txs:
        ident = txid(tx)
        require(ident not in seen_txids, 'duplicate transaction ID in block')
        seen_txids.add(ident)
    for tx in txs[1:]:
        require(tx.get('kind') == 'spend', 'unexpected transaction kind')
        ins, outs, witnesses = tx.get('inputs'), tx.get('outputs'), tx.get('witnesses')
        require(isinstance(ins, list) and bool(ins), 'transaction has no inputs')
        require(isinstance(outs, list) and bool(outs) and all(valid_output(o) for o in outs), 'invalid transaction output')
        require(isinstance(witnesses, list) and len(witnesses) == len(ins), 'witness count mismatch')
        seen = set(); total_in = 0; total_out = 0
        msg = spend_message(ins, outs)
        for inp, witness in zip(ins, witnesses):
            require(isinstance(inp, dict) and isinstance(inp.get('txid'), str) and type(inp.get('index')) is int and inp['index'] >= 0, 'malformed outpoint')
            op = f"{inp['txid']}:{inp['index']}"
            require(op not in seen, 'duplicate input outpoint')
            seen.add(op)
            require(op in state, 'missing or already spent input: ' + op)
            prev = state[op]
            try:
                pub = bytes.fromhex(witness['pubkey']); sig = bytes.fromhex(witness['signature'])
                require(address(witness['pubkey']) == prev['owner'], 'wrong public key for input')
                Ed25519PublicKey.from_public_bytes(pub).verify(sig, msg)
            except (KeyError, TypeError, ValueError) as exc:
                if isinstance(exc, ValidationError): raise
                raise ValidationError('malformed signature or public key') from exc
            except Exception as exc:
                raise ValidationError('invalid signature') from exc
            total_in += prev['value']
            require(total_in <= MAX_MONEY, 'input sum overflow')
        for o in outs:
            total_out += o['value']
            require(total_out <= MAX_MONEY, 'output sum overflow')
        require(total_in >= total_out, 'outputs exceed inputs')
        fees += total_in - total_out
        require(fees <= MAX_MONEY, 'fee sum overflow')
        for inp in ins: del state[f"{inp['txid']}:{inp['index']}"]
        ident = txid(tx)
        for i, o in enumerate(outs):
            op = f'{ident}:{i}'
            require(op not in state, 'duplicate output outpoint')
            state[op] = o.copy()
    require(cb['outputs'][0]['value'] <= SUBSIDY + fees, 'excess coinbase value')
    require(SUBSIDY + fees <= MAX_MONEY, 'coinbase allowance overflow')
    ident = txid(cb)
    for i, o in enumerate(cb['outputs']):
        op = f'{ident}:{i}'
        require(op not in state, 'duplicate coinbase outpoint')
        state[op] = o.copy()
    return state, fees

@dataclass
class ChainRecord:
    block: Block
    parent: Optional[str]
    height: int
    total_work: int
    state: dict = field(default_factory=dict)

class Node:
    def __init__(self, max_target=MAX_HASH):
        self.max_target = max_target
        self.records = {}
        self.tip = None
        self.events = []
    def utxos(self): return dict(self.records[self.tip].state) if self.tip else {}
    def path(self, tip=None):
        cursor = self.tip if tip is None else tip
        result = []
        while cursor:
            result.append(cursor)
            cursor = self.records[cursor].parent
        return list(reversed(result))
    def add(self, block):
        """Validate entire branch before storing; invalid blocks change nothing."""
        h = block.header
        require(h.version == 1, 'unsupported block version')
        require(type(h.timestamp) is int and h.timestamp >= 0, 'invalid timestamp')
        require(type(h.target) is int and 0 < h.target <= self.max_target, 'target exceeds permitted limit')
        require(type(h.nonce) is int and 0 <= h.nonce < 2**64, 'invalid nonce')
        try: digest = h.hash()
        except (ValueError, TypeError, OverflowError) as exc: raise ValidationError('malformed header') from exc
        require(bool(block.transactions), 'incorrect Merkle root: empty transactions')
        require(h.merkle_root == merkle(block.transactions), 'incorrect Merkle root')
        require(int(digest, 16) <= h.target, 'invalid proof of work')
        require(digest not in self.records, 'duplicate block')
        if h.previous == ZERO:
            parent = None; height = 0; prev_state = {}; total_work = 0
            require(not any(r.parent is None for r in self.records.values()), 'second genesis block not permitted')
        else:
            require(h.previous in self.records, 'unknown parent block')
            parent = h.previous
            ancestor = self.records[parent]
            height = ancestor.height + 1
            prev_state = ancestor.state
            total_work = ancestor.total_work
            require(h.timestamp >= ancestor.block.header.timestamp, 'timestamp before parent')
        state, fees = apply_transactions(block.transactions, prev_state, height)
        record = ChainRecord(block, parent, height, total_work + work(h.target), state)
        old = self.tip
        self.records[digest] = record
        if old is None or record.total_work > self.records[old].total_work:
            self.tip = digest
            if old is not None and parent != old:
                old_path, new_path = self.path(old), self.path(digest)
                common = 0
                while common < min(len(old_path), len(new_path)) and old_path[common] == new_path[common]: common += 1
                self.events.append({'type': 'reorg', 'disconnect': old_path[common:], 'connect': new_path[common:], 'old_tip': old, 'new_tip': digest})
            else: self.events.append({'type': 'extend', 'tip': digest})
        else: self.events.append({'type': 'side_branch', 'hash': digest})
        return {'hash': digest, 'height': height, 'fees': fees, 'cumulative_work': record.total_work, 'active': self.tip == digest}

def save_json(path, data):
    from pathlib import Path
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')

def snapshot(node):
    return {'tip': node.tip, 'height': node.records[node.tip].height if node.tip else -1,
            'cumulative_work': node.records[node.tip].total_work if node.tip else 0,
            'active_chain': node.path(), 'utxos': node.utxos()}
