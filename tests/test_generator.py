import pandas as pd

from generate_mock_data import generate_dataset, parse_as_of


def make_dataset(seed=42):
    return generate_dataset(1000, seed, parse_as_of("2026-10-27"))


def test_generator_row_relationships_and_payment_state_rules():
    sessions, events, orders, _ = make_dataset()
    assert len(sessions) == 1000
    assert sessions.session_id.is_unique
    assert events.event_id.is_unique
    assert orders.id.is_unique
    assert events.session_id.isin(set(sessions.session_id)).all()
    assert orders.session_id.isin(set(sessions.session_id)).all()
    assert events.loc[events.order_id.notna(), "order_id"].astype(int).isin(set(orders.id.astype(int))).all()
    assert set(orders.status).issubset({"SUCCESS", "FAILED", "PENDING"})
    assert orders.loc[orders.status == "SUCCESS", "mpesa_receipt_number"].notna().all()
    assert orders.loc[orders.status == "PENDING", "result_code"].isna().all()


def test_same_seed_and_as_of_are_reproducible():
    one = make_dataset(seed=7)
    two = make_dataset(seed=7)
    for first, second in zip(one[:3], two[:3]):
        pd.testing.assert_frame_equal(first, second)
    assert one[3] == two[3]


def test_phone_identifiers_are_non_routable_and_not_in_event_properties():
    sessions, events, orders, _ = make_dataset()
    assert orders.phone_number.str.startswith("SYNTHETIC-KE-").all()
    properties = events.properties.astype(str)
    assert not properties.str.contains(r"\+2547\d{8}", regex=True).any()
    assert not properties.str.contains("phone_number", case=False).any()


def test_payment_events_agree_with_business_order_status():
    _, events, orders, _ = make_dataset()
    successes = set(events.loc[events.event_name == "payment_succeeded", "order_id"].dropna().astype(int))
    failures = set(events.loc[events.event_name == "payment_failed", "order_id"].dropna().astype(int))
    expected_successes = set(orders.loc[orders.status == "SUCCESS", "id"].astype(int))
    expected_failures = set(orders.loc[orders.status == "FAILED", "id"].astype(int))
    assert successes == expected_successes
    assert failures == expected_failures
