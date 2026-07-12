# formatter.py
"""
Quetex Bot — Telegram Message Formatter
Rich emoji-formatted messages with MarkdownV2 escaping.
"""

import re


def _escape_md(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2 parse mode.
    Characters that must be escaped: _ * [ ] ( ) ~ ` > # + - = | { } . !
    """
    special_chars = r"_*[]()~`>#+-=|{}.!"
    escaped = ""
    for char in str(text):
        if char in special_chars:
            escaped += f"\\{char}"
        else:
            escaped += char
    return escaped


def format_signal(signal: dict) -> str:
    """
    Format a trading signal into a rich Telegram message.

    Args:
        signal: Signal dict from SignalGenerator.generate()

    Returns:
        MarkdownV2-formatted message string.
    """
    d = signal["direction"]
    is_buy = d == "BUY"

    # Emoji based on direction
    arrow = "🟢" if is_buy else "🔴"
    call_put = "CALL ↑" if is_buy else "PUT ↓"

    # Confidence color emoji
    conf = signal["confidence"]
    if conf >= 90:
        conf_emoji = "🔥"
    elif conf >= 80:
        conf_emoji = "🟠"
    else:
        conf_emoji = "🟡"

    # Build confirming indicators list
    ind_lines = "\n".join(
        [f"  ✅ {_escape_md(i)}" for i in signal["confirming_indicators"]]
    )

    # Escape dynamic values
    asset_esc = _escape_md(signal["asset"])
    expiry_esc = _escape_md(signal["expiry"])
    entry_esc = _escape_md(str(signal["entry_price"]))
    call_put_esc = _escape_md(call_put)
    conf_esc = _escape_md(str(conf))
    pattern_esc = _escape_md(signal["pattern"])
    ts_esc = _escape_md(signal["timestamp"])

    msg = (
        f"{arrow} *{_escape_md(d)} SIGNAL — {asset_esc}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Asset:* `{asset_esc}`\n"
        f"⏱ *Expiry:* `{expiry_esc}`\n"
        f"💵 *Entry:* `{entry_esc}`\n"
        f"📈 *Direction:* `{call_put_esc}`\n"
        f"{conf_emoji} *Confidence:* `{conf_esc}%`\n"
        f"🕯 *Pattern:* `{pattern_esc}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*Confirming Indicators:*\n"
        f"{ind_lines}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ `{ts_esc} UTC`\n"
        f"⚠️ _Trade responsibly\\. No signal is 100% accurate\\._"
    )
    return msg


def format_no_signal(asset: str) -> str:
    """Format a 'no signal' message for an asset."""
    asset_esc = _escape_md(asset)
    return (
        f"⚪ No strong signal for `{asset_esc}` at this time\\. "
        f"\\(Confidence below threshold\\)"
    )


def format_error(error: str) -> str:
    """Format an error message."""
    return f"❌ Error: `{_escape_md(error)}`"


def format_welcome() -> str:
    """Format the welcome / /start message."""
    return (
        "🤖 *Quetex Signal Bot*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Your personal Quotex trading signal assistant\\.\n"
        "\n"
        "*Commands:*\n"
        "/signal — Scan all assets now\n"
        "/scan EURUSD\\-OTC — Scan specific asset\n"
        "/auto — Toggle auto\\-scan on/off\n"
        "/assets — List configured assets\n"
        "/status — Bot status\n"
        "/help — Show commands\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🟢 Bot is active and ready\\.\n"
        "\n"
        "⚠️ _Signals are based on technical analysis and are NOT financial advice\\. "
        "Binary options trading involves high risk\\. Trade only what you can afford to lose\\. "
        "No algorithm can guarantee 100% accuracy\\._"
    )


def format_status(
    auto_mode: bool,
    last_scan: str | None,
    signals_today: int,
    connected: bool,
) -> str:
    """Format the /status message."""
    auto_str = "🟢 ON" if auto_mode else "🔴 OFF"
    conn_str = "🟢 Connected" if connected else "🔴 Disconnected"
    scan_str = _escape_md(last_scan) if last_scan else "Never"

    return (
        "📊 *Bot Status*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 *Auto\\-scan:* {auto_str}\n"
        f"🔌 *Quotex:* {conn_str}\n"
        f"🕐 *Last scan:* `{scan_str}`\n"
        f"📨 *Signals today:* `{_escape_md(str(signals_today))}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━"
    )


def format_assets(assets: list[str], last_signals: dict) -> str:
    """Format the /assets list message."""
    lines = ["📋 *Configured Assets*", "━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for asset in assets:
        last = last_signals.get(asset)
        if last:
            last_str = _escape_md(last.strftime("%H:%M:%S"))
            lines.append(f"  • `{_escape_md(asset)}` — Last signal: `{last_str}`")
        else:
            lines.append(f"  • `{_escape_md(asset)}` — No signals yet")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)
