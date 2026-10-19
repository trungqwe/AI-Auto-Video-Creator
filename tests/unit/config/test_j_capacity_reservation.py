"""J-12: Reservation capacity theo quota domain (CT-CAP-002, RM-RISK-007).

coveredIds: CT-CAP-002, RM-RISK-007
"""
import dataclasses
import inspect
import itertools
from datetime import datetime, timedelta, timezone

import pytest

from controlplane.application.config_security import capacity_reservation
from controlplane.application.config_security.capacity_reservation import (
    NO_CAPACITY, CapacityReservationBook, CapacityUnavailableError, Reservation, ReservationConflictError,
    ReservationStorePort,
)
from controlplane.domain.config_security.capacity_snapshot import (
    DomainCapacity, ProviderCapacitySnapshot, merge_quota_domain, quota_domain_key,
)

UTC = timezone.utc
NOW = datetime(2026, 10, 20, 10, 30, tzinfo=UTC)
RESET = '2026-10-20T12:00:00+00:00'
DOMAIN = quota_domain_key('gemini', 'proj-a', 'flash')
OTHER = quota_domain_key('gemini', 'proj-b', 'flash')


def _cap(remaining=4, domain=DOMAIN, reset_at=RESET) -> DomainCapacity:
    return DomainCapacity(
        domain_key=domain, limit_requests=10, used_requests=6, remaining_requests=remaining, health='healthy',
        confidence='observed' if remaining is not None else 'unknown', reset_at=reset_at,
        observed_at='2026-10-20T10:00:00+00:00',
    )


def _snapshot(account, **overrides) -> ProviderCapacitySnapshot:
    values = dict(
        snapshot_id='snap-' + account, provider='gemini', model='flash', project='proj-a', account=account,
        capability='text', limit_requests=10, used_requests=6, reset_at=RESET, health='healthy',
        confidence='observed', source='fixture', observed_at='2026-10-20T10:00:00+00:00',
    )
    values.update(overrides)
    return ProviderCapacitySnapshot(**values)


class FakeStore:
    """Fake ReservationStorePort: giữ dict trong bộ nhớ và ghi lại tên các lời gọi."""

    def __init__(self) -> None:
        self.items = {}
        self.calls = []

    def get_by_operation(self, operation_key):
        self.calls.append('get_by_operation')
        return next((item for item in self.items.values() if item.operation_key == operation_key), None)

    def list_by_domain(self, domain_key):
        self.calls.append('list_by_domain')
        return tuple(item for item in self.items.values() if item.domain_key == domain_key)

    def list_all(self):
        self.calls.append('list_all')
        return tuple(self.items.values())

    def add(self, reservation):
        self.calls.append('add')
        self.items[reservation.reservation_ref] = reservation

    def remove(self, reservation_ref):
        self.calls.append('remove')
        return self.items.pop(reservation_ref, None)


def _book(store) -> CapacityReservationBook:
    counter = itertools.count(1)
    return CapacityReservationBook(store=store, ref_factory=lambda: f'ref-{next(counter)}')


def _reserve(book, op='op-1', units=1, ttl=60, now=NOW, cap=None, domain=DOMAIN):
    return book.reserve(domain, units, ttl, op, now, cap)


def test_reservation_has_six_fields_in_spec_order_and_is_frozen():
    assert [f.name for f in dataclasses.fields(Reservation)] == [
        'reservation_ref', 'domain_key', 'units', 'expires_at', 'operation_key', 'confidence_flag',
    ]
    reservation = _reserve(_book(FakeStore()), cap=_cap())
    with pytest.raises(dataclasses.FrozenInstanceError):
        reservation.units = 9


def test_reserve_sets_expiry_from_ttl_and_known_confidence():
    reservation = _reserve(_book(FakeStore()), units=2, ttl=90, cap=_cap())
    assert (reservation.reservation_ref, reservation.domain_key, reservation.units) == ('ref-1', DOMAIN, 2)
    assert (reservation.operation_key, reservation.confidence_flag) == ('op-1', 'KNOWN')
    assert reservation.expires_at == NOW + timedelta(seconds=90)


def test_reserve_signature_has_no_defaults_and_no_account_parameter():
    params = inspect.signature(CapacityReservationBook.reserve).parameters
    assert list(params)[1:] == ['domain_key', 'units', 'ttl_seconds', 'operation_key', 'now', 'domain_capacity']
    assert all(p.default is inspect.Parameter.empty for p in params.values())


@pytest.mark.parametrize('units', [0, -1, True, False, 1.0, '1', None])
def test_units_must_be_positive_int(units):
    store = FakeStore()
    with pytest.raises(ValueError):
        _reserve(_book(store), units=units, cap=_cap())
    assert store.items == {}


