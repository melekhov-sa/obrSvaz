from datetime import datetime, timedelta, timezone

from bot.formatting import render_daily_bar_chart, render_usage_bar


def test_render_daily_bar_chart_shows_all_zero_when_no_complaints():
    result = render_daily_bar_chart({}, days=3)

    lines = result.split("\n")
    assert len(lines) == 3
    for line in lines:
        assert line.endswith(" 0")
        assert "█" not in line


def test_render_daily_bar_chart_scales_bars_to_peak():
    today = datetime.now(timezone.utc).date()
    counts = {
        today.isoformat(): 10,
        (today - timedelta(days=1)).isoformat(): 5,
    }

    result = render_daily_bar_chart(counts, days=2)

    lines = result.split("\n")
    assert lines[0].endswith(" 5")
    assert lines[1].endswith(" 10")
    assert lines[0].count("█") == 5
    assert lines[1].count("█") == 10


def test_render_daily_bar_chart_orders_oldest_to_newest():
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    counts = {today.isoformat(): 1, yesterday.isoformat(): 2}

    result = render_daily_bar_chart(counts, days=2)

    lines = result.split("\n")
    assert lines[0].startswith(yesterday.strftime("%d.%m"))
    assert lines[1].startswith(today.strftime("%d.%m"))


def test_render_usage_bar_returns_none_when_no_limit():
    assert render_usage_bar(used_bytes=1000, limit_bytes=None) is None
    assert render_usage_bar(used_bytes=1000, limit_bytes=0) is None


def test_render_usage_bar_shows_percentage_and_gb():
    limit = 50 * 1024 ** 3
    used = 34 * 1024 ** 3 + int(0.2 * 1024 ** 3)

    result = render_usage_bar(used_bytes=used, limit_bytes=limit)

    assert "68%" in result
    assert "34.2" in result
    assert "50.0" in result


def test_render_usage_bar_over_100_percent_not_clamped():
    limit = 50 * 1024 ** 3
    used = 60 * 1024 ** 3

    result = render_usage_bar(used_bytes=used, limit_bytes=limit)

    assert "120%" in result
    assert result.count("█") == 10
