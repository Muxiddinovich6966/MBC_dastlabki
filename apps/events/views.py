"""
Tadbirlar bilan ishlash: ro'yxat, qo'shish, ko'rish, o'chirish, yuborish.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Event, UserEvent, Venue, EventSendLog, Lead, LeadStatusLog, CalendarEvent
from apps.groups.models import Group
from apps.users.models import User


@login_required(login_url='/login/')
def events_list(request):
    """Tadbirlar ro'yxati + yangi tadbir qo'shish (ishchilar tadbiridan tanlanadi)."""
    from apps.workers.models import WorkEvent
    from datetime import date, datetime, time as time_cls

    if request.method == 'POST':
        venue_id = request.POST.get('venue_id')
        venue = Venue.objects.filter(pk=venue_id).first() if venue_id else None

        # Nomi, sanasi va vaqti ishchilar tadbiridan olinadi (majburiy tanlov)
        work_event_id = request.POST.get('work_event_id')
        work_event = WorkEvent.objects.filter(pk=work_event_id).first() if work_event_id else None

        if not work_event:
            messages.error(request, "Iltimos, ishchilar tadbirini tanlang.")
            return redirect('events_list')

        # Sana majburiy (ishchilar tadbiridan olinadi)
        if not work_event.event_date:
            messages.error(request, "Iltimos, sanani kiriting (tanlangan ishchilar tadbirida sana yo'q).")
            return redirect('events_list')

        # Vaqt ham ishchilar tadbiridan olinadi (nom va sana kabi — qo'lda kiritilmaydi)
        if not work_event.event_time:
            messages.error(request, "Tanlangan ishchilar tadbirida vaqt yo'q. Avval ishchilar tadbiriga vaqt qo'shing.")
            return redirect('events_list')
        event_time = work_event.event_time.strftime('%H:%M')

        # Kamida bitta nishon: guruh/kanal YOKI "hamma foydalanuvchi".
        group_ids = request.POST.getlist('send_groups')
        if not group_ids and 'send_to_all_users' not in request.POST:
            messages.error(request, "Kamida bir guruh/kanal tanlang yoki "
                                    "\"Hamma foydalanuvchiga yuborilsin\" ni yoqing.")
            return redirect('events_list')

        event = Event.objects.create(
            name=work_event.name,
            date=work_event.event_date.strftime('%Y-%m-%d'),
            theme=request.POST.get('theme', ''),
            description=request.POST.get('description'),
            time=event_time,
            venue=venue,
            location=venue.name if venue else '',
            latitude=venue.latitude if venue else '',
            longitude=venue.longitude if venue else '',
            speaker=request.POST.get('speaker', ''),
            category=request.POST.get('category', 'other'),
            send_to_all_users='send_to_all_users' in request.POST,
        )

        if 'image' in request.FILES:
            event.image = request.FILES['image']
            event.save()

        event.send_groups.set(group_ids)

        messages.success(request, "Tadbir qo'shildi.")
        return redirect('events_list')

    def _parse_event_dt(e):
        """Event.date (+time) ni datetime ga aylantiradi. Xato/bo'sh bo'lsa None."""
        d = None
        for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d-%m-%Y'):
            try:
                d = datetime.strptime((e.date or '').strip(), fmt).date()
                break
            except (ValueError, TypeError):
                continue
        if not d:
            return None
        t = None
        for tf in ('%H:%M', '%H:%M:%S'):
            try:
                t = datetime.strptime((e.time or '').strip(), tf).time()
                break
            except (ValueError, TypeError):
                continue
        return datetime.combine(d, t or time_cls.min)

    now = datetime.now()
    all_events = list(
        Event.objects.select_related('work_event').prefetch_related('responses', 'send_groups')
    )
    for e in all_events:
        e.event_dt = _parse_event_dt(e)
        # Sanasi o'tgan bo'lsa — o'tib ketgan (nofaol); aks holda kelajakdagi (faol)
        e.is_past = bool(e.event_dt and e.event_dt < now)

    # Kelajakdagilar: eng yaqin sana tepada. O'tganlar: eng yaqin o'tgan tepada, pastda.
    upcoming = sorted((e for e in all_events if not e.is_past),
                      key=lambda e: e.event_dt or datetime.max)
    past = sorted((e for e in all_events if e.is_past),
                  key=lambda e: e.event_dt or datetime.min, reverse=True)
    # Birinchi o'tib ketgan tadbirga "O'tib ketgan tadbirlar" sarlavhasini belgilaymiz
    if past:
        past[0].show_past_header = True
    events = upcoming + past

    groups = Group.objects.all()
    venues = Venue.objects.all()
    # Faqat sanasi o'tmagan (bugun yoki keyin) ishchilar tadbirlari
    work_events = WorkEvent.objects.filter(event_date__gte=date.today()).order_by('event_date')

    return render(request, 'events/list.html', {
        'events': events,
        'upcoming_count': len(upcoming),
        'past_count': len(past),
        'groups': groups,
        'venues': venues,
        'work_events': work_events,
    })

@login_required(login_url='/login/')
def calendar_view(request):
    """Barcha tadbirlar (mijozlar + ishchilar) bitta kalendarda + oy bo'yicha ro'yxat."""
    from django.urls import reverse
    from datetime import datetime, date as date_cls
    from apps.workers.models import WorkEvent

    def norm(value):
        """Turli sana formatlarini 'YYYY-MM-DD' ga keltiradi."""
        if not value:
            return None
        if not isinstance(value, str):
            try:
                return value.strftime('%Y-%m-%d')
            except Exception:
                return None
        for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d-%m-%Y'):
            try:
                return datetime.strptime(value, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        return None

    events_data = []
    hero_image = None
    today_str = date_cls.today().strftime('%Y-%m-%d')
    closest_diff = None

    # Mijozlar tadbirlari
    for e in Event.objects.all():
        d = norm(e.date)
        if not d:
            continue
        events_data.append({
            'name': e.name,
            'date': d,
            'time': str(e.time) if e.time else '',
            'url': reverse('event_detail', args=[e.id]) + '?from=calendar',
            'type': 'client',
            'speaker': e.speaker or '',
            'location': e.location or '',
        })
        if e.image:
            diff = abs((datetime.strptime(d, '%Y-%m-%d').date() - date_cls.today()).days)
            if closest_diff is None or diff < closest_diff:
                closest_diff = diff
                hero_image = e.image.url

    # Ishchilar tadbirlari
    for we in WorkEvent.objects.all():
        d = norm(we.event_date)
        if not d:
            continue
        events_data.append({
            'name': we.name,
            'date': d,
            'time': str(we.event_time) if getattr(we, 'event_time', None) else '',
            'url': reverse('work_event_detail', args=[we.id]) + '?from=calendar',
            'type': 'worker',
            'speaker': '',
            'location': '',
        })

    events_data.sort(key=lambda x: x['date'])

    return render(request, 'events/calendar.html', {
        'events_data': events_data,
        'hero_image': hero_image,
        'today_str': today_str,
    })


@login_required(login_url='/login/')
def planner_view(request):
    """Shaxsiy taqvim: qo'lda qo'shiladigan tadbirlar (ko'p kunlik ham bo'ladi).

    Faqat qachon qanday tadbir borligini ko'rish uchun — botga bog'liq emas.
    """
    from datetime import date as date_cls

    events_data = [
        {
            'id': ev.id,
            'name': ev.name,
            'start': ev.start_date.strftime('%Y-%m-%d'),
            'end': ev.end_date.strftime('%Y-%m-%d'),
        }
        for ev in CalendarEvent.objects.all()
    ]

    return render(request, 'events/planner.html', {
        'events_data': events_data,
        'today_str': date_cls.today().strftime('%Y-%m-%d'),
    })


@login_required(login_url='/login/')
def planner_add(request):
    """Taqvimga yangi tadbir qo'shish (nom + boshlanish [+ tugash] sanasi)."""
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        start_date = request.POST.get('start_date') or None
        end_date = request.POST.get('end_date') or None
        if not name or not start_date:
            messages.error(request, "Tadbir nomi va sanasini kiriting.")
        else:
            CalendarEvent.objects.create(
                name=name, start_date=start_date, end_date=end_date or start_date,
            )
            messages.success(request, "Taqvimga tadbir qo'shildi.")
    return redirect('planner')


