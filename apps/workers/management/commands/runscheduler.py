"""
Avtomatik vazifalar (scheduler).
Ishga tushirish:  python manage.py runscheduler

4 ta vazifani bajaradi (har daqiqada / har kuni tekshiradi):
  1. Tadbirni send_at vaqti kelganda avtomatik yuborish
  2. Tadbir eslatmalari (T-7, T-3, T-1 kun oldin)
  3. Obuna muddati tugaganda foydalanuvchini kanaldan chiqarish
  4. Ishchi vazifasi eslatmasi (deadline yaqinlashganda)
"""
import logging
from datetime import timedelta, date

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("scheduler")


# ─────────────────────────────────────────────
# 1. Tadbirni send_at vaqtida avtomatik yuborish
# ─────────────────────────────────────────────
def job_send_scheduled_events():
    from apps.events.models import Event
    from config.bot_notify import send_event_to_all

    now = timezone.now()
    events = Event.objects.filter(sent=False, send_at__isnull=False, send_at__lte=now, is_active=True)

    for event in events:
        try:
            image_path = event.image.path if event.image else None
            sent = send_event_to_all(event, image_path=image_path)
            event.sent = True
            event.save(update_fields=['sent'])
            log.info(f"[Avtomatik yuborildi] '{event.name}' — {sent} ta foydalanuvchiga")
        except Exception as e:
            log.error(f"[Tadbir yuborish xatosi] {event.name}: {e}")


# ─────────────────────────────────────────────
# 2. Tadbir eslatmalari (T-7, T-3, T-1 kun)
# ─────────────────────────────────────────────
def job_event_reminders():
    from apps.events.models import EventReminder
    from config.bot_notify import send_telegram_message
    from apps.users.models import User

    now = timezone.now()
    reminders = EventReminder.objects.filter(sent=False, remind_at__lte=now).select_related('event')

    for reminder in reminders:
        try:
            event = reminder.event
            text = (
                f"⏰ <b>Eslatma!</b>\n\n"
                f"🎉 <b>{event.name}</b>\n"
                f"📅 {event.date} soat {event.time}\n"
                f"📍 {event.location}\n\n"
                f"{reminder.label}"
            )
            users = User.objects.filter(role='user', is_active=True).exclude(tg_id__isnull=True).exclude(tg_id='')
            count = 0
            for user in users:
                if send_telegram_message(user.tg_id, text):
                    count += 1
            reminder.sent = True
            reminder.save(update_fields=['sent'])
            log.info(f"[Eslatma yuborildi] '{event.name}' — {count} ta foydalanuvchiga")
        except Exception as e:
            log.error(f"[Eslatma xatosi] {e}")


# ─────────────────────────────────────────────
# 3. Obuna muddati tugaganda kanal va guruhdan chiqarish
# ─────────────────────────────────────────────
def job_expired_subscriptions():
    from apps.users.models import UserPlan
    from config.bot_notify import ban_from_channel, send_telegram_message

    channel_id = getattr(settings, 'PRIVATE_CHANNEL_ID', '')
    group_id = getattr(settings, 'PRIVATE_GROUP_ID', '')

    if not channel_id and not group_id:
        return  # Hech qaysi joy sozlanmagan

    today = date.today()
    expired = UserPlan.objects.filter(end_date__lt=today).select_related('user')

    processed_users = set()
    for plan in expired:
        user = plan.user
        if user.id in processed_users:
            continue
        # Boshqa faol (tugamagan) obunasi bormi
        has_active = UserPlan.objects.filter(user=user, end_date__gte=today).exists()
        if has_active:
            continue
        try:
            if user.tg_id:
                # Kanal va guruhdan alohida chiqaramiz (har birini alohida log qilamiz)
                removed = False
                if channel_id:
                    ok = ban_from_channel(channel_id, user.tg_id)
                    natija = "OK" if ok else "a'zo emas yoki xato"
                    log.info(f"[Obuna tugadi] {user} kanaldan chiqarish: {natija}")
                    removed = removed or ok
                if group_id:
                    ok = ban_from_channel(group_id, user.tg_id)
                    natija = "OK" if ok else "a'zo emas yoki xato"
                    log.info(f"[Obuna tugadi] {user} guruhdan chiqarish: {natija}")
                    removed = removed or ok

                if removed:
                    send_telegram_message(
                        user.tg_id,
                        "⚠️ Obunangiz muddati tugadi. Yopiq kanal va guruhdan chiqarildingiz.\n\n"
                        "Qayta a'zo bo'lish uchun administrator bilan bog'laning."
                    )
                    log.info(f"[Obuna tugadi] {user} kanal/guruhdan chiqarildi")
                else:
                    log.info(f"[Obuna tugadi] {user} — obunasi tugagan, lekin kanal/guruhda a'zo emas edi")
            processed_users.add(user.id)
        except Exception as e:
            log.error(f"[Ban xatosi] {user}: {e}")
