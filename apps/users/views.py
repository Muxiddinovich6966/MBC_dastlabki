"""
Foydalanuvchilar (mijozlar) bilan ishlash: dashboard, ro'yxat, bitta foydalanuvchi sahifasi.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator

from .models import User, UserProfile, UserPlan
from apps.events.models import Event, Lead
from apps.trips.models import TripParticipant
from django.utils import timezone
from apps.groups.models import Group
from apps.messages_app.models import SendMessage
from ..workers.models import TemplateTask

@login_required(login_url='/login/')
def dashboard(request):
    from datetime import date, datetime, timedelta
    from django.db.models import Sum, Count
    from apps.trips.models import TripParticipant
    import json

    now = timezone.now()
    today = date.today()

    # ── A'ZOLAR ──────────────────────────────────────────
    all_users = User.objects.filter(role='user')
    total_users = all_users.count()
    active_users = all_users.filter(is_active=True).count()

    filled = UserProfile.objects.filter(user__role='user').exclude(name='').count()
    recent_users = all_users.select_related('profile').order_by('-created_at')[:5]

    # ── O'RTACHA (faqat kiritganlar bo'yicha) ──
    ages = []
    for bd in UserProfile.objects.exclude(birth_date='').values_list('birth_date', flat=True):
        try:
            dt = datetime.strptime(bd, '%d.%m.%Y')
            age = (today - dt.date()).days // 365
            if 15 <= age <= 80:
                ages.append(age)
        except Exception:
            pass
    avg_age = round(sum(ages) / len(ages)) if ages else None

    staff_values = []
    for v in UserProfile.objects.exclude(staff_count='').values_list('staff_count', flat=True):
        try:
            staff_values.append(int(str(v).replace(' ', '').replace(',', '')))
        except Exception:
            pass
    avg_staff = round(sum(staff_values) / len(staff_values)) if staff_values else None

    turnover_values = []
    for v in UserProfile.objects.exclude(turnover='').values_list('turnover', flat=True):
        try:
            n = int(str(v).replace(' ', '').replace(',', '').replace('.', ''))
            # Aql bovar qiladigan oraliq: 1 mln — 100 mlrd
            if 1_000_000 <= n <= 100_000_000_000:
                turnover_values.append(n)
        except Exception:
            pass
    if turnover_values:
        turnover_values.sort()
        mid = len(turnover_values) // 2
        avg_turnover = turnover_values[mid] if len(turnover_values) % 2 else (turnover_values[mid - 1] +
                                                                              turnover_values[mid]) // 2
    else:
        avg_turnover = None

    # ── TUSHUM ──────────────────────────────────────────
    # Diqqat: obuna — so'mda, safar to'lovi — dollarda. Ular boshqa valyuta
    # bo'lgani uchun QO'SHILMAYDI, alohida ko'rsatiladi.
    plan_income = UserPlan.objects.aggregate(total=Sum('price'))['total'] or 0
    trip_income = TripParticipant.objects.aggregate(total=Sum('paid'))['total'] or 0

    active_plans = UserPlan.objects.filter(end_date__gte=today).count()
    expiring_soon = UserPlan.objects.filter(
        end_date__gte=today, end_date__lte=today + timedelta(days=7)
    ).count()

    # ── SOHA TAQSIMOTI ──────────────────────────────────
    industry_stats = list(
        UserProfile.objects.exclude(industry='')
        .values('industry').annotate(count=Count('id')).order_by('-count')[:8]
    )

    # ── OYLIK O'SISH (oxirgi 6 oy) ──────────────────────
    monthly_growth = []
    cur = today.replace(day=1)
    months = []
    for _ in range(6):
        months.append(cur)
        cur = (cur - timedelta(days=1)).replace(day=1)
    for m in reversed(months):
        if m.month == 12:
            m_end = m.replace(year=m.year + 1, month=1)
        else:
            m_end = m.replace(month=m.month + 1)
        monthly_growth.append({
            'month': m.strftime('%b %Y'),
            'count': all_users.filter(created_at__gte=m, created_at__lt=m_end).count(),
        })

    # ── TOP SAFARLAR ─────────────────────────────────────
    top_trips = list(
        TripParticipant.objects.filter(went=True)
        .values('trip__name').annotate(count=Count('id')).order_by('-count')[:5]
    )

    # ── ESLATMALAR (Lead + Safar) ────────────────────────
    due_reminders = []

    leads = (
        Lead.objects.filter(status='follow_up', follow_up_at__lte=now)
        .select_related('event').order_by('follow_up_at')
    )
    for lead in leads:
        due_reminders.append({
            'kind': 'Lead',
            'name': lead.full_name,
            'detail': f"{lead.event.name} · {lead.phone}",
            'when': lead.follow_up_at,
            'url': '/events/leads/',
        })

    participants = (
        TripParticipant.objects.filter(travel_status='follow_up', follow_up_at__lte=now)
        .select_related('trip').order_by('follow_up_at')
    )
    for p in participants:
        due_reminders.append({
            'kind': 'Safar',
            'name': p.display_name,
            'detail': p.trip.name,
            'when': p.follow_up_at,
            'url': f'/trips/{p.trip_id}/',
        })

    due_reminders.sort(key=lambda item: item['when'])

    upcoming = []
    for e in Event.objects.filter(is_active=True):
        try:
            d=datetime.strptime(e.date,'%Y-%m-%d').date()
        except Exception:
            try:
                d = datetime.strptime(e.date, '%d.%m.%Y').date()
            except Exception:
                continue
        if d >= today:
            upcoming.append((d,e))

    upcoming.sort(key=lambda x: x[0])
    upcoming_events = [e for _,e in upcoming[:3]]

    # ── BILDIRISHNOMA: boshliq rad etgan tadbirlar (hali ko'rilmagan) ──
    from apps.workers.models import WorkEvent
    rejected_events = list(
        WorkEvent.objects.filter(status='rejected', rejection_seen=False).order_by('-id')
    )

    context = {
        'total_users': total_users,
        'active_users': active_users,
        'filled': filled,
        'recent_users': recent_users,
        'avg_age': avg_age,
        'avg_staff': avg_staff,
        'avg_turnover': avg_turnover,
        'plan_income': plan_income,
        'trip_income': trip_income,
        'active_plans': active_plans,
        'expiring_soon': expiring_soon,
        'industry_stats': json.dumps(industry_stats, ensure_ascii=False),
        'monthly_growth': json.dumps(monthly_growth, ensure_ascii=False),
        'top_trips': top_trips,
        'upcoming_events':upcoming_events,
        'due_reminders': due_reminders,
        'rejected_events': rejected_events,
        'events_count': Event.objects.count(),
        'groups_count': Group.objects.count(),
    }

    return render(request, 'dashboard/index.html', context)


@login_required(login_url='/login/')
def users_list(request):
    """Barcha ro'yxatdan o'tgan foydalanuvchilar."""
    from datetime import date

    search = request.GET.get('search', '')
    trips = request.GET.get('trips', '')
    sub = request.GET.get('sub', '')

    users_qs = User.objects.filter(role='user').select_related('profile')

    if search:
        users_qs = users_qs.filter(
            Q(tg_username__icontains=search) |
            Q(tg_id__icontains=search) |
            Q(profile__name__icontains=search) |
            Q(profile__surname__icontains=search) |
            Q(profile__phone__icontains=search)
        )

    # Safarlar guruhiga yuborilgan/yuborilmagan bo'yicha filtr
    if trips == 'sent':
        users_qs = users_qs.filter(profile__sent_to_trips_at__isnull=False)
    elif trips == 'not_sent':
        users_qs = users_qs.filter(profile__sent_to_trips_at__isnull=True)

    # Obuna holati bo'yicha filtr
    today = date.today()
    if sub == 'active':
        # Kamida bitta faol (muddati tugamagan) obunasi bor
        users_qs = users_qs.filter(plans__end_date__gte=today).distinct()
    elif sub == 'expired':
        # Obunasi bor, lekin hammasi tugagan (faol obunasi yo'q)
        users_qs = users_qs.filter(plans__isnull=False).exclude(plans__end_date__gte=today).distinct()
    elif sub == 'none':
        # Umuman obunasi yo'q
        users_qs = users_qs.filter(plans__isnull=True)

    users_qs = users_qs.order_by('-created_at')

    paginator = Paginator(users_qs, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'users/list.html', {
        'users': page_obj,
        'page_obj': page_obj,
        'search': search,
        'trips': trips,
        'sub': sub,
        'total_count': users_qs.count(),
    })


@login_required(login_url='/login/')
def user_manual_add(request):
    """Admin qo'lda foydalanuvchi qo'shadi (telefon bo'yicha).

    Ba'zi maydonlar bo'sh qolsa ham bo'ladi — foydalanuvchi botga /start bosganda
    telefoni orqali topiladi va bot faqat bo'sh qolgan maydonlarni so'raydi.
    """
    from .profile_fields import PROFILE_FIELDS, REGIONS, INDUSTRIES, TRIPS, LANGUAGES, normalize_phone, phone_key

    if request.method == 'POST':
        phone_raw = request.POST.get('phone', '').strip()
        phone = normalize_phone(phone_raw)
        if not phone or len(phone) < 13:
            messages.error(request, "To'g'ri telefon raqam kiriting (masalan 90 123 45 67).")
            return redirect('user_manual_add')

        # Shu telefon allaqachon bormi?
        pk_new = phone_key(phone)
        existing = UserProfile.objects.filter(phone__endswith=pk_new).first() if pk_new else None
        if existing:
            messages.error(request, f"Bu telefon bilan foydalanuvchi allaqachon bor: {existing.user.full_name}.")
            return redirect('user_detail', pk=existing.user_id)

        # Yangi foydalanuvchi (tg_id hali yo'q — odam /start bosganda to'ladi)
        user = User.objects.create(tg_id=None, role='user', tg_phone=phone)
        profile = UserProfile.objects.create(user=user, phone=phone)

        # Anketa maydonlarini POST dan olib to'ldiramiz (bo'sh bo'lsa — bo'sh qoladi)
        for f in PROFILE_FIELDS:
            key = f['key']
            if f['type'] == 'multi':
                setattr(profile, key, request.POST.getlist(key))
            else:
                val = request.POST.get(key, '').strip()
                if val:
                    setattr(profile, key, val)

        # Rasm (ixtiyoriy) — yuklangan bo'lsa saqlaymiz
        photo = request.FILES.get('photo')
        if photo:
            if (photo.content_type or '').startswith('image/'):
                profile.photo = photo
            else:
                messages.warning(request, "Rasm yuklanmadi: faqat rasm fayli (jpg, png) qabul qilinadi.")
        profile.save()

        messages.success(
            request,
            f"Foydalanuvchi qo'shildi: {user.full_name or phone}. "
            "U botga /start bosib, telefonini yuborganda qolgan ma'lumotlar so'raladi."
        )
        return redirect('user_detail', pk=user.id)

    return render(request, 'users/manual_add.html', {
        'fields': PROFILE_FIELDS,
        'regions': REGIONS,
        'industries': INDUSTRIES,
        'trips': TRIPS,
        'languages': LANGUAGES,
    })


@login_required(login_url='/login/')
def user_detail(request, pk):
    """Bitta foydalanuvchi haqida to'liq ma'lumot."""
    user = get_object_or_404(User, pk=pk)
    profile = getattr(user, 'profile', None)
    event_responses = user.event_responses.select_related('event').order_by('-created_at')
    plans = user.plans.all()
    # Safarlar guruhiga yuborish tarixi (kim/qachon)
    trips_logs = profile.trips_send_logs.select_related('sent_by').all() if profile else []

    # Platforma safarlari — foydalanuvchi haqiqatan borgan (Confirmed + to'liq to'langan)
    # safarlar. Holat o'zgarsa avtomatik yangilanadi (alohida saqlanmaydi).
    platform_trips = [
        p for p in user.trip_participations.select_related('trip').order_by('-created_at')
        if p.counts_as_went
    ]

    return render(request, 'users/detail.html', {
        'user_obj': user,
        'profile': profile,
        'event_responses': event_responses,
        'plans': plans,
        'trips_logs': trips_logs,
        'platform_trips': platform_trips,
    })


@login_required(login_url='/login/')
def user_photo_upload(request, pk):
    """Foydalanuvchi profiliga rasm yuklash / almashtirish / o'chirish.

    Eski bazadan rasmlar ko'chmagani uchun admin qo'lda yuklaydi.
    """
    user = get_object_or_404(User, pk=pk)
    if request.method != 'POST':
        return redirect('user_detail', pk=pk)

    profile = getattr(user, 'profile', None)

    # Rasmni o'chirish
    if request.POST.get('remove') == '1':
        if profile and profile.photo:
            profile.photo.delete(save=False)
            profile.photo = None
            profile.save(update_fields=['photo'])
            messages.success(request, "Rasm o'chirildi.")
        return redirect('user_detail', pk=pk)

    # Rasmni yuklash / almashtirish
    photo = request.FILES.get('photo')
    if not photo:
        messages.error(request, "Rasm tanlanmadi.")
        return redirect('user_detail', pk=pk)
    if not (photo.content_type or '').startswith('image/'):
        messages.error(request, "Faqat rasm fayli yuklang (jpg, png).")
        return redirect('user_detail', pk=pk)

    # Anketa hali bo'lmasa — yaratamiz (rasm saqlash uchun profil kerak)
    if not profile:
        profile = UserProfile.objects.create(user=user)

    # Eski rasm bo'lsa — fayl tizimidan o'chirib, yangisini qo'yamiz
    if profile.photo:
        profile.photo.delete(save=False)
    profile.photo = photo
    profile.save(update_fields=['photo'])
    messages.success(request, "Rasm saqlandi.")
    return redirect('user_detail', pk=pk)


@login_required(login_url='/login/')
def user_edit(request, pk):
    """Mavjud foydalanuvchi anketasini tahrirlash.

    Asosan eski bazadan ko'chirilgan CHALA ma'lumotlarni qo'lda to'ldirish uchun.
    QR (unique_id / user_unique_code) ga TEGMAYDI — faqat profil maydonlari yangilanadi.
    """
    from .profile_fields import (
        PROFILE_FIELDS, REGIONS, INDUSTRIES, TRIPS, LANGUAGES, normalize_phone,
    )

    user = get_object_or_404(User, pk=pk)
    profile, _ = UserProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        phone_raw = request.POST.get('phone', '').strip()
        if phone_raw:
            profile.phone = normalize_phone(phone_raw)

        # Anketa maydonlari — bo'sh kelsa ham yoziladi (admin tozalashi mumkin)
        for f in PROFILE_FIELDS:
            key = f['key']
            if f['type'] == 'multi':
                setattr(profile, key, request.POST.getlist(key))
            else:
                setattr(profile, key, request.POST.get(key, '').strip())

        # Rasm (ixtiyoriy) — yangi yuklansa eskisini almashtiramiz
        photo = request.FILES.get('photo')
        if photo:
            if not (photo.content_type or '').startswith('image/'):
                messages.error(request, "Faqat rasm fayli yuklang (jpg, png).")
                return redirect('user_edit', pk=pk)
            if profile.photo:
                profile.photo.delete(save=False)
            profile.photo = photo

        profile.save()

        # Telefon o'zgargan bo'lsa user.tg_phone ni ham moslashtiramiz
        if profile.phone and user.tg_phone != profile.phone:
            user.tg_phone = profile.phone
            user.save(update_fields=['tg_phone'])

        messages.success(request, "Ma'lumotlar yangilandi.")
        return redirect('user_detail', pk=pk)

    # GET — joriy qiymatlar bilan forma
    field_values = [{'f': f, 'value': getattr(profile, f['key'], '')} for f in PROFILE_FIELDS]

    return render(request, 'users/edit.html', {
        'user_obj': user,
        'profile': profile,
        'field_values': field_values,
        'regions': REGIONS,
        'industries': INDUSTRIES,
        'trips': TRIPS,
        'languages': LANGUAGES,
    })


@login_required(login_url='/login/')
def user_delete(request, pk):
    """Foydalanuvchini o'chirish."""
    user = get_object_or_404(User, pk=pk)
    user.delete()
    messages.success(request, "Foydalanuvchi o'chirildi.")
    return redirect('users_list')


@login_required(login_url='/login/')
def user_send_message(request, pk):
    """Bitta foydalanuvchiga Telegram orqali xabar yuborish."""
    user = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        text = request.POST.get('text', '').strip()
        if not text:
            messages.error(request, "Xabar matni bo'sh bo'lmasin.")
            return redirect('user_detail', pk=pk)

        if not user.tg_id:
            messages.error(request, "Bu foydalanuvchining Telegram ID si yo'q.")
            return redirect('user_detail', pk=pk)

        from config.bot_notify import send_telegram_message
        ok = send_telegram_message(user.tg_id, text)
        if ok:
            messages.success(request, "Xabar muvaffaqiyatli yuborildi.")
        else:
            messages.error(request, "Xabar yuborishda xatolik yuz berdi.")

    return redirect('user_detail', pk=pk)


@login_required(login_url='/login/')
def user_plan_add(request, pk):
    """Foydalanuvchiga yangi obuna qo'shish."""
    user = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        price = request.POST.get('price', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()
        payment_type = request.POST.get('payment_type', 'cash')
        note = request.POST.get('note', '').strip()

        if not price or not start_date or not end_date:
            messages.error(request, "Narx, boshlanish va tugash sanasini to'ldiring.")
            return redirect('user_detail', pk=pk)

        UserPlan.objects.create(
            user=user,
            price=int(price),
            start_date=start_date,
            end_date=end_date,
            payment_type=payment_type,
            note=note,
        )

        # Foydalanuvchiga yopiq kanalga taklif yuboramiz
        from config.bot_notify import create_channel_invite_link, send_subscription_invite
        from django.conf import settings

        channel_id = getattr(settings, 'PRIVATE_CHANNEL_ID', '')
        group_id = getattr(settings, 'PRIVATE_GROUP_ID', '')

        links = []
        if user.tg_id:
            if channel_id:
                link = create_channel_invite_link(channel_id, member_limit=1)
                if link:
                    links.append(("Kanal", link))
            if group_id:
                link = create_channel_invite_link(group_id, member_limit=1)
                if link:
                    links.append(("Guruh", link))

        if links:
            send_subscription_invite(user.tg_id, links, end_date)
            messages.success(request, f"Obuna qo'shildi va {len(links)} ta taklif yuborildi.")
        else:
            messages.success(request, "Obuna qo'shildi.")
    return redirect('user_detail', pk=pk)


@login_required(login_url='/login/')
def user_plan_delete(request, pk, plan_pk):
    """Foydalanuvchi obunasini o'chirish."""
    plan = get_object_or_404(UserPlan, pk=plan_pk, user_id=pk)
    plan.delete()
    messages.success(request, "Obuna o'chirildi.")
    return redirect('user_detail', pk=pk)


@login_required(login_url='/login/')
def user_send_to_trips(request, pk):
    """Bitta foydalanuvchini Safarlar guruhiga yuborish.

    Yuborishdan OLDIN a'zolik tekshiriladi:
      - a'zo bo'lsa — to'g'ridan-to'g'ri yuboriladi.
      - a'zo bo'lmasa — avval tasdiqlash sahifasi ko'rsatiladi (keyin baribir yuborsa bo'ladi).
    """
    from config.bot_notify import send_member_to_trips, get_trips_membership, check_telegram_connection
    from django.utils import timezone
    from .models import TripsSendLog

    user = get_object_or_404(User, pk=pk)
    profile = getattr(user, 'profile', None)

    if not profile:
        messages.error(request, "Bu foydalanuvchining anketasi to'ldirilmagan.")
        return redirect('user_detail', pk=pk)

    # Ulanishni tekshiramiz
    conn_ok, conn_info = check_telegram_connection()
    if not conn_ok:
        messages.error(request, f"Telegram API ga ulanib bo'lmadi: {conn_info}. Internetni tekshirib qayta urinib ko'ring.")
        return redirect('user_detail', pk=pk)

    # 'confirmed=1' bilan POST kelsa — a'zo bo'lmasa ham baribir yuborish tasdiqlangan
    forced = request.method == 'POST' and request.POST.get('confirmed') == '1'

    if not forced:
        # Yuborishdan OLDIN a'zolikni tekshiramiz
        status = get_trips_membership(user.tg_id) if user.tg_id else 'not_member'
        if status == 'error':
            messages.warning(request, "A'zolikni tekshirib bo'lmadi (tarmoq muammosi). Qayta urinib ko'ring.")
            return redirect('user_detail', pk=pk)
        if status == 'not_member':
            # Yubormaymiz — avval tasdiqlash so'raymiz
            return render(request, 'users/send_to_trips_single_confirm.html', {
                'user_obj': user, 'profile': profile,
            })
        is_member = True  # a'zo — pastda to'g'ridan-to'g'ri yuboramiz
    else:
        is_member = False  # a'zo emas edi, admin baribir yuborishni tasdiqladi

    ok, msg = send_member_to_trips(profile)
    TripsSendLog.objects.create(
        profile=profile, sent_by=request.user,
        was_member=is_member, success=ok, error='' if ok else msg[:256],
    )
    if ok:
        profile.sent_to_trips_at = timezone.now()
        profile.save(update_fields=['sent_to_trips_at'])
        if is_member:
            messages.success(request, "Safarlar guruhiga yuborildi.")
        else:
            messages.warning(request, "Yuborildi (diqqat: bu foydalanuvchi guruh a'zosi emas edi).")
    else:
        messages.error(request, f"Yuborilmadi: {msg}")

    return redirect('user_detail', pk=pk)


@login_required(login_url='/login/')
def users_send_to_trips_start(request):
    """Yengil oraliq sahifa: darhol "Tekshirilmoqda..." ko'rsatadi va JS orqali
    a'zolarni tekshiruvchi (sekin) sahifaga o'tadi. Shunda kutish paytida
    foydalanuvchi "Tekshirilmoqda" xabarini ko'rib turadi."""
    return render(request, 'users/send_to_trips_checking.html')


@login_required(login_url='/login/')
def users_send_to_trips_bulk(request):
    """
    Safarlar guruhidagi a'zolarni topib, ularning ma'lumotlarini guruhga yuboradi.
    GET  — nechta topilganini ko'rsatadi (tasdiqlash sahifasi)
    POST — yuboradi
    """
    from config.bot_notify import send_member_to_trips, get_trips_membership, check_telegram_connection
    from django.utils import timezone
    from django.conf import settings
    from .models import TripsSendLog
    import time

    if not getattr(settings, 'TRIPS_GROUP_ID', ''):
        messages.error(request, "TRIPS_GROUP_ID .env faylida sozlanmagan.")
        return redirect('users_list')

    # Internet/Telegram ulanishини oldindan tekshiramiz — aks holда har bir a'zoни
    # tekshirish so'rovi tarmoq sabab yiqilib, xato "0 a'zo topildi" chiqar edi.
    conn_ok, conn_info = check_telegram_connection()
    if not conn_ok:
        messages.error(
            request,
            f"Telegram API ga ulanib bo'lmadi: {conn_info}. "
            "Internet aloqasini tekshirib, qayta urinib ko'ring."
        )
        return redirect('users_list')

    # Anketasi to'ldirilgan, tg_id bor BARCHA foydalanuvchilar (yuborilgan/yuborilmagan — hammasi).
    # Allaqachon yuborilganlarni ham ko'rsatamiz — qayta yuborish mumkin bo'lsin.
    candidates = User.objects.filter(
        profile__isnull=False,
    ).exclude(tg_id__isnull=True).exclude(tg_id='').select_related('profile')

    # Guruhda a'zo bo'lganlarini ajratamiz.
    # Tarmoq xatosini ('error') "a'zo emas" bilan ARALASHTIRMAYMIZ.
    # Ketma-ket bir necha xato kelsa — internet uzilgan, 100 ta timeout kutmasdan to'xtaymiz.
    members = []
    net_errors = 0
    consecutive_errors = 0
    for u in candidates:
        status = get_trips_membership(u.tg_id)
        if status == 'member':
            u.already_sent = bool(u.profile.sent_to_trips_at)  # avval yuborilganmi (belgi uchun)
            members.append(u)
            consecutive_errors = 0
        elif status == 'error':
            net_errors += 1
            consecutive_errors += 1
            if consecutive_errors >= 5:
                messages.error(
                    request,
                    "Internet aloqasida uzilish — a'zolarni tekshirib bo'lmadi. "
                    "Aloqa barqarorlashgach qayta urinib ko'ring."
                )
                return redirect('users_list')
        else:  # not_member
            consecutive_errors = 0

    # Ba'zi tekshiruvlar tarmoq sabab o'tmagan bo'lsa — ogohlantiramiz (ro'yxat to'liq emas)
    if net_errors:
        messages.warning(
            request,
            f"Diqqat: {net_errors} ta foydalanuvchini tarmoq xatosi sabab tekshirib bo'lmadi. "
            "Ro'yxat to'liq bo'lmasligi mumkin."
        )

    if request.method == 'POST':
        sent, failed = 0, 0
        for i, u in enumerate(members):
            ok, err = send_member_to_trips(u.profile)
            # Har yuborishni jurnalga yozamiz (kim yubordi, muvaffaqiyatlimi)
            TripsSendLog.objects.create(
                profile=u.profile, sent_by=request.user,
                was_member=True, success=ok, error='' if ok else (err or '')[:256],
            )
            if ok:
                u.profile.sent_to_trips_at = timezone.now()
                u.profile.save(update_fields=['sent_to_trips_at'])
                sent += 1
            else:
                failed += 1
            # Telegram limitidan himoya
            if (i + 1) % 10 == 0:
                time.sleep(1)

        messages.success(request, f"✅ Yuborildi: {sent} ta. Xato: {failed} ta.")
        return redirect('users_list')

    # GET — tasdiqlash sahifasi
    return render(request, 'users/send_to_trips_confirm.html', {
        'members': members,
        'count': len(members),
    })