@login_required(login_url='/login/')
def planner_delete(request, pk):
    """Taqvim tadbirini o'chirish."""
    ev = get_object_or_404(CalendarEvent, pk=pk)
    ev.delete()
    messages.success(request, "Tadbir o'chirildi.")
    return redirect('planner')


# ══════════════════════════════════════════════════════════════
#  BIRLASHGAN TADBIR — kalendardan yaratish (wizard) + boshliq tasdig'i
# ══════════════════════════════════════════════════════════════

@login_required(login_url='/login/')
def event_wizard(request):
    """Tadbir yaratish — telefon uslubidagi kalendar (kirish sahifasi).

    Tepada foydalanuvchi yozgan tadbir NOMI chiplari (localStorage'da saqlanadi),
    pastda oylik kalendar. Bo'sh kunni bosish yoki nom chipini kunga sudrash/tanlash →
    forma (event_create_form). Tadbiri bor kunni bosish → o'sha kun tadbirlari (modal).
    """
    from apps.workers.models import WorkEvent
    from django.urls import reverse
    from datetime import datetime, date as date_cls

    def norm(value):
        if not value:
            return None
        if not isinstance(value, str):
            try:
                return value.strftime('%Y-%m-%d')
            except Exception:
                return None
        for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d-%m-%Y'):
            try:
                return datetime.strptime(value, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        return None

    def fmt_time(value):
        if not value:
            return ''
        try:
            return value.strftime('%H:%M')
        except AttributeError:
            return str(value)[:5]

    events_data = []
    STATUS_MARK = {'pending': '⏳', 'approved': '✅', 'rejected': '❌'}

    # Mijozlar tadbirlari (qizil) — boshliq tasdig'iga bog'langan bo'lsa holat belgisi bilan
    for e in Event.objects.select_related('work_event').all():
        d = norm(e.date)
        if not d:
            continue
        status = e.approval_status  # None | pending | approved | rejected
        events_data.append({
            'name': e.name, 'date': d,
            'time': fmt_time(e.time),
            'type': 'client',
            'status': status or '',
            'mark': STATUS_MARK.get(status, ''),
            'url': reverse('event_detail', args=[e.id]),
        })

    # Ishchilar tadbirlari (sariq) — status belgisi bilan
    for we in WorkEvent.objects.all():
        d = norm(we.event_date)
        if not d:
            continue
        events_data.append({
            'name': we.name, 'date': d,
            'time': fmt_time(we.event_time),
            'type': 'worker',
            'mark': STATUS_MARK.get(we.status, ''),
            'url': reverse('work_event_detail', args=[we.id]),
        })

    events_data.sort(key=lambda x: (x['date'], x['time']))

    return render(request, 'events/event_create.html', {
        'events_data': events_data,
        'today_str': date_cls.today().strftime('%Y-%m-%d'),
    })


@login_required(login_url='/login/')
def event_create_form(request):
    """Birlashgan tadbir formasi: 1) ishchilar (WorkEvent) 2) mijozlar (Event).

    Kalendardan sana/shablon oldindan tanlangan holda ochiladi. Yakunda hech narsa
    DARROV yuborilmaydi — 'pending' holatda yaratilib, boshliqqa ✅/❌ so'rov ketadi.
    """
    from apps.workers.models import WorkEvent, Template
    from apps.workers.views import _create_tasks_from_template
    from config.bot_notify import send_event_approval_request
    from datetime import date as date_cls

    if request.method == 'POST':
        # 1-qadam: ishchilar tadbiri (majburiy)
        name = (request.POST.get('name') or '').strip()
        event_date = request.POST.get('event_date') or None
        event_time = (request.POST.get('event_time') or '').strip()
        template_id = request.POST.get('template') or None

        if not name or not event_date or not event_time:
            messages.error(request, "Tadbir nomi, sanasi va vaqtini kiriting.")
            return redirect(f"{request.path}?date={event_date or ''}&template={template_id or ''}")

        work_event = WorkEvent.objects.create(
            name=name, event_date=event_date, event_time=event_time,
            template_id=template_id, status='pending',
        )
        if template_id:
            template = Template.objects.filter(pk=template_id).first()
            if template:
                _create_tasks_from_template(work_event, template)

        # 2-qadam: mijozlar e'loni (ixtiyoriy, lekin odatda to'ldiriladi)
        venue_id = request.POST.get('venue_id')
        venue = Venue.objects.filter(pk=venue_id).first() if venue_id else None
        client_event = Event.objects.create(
            name=name,
            date=event_date,
            time=event_time,
            theme=request.POST.get('theme', ''),
            description=request.POST.get('description', ''),
            venue=venue,
            location=venue.name if venue else '',
            latitude=venue.latitude if venue else '',
            longitude=venue.longitude if venue else '',
            speaker=request.POST.get('speaker', ''),
            category=request.POST.get('category', 'other'),
            send_to_all_users='send_to_all_users' in request.POST,
            sent=False,
            work_event=work_event,
        )
        if 'image' in request.FILES:
            client_event.image = request.FILES['image']
            client_event.save()
        group_ids = request.POST.getlist('send_groups')
        if group_ids:
            client_event.send_groups.set(group_ids)

        # Boshliqqa tasdiq so'rovi
        sent = send_event_approval_request(work_event)
        if sent:
            messages.success(request, "✅ Tadbir yaratildi va boshliqqa tasdiq uchun yuborildi.")
        else:
            messages.warning(request, "Tadbir yaratildi, lekin tasdiqlaydigan boshliq topilmadi "
                                      "(Telegram ID li boshliq yo'q).")
        return redirect('event_wizard')

    # GET — formani ko'rsatamiz (kalendardan sana/shablon oldindan tanlangan bo'lishi mumkin)
    return render(request, 'events/event_wizard.html', {
        'templates': Template.objects.all(),
        'groups': Group.objects.all(),
        'venues': Venue.objects.all(),
        'categories': Event.CATEGORY_CHOICES,
        'prefill_date': request.GET.get('date', ''),
        'prefill_template': request.GET.get('template', ''),
        'prefill_name': request.GET.get('name', ''),
        'today_str': date_cls.today().strftime('%Y-%m-%d'),
    })


def approve_combined_event(work_event_id):
    """Boshliq tasdiqlagach: ishchilarga vazifalar + mijozlarga e'lon yuboradi.

    Bot handleridan sync_to_async orqali chaqiriladi. Tadbir nomini qaytaradi
    (yoki None — topilmasa/allaqachon tasdiqlangan bo'lsa)."""
    from apps.workers.models import WorkEvent
    from apps.workers.views import _notify_new_tasks

    we = WorkEvent.objects.filter(pk=work_event_id).first()
    if not we or we.status == 'approved':
        return None
    we.status = 'approved'
    we.save(update_fields=['status'])

    # 1) Ishchilarga vazifalar (va checklist) — yaratish oqimidagi bilan bir xil
    tasks = list(we.tasks.prefetch_related('workers').all())
    try:
        _notify_new_tasks(we, tasks)
    except Exception as e:
        print(f"[TASDIQ] ishchilarga yuborish xatosi: {e}")

    # 2) Mijozlarga e'lon — nishon (guruh yoki 'hammaga') bo'lsa
    ev = getattr(we, 'client_event', None)
    if ev and (ev.send_groups.exists() or ev.send_to_all_users):
        ev.sent = True
        ev.save(update_fields=['sent'])
        import threading
        threading.Thread(target=_send_event_now_bg, args=(ev.id,), daemon=True).start()

    return we.name


def reject_combined_event(work_event_id):
    """Boshliq rad etganda — 'rejected' qilib qo'yadi, hech narsa yuborilmaydi.

    Saytda bildirishnoma chiqishi uchun rejection_seen=False qilamiz. Mijoz e'loni
    ham nofaol qilinadi — adashib yuborilmasin.
    """
    from apps.workers.models import WorkEvent
    we = WorkEvent.objects.filter(pk=work_event_id).first()
    if not we:
        return None
    we.status = 'rejected'
    we.rejection_seen = False
    we.save(update_fields=['status', 'rejection_seen'])

    # Bog'langan mijoz e'lonini nofaol qilamiz (yuborilmasin)
    ev = getattr(we, 'client_event', None)
    if ev and ev.is_active:
        ev.is_active = False
        ev.save(update_fields=['is_active'])

    return we.name


@login_required(login_url='/login/')
def event_rejection_dismiss(request, pk):
    """Dashboarddagi 'boshliq rad etdi' bildirishnomasini ko'rilgan deb belgilaydi."""
    from apps.workers.models import WorkEvent
    we = get_object_or_404(WorkEvent, pk=pk)
    we.rejection_seen = True
    we.save(update_fields=['rejection_seen'])
    return redirect('dashboard')


@login_required(login_url='/login/')
def event_detail(request, pk):
    """Bitta tadbir va unga javob bergan foydalanuvchilar."""
    event = get_object_or_404(Event, pk=pk)
    responses = event.responses.select_related('user', 'user__profile').order_by('-created_at')

    counts = {
        'boraman': responses.filter(rsvp_choice='boraman').count(),
        'balki_borarman': responses.filter(rsvp_choice='balki_borarman').count(),
        'balki_bormasman': responses.filter(rsvp_choice='balki_bormasman').count(),
        'bormayman': responses.filter(rsvp_choice='bormayman').count(),
    }

    delivery = _event_delivery_context(event)

    return render(request, 'events/detail.html', {
        'event': event,
        'responses': responses,
        'counts': counts,
        **delivery,
    })


@login_required(login_url='/login/')
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk)
    event.delete()
    messages.success(request, "Tadbir o'chirildi.")
    return redirect('events_list')


