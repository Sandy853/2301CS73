import copy
import json
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from wallet import (address_from_public, public_bytes, private_bytes, memo_hash,
                    canonical_bytes, sign_transaction, verify_envelope, validate_address)

class WalletTests(unittest.TestCase):
    def setUp(self):
        self.key=Ed25519PrivateKey.from_private_bytes(bytes(range(32))) # deterministic test vector ONLY
        self.other=Ed25519PrivateKey.from_private_bytes(bytes(range(1,33)))
        self.sender=address_from_public(public_bytes(self.key))
        self.recipient=address_from_public(public_bytes(self.other))
        self.tx={'version':1,'network_id':'course-testnet','sender':self.sender,'recipient':self.recipient,'amount_units':1250000,'nonce':7,'memo_hash':memo_hash('class demo')}
        self.env=sign_transaction(self.tx,private_bytes(self.key).hex())

    def test_valid_signature(self): self.assertTrue(verify_envelope(self.env))
    def test_canonical_order_and_whitespace(self):
        a=json.loads(json.dumps(self.tx,indent=4))
        b=json.loads(json.dumps(dict(reversed(list(self.tx.items()))),separators=(',',':')))
        self.assertEqual(canonical_bytes(a),canonical_bytes(b))
    def test_changed_fields(self):
        modifications={'version':2,'network_id':'othernet','sender':self.recipient,'recipient':self.sender,'amount_units':1250001,'nonce':8,'memo_hash':memo_hash('tampered')}
        for field,value in modifications.items():
            with self.subTest(field=field):
                env=copy.deepcopy(self.env);env['transaction'][field]=value
                with self.assertRaises(ValueError):verify_envelope(env)
    def test_wrong_signer(self):
        with self.assertRaises(ValueError):sign_transaction(self.tx,private_bytes(self.other).hex())
        env=copy.deepcopy(self.env);env['public_key']=public_bytes(self.other).hex()
        with self.assertRaises(ValueError):verify_envelope(env)
    def test_replay_nonce(self):
        seen=set();verify_envelope(self.env,seen)
        with self.assertRaisesRegex(ValueError,'replayed'):verify_envelope(self.env,seen)
    def test_bad_checksum_and_base58(self):
        with self.assertRaises(ValueError):validate_address(self.sender[:-1]+('1' if self.sender[-1]!='1' else '2'))
        with self.assertRaises(ValueError):validate_address('0OIl')
    def test_noncanonical_signature(self):
        for bad in (self.env['signature'].upper(),self.env['signature'][:-2],self.env['signature']+'00','zz'*64):
            env=copy.deepcopy(self.env);env['signature']=bad
            with self.assertRaises(ValueError):verify_envelope(env)
    def test_extra_fields_and_bad_integer(self):
        for key,value in [('extra',1),('amount_units',1.5),('nonce',True),('amount_units',-1)]:
            tx=dict(self.tx);tx[key]=value
            with self.assertRaises(ValueError):canonical_bytes(tx)

if __name__=='__main__':unittest.main()
