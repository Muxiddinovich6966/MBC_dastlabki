"""
Tadbirni telefon kalendariga qo'shish.
FAYL: apps/events/calendar_ics.py — views.py ga tegmaymiz.

Ikki endpoint:
  - event_calendar_page  (/events/<id>/calendar/)  → chiroyli sahifa, bitta tugma.
      Telefon turini aniqlaydi: iPhone/Mac → .ics (Apple Calendar "qo'shish" oynasi),
      Android/boshqa → Google Calendar sahifasi ("Saqlash" tugmasi bilan).
  - event_ics            (/events/<id>/calendar.ics) → .ics faylning o'zi.
      INLINE beriladi (attachment emas) — iPhone to'g'ridan "Kalendarga qo'shish"
      oynasini ochadi, yuklab olmaydi. Ichida VALARM — 1 soat oldin eslatma.
"""
from datetime import datetime, timedelta
from urllib.parse import quote

from django.conf import settings
from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_exempt

from apps.events.models import Event
from apps.events.miniapp import parse_event_date

# Tadbir uzunligi aniq bo'lmasa — standart 2 soat.
DEFAULT_DURATION = timedelta(hours=2)
# Tadbirdan qancha oldin eslatma (bildirishnoma).
REMINDER_BEFORE = 'PT1H'  # 1 soat oldin
# Mahalliy vaqt mintaqasi (Google Calendar uchun).
LOCAL_TZ = 'Asia/Tashkent'

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


def _event_details(e):
    """Tadbir maydonlarini ikkala endpoint uchun bir joyda tayyorlaydi.

    Qaytaradi: dict(name, description, location, start, end, all_day).
    start/end — datetime (vaqtli) yoki date (butun kunlik). all_day — bool.
    """
    d = parse_event_date(getattr(e, 'date', None))
    if not d:
        raise Http404("Tadbir sanasi noto'g'ri")

    tm = _parse_time(getattr(e, 'time', None))
    if tm:
        start = datetime(d.year, d.month, d.day, tm[0], tm[1])
        end = start + DEFAULT_DURATION
        all_day = False
    else:
        start = d
        end = d + timedelta(days=1)
        all_day = True

    venue = getattr(e, 'venue', None)
    parts = []
    if venue and getattr(venue, 'name', ''):
        parts.append(str(venue.name).strip())
    loc = getattr(e, 'location', '') or ''
    if loc:
        parts.append(str(loc).strip())
    seen = []
    for p in parts:
        if p and p not in seen:
            seen.append(p)
    location = ', '.join(seen)

    name = getattr(e, 'name', '') or 'Tadbir'
    description = getattr(e, 'description', '') or ''
    speaker = getattr(e, 'speaker', '') or ''
    if speaker:
        description = description + ('\n\n' if description else '') + f'Speaker: {speaker}'

    return {
        'name': name,
        'description': description,
        'location': location,
        'start': start,
        'end': end,
        'all_day': all_day,
    }


def _google_url(det):
    """Google Calendar 'render' havolasini tuzadi (brauzerda 'Saqlash' tugmali sahifa)."""
    if det['all_day']:
        dates = det['start'].strftime('%Y%m%d') + '/' + det['end'].strftime('%Y%m%d')
    else:
        dates = det['start'].strftime('%Y%m%dT%H%M%S') + '/' + det['end'].strftime('%Y%m%dT%H%M%S')
    params = [
        ('action', 'TEMPLATE'),
        ('text', det['name']),
        ('dates', dates),
        ('details', det['description']),
        ('location', det['location']),
        ('ctz', LOCAL_TZ),
    ]
    q = '&'.join(f'{k}={quote(str(v))}' for k, v in params if v)
    return 'https://calendar.google.com/calendar/render?' + q


def _is_apple(request):
    """User-Agent orqali iPhone/iPad/Mac ekanini aniqlaydi."""
    ua = request.META.get('HTTP_USER_AGENT', '').lower()
    return any(x in ua for x in ('iphone', 'ipad', 'ipod', 'mac os', 'macintosh'))


@xframe_options_exempt
def event_calendar_page(request, pk):
    """Kalendarga qo'shish uchun chiroyli oraliq sahifa (bitta tugma)."""
    try:
        e = Event.objects.get(pk=pk)
    except Event.DoesNotExist:
        raise Http404("Tadbir topilmadi")

    det = _event_details(e)
    site = settings.SITE_URL.rstrip('/')
    ics_url = f'{site}/events/{e.id}/calendar.ics'
    google_url = _google_url(det)

    if det['all_day']:
        when = det['start'].strftime('%d.%m.%Y')
    else:
        when = det['start'].strftime('%d.%m.%Y, %H:%M')

    ctx = {
        'event_name': det['name'],
        'when': when,
        'location': det['location'],
        'ics_url': ics_url,
        'google_url': google_url,
        'is_apple': _is_apple(request),
    }
    return render(request, 'events/calendar_add.html', ctx)


@xframe_options_exempt
def event_ics(request, pk):
    """Tadbirni .ics (iCalendar) ko'rinishida qaytaradi — INLINE (yuklab olmasdan)."""
    try:
        e = Event.objects.get(pk=pk)
    except Event.DoesNotExist:
        raise Http404("Tadbir topilmadi")

    det = _event_details(e)

    if det['all_day']:
        dtstart = 'DTSTART;VALUE=DATE:' + det['start'].strftime('%Y%m%d')
        dtend = 'DTEND;VALUE=DATE:' + det['end'].strftime('%Y%m%d')
    else:
        # "Floating" mahalliy vaqt (Z/TZID yo'q) — auditoriya mahalliy.
        dtstart = 'DTSTART:' + det['start'].strftime('%Y%m%dT%H%M%S')
        dtend = 'DTEND:' + det['end'].strftime('%Y%m%dT%H%M%S')

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
        _fold(f'SUMMARY:{_ics_escape(det["name"])}'),
    ]
    if det['location']:
        lines.append(_fold(f'LOCATION:{_ics_escape(det["location"])}'))
    if det['description']:
        lines.append(_fold(f'DESCRIPTION:{_ics_escape(det["description"])}'))

    lines += [
        'BEGIN:VALARM',
        'ACTION:DISPLAY',
        _fold(f'DESCRIPTION:{_ics_escape(det["name"])}'),
        f'TRIGGER:-{REMINDER_BEFORE}',
        'END:VALARM',
        'END:VEVENT',
        'END:VCALENDAR',
    ]

    body = '\r\n'.join(lines) + '\r\n'

    resp = HttpResponse(body, content_type='text/calendar; charset=utf-8; method=PUBLISH')
    # INLINE — attachment EMAS. iPhone to'g'ridan "Kalendarga qo'shish" oynasini ochadi.
    resp['Content-Disposition'] = f'inline; filename="tadbir-{e.id}.ics"'
    return resp