def _ensure_telegraph(event):
    """Tadbir uchun Telegraph sahifasi bo'lmasa yaratadi."""
    from config.telegraph_utils import create_telegraph_page
    if not event.telegraph_url:
        t_url = create_telegraph_page(event.name or "Tadbir")
        if t_url:
            event.telegraph_url = t_url
            event.save(update_fields=['telegraph_url'])


def _log_delivery(event, *, user=None, group=None, chat_id=None, msg_id=None):
    """Bitta yuborishni jurnalga yozadi (yoki mavjudini yangilaydi)."""
    target_type = 'group' if group else 'user'
    defaults = {
        'target_type': target_type,
        'chat_id': str(chat_id),
        'message_id': msg_id or None,
        'status': 'success' if msg_id else 'failed',
        'error': '' if msg_id else "Yuborilmadi",
    }
    if group:
        EventSendLog.objects.update_or_create(event=event, group=group, defaults=defaults)
    else:
        EventSendLog.objects.update_or_create(event=event, user=user, defaults=defaults)


def _send_event_to_targets(event, *, user_text, group_text, image_url=None, image_path=None, target_users=None):
    """Tadbirni foydalanuvchi va guruhlarga yuboradi, har birini jurnallaydi.

    Qaytadi: (yuborilgan_foydalanuvchi, yuborilgan_guruh) soni.
    """
    from config.bot_notify import send_event_message
    import time

    if target_users is None:
        if event.send_to_all_users:
            target_users = User.objects.filter(
                role='user', is_active=True
            ).exclude(tg_id__isnull=True).exclude(tg_id='')
        else:
            target_users = User.objects.none()

    user_ok = 0
    for i, user in enumerate(target_users):
        msg_id = send_event_message(
            user.tg_id, user_text, event.id,
            image_url=image_url, image_path=image_path,
            telegraph_url=event.telegraph_url, is_group=False,
        )
        _log_delivery(event, user=user, chat_id=user.tg_id, msg_id=msg_id)
        if msg_id:
            user_ok += 1
        if (i + 1) % 10 == 0:
            time.sleep(0.5)

    group_ok = 0
    for group in event.send_groups.all():
        msg_id = send_event_message(
            group.tg_id, group_text, event.id,
            image_url=image_url, image_path=image_path,
            telegraph_url=event.telegraph_url, is_group=True,
        )
        _log_delivery(event, group=group, chat_id=group.tg_id, msg_id=msg_id)
        if msg_id:
            group_ok += 1

    return user_ok, group_ok


