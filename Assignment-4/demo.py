"""Run with: python demo.py. Writes required sample deliverables to artifacts/."""
import json
from pathlib import Path
from ledger import Ledger, Wallet, build_payment, ValidationError, canonical


def main():
    folder = Path('artifacts')
    folder.mkdir(exist_ok=True)
    alice, bob, mallory = Wallet(), Wallet(), Wallet()
    ledger = Ledger()
    ledger.fund_for_demo(alice, [40, 70], 'alice-start')
    before = ledger.snapshot()
    ledger.save(folder / 'ledger_before.json')
    trace = []

    def attempt(name, tx):
        old = ledger.snapshot()
        try:
            fee = ledger.apply(tx)
            event = {'case': name, 'status': 'ACCEPTED', 'txid': tx.txid(), 'fee': fee}
        except ValidationError as exc:
            event = {'case': name, 'status': 'REJECTED', 'reason': str(exc),
                     'state_unchanged': ledger.snapshot() == old}
        trace.append(event)
        print(json.dumps(event, sort_keys=True))

    payment = build_payment(ledger, alice, bob.address, 85, 2)
    (folder / 'signed_payment.json').write_bytes(canonical(payment.to_dict()) + b'\n')
    attempt('Alice pays Bob 85, fee 2, change 23', payment)
    ledger.save(folder / 'ledger_after.json')
    attempt('replay same signed transaction', payment)
    attempt('nonexistent input', build_nonexistent(alice, bob))
    bad = build_payment(ledger, bob, alice.address, 10, 1)
    bad.inputs[0].signature = '00' * 64
    attempt('bad signature', bad)
    (folder / 'trace.json').write_text(json.dumps(trace, indent=2) + '\n', encoding='utf-8')
    reloaded = Ledger.load(folder / 'ledger_after.json')
    assert reloaded.snapshot() == ledger.snapshot()
    assert len(before['utxos']) == 2
    assert sorted(x['value'] for x in ledger.snapshot()['utxos']) == [23, 85]
    print('Snapshot reload: identical; artifacts written to', folder.resolve())


def build_nonexistent(alice, bob):
    from ledger import Input, Output, Transaction
    return alice.sign(Transaction([Input('f' * 64, 0)], [Output(1, bob.address)]))


if __name__ == '__main__':
    main()
