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


# ══════════════════════════════════════════════════════════════
#  BOSHLIQ TOMONI — vazifa qo'shish va tarix
# ══════════════════════════════════════════════════════════════

def boss_main_kb():
    """Boshliqning asosiy menyusi."""
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="➕ Vazifa qo'shish"),
            KeyboardButton(text="📜 Tarix"),
        ]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def bt_workers_kb(workers):
    """Vazifa biriktirish uchun ishchilar ro'yxati (bittasi tanlanadi)."""
    rows = [[InlineKeyboardButton(text=f"👤 {w.name}", callback_data=f"bt_wrk:{w.id}")]
            for w in workers]
    rows.append([InlineKeyboardButton(text="✖️ Bekor qilish", callback_data="bt_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bt_deadline_kb():
    """Deadline tanlash: tez tugmalar + kalendar + qo'lda."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Bugun", callback_data="bt_dl:today"),
            InlineKeyboardButton(text="Ertaga", callback_data="bt_dl:tomorrow"),
        ],
        [
            InlineKeyboardButton(text="+3 kun", callback_data="bt_dl:plus3"),
            InlineKeyboardButton(text="1 hafta", callback_data="bt_dl:week"),
        ],
        [InlineKeyboardButton(text="📅 Kalendardan tanlash", callback_data="bt_dl:cal")],
        [InlineKeyboardButton(text="✍️ Qo'lda kiritish", callback_data="bt_dl:manual")],
        [InlineKeyboardButton(text="✖️ Bekor qilish", callback_data="bt_cancel")],
    ])


_UZ_MONTHS = ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
              'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr']


def bt_history_months_kb():
    """Tarix uchun oy tanlash: oxirgi 6 oy + 'Hammasi'."""
    from datetime import date
    today = date.today()
    y, m = today.year, today.month
    btns = []
    for _ in range(6):
        btns.append(InlineKeyboardButton(
            text=f"{_UZ_MONTHS[m - 1]} {y}", callback_data=f"bt_hist:{y:04d}-{m:02d}"
        ))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    rows = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    rows.append([InlineKeyboardButton(text="📊 Hammasi (barcha oylar)", callback_data="bt_hist:all")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bt_calendar_kb(year, month):
    """Berilgan oy uchun inline kalendar (kun bosiladi)."""
    import calendar as _cal
    kbrd = [[InlineKeyboardButton(text=f"{_UZ_MONTHS[month - 1]} {year}", callback_data="bt_cal:ignore")]]
    kbrd.append([InlineKeyboardButton(text=d, callback_data="bt_cal:ignore")
                 for d in ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya']])

    for week in _cal.Calendar(firstweekday=0).monthdayscalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="bt_cal:ignore"))
            else:
                ds = f"{year:04d}-{month:02d}-{day:02d}"
                row.append(InlineKeyboardButton(text=str(day), callback_data=f"bt_cal:pick:{ds}"))
        kbrd.append(row)

    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)
    kbrd.append([
        InlineKeyboardButton(text="‹", callback_data=f"bt_cal:nav:{prev_y}:{prev_m}"),
        InlineKeyboardButton(text="✖️", callback_data="bt_cancel"),
        InlineKeyboardButton(text="›", callback_data=f"bt_cal:nav:{next_y}:{next_m}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kbrd)