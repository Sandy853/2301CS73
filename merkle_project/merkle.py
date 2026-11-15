"""Domain-separated SHA-256 Merkle tree with duplicate-last odd-node policy."""
from __future__ import annotations
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
EMPTY_ROOT = hashlib.sha256(b'\x02').digest()


def leaf_hash(data: bytes) -> bytes:
    if not isinstance(data, bytes):
        raise TypeError('leaf must be bytes')
    return hashlib.sha256(b'\x00' + data).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    if len(left) != 32 or len(right) != 32:
        raise ValueError('node children must be 32-byte hashes')
    return hashlib.sha256(b'\x01' + left + right).digest()


def _levels(leaves: list[bytes]) -> list[list[bytes]]:
    if not leaves:
        return []
    levels = [[leaf_hash(leaf) for leaf in leaves]]
    while len(levels[-1]) > 1:
        current = levels[-1]
        levels.append([node_hash(current[i], current[i + 1] if i + 1 < len(current) else current[i])
                       for i in range(0, len(current), 2)])
    return levels


def root(leaves: list[bytes]) -> str:
    levels = _levels(leaves)
    return (levels[-1][0] if levels else EMPTY_ROOT).hex()


def _height(n: int) -> int:
    height = 0
    while n > 1:
        n = (n + 1) // 2
        height += 1
    return height


def prove(leaves: list[bytes], index: int) -> dict[str, Any]:
    if type(index) is not int or not 0 <= index < len(leaves):
        raise ValueError('leaf index out of range')
    levels = _levels(leaves)
    siblings = []
    pos = index
    for level in levels[:-1]:
        sibling_pos = pos ^ 1
        if sibling_pos >= len(level):
            sibling_pos = pos
        siblings.append({'side': 'left' if pos % 2 else 'right', 'hash': level[sibling_pos].hex()})
        pos //= 2
    return {'leaf_index': index, 'tree_size': len(leaves), 'siblings': siblings}


def _parse_hash(value: Any) -> bytes:
    if not isinstance(value, str) or HASH_RE.fullmatch(value) is None:
        raise ValueError('hash must be exactly 64 lowercase hexadecimal characters')
    return bytes.fromhex(value)


def verify(leaf: bytes, proof: dict[str, Any], expected_root: str) -> bool:
    """Reject malformed/noncanonical proofs with ValueError; return False for wrong roots."""
    if not isinstance(leaf, bytes):
        raise TypeError('leaf must be bytes')
    expected = _parse_hash(expected_root)
    if not isinstance(proof, dict) or set(proof) != {'leaf_index', 'tree_size', 'siblings'}:
        raise ValueError('invalid proof fields')
    index, size, siblings = proof['leaf_index'], proof['tree_size'], proof['siblings']
    if type(size) is not int or size < 1 or type(index) is not int or not 0 <= index < size:
        raise ValueError('invalid tree size or leaf index')
    if not isinstance(siblings, list) or len(siblings) != _height(size):
        raise ValueError('incorrect proof length')
    h = leaf_hash(leaf)
    pos, width = index, size
    for entry in siblings:
        if not isinstance(entry, dict) or set(entry) != {'side', 'hash'}:
            raise ValueError('invalid sibling fields')
        side = entry['side']
        if side not in ('left', 'right') or not isinstance(side, str):
            raise ValueError('invalid sibling direction')
        sibling = _parse_hash(entry['hash'])
        required_side = 'left' if pos % 2 else 'right'
        if side != required_side:
            raise ValueError('incorrect sibling direction for index')
        if pos % 2 == 0 and pos + 1 == width and sibling != h:
            raise ValueError('odd-node duplicate must equal current hash')
        h = node_hash(sibling, h) if side == 'left' else node_hash(h, sibling)
        pos //= 2
        width = (width + 1) // 2
    return h == expected


def proof_json(proof: dict[str, Any]) -> str:
    return json.dumps(proof, indent=2)
