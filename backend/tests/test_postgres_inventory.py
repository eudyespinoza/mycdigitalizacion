import threading

import pytest
from django.db import close_old_connections, connection

from tests.test_commerce_domain import make_variant


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_concurrent_reservations_cannot_oversell_a_variant():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL integration test")

    from commerce.models import StockReservation
    from commerce.services import InsufficientStock, create_reservation

    variant = make_variant(sku="SYN-CONCURRENT", on_hand=5)
    barrier = threading.Barrier(2)
    outcomes = []

    def reserve(reference):
        close_old_connections()
        barrier.wait()
        try:
            create_reservation(variant=variant, quantity=4, reference=reference)
            outcomes.append("reserved")
        except InsufficientStock:
            outcomes.append("rejected")
        finally:
            close_old_connections()

    threads = [
        threading.Thread(target=reserve, args=(f"concurrent-{index}",))
        for index in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["rejected", "reserved"]
    assert StockReservation.objects.filter(status="active").count() == 1
