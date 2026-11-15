"""Generate reproducible PUBLIC deliverables and print them. No private keys are stored."""
import copy
import json
import subprocess
import sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from wallet import address_from_public, public_bytes, private_bytes, memo_hash, canonical_bytes, sign_transaction, verify_envelope

OUT=Path(__file__).resolve().parent/'deliverables'
OUT.mkdir(exist_ok=True)

def save(name,value):
    path=OUT/name
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('\n===',name,'===\n',path.read_text())

def main():
    # Fixed seeds ONLY for publicly reproducible test vectors, never real keys.
    alice=Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    bob=Ed25519PrivateKey.from_private_bytes(bytes(range(1,33)))
    sender=address_from_public(public_bytes(alice))
    recipient=address_from_public(public_bytes(bob))
    tx={'version':1,'network_id':'course-testnet','sender':sender,'recipient':recipient,'amount_units':1250000,'nonce':7,'memo_hash':memo_hash('class demo')}
    signed=sign_transaction(tx,private_bytes(alice).hex())
    save('public_keys.json',{'WARNING':'PUBLIC TEST VECTORS ONLY - DETERMINISTIC TEST KEYS ARE NOT SECRET','sender_public_key':public_bytes(alice).hex(),'recipient_public_key':public_bytes(bob).hex()})
    save('addresses.json',{'sender':sender,'recipient':recipient,'address_version_hex':'6f'})
    save('transaction.json',tx)
    save('signed_transaction.json',signed)
    save('canonical_bytes.json',{'encoding':'hex','canonical_transaction_bytes':canonical_bytes(tx).hex(),'length_bytes':len(canonical_bytes(tx))})
    save('verification.json',{'valid':verify_envelope(signed)})
    seen=set();verify_envelope(signed,seen)
    checks={}
    for label,field,newvalue in [('changed_amount','amount_units',1250001),('wrong_network','network_id','othernet'),('changed_nonce','nonce',8)]:
        modified=copy.deepcopy(signed);modified['transaction'][field]=newvalue
        try: verify_envelope(modified);checks[label]='ERROR: accepted'
        except ValueError as exc:checks[label]='REJECTED: '+str(exc)
    try:verify_envelope(signed,seen);checks['replayed_nonce']='ERROR: accepted'
    except ValueError as exc:checks['replayed_nonce']='REJECTED: '+str(exc)
    save('negative_checks.json',checks)
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=OUT.parent,capture_output=True,text=True)
    report={'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
    save('test_report.json',report)
    summary='Keys, Addresses, and Signed Transactions\n\nSender: '+sender+'\nRecipient: '+recipient+'\nCanonical bytes: '+canonical_bytes(tx).hex()+'\nSignature: '+signed['signature']+'\nVerified: true\n\n'+result.stdout+result.stderr
    (OUT/'run_output.txt').write_text(summary,encoding='utf-8')
    print('\n=== run_output.txt ===\n'+summary)
    if result.returncode: raise SystemExit(result.returncode)

if __name__=='__main__':main()
