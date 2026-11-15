"""CLI: keygen, address, sign, verify. Run python cli.py --help."""
import argparse
import json
import os
import tempfile
from pathlib import Path
from wallet import (generate_keypair, address_from_public, exact_hex, sign_transaction,
                    verify_envelope, validate_address, canonical_bytes)


def load(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,obj):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n',encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description='Educational wallet - testnet only, never real funds')
    sub=p.add_subparsers(dest='command',required=True)
    k=sub.add_parser('keygen'); k.add_argument('--public-out',default='public.json'); k.add_argument('--dev-private-out',help='TEST ONLY: unencrypted private key; chmod 600 on POSIX')
    a=sub.add_parser('address'); a.add_argument('--public',required=True)
    s=sub.add_parser('sign'); s.add_argument('--transaction',required=True); s.add_argument('--dev-private',required=True); s.add_argument('--output',default='signed_transaction.json')
    v=sub.add_parser('verify'); v.add_argument('--signed',required=True); v.add_argument('--public',help='Optional independent public-key file to match'); v.add_argument('--nonce-db',help='State file; required for cross-run replay detection'); v.add_argument('--output',default='verification.json')
    args=p.parse_args()
    try:
        if args.command=='keygen':
            if args.dev_private_out and Path(args.public_out).resolve()==Path(args.dev_private_out).resolve(): raise ValueError('public/private paths must differ')
            if Path(args.public_out).exists(): raise ValueError('public output exists; refusing overwrite')
            result=generate_keypair(args.public_out,args.dev_private_out)
            print('TEST ONLY: private key is unencrypted; do not use real funds.' if args.dev_private_out else 'Public key exported; private key not saved.')
            print(json.dumps(result,indent=2))
        elif args.command=='address':
            pub=exact_hex(load(args.public)['public_key'],32,'public_key')
            print(address_from_public(pub))
        elif args.command=='sign':
            private=load(args.dev_private)['private_key']
            result=sign_transaction(load(args.transaction),private)
            save(args.output,result); print(json.dumps(result,indent=2))
            print('Canonical signed bytes (hex):',canonical_bytes(result['transaction']).hex())
        elif args.command=='verify':
            env=load(args.signed)
            if args.public and env['public_key']!=load(args.public)['public_key']: raise ValueError('submitted public key does not match')
            used=set()
            if args.nonce_db:
                dbpath=Path(args.nonce_db)
                if dbpath.exists():
                    raw=load(dbpath)
                    if not isinstance(raw,list) or any(not isinstance(x,list) or len(x)!=3 for x in raw): raise ValueError('malformed nonce DB')
                    used={tuple(x) for x in raw}
            verify_envelope(env,used if args.nonce_db else None)
            if args.nonce_db:
                # Simple sequential-use demo; not safe for concurrent verification processes.
                save(args.nonce_db,[list(x) for x in sorted(used)])
            result={'valid':True,'network_id':env['transaction']['network_id'],'nonce':env['transaction']['nonce']}
            save(args.output,result); print(json.dumps(result,indent=2))
    except (ValueError,KeyError,TypeError,OSError,json.JSONDecodeError) as exc:
        if args.command=='verify':
            result={'valid':False,'reason':str(exc)}
            save(args.output,result)
            print(json.dumps(result,indent=2))
        else: print('ERROR:',str(exc))
        raise SystemExit(1)

if __name__=='__main__': main()
