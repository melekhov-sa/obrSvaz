from bot.marzban.status import UserStatus


def test_from_api_maps_fields():
    status = UserStatus.from_api(
        "ivan", {"status": "active", "used_traffic": 500, "data_limit": 1000, "expire": 1000086400}
    )

    assert status.login == "ivan"
    assert status.status == "active"
    assert status.used_traffic_bytes == 500
    assert status.data_limit_bytes == 1000
    assert status.expire_timestamp == 1000086400


def test_days_until_expiry_computes_full_days():
    status = UserStatus.from_api("ivan", {"expire": 1_000_000_000 + 3 * 86400})

    assert status.days_until_expiry(now_timestamp=1_000_000_000) == 3


def test_days_until_expiry_none_when_no_expiry():
    status = UserStatus.from_api("ivan", {"expire": None})

    assert status.days_until_expiry(now_timestamp=1_000_000_000) is None


def test_days_until_expiry_negative_when_already_expired():
    status = UserStatus.from_api("ivan", {"expire": 1_000_000_000 - 86400})

    assert status.days_until_expiry(now_timestamp=1_000_000_000) < 0
