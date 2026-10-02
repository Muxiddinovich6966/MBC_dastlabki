"""
Telegram Mini App — mijozlar boti uchun.
YANGI FAYL: apps/events/miniapp.py
views.py ga tegmaymiz, hammasi shu faylda.
"""
import hashlib
import hmac
import json
import os
from datetime import datetime, date, timedelta
from urllib.parse import parse_qsl

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_exempt

from apps.events.models import Event

# Event.date — CharField bo'lgani uchun turli formatlarni sinab ko'ramiz
DATE_FORMATS = ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%y', '%Y.%m.%d']


def parse_event_date(raw):
    if not raw:
        return None
    if isinstance(raw,datetime):
        return raw.date()
    if isinstance(raw,date):
        return raw
    s = str(raw).strip()
    s = s.split(' ')[0].split('T')[0]
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s,f).date()
        except ValueError:
            continue
    return



def verify_init_data(init_data, bot_token, max_afe_hours=24):
    """
    Telegram WebApp initData imzosini tekshiradi va.
    Tugri bulsa -> user dict, aks holda -> None
    """
    if not init_data or not bot_token:
        return None
    try:
        pairs = dict(parse_qsl(init_data,keep_blank_values=True))
    except Exception:
        return None

    received_hash = pairs.pop('hash',None)
    if not received_hash:
        return None

    data_check_string = '\n'.join(f'{k}={pairs[k]}' for k in sorted(pairs.keys()))
    secret_key = hmac.new(b'WebAppData', bot_token.encode(),hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key,data_check_string.encode(),hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calc_hash, received_hash):
        return None

    try:
        auth_ts = int(pairs.get('auth_date','0'))
        if auth_ts and datetime.utcnow() - datetime.utcfromtimestamp(auth_ts) > timedelta(hours=max_afe_hours):
            return None

    except (ValueError, TypeError):
        pass

    try:
        return json.loads(pairs.get('user','{}'))
    except Exception:
        return {}



def _safe(obj,*names):
    """Bir nechta ehtimoliy maydon nomidan birinchi topilganini qaytaradi."""
    for n in names:
        v = getattr(obj,n,None)
        if v:
            return v
    return ''


def _fmt_time(v):
    if not v:
        return ''
    if hasattr(v,'strftime'):
        return v.strftime('%H:%M')
    return str(v).strip()[:5]


def _event_json(request, e):
    d = parse_event_date(getattr(e, 'date', None))

    image = ''
    image_field = getattr(e,'image',None) or getattr(e,'photo', None)
    try:
        if image_field and getattr(image_field,'url',None):
            image = request.build_absolute_uri(image_field.url)

    except Exception:
        image = ''


    venue = getattr(e,'venue',None)
    venue_name = _safe(venue,'name','title') if venue else ''
    venue_addr = _safe(venue,'address','location') if venue else ''
    if not venue_name and not venue_addr:
        venue_addr = _safe(e,'location','address','place')

    lat = getattr(venue,'latitude',None) if venue else None
    lon = getattr(venue,'longitude',None) if venue else None
    if lat is None:
        lat = getattr(e,'latitude', None)
    if lon is None:
        lon = getattr(e,'longitude',None)


    return {
        'id':e.id,
        'name':_safe(e,'name','title') or 'Tadbir',
        'date':d.isoformat() if d else '',
        'date_str':d.strftime('%d.%m.%Y') if d else str(getattr(e,'date','') or ''),
        'time':_fmt_time(_safe(e,'time','start_time')),
        'venue_name':str(venue_name or ''),
        'venue_address':str(venue_addr or ''),
        'lat':str(lat) if lat not in (None,'') else'',
        'lon':str(lon) if lon not in (None,'') else '',
        'speaker':str(_safe(e,'speaker','speakers','guest') or ''),
        'description': str(_safe(e,'description','text','about') or ''),
        'image':image,
        'is_past': bool(d and d < date.today()),
    }

@xframe_options_exempt
def miniapp(request):
    """Telegram Mini App sahifasi."""

    return render(request,'events/miniapp.html')


@xframe_options_exempt
def miniapp_events(request):
    """
    Mini App uchun Json api.
    initdata 'X-Telegram_Init-Data' header orqali keladi (majburiy emas-
    bulmasa ham kalendar kurinadi, faqat ism chiqmaydi
    """

    init_data = request.headers.get('X-Telegram-Init-Data','')
    token = getattr(settings,'CLIENT_BOT_TOKEN','') or os.getenv('CLIENT_BOT_TOKEN','') or ''
    tg_user = verify_init_data(init_data,token) if init_data else None

    itmes = []
    for e in Event.objects.all().select_related('venue'):
        row = _event_json(request, e)
        if row ['date']:
            itmes.append(row)



    itmes.sort(key=lambda r: r['date'])

    return JsonResponse({
        'ok':True,
        'today':date.today().isoformat(),
        'user':{
            'id':(tg_user or {}).get('id'),
            'first_name':(tg_user or {}).get('first_name',''),
            'verfied':bool(tg_user),
        },
        'events':itmes,
    })