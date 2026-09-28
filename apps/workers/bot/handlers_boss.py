"""
Ishchilar boti — BOSHLIQ tomoni.

Boshliq bot orqali ishchiga to'g'ridan-to'g'ri vazifa biriktiradi:
  ➕ Vazifa qo'shish → matn → ishchini tanlash → deadline (tez/kalendar/qo'lda) → yuboriladi
Bu vazifalar tadbirga bog'lanmaydi va guruh check-listiga tushmaydi (event=None, source='boss').
Ishchiga "👔 Boshliqdan topshiriq" banneri bilan darrov boradi.
📜 Tarix → boshliq kim vaqtida/kechikib bajargan yoki bajarmaganini ko'radi (statistika bilan).
"""
import html
from datetime import date, datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async

from .states import BossTaskState
from . import keyboards as kb
from .keyboards import _UZ_MONTHS
from config.transcribe import transcribe_voice

router = Router()

# Menyu (reply) tugmalari — har qanday holatda ustun ishlaydi (chalkashmaslik uchun)
MENU_BUTTONS = {"➕ Vazifa qo'shish", "📜 Tarix"}


# ─────────── ORM yordamchilari ───────────
@sync_to_async
def get_boss(tg_id):
    from apps.workers.models import Worker
    return Worker.objects.filter(telegram_id=tg_id, role__in=['boss', 'admin']).first()


@sync_to_async
def get_assignable_workers():
    from apps.workers.models import Worker
    return list(Worker.objects.filter(role__in=['worker', 'boss'])
                .exclude(telegram_id__isnull=True).order_by('name'))


@sync_to_async
def get_worker(worker_id):
    from apps.workers.models import Worker
    return Worker.objects.filter(id=worker_id).first()


@sync_to_async
def create_boss_task(text, worker_id, deadline_date, boss_id):
    """Boshliq topshirig'ini yaratadi va ishchiga bog'laydi."""
    from apps.workers.models import Task, Worker
    w = Worker.objects.filter(id=worker_id).first()
    task = Task.objects.create(
        event=None, source='boss', assigned_by_id=boss_id,
        description=text, deadline_date=deadline_date,
        days_before=0, when='before', status='pending', reminder_sent=False,
    )
    if w:
        task.workers.add(w)
    return task.id, (w.name if w else '—'), (w.telegram_id if w else None)


@sync_to_async
def log_notification(task_id, chat_id, message_id):
    from apps.workers.models import NotificationLog
    NotificationLog.objects.create(
        task_id=task_id, chat_id=chat_id, message_id=message_id, role='worker'
    )


