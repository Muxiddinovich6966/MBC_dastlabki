"""
Ishchilar boti — ishchi tomoni oqimi.
"Aktiv vazifalar" → tadbir → vazifa → Bajardim → instruksiya → isbot → Tayyor → boshliqqa hisobot.
"""
import html
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async

from .states import ProofState
from . import keyboards as kb

router = Router()


# ─────────── ORM yordamchilari ───────────
@sync_to_async
def get_worker(tg_id):
    from apps.workers.models import Worker
    return Worker.objects.filter(telegram_id=tg_id).first()


@sync_to_async
def get_events_with_pending_tasks(worker_tg_id):
    """Shu ishchiga tayinlangan, bajarilmagan vazifasi bor tadbirlar."""
    from apps.workers.models import Task, WorkEvent
    worker = _worker_by_tg(worker_tg_id)
    if not worker:
        return []
    event_ids = (Task.objects
                 .filter(workers=worker, status__in=['pending', 'overdue'])
                 .values_list('event_id', flat=True).distinct())
    return list(WorkEvent.objects.filter(id__in=list(event_ids)).order_by('event_date'))


def _worker_by_tg(tg_id):
    from apps.workers.models import Worker
    return Worker.objects.filter(telegram_id=tg_id).first()


@sync_to_async
def get_pending_tasks_for_event(event_id, worker_tg_id):
    from apps.workers.models import Task
    worker = _worker_by_tg(worker_tg_id)
    if not worker:
        return []
    return list(Task.objects
                .filter(event_id=event_id, workers=worker, status__in=['pending', 'overdue'])
                .select_related('event'))


@sync_to_async
def get_task(task_id):
    from apps.workers.models import Task
    return Task.objects.filter(id=task_id).select_related('event').first()


@sync_to_async
def complete_task(task_id, completed_by_tg_id=None):
    """Vazifani ATOMIK ravishda 'bajarildi' qiladi.

    Faqat hali bajarilmagan bo'lsa yangilaydi (WHERE status != 'completed').
    Qaytadi: 1 — aynan biz bajardik; 0 — allaqachon boshqa ishchi bajargan.
    Bir vazifa bir nechta ishchiga biriktirilib, hammasi bir vaqtda bosganda
    faqat birinchisi yutadi — qolganlari 0 oladi.
    """
    from apps.workers.models import Task, Worker
    worker = (Worker.objects.filter(telegram_id=completed_by_tg_id).first()
              if completed_by_tg_id else None)
    return (Task.objects.filter(id=task_id)
            .exclude(status='completed')
            .update(status='completed', completed_by=worker))


@sync_to_async
def get_notification_logs(task_id):
    from apps.workers.models import NotificationLog
    return list(NotificationLog.objects.filter(task_id=task_id))


@sync_to_async
def delete_notification_logs(task_id):
    from apps.workers.models import NotificationLog
    NotificationLog.objects.filter(task_id=task_id).delete()


@sync_to_async
def get_boss_and_admin_ids():
    from apps.workers.models import Worker
    return list(Worker.objects
                .filter(role__in=['boss', 'admin'])
                .values_list('telegram_id', flat=True))


@sync_to_async
def log_task_message(task_id, chat_id, message_id):
    """'Aktiv vazifalar' orqali chiqarilgan xabarni jurnalga yozadi.
    Shunda tadbir tahrirlanganda bu xabar ham o'chiriladi."""
    from apps.workers.models import NotificationLog
    NotificationLog.objects.create(task_id=task_id, chat_id=chat_id, message_id=message_id)


# ─────────── "Aktiv vazifalar" ───────────
@router.message(F.text == "📝 Aktiv vazifalar")
async def show_active_tasks(message: Message):
    wait_msg = await message.answer("⏳ <i>Tadbir ro'yxati yuklanmoqda...</i>", parse_mode="HTML")

    events = await get_events_with_pending_tasks(message.from_user.id)

    if not events:
        await wait_msg.edit_text(
            "Hozircha sizda bajarilmagan vazifalar mavjud emas. Dam olishingiz mumkin! 😎"
        )
        return

    await wait_msg.edit_text(
        "Aktiv vazifalari bor tadbirlar:\nQaysi tadbirning vazifalarini ko'rmoqchisiz?",
        reply_markup=kb.active_events_kb(events)
    )


