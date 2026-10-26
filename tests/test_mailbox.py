import threading

import pytest

from agora.ledger.types import LedgerError


def test_broadcast_delivered_once_per_peer(ledger):
    ledger.mail.register(["P01", "P02", "P03"])
    ledger.mail.send("P01", None, "interfaces agreed", urgent=False)
    assert [m.text for m in ledger.mail.take("P02", urgent_only=False)] == ["interfaces agreed"]
    assert ledger.mail.take("P02", urgent_only=False) == []
    assert ledger.mail.take("P01", urgent_only=False) == []
    assert [m.text for m in ledger.mail.take("P03", urgent_only=False)] == ["interfaces agreed"]


def test_urgent_only_filter(ledger):
    ledger.mail.register(["P01", "P02"])
    ledger.mail.send("P01", "P02", "later", urgent=False)
    ledger.mail.send("P01", "P02", "now", urgent=True)
    assert [m.text for m in ledger.mail.take("P02", urgent_only=True)] == ["now"]
    assert [m.text for m in ledger.mail.take("P02", urgent_only=False)] == ["later"]


def test_dm_delivered_to_recipient_only(ledger):
    ledger.mail.register(["P01", "P02", "P03"])
    m = ledger.mail.send("P01", "P02", "psst", urgent=False)
    assert m.recipient == "P02" and m.sender == "P01" and m.urgent is False
    assert ledger.mail.take("P03", urgent_only=False) == []
    assert [x.text for x in ledger.mail.take("P02", urgent_only=False)] == ["psst"]


def test_messages_before_first_take_delivered_oldest_first(ledger, clock):
    ledger.mail.register(["P01", "P02"])
    ledger.mail.send("P01", "P02", "one", urgent=False)
    clock.advance(1)
    ledger.mail.send("P01", None, "two", urgent=False)
    assert [m.text for m in ledger.mail.take("P02", urgent_only=False)] == ["one", "two"]


def test_text_length_and_empty_rejected(ledger):
    ledger.mail.send("P01", "P02", "x" * 1000, urgent=False)
    with pytest.raises(LedgerError, match="1000"):
        ledger.mail.send("P01", "P02", "x" * 1001, urgent=False)
    with pytest.raises(LedgerError):
        ledger.mail.send("P01", "P02", "", urgent=False)


def test_concurrent_take_never_duplicates(ledger):
    ledger.mail.register(["P01", "P02"])
    for i in range(50):
        ledger.mail.send("P01", "P02", f"m{i}", urgent=False)
    results = []
    lock = threading.Lock()
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        got = ledger.mail.take("P02", urgent_only=False)
        with lock:
            results.extend(m.id for m in got)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 50
    assert len(set(results)) == 50
