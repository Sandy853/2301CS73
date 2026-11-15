"""Educational in-memory UTXO ledger (not production cryptocurrency software)."""
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

MAX_VALUE = (1 << 63) - 1


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pkh(public_key_hex):
    try:
        raw = bytes.fromhex(public_key_hex)
        if len(raw) != 32:
            raise ValueError()
    except ValueError:
        raise ValidationError('invalid public key encoding')
    return digest(raw)


class ValidationError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class Outpoint:
    txid: str
    index: int

    def key(self):
        return f'{self.txid}:{self.index}'


@dataclass(frozen=True)
class Output:
    value: int
    lock: str  # SHA-256 of 32-byte Ed25519 public key

    def to_dict(self):
        return {'value': self.value, 'lock': self.lock}


@dataclass
class Input:
    txid: str
    index: int
    pubkey: str = ''
    signature: str = ''

    def outpoint(self):
        return Outpoint(self.txid, self.index)

    def to_dict(self):
        return vars(self).copy()


@dataclass
class Transaction:
    inputs: List[Input]
    outputs: List[Output]
    version: int = 1

    def unsigned_dict(self):
        return {'version': self.version, 'inputs': [{'txid': i.txid, 'index': i.index} for i in self.inputs],
                'outputs': [o.to_dict() for o in self.outputs]}

    def to_dict(self):
        return {'version': self.version, 'inputs': [i.to_dict() for i in self.inputs],
                'outputs': [o.to_dict() for o in self.outputs]}

    def signing_bytes(self):
        return canonical(self.unsigned_dict())

    def txid(self):
        return digest(canonical(self.to_dict()))


class Wallet:
    def __init__(self, private_key=None):
        self.private_key = private_key or Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw).hex()
        self.address = pkh(self.public_key)

    def sign(self, tx):
        for i in tx.inputs:
            i.pubkey = self.public_key
            i.signature = self.private_key.sign(tx.signing_bytes()).hex()
        return tx


def check_value(value, label):
    if type(value) is not int or value < 0 or value > MAX_VALUE:
        raise ValidationError(f'{label}: value must be integer between 0 and {MAX_VALUE}')


def check_lock(lock):
    if not isinstance(lock, str) or len(lock) != 64:
        raise ValidationError('invalid locking condition')
    try:
        bytes.fromhex(lock)
    except ValueError:
        raise ValidationError('invalid locking condition')