# ─────────────────────────────────────────────
# 5. Obuna tugashiga oz qolganda ogohlantirish (14/10/5/3/0 kun)
# ─────────────────────────────────────────────
def job_subscription_warning():
    from apps.users.models import UserPlan
    from config.bot_notify import send_subscription_warning
    from datetime import date, timedelta

    today = date.today()
    warn_days = [14, 10, 5, 3, 0]

    for days in warn_days:
        target_date = today + timedelta(days=days)
        plans = UserPlan.objects.filter(end_date=target_date).select_related('user')

        for plan in plans:
            user = plan.user
            if not user.tg_id:
                continue
            has_later = UserPlan.objects.filter(user=user, end_date__gt=plan.end_date).exists()
            if has_later:
                continue
            try:
                send_subscription_warning(user.tg_id, plan.end_date, days)
                log.info(f"[Ogohlantirish] {user} - {days} kun qoldi")
            except Exception as e:
                log.error(f"[Ogohlantirish xatosi] {user}: {e}")

# ─────────────────────────────────────────────
# Kechikkan vazifa — boshliq, admin va ishchiga xabar
# ─────────────────────────────────────────────
def job_delayed_tasks():
    from apps.workers.models import Task, Worker
    from config.bot_notify import send_worker_bot_message

    today = date.today()

    # Deadline o'tgan, hali bajarilmagan vazifalar
    delayed = Task.objects.filter(
        deadline_date__lt=today, status='pending'
    ).select_related('worker', 'event')

    if not delayed.exists():
        return

    # Xabar oluvchilar: boshliq va admin
    notify_users = list(
        Worker.objects.filter(role__in=['boss', 'admin']).exclude(telegram_id__isnull=True)
    )

    for task in delayed:
        worker_name = task.worker.name if task.worker else "Noma'lum"

        # 1. Boshliq va adminga xabar
        boss_text = (
            "⚠️ <b>DIQQAT! Ishchi quyidagi vazifani vaqtida bajarmadi!</b>\n\n"
            f"🧑‍🔧 Ishchi: <b>{worker_name}</b>\n"
            f"🎉 Tadbir: <b>{task.event.name}</b>\n"
            f"📌 Vazifa: <b>{task.description}</b>\n"
            f"📅 Kechikkan sana: <b>{task.deadline_date}</b>"
        )
        for user in notify_users:
            try:
                send_worker_bot_message(user.telegram_id, boss_text)
            except Exception as e:
                log.error(f"[Boss/Admin xabar xatosi] {e}")

        # 2. Ishchiga ogohlantirish (Bajardim tugmasi yo'q)
        if task.worker and task.worker.telegram_id:
            worker_text = (
                "⚠️ <b>DIQQAT!</b> Siz quyidagi vazifani vaqtida bajarmadingiz!\n\n"
                f"🎉 Tadbir: <b>{task.event.name}</b>\n"
                f"📌 Vazifa: <b>{task.description}</b>\n"
                f"📅 Kechikkan sana: <b>{task.deadline_date}</b>\n\n"
                "Iltimos, tezroq bajaring! \"📝 Aktiv vazifalar\" bo'limidan topishingiz mumkin."
            )
            try:
                send_worker_bot_message(task.worker.telegram_id, worker_text)
            except Exception as e:
                log.error(f"[Ishchiga xabar xatosi] {e}")

        # Statusni overdue ga o'zgartiramiz (qayta xabar bermaslik uchun)
        task.status = 'overdue'
        task.save(update_fields=['status'])
        log.info(f"[Kechikkan vazifa] {task.description} — {worker_name}")