@login_required(login_url='/login/')
def event_send_now(request, pk):
    """Tadbirni hozir botga (foydalanuvchi + guruhlarga) yuborish.

    Yuborish fon rejimda (thread) bajariladi — sahifa qotib qolmasligi uchun.
    Darhol "yuborilmoqda" xabari ko'rsatiladi.
    """
    event = get_object_or_404(Event, pk=pk)

    # Boshliq tasdig'iga bog'langan tadbir — rad etilgan yoki hali tasdiqlanmagan bo'lsa yubormaymiz.
    we = event.work_event
    if we and we.status == 'rejected':
        messages.error(request, "❌ Bu tadbir boshliq tomonidan RAD ETILGAN — yuborib bo'lmaydi.")
        return redirect('events_list')
    if we and we.status == 'pending':
        messages.warning(request, "⏳ Bu tadbir hali boshliq tasdig'ini kutmoqda. Tasdiqlangach avtomatik yuboriladi.")
        return redirect('events_list')

    # Kamida bitta nishon bo'lishi kerak: guruh/kanal YOKI "hamma foydalanuvchi".
    # Guruh tanlanmasa ham, foydalanuvchilarga yuborish yoqilgan bo'lsa — o'tadi.
    if not event.send_groups.exists() and not event.send_to_all_users:
        messages.error(request, "Yuborish uchun kamida bir guruh/kanal tanlang yoki "
                                "\"Hamma foydalanuvchiga yuborilsin\" ni yoqing.")
        return redirect('event_edit', pk=event.pk)

    # Ikki marta yuborilmasligi uchun darhol 'sent' qilamiz (tugma yashiriladi)
    event.sent = True
    event.save(update_fields=['sent'])

    import threading
    threading.Thread(target=_send_event_now_bg, args=(event.id,), daemon=True).start()

    messages.success(request, "⏳ Tadbir foydalanuvchilarga yuborilmoqda...")
    return redirect('events_list')


