import logging
import os
import random
from typing import cast

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

import db
import quiz

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
DIRECTIONS = ["ro_en", "en_ro"]
SESSION_SIZE = 10

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Loaded once at startup
verbs: list[dict] = []

# In-memory session state per user_id
sessions: dict[int, dict] = {}


def _session(user_id: int) -> dict:
    if user_id not in sessions:
        sessions[user_id] = {
            "playing": False,
            "session_correct": 0,
            "session_total": 0,
        }
    return sessions[user_id]


def _main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Play", callback_data="menu:play")],
        [InlineKeyboardButton("📊 Stats", callback_data="menu:stats")],
        [InlineKeyboardButton("🗑 Reset stats", callback_data="menu:reset_ask")],
    ])


async def _send_summary_and_menu(
    user_id: int, context: ContextTypes.DEFAULT_TYPE, header: str
) -> None:
    session = _session(user_id)
    session["playing"] = False
    correct = session.get("session_correct", 0)
    total = session.get("session_total", 0)

    if total > 0:
        pct = round(correct / total * 100)
        summary = f"{header}\n\n✅ *{correct}/{total}* correct ({pct}%)"
    else:
        summary = header

    await context.bot.send_message(
        chat_id=user_id,
        text=summary + "\n\nWhat would you like to do?",
        reply_markup=_main_menu(),
        parse_mode="Markdown",
    )


async def _send_card(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = _session(user_id)
    all_stats = await db.get_all_stats(user_id)
    stats = {(row[0], row[1]): row[2] for row in all_stats}

    direction = random.choice(DIRECTIONS)
    word = quiz.select_word(verbs, stats, direction)
    card = quiz.build_card(word, verbs, direction)

    session["current_word"] = word["ro"]
    session["current_direction"] = direction
    session["correct_answer"] = card["correct_answer"]

    card_num = session["session_total"] + 1
    progress = f"*Card {card_num}/{SESSION_SIZE}*\n"

    labels = ["A", "B", "C"]
    keyboard = [
        [
            InlineKeyboardButton(
                f"{labels[i]})  {card['choices'][i]}",
                callback_data=f"ans:{word['ro']}:{direction}:{i}:{card['correct_idx']}",
            )
        ]
        for i in range(len(card["choices"]))
    ] + [[InlineKeyboardButton("🛑 Stop session", callback_data="menu:stop")]]

    await context.bot.send_message(
        chat_id=user_id,
        text=progress + card["question"],
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    await update.message.reply_text(
        "👋 *Romanian Verb Trainer*\n\n"
        "I'll show you Romanian verbs — pick the correct translation.\n"
        "A word is *mastered* once you answer it correctly 10 times in a row.\n"
        "Each session is *10 cards*.",
        reply_markup=_main_menu(),
        parse_mode="Markdown",
    )


async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user
    user_id = update.effective_user.id
    session = _session(user_id)
    session["playing"] = True
    session["session_correct"] = 0
    session["session_total"] = 0
    await _send_card(user_id, context)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message and update.effective_user
    user_id = update.effective_user.id
    session = _session(user_id)
    correct = session.get("session_correct", 0)
    total = session.get("session_total", 0)
    all_stats = await db.get_all_stats(user_id)

    mastered = sum(1 for _, _, h in all_stats if quiz.is_mastered(h))
    words_seen = len({word_ro for word_ro, _, _ in all_stats})

    lines = ["📊 *Your Progress*\n"]
    if total > 0:
        pct = round(correct / total * 100)
        lines.append(f"*This session:* {correct}/{total} correct ({pct}%)")
    else:
        lines.append("*This session:* Not started yet")
    lines.append(f"*Words seen (all time):* {words_seen}")
    lines.append(f"*Mastered words:* {mastered} 🏆")
    lines.append(f"*Total in deck:* {len(verbs)}")

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=_main_menu(),
        parse_mode="Markdown",
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    await update.message.reply_text(
        "⚠️ This will delete *all* your word history and mastery progress. Are you sure?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Yes, reset everything", callback_data="menu:reset_confirm"),
                InlineKeyboardButton("Cancel", callback_data="menu:reset_cancel"),
            ]
        ]),
        parse_mode="Markdown",
    )


