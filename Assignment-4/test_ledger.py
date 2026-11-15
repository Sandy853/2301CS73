import copy
import json
import tempfile
import unittest
from pathlib import Path
from ledger import (Ledger, Wallet, Transaction, Input, Output, Outpoint, ValidationError,
                    build_payment, canonical, MAX_VALUE)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b, self.c = Wallet(), Wallet(), Wallet()
        self.ledger = Ledger()
        self.ledger.fund_for_demo(self.a, [40, 70], 'initial')

    def payment(self, amount=85, fee=2):
        return build_payment(self.ledger, self.a, self.b.address, amount, fee)

    def rejects(self, tx, reason):
        old = copy.deepcopy(self.ledger.snapshot())
        with self.assertRaisesRegex(ValidationError, reason):
            self.ledger.apply(tx)
        self.assertEqual(self.ledger.snapshot(), old)

    def test_01_initial_funding(self):
        self.assertEqual(sorted(o.value for o in self.ledger.utxos.values()), [40, 70])

    def test_02_valid_payment_fee(self):
        self.assertEqual(self.ledger.apply(self.payment()), 2)

    def test_03_correct_change(self):
        tx = self.payment()
        self.assertEqual([(o.value, o.lock) for o in tx.outputs], [(85, self.b.address), (23, self.a.address)])

    def test_04_replay_rejected(self):
        tx = self.payment()
        self.ledger.apply(tx)
        self.rejects(tx, 'already spent')

    def test_05_nonexistent_input(self):
        tx = self.payment()
        tx.inputs[0].txid = 'f' * 64
        self.rejects(tx, 'nonexistent')

    def test_06_duplicate_input(self):
        tx = self.payment()
        tx.inputs.append(copy.deepcopy(tx.inputs[0]))
        self.rejects(self.a.sign(tx), 'duplicate input')

    def test_07_bad_signature(self):
        tx = self.payment()
        tx.inputs[0].signature = '00' * 64
        self.rejects(tx, 'bad signature')

    def test_08_wrong_public_key(self):
        tx = self.payment()
        tx.inputs[0].pubkey = self.c.public_key
        self.rejects(tx, 'does not satisfy lock')

    def test_09_tampered_amount(self):
        tx = self.payment()
        tx.outputs[0] = Output(84, self.b.address)
        self.rejects(tx, 'bad signature')

    def test_10_negative_output(self):
        tx = self.payment()
        tx.outputs[0] = Output(-1, self.b.address)
        self.rejects(tx, 'bad signature')

    def test_11_negative_output_resigned(self):
        tx = self.payment()
        tx.outputs[0] = Output(-1, self.b.address)
        self.rejects(self.a.sign(tx), 'value must be integer')

    def test_12_overflow_output(self):
        tx = self.payment()
        tx.outputs[0] = Output(MAX_VALUE + 1, self.b.address)
        self.rejects(self.a.sign(tx), 'value must be integer')

    def test_13_excessive_creation(self):
        tx = self.payment()
        tx.outputs[0] = Output(110, self.b.address)
        self.rejects(self.a.sign(tx), 'creates value')

    def test_14_bad_change_creates_value(self):
        tx = self.payment()
        tx.outputs[1] = Output(26, self.a.address)
        self.rejects(self.a.sign(tx), 'creates value')

    def test_15_bad_change_reduces_fee_incorrectly(self):
        tx = self.payment()
        tx.outputs[1] = Output(22, self.a.address)
        self.assertEqual(self.ledger.validate(self.a.sign(tx)), 3)
        self.assertNotEqual(self.ledger.validate(tx), 2)

    def test_16_insufficient_funds(self):
        with self.assertRaisesRegex(ValidationError, 'insufficient funds'):
            self.payment(200, 2)

    def test_17_no_inputs(self):
        self.rejects(Transaction([], [Output(1, self.b.address)]), 'no inputs')

    def test_18_no_outputs(self):
        tx = self.payment()
        tx.outputs = []
        self.rejects(tx, 'no outputs')

    def test_19_unsupported_version(self):
        tx = self.payment()
        tx.version = 2
        self.rejects(tx, 'unsupported')

    def test_20_zero_output(self):
        tx = self.payment()
        tx.outputs[0] = Output(0, self.b.address)
        self.rejects(self.a.sign(tx), 'zero value')

    def test_21_invalid_lock(self):
        tx = self.payment()
        tx.outputs[0] = Output(85, 'not-a-lock')
        self.rejects(self.a.sign(tx), 'invalid locking')

    def test_22_deterministic_selection(self):
        tx = self.payment()
        values = [self.ledger.utxos[i.outpoint()].value for i in tx.inputs]
        self.assertEqual(values, [70, 40])
        self.assertEqual(tx.to_dict(), self.payment().to_dict())

    def test_23_exact_amount_no_change(self):
        tx = self.payment(68, 2)
        self.assertEqual(len(tx.outputs), 1)
        self.assertEqual(len(tx.inputs), 1)

    def test_24_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'snapshot.json'
            self.ledger.save(path)
            self.assertEqual(self.ledger.snapshot(), Ledger.load(path).snapshot())

    def test_25_save_load_after_payment(self):
        self.ledger.apply(self.payment())
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'snapshot.json'
            self.ledger.save(path)
            self.assertEqual(self.ledger.snapshot(), Ledger.load(path).snapshot())

    def test_26_duplicate_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'snapshot.json'
            obj = self.ledger.snapshot()
            obj['utxos'].append(obj['utxos'][0])
            path.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValidationError, 'duplicate snapshot'):
                Ledger.load(path)

    def test_27_transaction_id_changes_on_signature(self):
        tx = self.payment()
        first = tx.txid()
        tx.inputs[0].signature = '00' * 64
        self.assertNotEqual(first, tx.txid())

    def test_28_overflow_sum(self):
        self.ledger = Ledger()
        self.ledger.fund_for_demo(self.a, [MAX_VALUE, 1], 'large')
        tx = build_payment(self.ledger, self.a, self.b.address, MAX_VALUE - 1, 1)
        # force both inputs to test sum overflow
        extra = next(op for op in self.ledger.utxos if op != tx.inputs[0].outpoint())
        tx.inputs.append(Input(extra.txid, extra.index))
        self.rejects(self.a.sign(tx), 'input sum overflow')

    def test_29_output_sum_overflow(self):
        tx = self.payment()
        tx.outputs = [Output(MAX_VALUE, self.b.address), Output(1, self.a.address)]
        self.rejects(self.a.sign(tx), 'output sum overflow')

    def test_30_invalid_signature_encoding(self):
        tx = self.payment()
        tx.inputs[0].signature = 'xx'
        self.rejects(tx, 'invalid signature encoding')

    def test_31_zero_amount_builder(self):
        with self.assertRaisesRegex(ValidationError, 'amount must be positive'):
            self.payment(0, 1)

    def test_32_builder_overflow(self):
        with self.assertRaisesRegex(ValidationError, 'amount plus fee overflow'):
            self.payment(MAX_VALUE, 1)

    def test_33_atomic_reject_after_valid_input(self):
        tx = self.payment()
        tx.inputs[-1].signature = '00' * 64
        self.rejects(tx, 'bad signature')

    def test_34_canonical_order(self):
        self.assertEqual(canonical({'b': 2, 'a': 1}), b'{"a":1,"b":2}')


if __name__ == '__main__':
    unittest.main()