class Ledger:
    def __init__(self):
        self.utxos = {}  # Outpoint -> Output

    def fund_for_demo(self, wallet, values, label='genesis'):
        """Trusted test-only funding; never used by transaction validator."""
        for n, value in enumerate(values):
            check_value(value, 'funding')
            if value == 0:
                raise ValidationError('funding must be positive')
            op = Outpoint(digest(canonical({'demo_funding': label, 'index': n, 'address': wallet.address})), 0)
            if op in self.utxos:
                raise ValidationError('duplicate demo funding')
            self.utxos[op] = Output(value, wallet.address)

    def snapshot(self):
        return {'utxos': [{'txid': op.txid, 'index': op.index, **out.to_dict()}
                          for op, out in sorted(self.utxos.items())]}

    def save(self, path):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + '.tmp')
        tmp.write_bytes(canonical(self.snapshot()) + b'\n')
        os.replace(tmp, target)

    @classmethod
    def load(cls, path):
        obj = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(obj, dict) or set(obj) != {'utxos'} or not isinstance(obj['utxos'], list):
            raise ValidationError('invalid snapshot structure')
        ledger = cls()
        for entry in obj['utxos']:
            if set(entry) != {'txid', 'index', 'value', 'lock'}:
                raise ValidationError('invalid snapshot entry')
            op = Outpoint(entry['txid'], entry['index'])
            if not isinstance(op.txid, str) or len(op.txid) != 64 or type(op.index) is not int or op.index < 0:
                raise ValidationError('invalid snapshot outpoint')
            try:
                bytes.fromhex(op.txid)
            except ValueError:
                raise ValidationError('invalid snapshot outpoint')
            check_value(entry['value'], 'snapshot')
            check_lock(entry['lock'])
            if op in ledger.utxos:
                raise ValidationError('duplicate snapshot outpoint')
            ledger.utxos[op] = Output(entry['value'], entry['lock'])
        return ledger

    def validate(self, tx):
        if type(tx.version) is not int or tx.version != 1:
            raise ValidationError('unsupported transaction version')
        if not tx.inputs:
            raise ValidationError('transaction has no inputs')
        if not tx.outputs:
            raise ValidationError('transaction has no outputs')
        seen = set()
        total_in = 0
        for i in tx.inputs:
            op = i.outpoint()
            if type(i.index) is not int or i.index < 0 or not isinstance(i.txid, str):
                raise ValidationError('invalid input outpoint')
            if op in seen:
                raise ValidationError(f'duplicate input outpoint: {op.key()}')
            seen.add(op)
            if op not in self.utxos:
                raise ValidationError(f'nonexistent or already spent input: {op.key()}')
            prev = self.utxos[op]
            if pkh(i.pubkey) != prev.lock:
                raise ValidationError(f'public key does not satisfy lock: {op.key()}')
            try:
                sig = bytes.fromhex(i.signature)
                Ed25519PublicKey.from_public_bytes(bytes.fromhex(i.pubkey)).verify(sig, tx.signing_bytes())
            except (ValueError, TypeError):
                raise ValidationError(f'invalid signature encoding: {op.key()}')
            except Exception:
                raise ValidationError(f'bad signature: {op.key()}')
            if total_in > MAX_VALUE - prev.value:
                raise ValidationError('input sum overflow')
            total_in += prev.value
        total_out = 0
        for n, o in enumerate(tx.outputs):
            check_value(o.value, f'output {n}')
            if o.value == 0:
                raise ValidationError(f'output {n}: zero value not allowed')
            check_lock(o.lock)
            if total_out > MAX_VALUE - o.value:
                raise ValidationError('output sum overflow')
            total_out += o.value
        if total_out > total_in:
            raise ValidationError(f'creates value: inputs={total_in}, outputs={total_out}')
        return total_in - total_out

    def apply(self, tx):
        fee = self.validate(tx)  # no state mutations until every check passes
        new_set = self.utxos.copy()
        for i in tx.inputs:
            del new_set[i.outpoint()]
        txid = tx.txid()
        for n, out in enumerate(tx.outputs):
            op = Outpoint(txid, n)
            if op in new_set:
                raise ValidationError('transaction ID collision')
            new_set[op] = out
        self.utxos = new_set  # atomic in-memory replacement
        return fee


def build_payment(ledger, sender, recipient_address, amount, fee):
    """Deterministic largest-first selection, tie-break by txid and index."""
    check_value(amount, 'amount')
    check_value(fee, 'fee')
    if amount == 0:
        raise ValidationError('amount must be positive')
    check_lock(recipient_address)
    if amount > MAX_VALUE - fee:
        raise ValidationError('amount plus fee overflow')
    target = amount + fee
    candidates = sorted(((op, out) for op, out in ledger.utxos.items() if out.lock == sender.address),
                        key=lambda pair: (-pair[1].value, pair[0].txid, pair[0].index))
    selected, total = [], 0
    for op, out in candidates:
        if total > MAX_VALUE - out.value:
            raise ValidationError('selected input sum overflow')
        selected.append(op)
        total += out.value
        if total >= target:
            break
    if total < target:
        raise ValidationError(f'insufficient funds: need={target}, available={total}')
    outputs = [Output(amount, recipient_address)]
    change = total - target
    if change:
        outputs.append(Output(change, sender.address))
    return sender.sign(Transaction([Input(op.txid, op.index) for op in selected], outputs))
