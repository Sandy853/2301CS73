"""Command line interface for Merkle roots, inclusion proofs and verification."""
import argparse
import json
import sys
from pathlib import Path
from merkle import root, prove, verify, proof_json


def read_leaves(path: str) -> list[bytes]:
    # UTF-8 file, one transaction per line; blank lines are valid empty transactions.
    # splitlines() avoids creating an extra transaction for the final newline.
    return [line.encode('utf-8') for line in Path(path).read_text(encoding='utf-8').splitlines()]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='SHA-256 Merkle tree CLI')
    commands = parser.add_subparsers(dest='command', required=True)
    p_root = commands.add_parser('root', help='Calculate Merkle root')
    p_root.add_argument('--input', required=True, help='UTF-8 transactions file (one per line)')
    p_root.add_argument('--output', help='Save root JSON to this file')
    p_prove = commands.add_parser('prove', help='Generate proof for transaction index')
    p_prove.add_argument('--input', required=True)
    p_prove.add_argument('--index', required=True, type=int)
    p_prove.add_argument('--output', help='Save proof JSON to this file')
    p_verify = commands.add_parser('verify', help='Verify a proof against a root')
    p_verify.add_argument('--leaf', required=True, help='Exact UTF-8 transaction text')
    p_verify.add_argument('--proof', required=True, help='Proof JSON file')
    p_verify.add_argument('--root', required=True, help='Expected 64-char lowercase hex root')
    p_verify.add_argument('--output', help='Save verification result JSON')
    args = parser.parse_args(argv)
    try:
        if args.command == 'root':
            leaves = read_leaves(args.input)
            result = {'tree_size': len(leaves), 'root': root(leaves)}
            rendered = json.dumps(result, indent=2)
        elif args.command == 'prove':
            leaves = read_leaves(args.input)
            rendered = proof_json(prove(leaves, args.index))
        else:
            proof = json.loads(Path(args.proof).read_text(encoding='utf-8'))
            valid = verify(args.leaf.encode('utf-8'), proof, args.root)
            rendered = json.dumps({'valid': valid}, indent=2)
        print(rendered)
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(rendered + '\n', encoding='utf-8')
            print(f'Saved: {args.output}', file=sys.stderr)
        return 0 if args.command != 'verify' or valid else 1
    except (ValueError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
