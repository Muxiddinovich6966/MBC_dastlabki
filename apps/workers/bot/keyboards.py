"""
Ishchilar boti uchun tugmalar (klaviaturalar).
"""
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove,
)


def worker_main_kb():
    """Ishchining asosiy menyusi."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📝 Aktiv vazifalar")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def active_events_kb(events):
    """Aktiv vazifasi bor tadbirlar ro'yxati (inline)."""
    rows = []
    for event in events:
        rows.append([InlineKeyboardButton(
            text=event.name,
            callback_data=f"we_event_{event.id}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def task_done_kb(task_id: int):
    """Vazifa ostidagi '✅ Bajardim' tugmasi."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Bajardim", callback_data=f"we_done_{task_id}")
    ]])


def task_confirm_kb(task_id: int):
    """Instruksiya ko'rsatilgach '✅ Tasdiqlash' tugmasi."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"we_confirm_{task_id}")
    ]])


def proof_done_kb():
    """Isbot yuborib bo'lgach '✅ Tayyor' tugmasi."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tayyor", callback_data="we_proof_done")
    ]])


def clear_kb():
    return ReplyKeyboardRemove()