@pytest.mark.parametrize('ttl', [0, -5, True, False, 1.5, '60', None, 10**12])
def test_ttl_seconds_must_be_positive_int_and_representable(ttl):
    store = FakeStore()
    with pytest.raises(ValueError):
        _reserve(_book(store), ttl=ttl, cap=_cap())
    assert store.items == {}


@pytest.mark.parametrize('now', [datetime(2026, 10, 20, 10, 30), '2026-10-20T10:30:00+00:00', None])
def test_now_must_be_timezone_aware_datetime(now):
    store = FakeStore()
    with pytest.raises(ValueError):
        _reserve(_book(store), now=now, cap=_cap())
    assert store.items == {}


@pytest.mark.parametrize('field', ['domain_key', 'operation_key'])
@pytest.mark.parametrize('value', ['', '   ', None, 5])
def test_keys_must_be_non_empty_strings(field, value):
    store = FakeStore()
    kwargs = dict(domain_key=DOMAIN, units=1, ttl_seconds=60, operation_key='op-1', now=NOW, domain_capacity=None)
    kwargs[field] = value
    with pytest.raises(ValueError):
        _book(store).reserve(**kwargs)
    assert store.items == {}


@pytest.mark.parametrize('capacity', [_cap(domain=OTHER), 'cap', 4])
def test_domain_capacity_must_be_domain_capacity_of_same_domain(capacity):
    store = FakeStore()
    with pytest.raises(ValueError):
        _reserve(_book(store), cap=capacity)
    assert store.items == {}


def test_same_operation_key_returns_same_reservation_without_second_entry():
    store = FakeStore()
    book = _book(store)
    first = _reserve(book, units=2, cap=_cap())
    again = _reserve(book, units=2, now=NOW + timedelta(seconds=30), cap=_cap())
    assert again == first and again.reservation_ref == 'ref-1'
    assert again.expires_at == NOW + timedelta(seconds=60)
    assert len(store.items) == 1


def test_replay_returns_old_reservation_even_if_remaining_no_longer_fits():
    book = _book(FakeStore())
    first = _reserve(book, units=4, cap=_cap())
    assert _reserve(book, units=4, cap=_cap()) == first


@pytest.mark.parametrize('units, domain', [(3, DOMAIN), (2, OTHER)])
def test_same_operation_key_with_other_units_or_domain_conflicts(units, domain):
    store = FakeStore()
    book = _book(store)
    _reserve(book, units=2, cap=_cap())
    with pytest.raises(ReservationConflictError):
        _reserve(book, units=units, domain=domain, cap=_cap(domain=domain))
    assert len(store.items) == 1


def test_operation_key_is_forgotten_after_expiry_and_after_release():
    book = _book(FakeStore())
    _reserve(book, units=2, cap=_cap())
    later = _reserve(book, units=3, now=NOW + timedelta(seconds=60), cap=_cap())
    assert (later.reservation_ref, later.units) == ('ref-2', 3)
    assert book.release('ref-2') is True
    third = _reserve(book, units=1, now=NOW + timedelta(seconds=61), cap=_cap())
    assert third.reservation_ref == 'ref-3'


def test_two_accounts_of_same_quota_domain_share_one_remaining_budget():
    merged = merge_quota_domain([_snapshot('acct-1'), _snapshot('acct-2')], NOW)
    assert list(merged) == [DOMAIN]
    capacity = merged[DOMAIN]
    assert capacity.remaining_requests == 4
    book = _book(FakeStore())
    _reserve(book, op='op-a', units=3, cap=capacity)
    with pytest.raises(CapacityUnavailableError) as info:
        _reserve(book, op='op-b', units=2, cap=capacity)
    assert info.value.code == NO_CAPACITY == 'NO_CAPACITY'


def test_four_accounts_do_not_multiply_the_domain_budget():
    capacity = merge_quota_domain([_snapshot(f'acct-{i}') for i in range(1, 5)], NOW)[DOMAIN]
    book = _book(FakeStore())
    granted = 0
    for index in range(1, 6):
        try:
            _reserve(book, op=f'op-{index}', units=1, cap=capacity)
            granted += 1
        except CapacityUnavailableError:
            pass
    assert granted == 4


def test_exact_fit_is_granted_and_one_more_unit_is_refused():
    book = _book(FakeStore())
    _reserve(book, op='op-a', units=4, cap=_cap())
    with pytest.raises(CapacityUnavailableError):
        _reserve(book, op='op-b', units=1, cap=_cap())


@pytest.mark.parametrize('remaining, units', [(4, 5), (0, 1)])
def test_units_above_remaining_are_refused_on_empty_book(remaining, units):
    with pytest.raises(CapacityUnavailableError):
        _reserve(_book(FakeStore()), units=units, cap=_cap(remaining=remaining))


