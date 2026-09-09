"""
Tadbirlar bilan ishlash: ro'yxat, qo'shish, ko'rish, o'chirish, yuborish.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Event, UserEvent, Venue, EventSendLog, Lead, LeadStatusLog
from apps.groups.models import Group
from apps.users.models import User


@login_required(login_url='/login/')
def events_list(request):
    """Tadbirlar ro'yxati + yangi tadbir qo'shish (ishchilar tadbiridan tanlanadi)."""
    from apps.workers.models import WorkEvent
    from datetime import date

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

        # Guruh/kanal tanlash majburiy
        group_ids = request.POST.getlist('send_groups')
        if not group_ids:
            messages.error(request, "Iltimos, qaysi guruh yoki kanalga ketishini belgilang.")
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

    events = Event.objects.prefetch_related('responses', 'send_groups').order_by('-created_at')
    groups = Group.objects.all()
    venues = Venue.objects.all()
    # Faqat sanasi o'tmagan (bugun yoki keyin) ishchilar tadbirlari
    work_events = WorkEvent.objects.filter(event_date__gte=date.today()).order_by('event_date')

    return render(request, 'events/list.html', {
        'events': events,
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

    # Guruh/kanal tanlanmagan bo'lsa — yubormaymiz
    if not event.send_groups.exists():
        messages.error(request, "Iltimos, qaysi guruh yoki kanalga ketishini belgilang.")
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
        # Guruh/kanal tanlash majburiy
        group_ids = request.POST.getlist('send_groups')
        if not group_ids:
            messages.error(request, "Iltimos, qaysi guruh yoki kanalga ketishini belgilang.")
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

        # Faqat allaqachon yuborilgan tadbirlarni qayta yuboramiz.
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

    event = get_object_or_404(Event, pk=pk)
    result = None

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
                    result = {'status':'warning','message':f"{user.full_name} allaqachon belgilangan😎."}
                else:
                    user_event.is_attendance=True
                    user_event.save()
                    result={'status':'success','message':f"{user.full_name} - keldi deb belgilandi😎"}

#     Tadbirga kelganlar ruyxati
    attended = event.responses.filter(is_attendance=True).select_related('user','user__profile')
    # Shu tadbirga qo'shilgan ledlar
    leads = event.leads.all()

    return render(request, 'events/checkin.html',{
        'event':event,
        'result':result,
        'attended':attended,
        'leads':leads,
    })


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











