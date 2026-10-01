"""
Tadbirni telefon kalendariga qo'shish uchun .ics fayl beradi.
YANGI FAYL: apps/events/calendar_ics.py — views.py ga tegmaymiz.

Odam botdagi "📅 Kalendarga qo'shish" tugmasini bosganda shu URL ochiladi.
Telefon (iPhone/Android) .ics ni tanib, kalendarga tadbir qo'shishni taklif qiladi.
Ichida VALARM bor — tadbirdan 1 soat oldin bildirishnoma keladi.
"""
from datetime import datetime, timedelta

from django.conf import settings
from django.http import HttpResponse, Http404
from django.views.decorators.clickjacking import xframe_options_exempt

from apps.events.models import Event
from apps.events.miniapp import parse_event_date

# Tadbir uzunligi aniq bo'lmasa — standart 2 soat.
DEFAULT_DURATION = timedelta(hours=2)
# Tadbirdan qancha oldin eslatma (bildirishnoma).
REMINDER_BEFORE = 'PT1H'  # 1 soat oldin

TIME_FORMATS = ['%H:%M', '%H.%M', '%H:%M:%S', '%H', '%Hh%M']


def _ics_escape(text):
    """ICS matn maydonlari uchun maxsus belgilarni ekranlaydi."""
    if not text:
        return ''
    return (
        str(text)
        .replace('\\', '\\\\')
        .replace(';', '\\;')
        .replace(',', '\\,')
        .replace('\r\n', '\\n')
        .replace('\n', '\\n')
        .replace('\r', '\\n')
    )


def _fold(line):
    """ICS qatorlari 75 oktetdan oshmasligi kerak — uzun qatorni bo'ladi."""
    out = []
    while len(line.encode('utf-8')) > 73:
        # 73 ta belgini kesib olamiz (ko'p tilli uchun ehtiyot bilan)
        chunk = line[:73]
        out.append(chunk)
        line = ' ' + line[73:]
    out.append(line)
    return '\r\n'.join(out)


def _parse_time(raw):
    """'19:00' kabi vaqt matnini (soat, daqiqa) ga aylantiradi. Topilmasa None."""
    if not raw:
        return None
    s = str(raw).strip()
    for f in TIME_FORMATS:
        try:
            t = datetime.strptime(s, f)
            return t.hour, t.minute
        except ValueError:
            continue
    return None


@xframe_options_exempt
def event_ics(request, pk):
    """Tadbirni .ics (iCalendar) fayl ko'rinishida qaytaradi."""
    try:
        e = Event.objects.get(pk=pk)
    except Event.DoesNotExist:
        raise Http404("Tadbir topilmadi")

    d = parse_event_date(getattr(e, 'date', None))
    if not d:
        raise Http404("Tadbir sanasi noto'g'ri")

    tm = _parse_time(getattr(e, 'time', None))

    # Telefonning mahalliy vaqtida ko'rsatish uchun "floating" vaqt ishlatamiz
    # (Z yoki TZID qo'shmaymiz) — auditoriya mahalliy bo'lgani uchun eng ishonchlisi.
    if tm:
        start = datetime(d.year, d.month, d.day, tm[0], tm[1])
        end = start + DEFAULT_DURATION
        dtstart = 'DTSTART:' + start.strftime('%Y%m%dT%H%M%S')
        dtend = 'DTEND:' + end.strftime('%Y%m%dT%H%M%S')
    else:
        # Vaqt yo'q — butun kunlik tadbir.
        start = d
        end = d + timedelta(days=1)
        dtstart = 'DTSTART;VALUE=DATE:' + start.strftime('%Y%m%d')
        dtend = 'DTEND;VALUE=DATE:' + end.strftime('%Y%m%d')

    # Joy nomi/manzil
    venue = getattr(e, 'venue', None)
    location_parts = []
    if venue and getattr(venue, 'name', ''):
        location_parts.append(str(venue.name).strip())
    loc = getattr(e, 'location', '') or ''
    if loc:
        location_parts.append(str(loc).strip())
    # Bir xil qismlarni takrorlamaymiz (masalan joy nomi == manzil)
    seen = []
    for p in location_parts:
        if p and p not in seen:
            seen.append(p)
    location = ', '.join(seen)

    name = getattr(e, 'name', '') or 'Tadbir'
    description = getattr(e, 'description', '') or ''
    speaker = getattr(e, 'speaker', '') or ''
    if speaker:
        description = (description + ('\n\n' if description else '') + f'Speaker: {speaker}')

    dtstamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    domain = settings.SITE_URL.split('//')[-1]
    uid = f'event-{e.id}@{domain}'

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//MBC Platform//Tadbir//UZ',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        f'UID:{uid}',
        f'DTSTAMP:{dtstamp}',
        dtstart,
        dtend,
        _fold(f'SUMMARY:{_ics_escape(name)}'),
    ]
    if location:
        lines.append(_fold(f'LOCATION:{_ics_escape(location)}'))
    if description:
        lines.append(_fold(f'DESCRIPTION:{_ics_escape(description)}'))

    # Eslatma (bildirishnoma) — tadbirdan oldin
    lines += [
        'BEGIN:VALARM',
        'ACTION:DISPLAY',
        _fold(f'DESCRIPTION:{_ics_escape(name)}'),
        f'TRIGGER:-{REMINDER_BEFORE}',
        'END:VALARM',
        'END:VEVENT',
        'END:VCALENDAR',
    ]

    body = '\r\n'.join(lines) + '\r\n'

    resp = HttpResponse(body, content_type='text/calendar; charset=utf-8')
    # Telefon faylni kalendarga qo'shish uchun ochsin
    resp['Content-Disposition'] = f'attachment; filename="tadbir-{e.id}.ics"'
    return resp
