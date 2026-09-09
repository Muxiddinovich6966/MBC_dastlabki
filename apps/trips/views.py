"""
Safarlar: safarlar ro'yxati va Google Sheets uslubidagi jadval.
Jadvaldagi har bir katak o'zgarganda AJAX orqali avtomatik saqlanadi.
"""
import json
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, F, Value
from django.db.models.functions import Coalesce
from django.views.decorators.http import require_POST

from .models import Trip, TripParticipant, TripCountry
from apps.users.models import User


# Jadvalda AJAX orqali tahrirlash mumkin bo'lgan maydonlar
TEXT_FIELDS = {'full_name', 'comment'}
NUMBER_FIELDS = {'entry_sum', 'trip_sum', 'deposit', 'paid'}
DATETIME_FIELDS = {'follow_up_at'}
CHOICE_FIELDS = {

    'status': dict(TripParticipant.STATUS_CHOICES),
    'travel_status': dict(TripParticipant.TRAVEL_CHOICES),
    'subscription': dict(TripParticipant.SUB_CHOICES),
    'payment_status': dict(TripParticipant.PAYMENT_CHOICES),
}

BOOL_FIELDS={'went'}

def _trip_totals(trip):
    """Jadval pastidagi/ustidagi umumiy summalar."""
    agg = trip.participants.aggregate(
        entry=Coalesce(Sum('entry_sum'), Value(0)),
        trip_s=Coalesce(Sum('trip_sum'), Value(0)),
        deposit=Coalesce(Sum('deposit'), Value(0)),
        paid=Coalesce(Sum('paid'), Value(0)),
    )
    must_pay = agg['entry'] + agg['trip_s']
    return {
        'entry': agg['entry'],
        'trip_s': agg['trip_s'],
        'must_pay': must_pay,
        'deposit': agg['deposit'],
        'paid': agg['paid'],
        'remaining': must_pay - agg['deposit'] - agg['paid'],
    }


@login_required(login_url='/login/')
def trips_list(request):
    """Safarlar ro'yxati + yangi safar yaratish."""
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        country = (request.POST.get('country') or '').strip()
        # Nom majburiy emas — bo'sh bo'lsa davlat nomi ishlatiladi
        if not name:
            name = country
        if not name:
            messages.error(request, "Davlatni tanlang yoki safar nomini kiriting.")
            return redirect('trips_list')
        trip = Trip.objects.create(
            name=name,
            country=country,
            note=(request.POST.get('note') or '').strip(),
        )
        # Yangi davlat bazada bo'lmasa va admin "ha" tasdiqlagan bo'lsa — ro'yxatga qo'shamiz
        if country and request.POST.get('add_country') == 'yes':
            TripCountry.objects.get_or_create(name=country)
        messages.success(request, f"'{trip.name}' safari yaratildi. Endi qatorlar qo'shing.")
        return redirect('trip_detail', pk=trip.pk)

    trips = Trip.objects.all()
    countries = TripCountry.objects.all()
    return render(request, 'trips/list.html', {'trips': trips, 'countries': countries})


@login_required(login_url='/login/')
@require_POST
def trip_delete(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    trip.delete()
    messages.success(request, "Safar o'chirildi.")
    return redirect('trips_list')


@login_required(login_url='/login/')
def trip_detail(request, pk):
    """Bitta safar jadvali (Google Sheets uslubida tahrirlanadigan)."""
    trip = get_object_or_404(Trip, pk=pk)
    participants = trip.participants.select_related('user', 'user__profile')

    # "Foydalanuvchidan qo'shish" ro'yxati — hali qo'shilmaganlar
    added_user_ids = participants.exclude(user__isnull=True).values_list('user_id', flat=True)
    available_users = User.objects.exclude(id__in=list(added_user_ids)).select_related('profile').order_by('-created_at')

    return render(request, 'trips/detail.html', {
        'trip': trip,
        'participants': participants,
        'available_users': available_users,
        'totals': _trip_totals(trip),
        'status_choices': TripParticipant.STATUS_CHOICES,
        'travel_choices': TripParticipant.TRAVEL_CHOICES,
        'sub_choices': TripParticipant.SUB_CHOICES,
        'payment_choices': TripParticipant.PAYMENT_CHOICES,
    })


@login_required(login_url='/login/')
@require_POST
def participant_add(request, pk):
    """Jadvalga qator qo'shish: foydalanuvchi(lar)dan yoki qo'lda bo'sh qator."""
    trip = get_object_or_404(Trip, pk=pk)
    next_order = (trip.participants.count())

    user_ids = request.POST.getlist('user_ids')
    if user_ids:
        users = User.objects.filter(id__in=user_ids).select_related('profile')
        for i, u in enumerate(users):
            TripParticipant.objects.create(
                trip=trip, user=u,
                full_name=(u.full_name or ''),
                order=next_order + i,
            )
        messages.success(request, f"{len(users)} ta foydalanuvchi qo'shildi.")
    else:
        # Qo'lda bo'sh qator (mehmon)
        TripParticipant.objects.create(
            trip=trip,
            full_name=(request.POST.get('full_name') or '').strip(),
            order=next_order,
        )
        messages.success(request, "Yangi qator qo'shildi.")
    return redirect('trip_detail', pk=trip.pk)


@login_required(login_url='/login/')
@require_POST
def participant_delete(request, pk):
    p = get_object_or_404(TripParticipant, pk=pk)
    trip_id = p.trip_id
    p.delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    messages.success(request, "Qator o'chirildi.")
    return redirect('trip_detail', pk=trip_id)


@login_required(login_url='/login/')
@require_POST
def participant_update(request, pk):
    """Bitta katakni AJAX orqali saqlash. JSON: {field, value}."""
    p = get_object_or_404(TripParticipant, pk=pk)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': "Noto'g'ri so'rov."}, status=400)

    field = data.get('field')
    value = data.get('value')

    if field in TEXT_FIELDS:
        setattr(p, field, (value or '').strip())
    elif field in NUMBER_FIELDS:
        raw = str(value or '').replace(' ', '').replace(',', '').replace('\xa0', '')
        try:
            setattr(p, field, int(raw or 0))
        except ValueError:
            return JsonResponse({'ok': False, 'error': "Raqam kiriting."}, status=400)
    elif field in CHOICE_FIELDS:
        if value and value not in CHOICE_FIELDS[field]:
            return JsonResponse({'ok': False, 'error': "Noto'g'ri qiymat."}, status=400)
        setattr(p, field, value or '')
    elif field in BOOL_FIELDS:
        setattr(p,field,bool(value))
    elif field in DATETIME_FIELDS:
        raw = str(value or '').strip()

        if not raw:
            setattr(p, field, None)
        else:
            parsed = parse_datetime(raw)

            if not parsed:
                return JsonResponse(
                    {'ok': False, 'error': "Sana-vaqt noto'g'ri."},
                    status=400
                )

            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(
                    parsed,
                    timezone.get_current_timezone()
                )

            setattr(p, field, parsed)
    else:
        return JsonResponse({'ok': False, 'error': "Bu maydonni tahrirlab bo'lmaydi."}, status=400)

    p.save(update_fields=[field])

    return JsonResponse({
        'ok': True,
        'must_pay': p.must_pay,
        'remaining': p.remaining,
        'totals': _trip_totals(p.trip),
    })
