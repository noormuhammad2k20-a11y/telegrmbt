# bot.py
"""
Quetex Bot — Telegram Bot
Full async Telegram bot with commands, inline keyboards, auto-scan scheduler,
cooldown tracking, signal logging, and single-user security.
"""

import json
import logging
import os
from datetime import datetime, timezone

# pyrefly: ignore [missing-import]
from apscheduler.schedulers.asyncio import AsyncIOScheduler
# pyrefly: ignore [missing-import]
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
# pyrefly: ignore [missing-import]
from telegram.constants import ParseMode
# pyrefly: ignore [missing-import]
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from config import (
    ASSETS,
    COOLDOWN_MINUTES,
    SIGNAL_INTERVAL,
    TELEGRAM_CHAT_ID,
    TIMEFRAMES,
)
from formatter import (
    format_assets,
    format_error,
    format_no_signal,
    format_signal,
    format_status,
    format_welcome,
)

logger = logging.getLogger(__name__)

# Path for persisting auto-mode state across restarts
AUTO_STATE_FILE = "auto_state.json"


class QuetexBot:
    """Telegram bot for Quotex trading signals."""

    def __init__(
        self,
        token: str,
        chat_id: int,
        qx_client,
        analyzer,
        signal_gen,
    ):
        self.token = token
        self.chat_id = chat_id
        self.qx_client = qx_client
        self.analyzer = analyzer
        self.signal_gen = signal_gen

        # State
        self.auto_mode: bool = False
        self.last_signal: dict[str, datetime] = {}  # asset -> last signal time
        self.last_scan_time: str | None = None
        self.signals_today: int = 0
        self._today: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Scheduler
        self.scheduler = AsyncIOScheduler()

        # Telegram application (built later in run())
        self.app: Application | None = None

        # Load persisted auto state
        self._load_auto_state()

    # ──────────────────────────────────────────────────────────
    # Security
    # ──────────────────────────────────────────────────────────

    def _is_authorized(self, update: Update) -> bool:
        """Check if the message is from the authorized chat."""
        return update.effective_chat.id == self.chat_id

    # ──────────────────────────────────────────────────────────
    # Cooldown
    # ──────────────────────────────────────────────────────────

    def _is_on_cooldown(self, asset: str) -> bool:
        """Check if asset is still in cooldown period."""
        if asset not in self.last_signal:
            return False
        delta = datetime.now(timezone.utc) - self.last_signal[asset]
        return delta.total_seconds() < COOLDOWN_MINUTES * 60

    def _update_cooldown(self, asset: str):
        """Record a signal time for cooldown tracking."""
        self.last_signal[asset] = datetime.now(timezone.utc)

    # ──────────────────────────────────────────────────────────
    # Signal Counter (daily reset)
    # ──────────────────────────────────────────────────────────

    def _increment_signal_count(self):
        """Increment daily signal counter, resetting if new day."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._today:
            self._today = today
            self.signals_today = 0
        self.signals_today += 1

    # ──────────────────────────────────────────────────────────
    # Signal Logging
    # ──────────────────────────────────────────────────────────

    def _log_signal(self, signal: dict):
        """Append signal to signals.log file."""
        try:
            with open("signals.log", "a", encoding="utf-8") as f:
                f.write(
                    f"{signal['timestamp']} | {signal['asset']} | "
                    f"{signal['direction']} | {signal['confidence']}% | "
                    f"Expiry: {signal['expiry']}\n"
                )
        except Exception as e:
            logger.error(f"[Bot] Error writing to signals.log: {e}")

    # ──────────────────────────────────────────────────────────
    # Auto State Persistence
    # ──────────────────────────────────────────────────────────

    def _save_auto_state(self):
        """Save auto-mode state to JSON file for restart persistence."""
        try:
            with open(AUTO_STATE_FILE, "w") as f:
                json.dump({"auto_mode": self.auto_mode}, f)
        except Exception as e:
            logger.error(f"[Bot] Error saving auto state: {e}")

    def _load_auto_state(self):
        """Load auto-mode state from JSON file."""
        try:
            if os.path.exists(AUTO_STATE_FILE):
                with open(AUTO_STATE_FILE, "r") as f:
                    data = json.load(f)
                    self.auto_mode = data.get("auto_mode", False)
                    logger.info(
                        f"[Bot] Loaded auto state: {'ON' if self.auto_mode else 'OFF'}"
                    )
        except Exception as e:
            logger.error(f"[Bot] Error loading auto state: {e}")

    # ──────────────────────────────────────────────────────────
    # Core Scan Logic
    # ──────────────────────────────────────────────────────────

    async def _scan_asset(
        self, asset: str, timeframe: int
    ) -> dict | None:
        """
        Scan a single asset on a single timeframe.
        Returns signal dict or None.
        """
        try:
            # Fetch candles
            df = await self.qx_client.get_candles(asset, timeframe)
            if df.empty or len(df) < 50:
                logger.warning(
                    f"[Bot] Insufficient candle data for {asset} (got {len(df)})"
                )
                return None

            # Get current price
            current_price = await self.qx_client.get_current_price(asset)
            if current_price <= 0:
                # Fallback: use last candle close
                current_price = df["close"].iloc[-1]

            # Run analysis
            analysis = self.analyzer.analyze(df, current_price)

            # Generate signal (returns None if below threshold)
            signal = self.signal_gen.generate(analysis, asset, timeframe)
            return signal

        except Exception as e:
            logger.error(f"[Bot] Error scanning {asset} tf={timeframe}: {e}")
            return None

    async def _scan_all_assets(self, context: ContextTypes.DEFAULT_TYPE = None):
        """Scan all configured assets on all timeframes. Used by /signal and auto-scan."""
        self.last_scan_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        signals_found = 0

        for asset in ASSETS:
            # Skip if on cooldown
            if self._is_on_cooldown(asset):
                logger.info(f"[Bot] {asset} is on cooldown. Skipping.")
                continue

            best_signal = None
            best_confidence = 0.0

            for tf in TIMEFRAMES:
                signal = await self._scan_asset(asset, tf)
                if signal and signal["confidence"] > best_confidence:
                    best_signal = signal
                    best_confidence = signal["confidence"]

            if best_signal:
                # Send signal message
                msg = format_signal(best_signal)
                await self._send_message(msg, context)
                self._log_signal(best_signal)
                self._update_cooldown(asset)
                self._increment_signal_count()
                signals_found += 1

        if signals_found == 0 and context is None:
            # Only send "no signals" when manually triggered (context is None means
            # it was called from a handler, not auto-scan)
            pass

        return signals_found

    async def _send_message(
        self, text: str, context: ContextTypes.DEFAULT_TYPE = None
    ):
        """Send a message to the authorized chat."""
        try:
            if context and context.bot:
                await context.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            elif self.app and self.app.bot:
                await self.app.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
        except Exception as e:
            logger.error(f"[Bot] Error sending message: {e}")
            # Try sending without markdown as fallback
            try:
                plain_text = text.replace("\\", "")
                if context and context.bot:
                    await context.bot.send_message(
                        chat_id=self.chat_id, text=plain_text
                    )
                elif self.app and self.app.bot:
                    await self.app.bot.send_message(
                        chat_id=self.chat_id, text=plain_text
                    )
            except Exception as e2:
                logger.error(f"[Bot] Fallback message also failed: {e2}")

    # ──────────────────────────────────────────────────────────
    # Auto-scan Scheduler
    # ──────────────────────────────────────────────────────────

    async def _auto_scan_job(self):
        """Scheduled job: scan all assets automatically."""
        if not self.auto_mode:
            return
        logger.info("[Bot] ⏰ Auto-scan triggered")
        await self._scan_all_assets()

    def _start_scheduler(self):
        """Start the APScheduler for auto-scan."""
        if not self.scheduler.running:
            self.scheduler.add_job(
                self._auto_scan_job,
                "interval",
                minutes=SIGNAL_INTERVAL,
                id="auto_scan",
                replace_existing=True,
            )
            self.scheduler.start()
            logger.info(
                f"[Bot] Scheduler started (interval: {SIGNAL_INTERVAL} min)"
            )

    def _stop_scheduler(self):
        """Stop the auto-scan scheduler."""
        if self.scheduler.running:
            self.scheduler.remove_all_jobs()
            self.scheduler.shutdown(wait=False)
            logger.info("[Bot] Scheduler stopped")

    # ──────────────────────────────────────────────────────────
    # Command Handlers
    # ──────────────────────────────────────────────────────────

    async def cmd_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /start command — welcome message + keyboard."""
        if not self._is_authorized(update):
            await update.message.reply_text("Unauthorized.")
            return

        keyboard = [
            [InlineKeyboardButton("🔍 Scan Now", callback_data="scan_all")],
            [
                InlineKeyboardButton("🤖 Auto Mode", callback_data="toggle_auto"),
                InlineKeyboardButton("📊 Status", callback_data="status"),
            ],
            [
                InlineKeyboardButton("📋 Assets", callback_data="assets"),
                InlineKeyboardButton("❓ Help", callback_data="help"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            format_welcome(),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=reply_markup,
        )

    async def cmd_signal(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /signal command — scan all assets now."""
        if not self._is_authorized(update):
            await update.message.reply_text("Unauthorized.")
            return

        await update.message.reply_text(
            "🔍 Scanning all assets\\.\\.\\. Please wait\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        signals_found = await self._scan_all_assets(context)

        if signals_found == 0:
            await update.message.reply_text(
                "⚪ No strong signals found across all assets at this time\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )

    async def cmd_scan(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /scan ASSET command — scan specific asset."""
        if not self._is_authorized(update):
            await update.message.reply_text("Unauthorized.")
            return

        if not context.args or len(context.args) == 0:
            await update.message.reply_text(
                "Usage: `/scan EURUSD\\-OTC`",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        asset = context.args[0].upper()

        await update.message.reply_text(
            f"🔍 Scanning `{formatter_escape(asset)}`\\.\\.\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        signal_found = False
        for tf in TIMEFRAMES:
            signal = await self._scan_asset(asset, tf)
            if signal:
                msg = format_signal(signal)
                await update.message.reply_text(
                    msg, parse_mode=ParseMode.MARKDOWN_V2
                )
                self._log_signal(signal)
                self._update_cooldown(asset)
                self._increment_signal_count()
                signal_found = True
                break  # Send best (first found above threshold)

        if not signal_found:
            await update.message.reply_text(
                format_no_signal(asset),
                parse_mode=ParseMode.MARKDOWN_V2,
            )

    async def cmd_auto(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /auto command — toggle auto-scan on/off."""
        if not self._is_authorized(update):
            await update.message.reply_text("Unauthorized.")
            return

        self.auto_mode = not self.auto_mode
        self._save_auto_state()

        if self.auto_mode:
            self._start_scheduler()
            status_msg = (
                f"🤖 Auto\\-scan *ON*\n"
                f"Scanning every `{SIGNAL_INTERVAL}` minutes\\."
            )
        else:
            self._stop_scheduler()
            status_msg = "🤖 Auto\\-scan *OFF*"

        await update.message.reply_text(
            status_msg, parse_mode=ParseMode.MARKDOWN_V2
        )

    async def cmd_assets(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /assets command — list configured assets."""
        if not self._is_authorized(update):
            await update.message.reply_text("Unauthorized.")
            return

        msg = format_assets(ASSETS, self.last_signal)
        await update.message.reply_text(
            msg, parse_mode=ParseMode.MARKDOWN_V2
        )

    async def cmd_status(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /status command — show bot status."""
        if not self._is_authorized(update):
            await update.message.reply_text("Unauthorized.")
            return

        msg = format_status(
            auto_mode=self.auto_mode,
            last_scan=self.last_scan_time,
            signals_today=self.signals_today,
            connected=self.qx_client.connected,
        )
        await update.message.reply_text(
            msg, parse_mode=ParseMode.MARKDOWN_V2
        )

    async def cmd_help(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle /help command — show all commands."""
        if not self._is_authorized(update):
            await update.message.reply_text("Unauthorized.")
            return

        help_msg = (
            "📖 *Quetex Bot Commands*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "/start — Welcome \\+ menu\n"
            "/signal — Scan all assets now\n"
            "/scan `ASSET` — Scan specific asset\n"
            "/auto — Toggle auto\\-scan on/off\n"
            "/assets — List configured assets\n"
            "/status — Bot status\n"
            "/help — Show this message\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(
            help_msg, parse_mode=ParseMode.MARKDOWN_V2
        )

    # ──────────────────────────────────────────────────────────
    # Inline Keyboard Callback Handler
    # ──────────────────────────────────────────────────────────

    async def callback_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle inline keyboard button presses."""
        query = update.callback_query
        await query.answer()

        if query.from_user and update.effective_chat.id != self.chat_id:
            return

        data = query.data

        if data == "scan_all":
            await query.edit_message_text(
                "🔍 Scanning all assets\\.\\.\\. Please wait\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            signals_found = await self._scan_all_assets(context)
            if signals_found == 0:
                await self._send_message(
                    "⚪ No strong signals found across all assets at this time\\.",
                    context,
                )

        elif data == "toggle_auto":
            self.auto_mode = not self.auto_mode
            self._save_auto_state()
            if self.auto_mode:
                self._start_scheduler()
                status = "🟢 ON"
            else:
                self._stop_scheduler()
                status = "🔴 OFF"
            await query.edit_message_text(
                f"🤖 Auto\\-scan: {status}",
                parse_mode=ParseMode.MARKDOWN_V2,
            )

        elif data == "status":
            msg = format_status(
                auto_mode=self.auto_mode,
                last_scan=self.last_scan_time,
                signals_today=self.signals_today,
                connected=self.qx_client.connected,
            )
            await query.edit_message_text(
                msg, parse_mode=ParseMode.MARKDOWN_V2
            )

        elif data == "assets":
            msg = format_assets(ASSETS, self.last_signal)
            await query.edit_message_text(
                msg, parse_mode=ParseMode.MARKDOWN_V2
            )

        elif data == "help":
            help_msg = (
                "📖 *Quetex Bot Commands*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "/start — Welcome \\+ menu\n"
                "/signal — Scan all assets now\n"
                "/scan `ASSET` — Scan specific asset\n"
                "/auto — Toggle auto\\-scan on/off\n"
                "/assets — List configured assets\n"
                "/status — Bot status\n"
                "/help — Show this message\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            await query.edit_message_text(
                help_msg, parse_mode=ParseMode.MARKDOWN_V2
            )

    # ──────────────────────────────────────────────────────────
    # Run
    # ──────────────────────────────────────────────────────────

    async def run(self):
        """Start the Telegram bot with polling and scheduler."""
        self.app = (
            Application.builder()
            .token(self.token)
            .build()
        )

        # Register command handlers
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("signal", self.cmd_signal))
        self.app.add_handler(CommandHandler("scan", self.cmd_scan))
        self.app.add_handler(CommandHandler("auto", self.cmd_auto))
        self.app.add_handler(CommandHandler("assets", self.cmd_assets))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("help", self.cmd_help))

        # Register callback query handler for inline buttons
        self.app.add_handler(CallbackQueryHandler(self.callback_handler))

        # Start auto-scan if it was on before restart
        if self.auto_mode:
            self._start_scheduler()
            logger.info("[Bot] Auto-scan restored from saved state (ON)")

        # Start polling
        logger.info("[Bot] 🚀 Quetex bot is running!")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

        # Keep running until interrupted
        try:
            # Block forever (until Ctrl+C or signal)
            import asyncio
            stop_event = asyncio.Event()
            await stop_event.wait()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            logger.info("[Bot] Shutting down...")
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            await self.qx_client.disconnect()


def formatter_escape(text: str) -> str:
    """Quick escape for inline MarkdownV2 in bot.py messages."""
    special_chars = r"_*[]()~`>#+-=|{}.!"
    escaped = ""
    for char in str(text):
        if char in special_chars:
            escaped += f"\\{char}"
        else:
            escaped += char
    return escaped