@router.callback_query(F.data.startswith("we_event_"))
async def process_event_selection(callback: CallbackQuery):
    event_id = int(callback.data.split("_")[2])
    tasks = await get_pending_tasks_for_event(event_id, callback.from_user.id)

    if not tasks:
        await callback.answer("Bu tadbirda aktiv vazifalar yo'q!", show_alert=True)
        return

    await callback.message.delete()

    for t in tasks:
        overdue = "⚠️ <b>(MUDDATI O'TGAN)</b> " if t.status == 'overdue' else ""
        text = (
            f"🎉 <b>Tadbir:</b> {t.event.name}\n"
            f"📌 <b>Vazifa:</b> {t.description}\n"
            f"⏳ <b>Muddati:</b> {t.deadline_date} {overdue}"
        )
        sent = await callback.message.answer(text, reply_markup=kb.task_done_kb(t.id), parse_mode="HTML")
        # Xabarni jurnalga yozamiz — tadbir tahrirlanganda o'chirilishi uchun
        await log_task_message(t.id, sent.chat.id, sent.message_id)

    await callback.answer()


# ─────────── "Bajardim" ───────────
@router.callback_query(F.data.startswith("we_done_"))
async def process_task_done(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == ProofState.waiting_for_proof.state:
        await callback.answer("⚠️ Avval joriy vazifaning isbotini yuboring!", show_alert=True)
        return

    task_id = int(callback.data.split("_")[2])
    task = await get_task(task_id)

    if not task:
        await callback.answer("Vazifa topilmadi!", show_alert=True)
        return
    if task.status == 'completed':
        await callback.answer("Bu vazifa allaqachon bajarilgan!", show_alert=True)
        return

    if task.instruction:
        await state.update_data(
            proof_task_id=task_id,
            proof_original_message_id=callback.message.message_id,
            proof_chat_id=callback.message.chat.id,
            proof_message_ids=[],
            isbot_request_message_id=None,
        )
        await state.set_state(ProofState.waiting_for_instruction)

        original_text = callback.message.html_text
        safe_instruction = html.escape(task.instruction)
        new_text = f"{original_text}\n\n📋 <b>Instruksiya:</b>\n\n{safe_instruction}"
        await callback.message.edit_text(
            text=new_text, parse_mode="HTML",
            reply_markup=kb.task_confirm_kb(task_id)
        )
        await callback.answer()
    else:
        # Instruksiya yo'q — "Bajardim" tugmasini darrov olib tashlaymiz,
        # so'ng isbot so'raymiz (tugma isbot/Tayyorni kutib turmaydi).
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await state.update_data(
            proof_task_id=task_id,
            proof_original_message_id=callback.message.message_id,
            proof_chat_id=callback.message.chat.id,
            proof_message_ids=[],
        )
        await state.set_state(ProofState.waiting_for_proof)
        msg = await callback.message.answer(
            "📎 Isbotlarni yuboring!\n\nTugatgach — <b>✅ Tayyor</b> tugmasini bosing.",
            parse_mode="HTML", reply_markup=kb.proof_done_kb()
        )
        await state.update_data(isbot_request_message_id=msg.message_id)


# ─────────── "Tasdiqlash" (instruksiyadan keyin) ───────────
@router.callback_query(F.data.startswith("we_confirm_"))
async def process_task_confirm(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == ProofState.waiting_for_proof.state:
        await callback.answer("⚠️ Avval joriy vazifaning isbotini yuboring!", show_alert=True)
        return

    task_id = int(callback.data.split("_")[2])
    task = await get_task(task_id)
    if not task:
        await callback.answer("Vazifa topilmadi!", show_alert=True)
        return
    if task.status == 'completed':
        # Bir vaqtda bosilib, boshqa ishchi allaqachon bajargan bo'lishi mumkin.
        await callback.answer("Bu vazifa allaqachon bajarilgan!", show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    msg = await callback.message.answer(
        "📎 Isbotlarni yuboring!\n\n"
        "Rasm, fayl, matn yuborishingiz mumkin. Bir nechta ham bo'ladi.\n\n"
        "Yuborib bo'lgach <b>✅ Tayyor</b> tugmasini bosing.",
        parse_mode="HTML", reply_markup=kb.proof_done_kb()
    )
    await state.update_data(
        proof_task_id=task_id,
        proof_original_message_id=callback.message.message_id,
        proof_chat_id=callback.message.chat.id,
        proof_message_ids=[],
        isbot_request_message_id=msg.message_id,
    )
    await state.set_state(ProofState.waiting_for_proof)
    await callback.answer()


# ─────────── Isbot xabarlarini yig'ish ───────────
@router.message(ProofState.waiting_for_proof)
async def process_proof_message(message: Message, state: FSMContext):
    data = await state.get_data()
    proof_ids = data.get('proof_message_ids', [])
    proof_ids.append(message.message_id)
    await state.update_data(proof_message_ids=proof_ids, proof_chat_id=message.chat.id)


# ─────────── "Tayyor" — yakunlash ───────────
@router.callback_query(ProofState.waiting_for_proof, F.data == "we_proof_done")
async def process_proof_done(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    task_id = data.get('proof_task_id')
    proof_ids = data.get('proof_message_ids', [])
    proof_chat_id = data.get('proof_chat_id')
    isbot_req_id = data.get('isbot_request_message_id')
    original_msg_id = data.get('proof_original_message_id')

    if not proof_ids:
        await callback.answer("Iltimos, avval isbot yuboring!", show_alert=True)
        return

    task = await get_task(task_id)
    if not task:
        await callback.answer("Vazifa topilmadi!", show_alert=True)
        return

    event_name = task.event.name
    worker_name = callback.from_user.full_name

    # Vazifani bajarildi deb belgilash (kim bajarganini ham saqlaymiz) — ATOMIK.
    just_completed = await complete_task(task_id, callback.from_user.id)
    if not just_completed:
        # Bir vaqtda bosilgan — boshqa ishchi allaqachon bajargan.
        # Bu ishchining isbot so'rovi va "Tayyor" tugmasini tozalab, to'xtaymiz
        # (xabarlarni qayta tahrirlamaymiz, boshliqqa takror hisobot yubormaymiz).
        if isbot_req_id:
            try:
                await bot.delete_message(chat_id=proof_chat_id, message_id=isbot_req_id)
            except Exception:
                pass
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer(
            "Bu vazifa allaqachon boshqa ishchi tomonidan bajarilgan!", show_alert=True
        )
        await state.clear()
        return

    # Shu vazifaga tegishli BARCHA xabarlarni yangilaymiz — ya'ni boshqa
    # biriktirilgan ishchilar (B) va boshliqning xabarlari ham. Tugma yo'qoladi
    # va "Bajardi: A" deb ko'rsatiladi.
    logs = await get_notification_logs(task_id)
    for log in logs:
        try:
            new_text = (
                f"✅ <b>Vazifa Bajarildi!</b>\n\n"
                f"🎉 Tadbir: <b>{event_name}</b>\n"
                f"📌 Vazifa: <b>{task.description}</b>\n"
                f"👤 Bajardi: <b>{worker_name}</b>\n"
                f"📊 Holati: ✅ Bajarildi"
            )
            await bot.edit_message_text(
                chat_id=log.chat_id, message_id=log.message_id,
                text=new_text, parse_mode="HTML"
            )
        except Exception as e:
            print(f"Xabarni yangilashda xatolik: {e}")

    await delete_notification_logs(task_id)

    # Admin va boshliqqa isbotni forward qilish
    notify_text = (
        f"✅ <b>Vazifa Bajarildi!</b>\n\n"
        f"👤 Ishchi: <b>{worker_name}</b>\n"
        f"🎉 Tadbir: <b>{event_name}</b>\n"
        f"📌 Vazifa: <b>{task.description}</b>\n\n"
        f"📎 Isbot:"
    )
    notify_ids = await get_boss_and_admin_ids()
    for uid in set(notify_ids):
        try:
            await bot.send_message(chat_id=uid, text=notify_text, parse_mode="HTML")
            for mid in proof_ids:
                await bot.forward_message(chat_id=uid, from_chat_id=proof_chat_id, message_id=mid)
        except Exception as e:
            print(f"Xabar yuborishda xatolik: {e}")

    # Isbot so'ragan xabarni o'chirish
    if isbot_req_id:
        try:
            await bot.delete_message(chat_id=proof_chat_id, message_id=isbot_req_id)
        except Exception:
            pass

    # "Tayyor" tugmasi xabarini o'chirish
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Original vazifa xabarini "Bajarildi" deb yangilash
    if original_msg_id:
        try:
            await bot.edit_message_text(
                chat_id=proof_chat_id, message_id=original_msg_id,
                text=(
                    f"✅ <b>Vazifa bajarildi!</b>\n\n"
                    f"🎉 Tadbir: <b>{event_name}</b>\n"
                    f"📌 Vazifa: <b>{task.description}</b>\n"
                    f"⏳ Deadline: <b>{task.deadline_date}</b>\n"
                    f"👤 Bajargan: <b>{worker_name}</b>\n"
                    f"🕐 Vaqt: <b>{datetime.now().strftime('%Y-%m-%d %H:%M')}</b>"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Original xabarni yangilashda xatolik: {e}")

    await bot.send_message(chat_id=proof_chat_id, text="✅ <b>Isbot yuborildi!</b>", parse_mode="HTML")
    await callback.answer("Vazifa bajarildi!", show_alert=True)
    await state.clear()