def _send_event_now_bg(event_id):
    """Tadbirni fon rejimda foydalanuvchi va guruhlarga yuboradi (jurnal bilan)."""
    from config.bot_notify import build_event_text

    event = Event.objects.filter(pk=event_id).first()
    if not event:
        return

    _ensure_telegraph(event)
    text = build_event_text(event)
    image_path = event.image.path if event.image else None

    user_ok, group_ok = _send_event_to_targets(
        event, user_text=text, group_text=text, image_path=image_path,
    )
    print(f"[Tadbir yuborildi] {user_ok} foydalanuvchi + {group_ok} guruh")


@login_required(login_url='/login/')
def event_group_message_delete(request, pk, group_id):
    """Tadbir xabarini bitta guruh/kanaldan o'chiradi (adashib yuborilgan bo'lsa)."""
    from config.bot_notify import delete_telegram_message

    event = get_object_or_404(Event, pk=pk)
    log = event.send_logs.filter(target_type='group', group_id=group_id).first()

    if not log or not log.message_id:
        messages.error(request, "Bu guruh uchun yuborilgan xabar topilmadi.")
        return redirect('event_edit', pk=event.pk)

    ok = delete_telegram_message(log.chat_id, log.message_id)
    # Guruhni tadbir maqsadidan chiqaramiz va jurnaldan o'chiramiz
    event.send_groups.remove(group_id)
    log.delete()

    if ok:
        messages.success(request, "Tadbir shu guruh/kanaldan o'chirildi.")
    else:
        messages.warning(request, "Guruhdan chiqarildi (xabar allaqachon o'chirilgan bo'lishi mumkin).")
    return redirect('event_edit', pk=event.pk)

@login_required(login_url='/login/')
def event_edit(request, pk):
    """Tadbirni tahrirlash. Saqlaganda eski xabar o'chirilib, yangisi qayta yuboriladi."""
    event = get_object_or_404(Event, pk=pk)

    if request.method == "POST":
        # Kamida bitta nishon: guruh/kanal YOKI "hamma foydalanuvchi".
        group_ids = request.POST.getlist('send_groups')
        send_to_all = 'send_to_all_users' in request.POST
        if not group_ids and not send_to_all:
            messages.error(request, "Kamida bir guruh/kanal tanlang yoki "
                                    "\"Hamma foydalanuvchiga yuborilsin\" ni yoqing.")
            return redirect('event_edit', pk=event.pk)

        venue_id = request.POST.get('venue_id')
        venue = Venue.objects.filter(pk=venue_id).first() if venue_id else None

        event.name = request.POST.get('name')
        event.theme = request.POST.get('theme', '')
        event.description = request.POST.get('description')
        event.date = request.POST.get('date')
        event.time = request.POST.get('time')
        event.venue = venue
        event.location = venue.name if venue else event.location
        event.latitude = venue.latitude if venue else event.latitude
        event.longitude = venue.longitude if venue else event.longitude
        event.speaker = request.POST.get('speaker', '')
        event.category = request.POST.get('category', 'other')
        event.send_to_all_users = 'send_to_all_users' in request.POST

        if 'image' in request.FILES:
            event.image = request.FILES['image']

        event.save()

        event.send_groups.set(group_ids)

        # Boshliq tasdig'iga bog'langan tadbir RAD ETILGAN yoki TASDIQ KUTAYOTGAN bo'lsa —
        # tahrirlab saqlash to'g'ridan-to'g'ri YUBORMAYDI, balki QAYTA boshliq tasdig'iga yuboradi.
        we = event.work_event
        if we and we.status in ('rejected', 'pending'):
            from config.bot_notify import send_event_approval_request
            we.status = 'pending'
            we.rejection_seen = True   # eski "rad etildi" bildirishnomasi yopiladi
            we.save(update_fields=['status', 'rejection_seen'])
            # Tadbirni "hali yuborilmagan" holatiga qaytaramiz (adashib yuborilmasin)
            event.sent = False
            event.is_active = True
            event.save(update_fields=['sent', 'is_active'])

            sent = send_event_approval_request(we)
            if sent:
                messages.success(request, "✅ Tadbir yangilandi va boshliqqa QAYTA tasdiq uchun yuborildi.")
            else:
                messages.warning(request, "Tadbir yangilandi, lekin tasdiqlaydigan boshliq topilmadi "
                                          "(Telegram ID li boshliq yo'q).")
            return redirect('events_list')

        # Faqat allaqachon yuborilgan (va tasdiqlangan/bog'lanmagan) tadbirlarni qayta yuboramiz.
        # (Hali yuborilmagan tadbir uchun tahrirlash — oddiy saqlash.)
        if event.sent:
            import threading
            threading.Thread(target=_resend_event_after_edit, args=(event.id,), daemon=True).start()
            messages.success(request, "Tadbir yangilandi. Eski xabarlar o'chirilib, yangisi yuborilmoqda...")
        else:
            messages.success(request, "Tadbir yangilandi.")

        return redirect('events_list')

    groups = Group.objects.all()
    venues = Venue.objects.all()
    selected_group_ids = list(event.send_groups.values_list('id', flat=True))
    # Yuborish tarixi (qaysi guruhga/foydalanuvchiga ketgan) — tahrirlash sahifasida ko'rsatamiz
    delivery = _event_delivery_context(event)
    return render(request, 'events/edit.html', {
        'event': event,
        'groups': groups,
        'venues': venues,
        'selected_group_ids': selected_group_ids,
        'show_group_delete': True,  # o'chirish faqat tahrirlashda ko'rinadi
        **delivery,
    })