# ─────────────────────────────────────────────
# 4b. Deadline bugun — ishchiga eslatma
# ─────────────────────────────────────────────
def job_upcoming_deadlines():
    from apps.workers.models import Task
    from config.bot_notify import send_worker_bot_message

    today = date.today()
    tasks = Task.objects.filter(
        deadline_date=today, status='pending', reminder_sent=False
    ).select_related('worker', 'event')

    for task in tasks:
        if not task.worker or not task.worker.telegram_id:
            continue
        hours_str = f" ({task.hours_before} soat oldin)" if task.hours_before else ""
        text = (
            "⏰ <b>Eslatma!</b> Bugun vazifa muddati!\n\n"
            f"🎉 Tadbir: <b>{task.event.name}</b>\n"
            f"📌 Vazifa: <b>{task.description}</b>\n"
            f"⏳ Deadline: <b>{task.deadline_date}</b>{hours_str}\n\n"
            "Iltimos, bugun bajarishni unutmang!"
        )
        keyboard = {"inline_keyboard": [[
            {"text": "✅ Bajardim", "callback_data": f"we_done_{task.id}"}
        ]]}
        import json
        try:
            send_worker_bot_message(
                task.worker.telegram_id, text,
                reply_markup=json.dumps(keyboard)
            )
            task.reminder_sent = True
            task.save(update_fields=['reminder_sent'])
            log.info(f"[Deadline eslatmasi] {task.worker.name} — {task.description}")
        except Exception as e:
            log.error(f"[Deadline eslatma xatosi] {e}")


# ─────────────────────────────────────────────
# 4c. Tadbirdan 2 soat oldin — ishchiga eslatma
# ─────────────────────────────────────────────
def job_event_time_reminders():
    from apps.workers.models import WorkEvent, Task
    from config.bot_notify import send_worker_bot_message

    now = timezone.localtime()  # Asia/Tashkent (USE_TZ=True) — server OS UTC bo'lsa ham to'g'ri soat
    today = now.date()
    current_hour = now.hour

    events = WorkEvent.objects.filter(event_date=today)
    for event in events:
        if not event.event_time:
            continue
        try:
            event_hour = event.event_time.hour if hasattr(event.event_time, 'hour') else int(str(event.event_time).split(':')[0])
        except Exception:
            continue

        # Tadbirdan aynan 2 soat oldin
        if current_hour != event_hour - 2:
            continue

        tasks = Task.objects.filter(
            event=event, status='pending', time_reminder_sent=False
        ).select_related('worker')
        for task in tasks:
            if not task.worker or not task.worker.telegram_id:
                continue
            event_time_str = event.event_time.strftime('%H:%M') if hasattr(event.event_time, 'strftime') else str(event.event_time)
            text = (
                "🔔 <b>Diqqat!</b> Tadbir 2 soatdan keyin boshlanadi!\n\n"
                f"🎉 Tadbir: <b>{event.name}</b>\n"
                f"🕐 Tadbir vaqti: <b>{event_time_str}</b>\n\n"
                f"📌 Sizning vazifangiz: <b>{task.description}</b>\n"
                f"⏳ Deadline: {task.deadline_date}"
            )
            keyboard = {"inline_keyboard": [[
                {"text": "✅ Bajardim", "callback_data": f"we_done_{task.id}"}
            ]]}
            import json
            try:
                send_worker_bot_message(
                    task.worker.telegram_id, text,
                    reply_markup=json.dumps(keyboard)
                )
                task.time_reminder_sent = True
                task.save(update_fields=['time_reminder_sent'])
                log.info(f"[Tadbir 2 soat] {task.worker.name} — {task.description}")
            except Exception as e:
                log.error(f"[Tadbir eslatma xatosi] {e}")

class Command(BaseCommand):
    help = "Avtomatik vazifalar schedulerini ishga tushiradi"

    def handle(self, *args, **options):
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BlockingScheduler(timezone=str(timezone.get_current_timezone()))

        # Har daqiqada — tadbir yuborish va eslatmalar
        scheduler.add_job(job_send_scheduled_events, IntervalTrigger(minutes=1), id='send_events')
        scheduler.add_job(job_event_reminders, IntervalTrigger(minutes=1), id='event_reminders')
        # Ishchilar boti eslatmalari
        scheduler.add_job(job_delayed_tasks, IntervalTrigger(minutes=1), id='delayed_tasks')
        scheduler.add_job(job_upcoming_deadlines, IntervalTrigger(minutes=1), id='deadline_reminders')
        scheduler.add_job(job_event_time_reminders, IntervalTrigger(minutes=1), id='event_time_reminders')

        # Obuna tekshiruvi — har kuni kechasi 00:00 (ban va ogohlantirish xabarlari kunda 1 marta)
        scheduler.add_job(job_expired_subscriptions, CronTrigger(hour=0, minute=0), id='expired_subs')
        scheduler.add_job(job_subscription_warning, CronTrigger(hour=0, minute=0), id='sub_warning')

        self.stdout.write(self.style.SUCCESS("Scheduler ishga tushdi. To'xtatish: Ctrl+C"))
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.stdout.write(self.style.WARNING("Scheduler to'xtatildi."))