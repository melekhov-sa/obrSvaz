from dataclasses import dataclass


@dataclass
class UserStatus:
    login: str
    status: str
    used_traffic_bytes: int
    data_limit_bytes: int | None
    expire_timestamp: int | None

    @classmethod
    def from_api(cls, login: str, data: dict) -> "UserStatus":
        return cls(
            login=login,
            status=data.get("status", "unknown"),
            used_traffic_bytes=data.get("used_traffic", 0),
            data_limit_bytes=data.get("data_limit"),
            expire_timestamp=data.get("expire"),
        )

    def days_until_expiry(self, now_timestamp: int) -> int | None:
        if self.expire_timestamp is None:
            return None
        seconds_left = self.expire_timestamp - now_timestamp
        return seconds_left // 86400