@sync_to_async
def build_history(boss_id, year=None, month=None):
    """Boshliq topshiriqlari tarixi — ishchi bo'yicha guruhlab (rasmga mos ko'rinish).

    year/month berilsa — faqat shu oy (deadline bo'yicha). Aks holda hammasi.
    """
    from apps.workers.models import Task
    from django.utils import timezone
    from collections import OrderedDict

    today = date.today()
    qs = Task.objects.filter(source='boss', assigned_by_id=boss_id)
    if year and month:
        qs = qs.filter(deadline_date__year=year, deadline_date__month=month)
    tasks = list(qs.prefetch_related('workers').order_by('deadline_date'))
    if not tasks:
        return None

    def classify(t):
        if t.status == 'completed':
            done_date = timezone.localtime(t.completed_at).date() if t.completed_at else None
            if done_date and done_date <= t.deadline_date:
                return 'ontime'
            return 'late'
        if t.deadline_date < today:
            return 'missed'
        return 'pending'

    ICON = {'ontime': '✅', 'late': '⏰', 'missed': '❌', 'pending': '⏳'}

    overall = {'ontime': 0, 'late': 0, 'missed': 0, 'pending': 0}
    groups = OrderedDict()
    for t in tasks:
        c = classify(t)
        wname = ", ".join(w.name for w in t.workers.all()) or '—'
        groups.setdefault(wname, []).append((t, c))

    def pct_of(counts):
        # Ishlash foizi = vaqtida / (vaqtida + kechikkan + bajarilmagan).
        # "kutilmoqda" (muddati kelmagan) hisobga olinmaydi. None = hali baholanmadi.
        base = counts['ontime'] + counts['late'] + counts['missed']
        return round(counts['ontime'] / base * 100) if base else None

    def counts_line(counts):
        return (f"✅ {counts['ontime']}   ⏰ {counts['late']}   "
                f"❌ {counts['missed']}   ⏳ {counts['pending']}")

    title = f"{_UZ_MONTHS[month - 1]} {year}" if (year and month) else "Barcha oylar"
    lines = [
        f"📜 <b>TARIX — {title.upper()}</b>",
        "<i>🗓 muddat → bajarilgan sana</i>",
        "━━━━━━━━━━━━━━━━━━",
        "",
    ]

    worker_list = list(groups.items())
    for idx, (wname, items) in enumerate(worker_list):
        wc = {'ontime': 0, 'late': 0, 'missed': 0, 'pending': 0}
        task_lines = []
        for t, c in items:
            wc[c] += 1
            overall[c] += 1
            dl = t.deadline_date.strftime('%d/%m')
            done = timezone.localtime(t.completed_at).strftime('%d/%m') if t.completed_at else '—'
            task_lines.append(f"{ICON[c]} <b>{t.description}</b>")
            task_lines.append(f"      🗓 {dl} → {done}")

        p = pct_of(wc)
        rate = f"📊 <b>{p}%</b>" if p is not None else "📊 <i>hali baholanmadi</i>"
        lines.append(f"👤 <b>{wname}</b>    {rate}")
        lines.append(counts_line(wc))
        lines.append("")
        lines.extend(task_lines)

        # Ishchilar orasiga ajratuvchi (oxirgisidan keyin qo'yilmaydi)
        if idx < len(worker_list) - 1:
            lines.append("")
            lines.append("┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
            lines.append("")

    if len(groups) > 1:
        p = pct_of(overall)
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append(f"📈 <b>UMUMIY:  {p}%</b>" if p is not None else "📈 <b>UMUMIY</b>")
        lines.append(counts_line(overall))
    return "\n".join(lines)


# ─────────── Yordamchi: sana parse ───────────
def parse_date(text):
    text = (text or '').strip()
    for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


# ─────────── ➕ Vazifa qo'shish (boshlash) ───────────
@router.message(F.text == "➕ Vazifa qo'shish")
async def bt_start(message: Message, state: FSMContext):
    boss = await get_boss(message.from_user.id)
    if not boss:
        return  # boshliq emas — e'tiborsiz
    await state.clear()
    await state.set_state(BossTaskState.waiting_for_text)
    await message.answer(
        "➕ <b>Yangi vazifa</b>\n\n"
        "Vazifa matnini yozing yoki 🎤 <b>ovozli xabar</b> yuboring "
        "(bot uni matnga aylantiradi).",
        parse_mode="HTML"
    )


async def _ask_worker(message: Message, state: FSMContext, text: str):
    """Matn tayyor — ishchi tanlash bosqichiga o'tadi."""
    workers = await get_assignable_workers()
    if not workers:
        await state.clear()
        await message.answer("Hozircha biriktiriladigan ishchi yo'q (Telegram ID li).")
        return
    await state.update_data(text=text)
    await state.set_state(BossTaskState.waiting_for_worker)
    await message.answer(
        f"📌 Vazifa: <b>{html.escape(text)}</b>\n\nKimga biriktiramiz?",
        parse_mode="HTML", reply_markup=kb.bt_workers_kb(workers)
    )


async def _handle_voice(message: Message, state: FSMContext, bot: Bot):
    """Ovozli xabarni matnga aylantirib, tasdiqlash uchun ko'rsatadi."""
    voice = message.voice or message.audio
    if not voice:
        return
    status = await message.answer("⏳ Ovoz matnga aylantirilmoqda...")
    ok, result = await transcribe_voice(bot, voice.file_id)
    try:
        await status.delete()
    except Exception:
        pass
    if not ok:
        await message.answer(
            f"❌ Ovozni matnga aylantirib bo'lmadi ({result}).\n\n"
            "Qayta ovoz yuboring yoki vazifa matnini yozib yuboring."
        )
        return
    await state.update_data(text=result)
    await state.set_state(BossTaskState.confirming_text)
    esc = html.escape(result)
    await message.answer(
        "🎤➡️📝 <b>Ovozdan olingan matn:</b>\n\n"
        f"<b>{esc}</b>\n\n"
        "✅ To'g'ri bo'lsa — «To'g'ri, davom» tugmasini bosing.\n"
        "✏️ Xato bo'lsa — pastdagi matnni <b>bosib nusxalang</b>, xato harflarni "
        "to'g'rilab qayta yuboring (yoki klaviaturada yangidan yozing):\n\n"
        f"<code>{esc}</code>",
        parse_mode="HTML", reply_markup=kb.bt_confirm_text_kb()
    )


@router.message(BossTaskState.waiting_for_text, F.voice | F.audio)
async def bt_got_voice(message: Message, state: FSMContext, bot: Bot):
    await _handle_voice(message, state, bot)


@router.message(BossTaskState.waiting_for_text, F.text)
async def bt_got_text(message: Message, state: FSMContext):
    text = (message.text or '').strip()
    # Menyu tugmasi bosildi — joriy oqimni bekor qilib, o'sha amalga o'tamiz
    if text in MENU_BUTTONS:
        await state.clear()
        if text == "➕ Vazifa qo'shish":
            return await bt_start(message, state)
        return await bt_history(message, state)
    if not text:
        await message.answer("Iltimos, vazifa matnini yozing yoki ovoz yuboring.")
        return
    await _ask_worker(message, state, text)


# ─────────── Ovozdan chiqqan matnni tasdiqlash / tuzatish ───────────
@router.callback_query(BossTaskState.confirming_text, F.data == "bt_txt:ok")
async def bt_txt_ok(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = (data.get('text') or '').strip()
    if not text:
        await callback.answer("Matn topilmadi, qayta yuboring.", show_alert=True)
        return
    await callback.answer()
    await _ask_worker(callback.message, state, text)


@router.callback_query(BossTaskState.confirming_text, F.data == "bt_txt:redo")
async def bt_txt_redo(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BossTaskState.waiting_for_text)
    data = await state.get_data()
    text = (data.get('text') or '').strip()
    await callback.answer()
    prompt = ("✏️ Tuzatib qayta yuboring — quyidagi matnni <b>bosib nusxalang</b>, "
              "xato harflarni to'g'rilab jo'nating (yoki klaviaturada yangidan yozing):")
    if text:
        prompt += f"\n\n<code>{html.escape(text)}</code>"
    try:
        await callback.message.edit_text(prompt, parse_mode="HTML")
    except Exception:
        await callback.message.answer(prompt, parse_mode="HTML")


@router.message(BossTaskState.confirming_text, F.voice | F.audio)
async def bt_confirm_voice(message: Message, state: FSMContext, bot: Bot):
    await _handle_voice(message, state, bot)


@router.message(BossTaskState.confirming_text, F.text)
async def bt_confirm_text_edit(message: Message, state: FSMContext):
    """Tasdiqlash bosqichida matn yozilsa — uni tuzatilgan yakuniy matn deb qabul qiladi."""
    text = (message.text or '').strip()
    if text in MENU_BUTTONS:
        await state.clear()
        if text == "➕ Vazifa qo'shish":
            return await bt_start(message, state)
        return await bt_history(message, state)
    if not text:
        return
    await _ask_worker(message, state, text)


# ─────────── Ishchi tanlandi ───────────
@router.callback_query(BossTaskState.waiting_for_worker, F.data.startswith("bt_wrk:"))
async def bt_pick_worker(callback: CallbackQuery, state: FSMContext):
    worker_id = int(callback.data.split(":")[1])
    w = await get_worker(worker_id)
    if not w:
        await callback.answer("Ishchi topilmadi!", show_alert=True)
        return
    await state.update_data(worker_id=worker_id, worker_name=w.name)
    await state.set_state(BossTaskState.waiting_for_deadline)
    await callback.message.edit_text(
        f"👤 Ishchi: <b>{w.name}</b>\n\nMuddat (deadline) ni tanlang:",
        parse_mode="HTML", reply_markup=kb.bt_deadline_kb()
    )
    await callback.answer()


# ─────────── Deadline: tez tugmalar / kalendar / qo'lda ───────────
@router.callback_query(BossTaskState.waiting_for_deadline, F.data.startswith("bt_dl:"))
async def bt_deadline_choice(callback: CallbackQuery, state: FSMContext, bot: Bot):
    choice = callback.data.split(":")[1]
    today = date.today()

    quick = {'today': today, 'tomorrow': today + timedelta(days=1),
             'plus3': today + timedelta(days=3), 'week': today + timedelta(days=7)}

    if choice in quick:
        await callback.answer()
        await _finalize(callback, state, bot, quick[choice])
    elif choice == 'cal':
        await callback.message.edit_text(
            "📅 Sanani tanlang:", reply_markup=kb.bt_calendar_kb(today.year, today.month)
        )
        await callback.answer()
    elif choice == 'manual':
        await state.set_state(BossTaskState.waiting_for_manual_date)
        await callback.message.edit_text(
            "✍️ Sanani yozing (masalan: <b>25.09.2026</b>):", parse_mode="HTML"
        )
        await callback.answer()


# ─────────── Kalendar: navigatsiya / tanlash ───────────
@router.callback_query(F.data == "bt_cal:ignore")
async def bt_cal_ignore(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("bt_cal:nav:"))
async def bt_cal_nav(callback: CallbackQuery):
    _, _, y, m = callback.data.split(":")
    await callback.message.edit_reply_markup(reply_markup=kb.bt_calendar_kb(int(y), int(m)))
    await callback.answer()


@router.callback_query(BossTaskState.waiting_for_deadline, F.data.startswith("bt_cal:pick:"))
async def bt_cal_pick(callback: CallbackQuery, state: FSMContext, bot: Bot):
    ds = callback.data.split(":", 2)[2]
    picked = parse_date(ds)
    if not picked:
        await callback.answer("Sana xato!", show_alert=True)
        return
    await callback.answer()
    await _finalize(callback, state, bot, picked)


# ─────────── Qo'lda sana kiritish ───────────
@router.message(BossTaskState.waiting_for_manual_date)
async def bt_manual_date(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or '').strip()
    if text in MENU_BUTTONS:
        await state.clear()
        if text == "➕ Vazifa qo'shish":
            return await bt_start(message, state)
        return await bt_history(message, state)
    picked = parse_date(message.text)
    if not picked:
        await message.answer("❌ Sana formati noto'g'ri. Masalan: <b>25.09.2026</b>", parse_mode="HTML")
        return
    if picked < date.today():
        await message.answer("⚠️ O'tgan sanani kiritdingiz. Bugungi yoki keyingi sanani yozing.")
        return
    await _finalize(message, state, bot, picked)


# ─────────── Bekor qilish ───────────
@router.callback_query(F.data == "bt_cancel")
async def bt_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text("✖️ Bekor qilindi.")
    except Exception:
        pass
    await callback.answer()


# ─────────── Yakunlash: vazifani yaratish va ishchiga yuborish ───────────
async def _finalize(event, state: FSMContext, bot: Bot, deadline_date):
    """event — Message yoki CallbackQuery bo'lishi mumkin."""
    data = await state.get_data()
    text = data.get('text')
    worker_id = data.get('worker_id')
    from_user = event.from_user

    boss = await get_boss(from_user.id)
    if not boss or not text or not worker_id:
        await state.clear()
        return

    task_id, worker_name, worker_tg = await create_boss_task(
        text, worker_id, deadline_date, boss.id
    )
    dl_str = deadline_date.strftime('%d.%m.%Y')
    esc_text = html.escape(text)

    # Ishchiga darrov — "Boshliqdan topshiriq" banneri bilan
    delivered = False
    if worker_tg:
        worker_msg = (
            "👔 <b>BOSHLIQDAN SHAXSIY TOPSHIRIQ</b>\n"
            f"📨 Yubordi: <b>{html.escape(boss.name)}</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>Vazifa:</b> {esc_text}\n"
            f"⏳ <b>Muddat:</b> {dl_str}"
        )
        try:
            sent = await bot.send_message(
                chat_id=worker_tg, text=worker_msg,
                parse_mode="HTML", reply_markup=kb.task_done_kb(task_id)
            )
            await log_notification(task_id, worker_tg, sent.message_id)
            delivered = True
        except Exception as e:
            print(f"Boshliq topshirig'ini yuborish xatosi: {e}")

    await state.clear()

    confirm = (
        "✅ <b>Vazifa biriktirildi!</b>\n\n"
        f"👤 Ishchi: <b>{html.escape(worker_name)}</b>\n"
        f"📌 Vazifa: <b>{esc_text}</b>\n"
        f"⏳ Muddat: <b>{dl_str}</b>\n\n"
        + ("📨 Ishchiga yuborildi." if delivered
           else "⚠️ Ishchiga yuborilmadi (Telegram ID topilmadi yoki bloklagan).")
    )
    # CallbackQuery bo'lsa xabarni tahrirlaymiz, Message bo'lsa yangi javob
    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(confirm, parse_mode="HTML")
        except Exception:
            await event.message.answer(confirm, parse_mode="HTML")
    else:
        await event.answer(confirm, parse_mode="HTML")


# ─────────── 📜 Tarix — avval oy so'raladi ───────────
@router.message(F.text == "📜 Tarix")
async def bt_history(message: Message, state: FSMContext = None):
    boss = await get_boss(message.from_user.id)
    if not boss:
        return
    if state is not None:
        await state.clear()
    await message.answer(
        "📜 <b>Tarix</b>\n\nQaysi oy statistikasini ko'rmoqchisiz?",
        parse_mode="HTML", reply_markup=kb.bt_history_months_kb()
    )


@router.callback_query(F.data.startswith("bt_hist:"))
async def bt_history_show(callback: CallbackQuery):
    boss = await get_boss(callback.from_user.id)
    if not boss:
        await callback.answer()
        return
    arg = callback.data.split(":", 1)[1]
    if arg == 'all':
        text = await build_history(boss.id)
        empty = "📭 Hali biriktirilgan topshiriq yo'q."
    else:
        y, m = arg.split("-")
        text = await build_history(boss.id, int(y), int(m))
        empty = "📭 Bu oyda topshiriq yo'q."
    await callback.answer()
    try:
        await callback.message.edit_text(text or empty, parse_mode="HTML",
                                         reply_markup=kb.bt_history_months_kb())
    except Exception:
        await callback.message.answer(text or empty, parse_mode="HTML")