def _event_delivery_context(event):
    """Tadbir yuborish tarixini shablon uchun tayyorlaydi.

    - group_delivery: har bir tanlangan guruh + holati (yuborildi/yuborilmadi)
    - user_logs, user_sent, user_failed: foydalanuvchilarga yuborish jurnali va sonlar
    """
    logs = list(event.send_logs.select_related('user', 'user__profile', 'group').all())
    group_log_map = {log.group_id: log for log in logs if log.group_id}

    group_delivery = []
    for g in event.send_groups.all():
        log = group_log_map.get(g.id)
        group_delivery.append({
            'group': g,
            'sent': bool(log and log.status == 'success'),
            'log': log,
        })

    user_logs = [log for log in logs if log.user_id]
    user_sent = sum(1 for log in user_logs if log.status == 'success')
    user_failed = len(user_logs) - user_sent

    return {
        'group_delivery': group_delivery,
        'user_logs': user_logs,
        'user_sent': user_sent,
        'user_failed': user_failed,
        'has_delivery': bool(logs),
    }


def _resend_event_after_edit(event_id):
    """Tahrirlashdan keyin o'zgarishni yuboradi.

    Qoidalar (foydalanuvchi kelishuvi bo'yicha):
      • Faqat TANLANGAN guruhlarda o'zgaradi — eski xabar o'chiriladi, yangisi yuboriladi.
      • Tanlanmagan guruhga TEGILMAYDI (eski xabar o'sha joyda qoladi).
      • Foydalanuvchilarga faqat 'send_to_all_users' yoqilgan bo'lsa ketadi:
        eski xabar o'chiriladi, o'rniga 'MUHIM o'zgarish' xabari yuboriladi.

    Alohida oqimda (thread) ishlaydi. Har bir yuborish jurnalga yoziladi.
    """
    from config.bot_notify import send_event_message, build_event_text, delete_telegram_message
    import time

    event = Event.objects.filter(pk=event_id).first()
    if not event:
        return

    _ensure_telegraph(event)
    image_path = event.image.path if event.image else None

    base_text = build_event_text(event)
    user_text = (
        "⚠️ <b>MUHIM! TADBIRDA O'ZGARISH!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "<i>Quyidagi tadbir yangilandi. Iltimos, ma'lumotlarni diqqat bilan o'qing va javobingizni yangilang 👇</i>\n\n"
        + base_text
    )
    # Guruh/kanal xabari ham "o'zgarish" sarlavhasi bilan ketadi
    group_text = (
        "⚠️ <b>DIQQAT! TADBIRDA O'ZGARISH!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "<i>Quyidagi tadbir ma'lumotlari yangilandi 👇</i>\n\n"
        + base_text
    )

    # ── Guruhlar: faqat tanlanganlarida o'zgartiramiz ──
    existing_group_logs = {
        log.group_id: log for log in event.send_logs.filter(target_type='group')
    }
    group_ok = 0
    for group in event.send_groups.all():
        old = existing_group_logs.get(group.id)
        if old and old.message_id:
            delete_telegram_message(old.chat_id, old.message_id)  # eskisi uchadi
        msg_id = send_event_message(
            group.tg_id, group_text, event.id,
            image_path=image_path, telegraph_url=event.telegraph_url, is_group=True,
        )
        _log_delivery(event, group=group, chat_id=group.tg_id, msg_id=msg_id)
        if msg_id:
            group_ok += 1
    # Tanlanmagan guruhga TEGILMAYDI: uning eski xabari va logi o'zgarishsiz qoladi
    # (keyin qayta tanlansa, eski message_id orqali o'chirib dublikatning oldini olamiz).

    # ── Foydalanuvchilar: faqat belgilangan bo'lsa ──
    user_ok = 0
    if event.send_to_all_users:
        # Eski foydalanuvchi xabarlarini o'chiramiz
        for log in event.send_logs.filter(target_type='user'):
            if log.message_id:
                delete_telegram_message(log.chat_id, log.message_id)
        target_users = User.objects.filter(
            role='user', is_active=True
        ).exclude(tg_id__isnull=True).exclude(tg_id='')
        for i, user in enumerate(target_users):
            msg_id = send_event_message(
                user.tg_id, user_text, event.id,
                image_path=image_path, telegraph_url=event.telegraph_url, is_group=False,
            )
            _log_delivery(event, user=user, chat_id=user.tg_id, msg_id=msg_id)
            if msg_id:
                user_ok += 1
            if (i + 1) % 10 == 0:
                time.sleep(0.5)

    print(f"[Tadbir yangilanish] {user_ok} foydalanuvchi + {group_ok} guruhga qayta yuborildi")