# ── Callback handler ──────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.callback_query and update.effective_user
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    assert query.data
    data = query.data

    # ── Menu actions ─────────────────────────────────────────────
    if data == "menu:play":
        session = _session(user_id)
        session["playing"] = True
        session["session_correct"] = 0
        session["session_total"] = 0
        await query.edit_message_reply_markup(reply_markup=None)
        await _send_card(user_id, context)
        return

    if data == "menu:stats":
        session = _session(user_id)
        correct = session.get("session_correct", 0)
        total = session.get("session_total", 0)
        all_stats = await db.get_all_stats(user_id)
        mastered = sum(1 for _, _, h in all_stats if quiz.is_mastered(h))
        words_seen = len({word_ro for word_ro, _, _ in all_stats})
        lines = ["📊 *Your Progress*\n"]
        if total > 0:
            pct = round(correct / total * 100)
            lines.append(f"*This session:* {correct}/{total} correct ({pct}%)")
        else:
            lines.append("*This session:* Not started yet")
        lines.append(f"*Words seen (all time):* {words_seen}")
        lines.append(f"*Mastered words:* {mastered} 🏆")
        lines.append(f"*Total in deck:* {len(verbs)}")
        await query.edit_message_text(
            "\n".join(lines) + "\n\nWhat would you like to do?",
            reply_markup=_main_menu(),
            parse_mode="Markdown",
        )
        return

    if data == "menu:stop":
        await query.edit_message_reply_markup(reply_markup=None)
        await _send_summary_and_menu(user_id, context, "Session stopped.")
        return

    if data == "menu:reset_ask":
        await query.edit_message_text(
            "⚠️ This will delete *all* your word history and mastery progress. Are you sure?",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Yes, reset everything", callback_data="menu:reset_confirm"),
                    InlineKeyboardButton("Cancel", callback_data="menu:reset_cancel"),
                ]
            ]),
            parse_mode="Markdown",
        )
        return

    if data == "menu:reset_confirm":
        await db.reset_stats(user_id)
        sessions.pop(user_id, None)
        await query.edit_message_text(
            "✅ All stats have been reset.\n\nWhat would you like to do?",
            reply_markup=_main_menu(),
        )
        return

    if data == "menu:reset_cancel":
        await query.edit_message_text(
            "Reset cancelled.\n\nWhat would you like to do?",
            reply_markup=_main_menu(),
        )
        return

    # ── Answer handler ────────────────────────────────────────────
    if not data.startswith("ans:"):
        return

    session = _session(user_id)
    if not session.get("playing"):
        await query.edit_message_text("Send /play to start a session.")
        return

    parts = data.split(":")
    if len(parts) != 5:
        return

    _, word_ro, direction, choice_str, correct_str = parts
    is_correct = choice_str == correct_str

    session["session_total"] += 1
    if is_correct:
        session["session_correct"] += 1

    await db.record_answer(user_id, word_ro, direction, is_correct)

    correct_answer = session.get("correct_answer", "?")
    card_message = cast(Message, query.message)
    original = card_message.text or ""

    if is_correct:
        result = f"✅ *Correct!*\n\n_{original}_"
    else:
        result = f"❌ *Wrong* — the answer was: *{correct_answer}*\n\n_{original}_"

    await query.edit_message_text(result, parse_mode="Markdown", reply_markup=None)

    if session["session_total"] >= SESSION_SIZE:
        await _send_summary_and_menu(
            user_id, context, f"Session complete! 🎉"
        )
    else:
        await _send_card(user_id, context)


# ── App lifecycle ─────────────────────────────────────────────────────────────

async def post_init(application: Application) -> None:
    global verbs
    verbs = quiz.load_verbs()
    await db.init_db()
    logger.info("Loaded %d verbs. DB ready.", len(verbs))


def main() -> None:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("play", cmd_play))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Bot polling …")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