def test_no_capacity_error_carries_code_domain_and_retry_after_from_reset_at():
    store = FakeStore()
    with pytest.raises(CapacityUnavailableError) as info:
        _reserve(_book(store), units=5, cap=_cap())
    assert (info.value.code, info.value.domain_key) == ('NO_CAPACITY', DOMAIN)
    assert info.value.retry_after == datetime(2026, 10, 20, 12, tzinfo=UTC)
    assert store.items == {}


@pytest.mark.parametrize('reset_at, expected', [
    (datetime(2026, 10, 20, 12, tzinfo=UTC), datetime(2026, 10, 20, 12, tzinfo=UTC)),
    ('2026-10-20T12:00:00Z', datetime(2026, 10, 20, 12, tzinfo=UTC)),
    (None, None), ('2026-10-20T09:00:00+00:00', None), ('2026-10-20T10:30:00+00:00', None),
    ('bad', None), ('', None), ('2026-10-20T12:00:00', None),
])
def test_retry_after_is_future_aware_reset_at_or_none(reset_at, expected):
    with pytest.raises(CapacityUnavailableError) as info:
        _reserve(_book(FakeStore()), units=5, cap=_cap(reset_at=reset_at))
    assert info.value.retry_after == expected


@pytest.mark.parametrize('capacity', [None, _cap(remaining=None)])
def test_unknown_remaining_is_granted_as_uncertain_without_summing(capacity):
    book = _book(FakeStore())
    first = _reserve(book, op='op-a', units=500, cap=capacity)
    second = _reserve(book, op='op-b', units=500, cap=capacity)
    assert (first.confidence_flag, second.confidence_flag) == ('UNCERTAIN', 'UNCERTAIN')


def test_expired_snapshot_gives_uncertain_reservation():
    capacity = merge_quota_domain([_snapshot('acct-1', expires_at='2026-10-20T10:00:00+00:00')], NOW)[DOMAIN]
    assert capacity.remaining_requests is None
    assert _reserve(_book(FakeStore()), cap=capacity).confidence_flag == 'UNCERTAIN'


def test_reservations_of_other_domains_do_not_consume_this_domain():
    book = _book(FakeStore())
    _reserve(book, op='op-a', units=4, cap=_cap())
    other = _reserve(book, op='op-b', units=4, domain=OTHER, cap=_cap(domain=OTHER))
    assert other.domain_key == OTHER


def test_expired_reservation_does_not_hold_capacity():
    book = _book(FakeStore())
    _reserve(book, op='op-a', units=4, cap=_cap())
    with pytest.raises(CapacityUnavailableError):
        _reserve(book, op='op-b', units=1, now=NOW + timedelta(seconds=59), cap=_cap())
    granted = _reserve(book, op='op-b', units=4, now=NOW + timedelta(seconds=60), cap=_cap())
    assert granted.reservation_ref == 'ref-2'


def test_expire_releases_only_expired_reservations_and_returns_their_refs():
    store = FakeStore()
    book = _book(store)
    _reserve(book, op='op-a', units=1, ttl=30, cap=_cap())
    _reserve(book, op='op-b', units=1, ttl=60, cap=_cap())
    assert book.expire(NOW + timedelta(seconds=29)) == ()
    assert book.expire(NOW + timedelta(seconds=30)) == ('ref-1',)
    assert list(store.items) == ['ref-2']
    assert book.expire(NOW + timedelta(seconds=30)) == ()


def test_expire_requires_timezone_aware_now():
    with pytest.raises(ValueError):
        _book(FakeStore()).expire(datetime(2026, 10, 20, 10, 30))


def test_release_frees_capacity_and_is_idempotent():
    book = _book(FakeStore())
    held = _reserve(book, op='op-a', units=4, cap=_cap())
    assert book.release(held.reservation_ref) is True
    assert book.release(held.reservation_ref) is False
    assert book.release('missing') is False
    assert _reserve(book, op='op-b', units=4, cap=_cap()).reservation_ref == 'ref-2'


@pytest.mark.parametrize('ref', ['', '  ', None, 3])
def test_release_rejects_blank_reference(ref):
    with pytest.raises(ValueError):
        _book(FakeStore()).release(ref)


def test_book_uses_injected_store_port():
    store = FakeStore()
    book = _book(store)
    held = _reserve(book, cap=_cap())
    book.release(held.reservation_ref)
    assert 'add' in store.calls and 'remove' in store.calls


def test_port_declares_five_methods_and_default_store_works():
    assert {'get_by_operation', 'list_by_domain', 'list_all', 'add', 'remove'} <= set(dir(ReservationStorePort))
    reservation = _reserve(CapacityReservationBook(), cap=_cap())
    assert reservation.reservation_ref.startswith('res-')


def test_module_does_not_read_clock_sleep_or_use_threads():
    source = inspect.getsource(capacity_reservation)
    for token in ('import time', 'time.sleep', 'datetime.now', 'utcnow', 'asyncio', 'threading'):
        assert token not in source