@login_required(login_url='/login/')
def event_toggle_active(request, pk):
    """Tadbirni faol/nofaol qilish."""
    event = get_object_or_404(Event, pk=pk)
    event.is_active = not event.is_active
    event.save(update_fields=['is_active'])
    state = "faollashtirildi" if event.is_active else "nofaol qilindi"
    messages.success(request, f"Tadbir {state}.")
    return redirect('events_list')


@login_required(login_url='/login/')
def event_checkin(request,pk):
    """
       Tadbir kuni QR/ID orqali "keldi" deb belgilash sahifasi.
       Admin 4 xonali ID kiritadi (yoki QR skaner shu ID ni yuboradi),
       shu ID ga ega foydalanuvchi bu tadbirga 'keldi' deb belgilanadi.
       """
    from apps.users.models import User
    from apps.trips.models import Trip

    event = get_object_or_404(Event, pk=pk)
    result = None

    # Qaysi safar bo'yicha to'lov ko'rsatilsin (adashmaslik uchun oldindan tanlanadi).
    # POST orqali (skan bilan birga) yoki GET orqali (select o'zgarganда) keladi.
    selected_trip_id = request.POST.get('trip_id') or request.GET.get('trip') or ''
    selected_trip = Trip.objects.filter(pk=selected_trip_id).first() if selected_trip_id else None
    active_trips = Trip.objects.filter(is_active=True).order_by('-created_at')

    if request.method == 'POST':
        # Ikki xil forma: (1) ID/QR nazorati, (2) Lead (ro'yxatdan o'tmagan mehmon)
        if 'lead_full_name' in request.POST or 'lead_phone' in request.POST:
            full_name = request.POST.get('lead_full_name', '').strip()
            phone = normalize_phone(request.POST.get('lead_phone', ''))

            if not full_name or not phone:
                result = {'status': 'error', 'message': "Ism-familiya va telefon raqamni to'liq kiriting."}
            else:
                Lead.objects.create(
                    event=event,
                    full_name=full_name,
                    phone=phone,
                    note=request.POST.get('lead_note', '').strip(),
                )
                result = {'status': 'success', 'message': f"Lead qo'shildi: {full_name} 🎯"}
        else:
            code = request.POST.get('code','').strip()

            try:
                user = User.objects.get(unique_id=code)
            except User.DoesNotExist:
                user = None

            if not user:
                result = {'status':'error','message':f"'{code}' ID li foydalanuvchi topilmadi."}
            else:
                user_event,created= UserEvent.objects.get_or_create(user=user,event=event)
                if user_event.is_attendance:
                    status, msg = 'warning', f"{user.full_name} allaqachon belgilangan😎."
                else:
                    user_event.is_attendance=True
                    user_event.save()
                    status, msg = 'success', f"{user.full_name} - keldi deb belgilandi😎"
                # QR skanda: shu odamning safar to'lov/qarz holatini chiqaramiz.
                # Safar tanlangan bo'lsa — faqat o'sha safar bo'yicha (adashmaslik uchun).
                result = {
                    'status': status,
                    'message': msg,
                    'user_name': user.full_name or str(user),
                    'user_id': user.unique_id,
                    'trips': _user_trip_payments(user, trip_id=selected_trip_id or None),
                    'selected_trip_name': selected_trip.name if selected_trip else '',
                }

#     Tadbirga kelganlar ruyxati
    attended = event.responses.filter(is_attendance=True).select_related('user','user__profile')
    # Shu tadbirga qo'shilgan ledlar
    leads = event.leads.all()

    return render(request, 'events/checkin.html',{
        'event':event,
        'result':result,
        'attended':attended,
        'leads':leads,
        'active_trips': active_trips,
        'selected_trip_id': selected_trip_id,
    })


def _user_trip_payments(user, trip_id=None):
    """Foydalanuvchining safar(lar)dagi to'lov/qarz holati (QR skanda ko'rsatish uchun).

    trip_id berilsa — faqat o'sha safar bo'yicha. Aks holda barcha FAOL safarlar.
    Har bir safar uchun: berishi kerak, to'langan (berdi + omonat), qoldiq (qarz).
    """
    from apps.trips.models import TripParticipant
    parts = TripParticipant.objects.filter(user=user).select_related('trip')
    if trip_id:
        parts = parts.filter(trip_id=trip_id)
    else:
        parts = parts.filter(trip__is_active=True)
    parts = parts.order_by('-trip__created_at')
    rows = []
    for p in parts:
        rows.append({
            'trip_name': p.trip.name,
            'payment_status': p.get_payment_status_display() or '—',
            'travel_status': p.get_travel_status_display() or '',
            'must_pay': p.must_pay,
            'paid_total': (p.paid or 0) + (p.deposit or 0),
            'remaining': p.remaining,
            'went': p.went,
        })
    return rows


