from datetime import datetime, timedelta, timezone

BAR_WIDTH = 10


def render_daily_bar_chart(counts_by_day: dict[str, int], days: int) -> str:
    today = datetime.now(timezone.utc).date()
    ordered_days = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    values = [counts_by_day.get(day.isoformat(), 0) for day in ordered_days]
    peak = max(values) if values else 0

    lines = []
    for day, value in zip(ordered_days, values):
        filled = round((value / peak) * BAR_WIDTH) if peak > 0 else 0
        bar = "█" * filled + "░" * (BAR_WIDTH - filled)
        lines.append(f"{day.strftime('%d.%m')} {bar} {value}")
    return "\n".join(lines)


def render_usage_bar(used_bytes: int, limit_bytes: int | None, width: int = BAR_WIDTH) -> str | None:
    if not limit_bytes:
        return None

    used_gb = used_bytes / (1024 ** 3)
    limit_gb = limit_bytes / (1024 ** 3)
    ratio = used_bytes / limit_bytes
    filled = min(width, round(ratio * width))
    bar = "█" * filled + "░" * (width - filled)
    percent = round(ratio * 100)
    return f"[{bar}] {percent}% ({used_gb:.1f} / {limit_gb:.1f} ГБ)"