def normalize_phone(raw):
    """Telefon raqamni +998XXXXXXXXX ko'rinishiga keltiradi.

    Foydalanuvchi +998 yozmasa ham, faqat raqamlarni kiritsa ham to'g'ri saqlanadi.
    Masalan: '901234567' yoki '90 123 45 67' -> '+998901234567'.
    """
    digits = ''.join(ch for ch in (raw or '') if ch.isdigit())
    if not digits:
        return ''
    if digits.startswith('998'):
        digits = digits[3:]
    return '+998' + digits


@login_required(login_url='/login/')
def leads_list(request):
    """Barcha ledlar (ro'yxatdan o'tmagan mehmonlar) — qaysi tadbirga kelgani bilan."""
    leads = Lead.objects.select_related('event').prefetch_related('status_logs').order_by('-created_at')

    # Tadbir bo'yicha filtr
    event_id = request.GET.get('event')
    if event_id:
        leads = leads.filter(event_id=event_id)

    # Holat bo'yicha filtr
    status = request.GET.get('status')
    if status:
        leads = leads.filter(status=status)

    events = Event.objects.order_by('-created_at')
    return render(request, 'events/leads_list.html', {
        'leads': leads,
        'events': events,
        'selected_event_id': event_id,
        'selected_status': status,
        'status_choices': Lead.STATUS_CHOICES,
    })


@login_required(login_url='/login/')
def lead_change_status(request, pk):
    lead = get_object_or_404(Lead, pk=pk)

    if request.method == 'POST':
        new_status = request.POST.get('status', '').strip()
        note = request.POST.get('note', '').strip()
        follow_up_raw = request.POST.get('follow_up_at', '').strip()
        valid = dict(Lead.STATUS_CHOICES)

        if new_status not in valid:
            messages.error(request, "Noto'g'ri holat tanlandi.")
        else:
            follow_up_at = None

            if new_status == 'follow_up':
                parsed = parse_datetime(follow_up_raw)

                if not parsed:
                    messages.error(
                        request,
                        "Qayta aloqa uchun sana va vaqtni kiriting."
                    )
                    return redirect('leads_list')

                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(
                        parsed,
                        timezone.get_current_timezone()
                    )

                follow_up_at = parsed

            if new_status != lead.status:
                LeadStatusLog.objects.create(
                    lead=lead,
                    old_status=lead.status,
                    new_status=new_status,
                    changed_by=request.user.get_username(),
                    note=note,
                )
                lead.status_changed_at = timezone.now()

            lead.status = new_status
            lead.follow_up_at = follow_up_at
            lead.save(
                update_fields=[
                    'status',
                    'status_changed_at',
                    'follow_up_at',
                ]
            )

            messages.success(
                request,
                f"Holat yangilandi: {valid[new_status]}"
            )

    next_url = request.POST.get('next') or request.GET.get('next')

    if next_url == 'checkin':
        return redirect('event_checkin', pk=lead.event_id)

    return redirect('leads_list')

@login_required(login_url='/login/')
def lead_delete(request, pk):
    """Bitta leadni o'chirish."""
    lead = get_object_or_404(Lead, pk=pk)
    event_pk = lead.event_id
    lead.delete()
    messages.success(request, "Lead o'chirildi.")
    # Qayerdan kelgan bo'lsa o'sha yerga qaytamiz
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url == 'checkin':
        return redirect('event_checkin', pk=event_pk)
    return redirect('leads_list')


@login_required(login_url='/login/')
def lead_edit(request, pk):
    """Leadni tahrirlash: ism-familiya, telefon, izoh."""
    lead = get_object_or_404(Lead, pk=pk)

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone = normalize_phone(request.POST.get('phone', ''))

        if not full_name or not phone:
            messages.error(request, "Ism-familiya va telefon raqam majburiy.")
        else:
            lead.full_name = full_name
            lead.phone = phone
            lead.note = request.POST.get('note', '').strip()
            lead.save()
            messages.success(request, "Lead yangilandi.")

    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url == 'checkin':
        return redirect('event_checkin', pk=lead.event_id)
    return redirect('leads_list')


@login_required(login_url='/login/')
def venues_list(request):
    """Manzillar ro'yxati + yangi manzil qo'shish."""
    from .models import Venue

    if request.method == 'POST':
        Venue.objects.create(
            name=request.POST.get('name'),
            address=request.POST.get('address', ''),
            latitude=request.POST.get('latitude', ''),
            longitude=request.POST.get('longitude', ''),
        )
        messages.success(request, "Manzil qo'shildi.")
        return redirect('venues_list')

    venues = Venue.objects.all()
    return render(request, 'events/venues_list.html', {'venues': venues})


@login_required(login_url='/login')
def venue_delete(request,pk):
    from .models import Venue
    venue = get_object_or_404(Venue,pk=pk)
    venue.delete()
    messages.success(request,"Manzil o'chirildi.")
    return redirect('venues_list')











