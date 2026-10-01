

"""
Saytdan Telegram API orqali xabar yuborish.
"""
import time
import requests
from django.conf import settings


def send_telegram_message(chat_id, text, parse_mode='HTML'):
    """Oddiy matnli xabar."""
    token = settings.CLIENT_BOT_TOKEN
    if not token:
        print("CLIENT_BOT_TOKEN yo'q!")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
        }, timeout=10)
        resp = r.json()
        if not resp.get('ok'):
            print(f"[BOT XATO] {resp}")
        return resp.get('ok', False)
    except Exception as e:
        print(f"Xatolik: {e}")
        return False


import json

def send_event_message(chat_id, text, event_id, image_url=None, image_path=None, telegraph_url=None,
                       parse_mode='HTML', is_group=False, bot_username=None):
    """
    Tadbir xabarini yuboradi.
    - Foydalanuvchilarga: 6 ta RSVP tugma
    - Guruhlarga: Ro'yxatdan o'tish tugmasi
    """
    token = settings.CLIENT_BOT_TOKEN
    if not token:
        print("CLIENT_BOT_TOKEN yo'q!")
        return False

    bot_link = f"https://t.me/{bot_username}" if bot_username else "https://t.me/MBC_platforum_bot"
    t_url = telegraph_url if telegraph_url else "https://telegra.ph/"

    # Eslatma: kalendarga qo'shish havolasi endi xabar MATNIDA (build_event_text), tugma emas.

    if is_group:
        # Guruh/kanalga — ovozlarni ko'rish (Telegraph) tugmasi
        keyboard = {
            "inline_keyboard": [[
                {"text": "👥 Ovozlarni ko'rish", "url": t_url},
            ]]
        }
    else:
        # Foydalanuvchiga — 6 ta tugma
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Boraman",
                     "callback_data": f"rsvp:boraman:{event_id}"},
                    {"text": "🤔 Balki borarman",
                     "callback_data": f"rsvp:balki_borarman:{event_id}"},
                ],
                [
                    {"text": "😐 Balki bormasman",
                     "callback_data": f"rsvp:balki_bormasman:{event_id}"},
                    {"text": "❌ Bormayman",
                     "callback_data": f"rsvp:bormayman:{event_id}"},
                ],
                [
                    {"text": "👥 Ovozlarni ko'rish", "url": t_url},
                    {"text": "🤖 Ro'yxatdan o'tish", "url": f"{bot_link}?start=register"}
                ]
            ]
        }

    try:
        import os
        if image_path and os.path.exists(image_path):
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            payload = {
                'chat_id': chat_id,
                'caption': text,
                'parse_mode': parse_mode,
                'reply_markup': json.dumps(keyboard),
            }
            with open(image_path, 'rb') as f:
                r = requests.post(url, data=payload, files={'photo': f}, timeout=60)
        elif image_url:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            payload = {
                'chat_id': chat_id,
                'photo': image_url,
                'caption': text,
                'parse_mode': parse_mode,
                'reply_markup': keyboard,
            }
            r = requests.post(url, json=payload, timeout=60)
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'reply_markup': keyboard,
            }
            r = requests.post(url, json=payload, timeout=60)
        
        resp = r.json()
        if not resp.get('ok'):
            print(f"[BOT XATO] {resp}")
            return False
        # Muvaffaqiyatli — xabar ID sini qaytaramiz (message_id > 0, ya'ni truthy).
        # Bu keyinchalik tahrirlashda eski xabarni o'chirish uchun kerak.
        return resp['result']['message_id']
    except Exception as e:
        print(f"Xatolik: {e}")
        return False


def check_telegram_connection():
    """Telegram API ga ulanish bor-yo'qligini bitta getMe so'rovi bilan tekshiradi.

    Qaytadi: (ok, natija) — ok=True bo'lsa bot username; aks holda xato sababi.
    Ommaviy amallardан oldin ishlatiladi: internet yo'q bo'lsa, 100 ta so'rovни
    behuda kutmasдан, adminга aniq "internet yo'q" xabarини ko'rsatish uchun.
    """
    token = settings.CLIENT_BOT_TOKEN
    if not token:
        return False, "CLIENT_BOT_TOKEN yo'q"
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        resp = r.json()
        if resp.get('ok'):
            return True, resp['result'].get('username', '')
        return False, resp.get('description', 'noma\'lum xato')
    except Exception:
        return False, "Telegram API ga ulanib bo'lmadi (internet yoki DNS muammosi)"


def get_telegram_chat(chat_id):
    """Chatni getChat orqali tekshiradi (bot uni ko'ra oladimi).

    Qaytadi: (ok, natija) — ok=True bo'lsa natija chat nomi; aks holda xato matni.
    Guruh/kanal qo'shishда ID to'g'riligini tekshirish uchun ishlatiladi.
    """
    token = settings.CLIENT_BOT_TOKEN
    if not token:
        return False, "CLIENT_BOT_TOKEN yo'q"
    url = f"https://api.telegram.org/bot{token}/getChat"
    try:
        r = requests.get(url, params={'chat_id': chat_id}, timeout=10)
        resp = r.json()
        if resp.get('ok'):
            res = resp['result']
            return True, res.get('title') or res.get('username') or str(chat_id)
        return False, resp.get('description', 'chat topilmadi')
    except Exception as e:
        return False, str(e)


def delete_telegram_message(chat_id, message_id):
    """Yuborilgan tadbir xabarini o'chiradi (tahrirlashda eskisini uchirish uchun)."""
    token = settings.CLIENT_BOT_TOKEN
    if not token or not message_id:
        return False
    url = f"https://api.telegram.org/bot{token}/deleteMessage"
    try:
        r = requests.post(url, json={
            'chat_id': chat_id,
            'message_id': message_id,
        }, timeout=10)
        return r.json().get('ok', False)
    except Exception as e:
        print(f"Xabar o'chirish xatosi ({chat_id}): {e}")
        return False


def delete_worker_bot_message(chat_id, message_id):
    """Ishchilar boti orqali yuborilgan xabarni o'chiradi (tadbir tahrirlanganda)."""
    token = settings.WORKER_BOT_TOKEN
    if not token or not message_id:
        return False
    url = f"https://api.telegram.org/bot{token}/deleteMessage"
    try:
        r = requests.post(url, json={
            'chat_id': chat_id,
            'message_id': message_id,
        }, timeout=10)
        return r.json().get('ok', False)
    except Exception as e:
        print(f"Worker xabar o'chirish xatosi ({chat_id}): {e}")
        return False


def build_event_text(event):
    """Tadbir uchun chiroyli Telegram xabar matni.
    Tartib: description → ajratgich → tafsilotlar → ovoz so'rovi
    """
    lines = []

    # Birinchi — tavsif (rasm caption'i sifatida keladi)
    if event.description:
        lines.append(event.description)
        lines.append("")

    lines.append("─" * 20)

    # Tadbir nomi — tavsifdan keyin, speaker oldida (sarlavha)
    if event.name:
        lines.append(f"🎉 <b>{event.name}</b>")

    if event.speaker:
        lines.append(f"🎙 <b>Speaker:</b> {event.speaker}")
    if event.theme:
        lines.append(f"📌 <b>Mavzu:</b> {event.theme}")

    lines.append("")
    lines.append(f"📅 <b>Sana:</b> {event.date}")
    lines.append(f"🕐 <b>Vaqt:</b> {event.time}")

    if event.latitude and event.longitude:
        map_url = f"https://maps.google.com/?q={event.latitude},{event.longitude}"
        lines.append(f"📍 <b>Manzil:</b> {event.location}")
        lines.append(f'🗺 <a href="{map_url}">Xaritada ko\'rish</a>')
    else:
        lines.append(f"📍 <b>Manzil:</b> {event.location}")

    # Tadbirni telefon kalendariga qo'shish havolasi (chiroyli sahifa → bitta tugma).
    site_url = getattr(settings, 'SITE_URL', 'https://mbc-platform.duckdns.org').rstrip('/')
    cal_url = f"{site_url}/events/{event.id}/calendar/"
    lines.append("")
    lines.append("📅 <b>Tadbirni kalendarga qo'shish uchun link ustidan bosing:</b>")
    lines.append(f'<a href="{cal_url}">{cal_url}</a>')

    lines.append("─" * 20)
    lines.append("")
    lines.append("👇 <i>Ishtirok etasizmi?</i>")

    return "\n".join(lines)


def send_event_to_all(event, image_url=None, image_path=None, bot_username=None):
    """
    Tadbirni barcha foydalanuvchi va guruhlarga batch tarzda yuboradi.
    Qaytadi: yuborilgan foydalanuvchilar soni.
    """
    from apps.users.models import User
    from apps.events.models import EventSendLog

    def _log(*, user=None, group=None, chat_id=None, msg_id=None):
        """Yuborishni jurnalga yozadi (tahrirlashda eski xabarni o'chirish uchun)."""
        defaults = {
            'target_type': 'group' if group else 'user',
            'chat_id': str(chat_id),
            'message_id': msg_id or None,
            'status': 'success' if msg_id else 'failed',
            'error': '' if msg_id else "Yuborilmadi",
        }
        try:
            if group:
                EventSendLog.objects.update_or_create(event=event, group=group, defaults=defaults)
            else:
                EventSendLog.objects.update_or_create(event=event, user=user, defaults=defaults)
        except Exception as e:
            print(f"[LOG XATO] {e}")

    text = build_event_text(event)

    from config.telegraph_utils import create_telegraph_page
    if not event.telegraph_url:
        t_url = create_telegraph_page(event.name or "Tadbir")
        if t_url:
            event.telegraph_url = t_url
            event.save(update_fields=['telegraph_url'])

    sent_count = 0

    # Foydalanuvchilarga batch tarzda
    if event.send_to_all_users:
        users = list(User.objects.filter(
            role='user', is_active=True
        ).exclude(tg_id__isnull=True).exclude(tg_id=''))

        for i, user in enumerate(users):
            msg_id = send_event_message(
                chat_id=user.tg_id,
                text=text,
                event_id=event.id,
                image_url=image_url,
                image_path=image_path,
                telegraph_url=event.telegraph_url,
                is_group=False,
            )
            _log(user=user, chat_id=user.tg_id, msg_id=msg_id)
            if msg_id:
                sent_count += 1
            # Har 10 tadan keyin 0.5 sekund kutish
            if (i + 1) % 10 == 0:
                time.sleep(0.5)

    # Guruhlarga
    for group in event.send_groups.all():
        msg_id = send_event_message(
            chat_id=group.tg_id,
            text=text,
            event_id=event.id,
            image_url=image_url,
            image_path=image_path,
            telegraph_url=event.telegraph_url,
            is_group=True,
            bot_username=bot_username,
        )
        _log(group=group, chat_id=group.tg_id, msg_id=msg_id)

    return sent_count

def create_channel_invite_link(channel_id,member_limit=1):
    """
    Yopiq kanal uchun bir martalik taklif havolasi yatadi.
    member_limit=1 - havoladan faqat 1 kishi foydalana oladi.
    """
    token = settings.CLIENT_BOT_TOKEN
    if not token:
        print("CLIENT_BOT_TOKE yuq")
        return None
    url = f"https://api.telegram.org/bot{token}/createChatInviteLink"
    try:
        r = requests.post(url,json={
            'chat_id': channel_id,
            'member_limit': member_limit,
        },timeout=10)
        resp = r.json()
        if resp.get('ok'):
            return resp['result']['invite_link']
        print(f"[INVITE XATO] {resp}")
        return None
    except Exception as e:
        print(f"Invite link xatosi:{e}")
        return None


def send_subscription_invite(user_tg_id, links, end_date):
    """
    Obuna faollashganda foydalanuvchiga taklif yuboradi.
    links — ro'yxat: [("Kanal", "https://..."), ("Guruh", "https://...")]
    """
    text = (
        "🎉 <b>Tabriklaymiz! Obunangiz faollashtirildi.</b>\n\n"
        f"📅 Amal qilish muddati: <b>{end_date}</b> gacha\n\n"
        "Quyidagi havolalar orqali yopiq guruhlarimizga qo'shiling 👇"
    )
    # Har bir havola uchun alohida tugma
    buttons = []
    for name, link in links:
        buttons.append([{"text": f"🔑 {name}ga kirish", "url": link}])

    keyboard = {"inline_keyboard": buttons}

    token = settings.CLIENT_BOT_TOKEN
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={
            'chat_id': user_tg_id,
            'text': text,
            'parse_mode': 'HTML',
            'reply_markup': keyboard,
        }, timeout=10)
        return r.json().get('ok', False)
    except Exception as e:
        print(f"Taklif yuborish xatosi: {e}")
        return False



def ban_from_channel(channel_id,user_tg_id):
    """Foydalanuvchini yopiq kanal/guruhdan chiqaradi (obuna tugaganda).

    Diqqat: darhol unban QILMAYMIZ. Sabab: (1) oddiy guruhda darhol unban odamni
    qayta qo'shib yuboradi; (2) obunasi tugagan odam baribir o'zicha qayta kira
    olmasligi kerak. Qayta a'zo bo'lganda administrator uni qayta qo'shadi.
    """
    token = settings.CLIENT_BOT_TOKEN
    if not token:
        return False
    url = f"https://api.telegram.org/bot{token}/banChatMember"
    try:
        r = requests.post(url,json={
            'chat_id': channel_id,
            'user_id': int(user_tg_id),
        },timeout=10)
        resp = r.json()
        if not resp.get('ok'):
            print(f"[BAN XATO]{resp}")
        return resp.get('ok',False)
    except Exception as e:
        print(f"Ban xatosi:{e}")
        return False


def send_subscription_warning(user_tg_id, end_date,days_left):
    """
    Obuna tugashidan oldin ogohlantirish yuboradi.
    days_left -- necha kun qolganini (0 bulsa bugun tugaydi)
    """
    token = settings.CLIENT_BOT_TOKEN
    if not token:
        return False

    if days_left ==0:
        text = (
            "⏳ <b>Eslatma: obunangiz BUGUN tugaydi!</b>\n\n"
            f"📅 Tugash sanasi: <b>{end_date}</b>\n\n"
            "<i>Agar bugun uzaytirmasangiz, ertaga yopiq kanaldan "
            "avtomatik chiqarib yuborilasiz.</i>\n\n"
            "Obunani uzaytirishni xohlaysizmi?"
        )
    else:
        text = (
            f"⏳ <b>Obunangiz tugashiga {days_left} kun qoldi</b>\n\n"
            f"📅 Tugash sanasi: <b>{end_date}</b>\n\n"
            "<i>Obuna tugaganda yopiq kanaldan chiqarib yuborilasiz.</i>\n\n"
            "Obunani uzaytirishni xohlaysizmi?"
        )

    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Ha, administratorga murojaat", "callback_data": "sub_extend:yes"},
            {"text": "❌ Yo'q", "callback_data": "sub_extend:no"},
        ]]
    }

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={
            'chat_id': user_tg_id,
            'text': text,
            'parse_mode': 'HTML',
            'reply_markup': keyboard,
        }, timeout=10)
        return r.json().get('ok', False)
    except Exception as e:
        print(f"Ogohlantirish xatosi: {e}")
        return False


def send_worker_task(worker_tg_id, event_name, event_date, task_description, deadline_date, days_before, task_id, is_update=False, overdue_grace=False, co_worker_names=None):
    """Ishchiga vazifa xabari (ishchilar boti tokeni bilan).

    is_update=True bo'lsa — 'yangi vazifa' emas, 'tadbir o'zgardi' deb yuboradi.
    overdue_grace=True bo'lsa — vazifa muddati o'tib ketgan holda yaratilgan,
    ishchiga 1 kun (ertagacha) muhlat berilganini eslatamiz.
    co_worker_names — shu vazifa biriktirilgan BOSHQA ishchilar ismi (ro'yxat).
    Bo'lsa, "bu vazifa sizga va ... ga biriktirilgan" deb ko'rsatiladi.
    """
    token = settings.WORKER_BOT_TOKEN
    if not token:
        print("WORKER_BOT_TOKEN yo'q!")
        return False
    if is_update:
        header = (
            "⚠️ <b>DIQQAT! TADBIR O'ZGARDI!</b>\n"
            "<i>Quyidagi tadbir/vazifa yangilandi — iltimos, e'tibor bering 👇</i>\n\n"
        )
    else:
        header = "🎉 <b>Sizga yangi tadbir va vazifa biriktirildi!</b>\n\n"
    grace_note = (
        "\n\n⚠️ <b>Bu vazifaning asl muddati o'tib ketgan.</b>\n"
        "Sizga 1 kun — <b>ertagacha</b> muhlat berildi. Iltimos, kechiktirmang!"
        if overdue_grace else ""
    )
    # Vazifa bir nechta ishchiga biriktirilgan bo'lsa — hamkorlar ismini ko'rsatamiz.
    shared_note = ""
    if co_worker_names:
        names = ", ".join(co_worker_names)
        shared_note = (
            f"\n👥 Bu vazifa <b>sizga va {names}</b> ga biriktirilgan.\n"
            f"<i>Biringiz bajarsangiz kifoya.</i>\n"
        )
    text = (
        header +
        f"🎉 Tadbir: <b>{event_name}</b>\n"
        f"📅 Sana: {event_date}\n\n"
        f"📌 Vazifa: {task_description}\n"
        + shared_note +
        f"⏳ Qachongacha: {deadline_date}"
        + grace_note
    )
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Bajardim", "callback_data": f"we_done_{task_id}"},
        ]]
    }
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={
            'chat_id': worker_tg_id, 'text': text,
            'parse_mode': 'HTML', 'reply_markup': keyboard,
        }, timeout=10)
        resp = r.json()
        if resp.get('ok'):
            # Xabar ID sini qaytaramiz (NotificationLog uchun kerak bo'lishi mumkin)
            return resp['result']['message_id']
        print(f"[WORKER XATO] {resp}")
        return False
    except Exception as e:
        print(f"Ishchiga xabar xatosi: {e}")
        return False


def send_boss_task_pending(boss_tg_id,worker_name,event_name,event_date,task_description,deadline_date, is_update=False):
    """
    Boshliqqa har bir vazifa alohida - 'Kutilmoqda' statusi bilan.
    Vazifa bajarilganda shu xabar 'Bajarildi' ga yangilanadi.
    is_update=True bo'lsa — 'tadbir o'zgardi' deb yuboradi.
    Qaytadi : yuborilgan xabarning message_id si (NotificationLog un).
    """
    token= settings.WORKER_BOT_TOKEN
    if not token:
        print("WORKER_BOT_TOKEN yuq!")
        return None
    header = "⚠️ <b>Tadbir o'zgardi — vazifa yangilandi</b>\n\n" if is_update else "🆕 <b>Yangi vazifa</b>\n\n"
    text = (
        header +
        f"👤 Ishchi: <b>{worker_name}</b>\n"
        f"🎉 Tadbir: <b>{event_name}</b>\n"
        f"📅 Sana: {event_date}\n"
        f"📌 Vazifa: <b>{task_description}</b>\n"
        f"⏳ Deadline: <b>{deadline_date}</b>\n"
        f"📊 Holati: ⏳ Kutilmoqda"
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={
            'chat_id': boss_tg_id,'text':text,'parse_mode':'HTML',
        },timeout=10)
        resp = r.json()
        if resp.get('ok'):
            return resp['result']['message_id']
        print(f"[BOSS XATO] {resp}")
        return None
    except Exception as e:
        print(f"Boshliqqa xabar xatosi: {e}")
        return None



def send_worker_bot_message(chat_id, text, parse_mode='HTML', reply_markup=None):
    """Ishchilar boti tokeni bilan xabar yuboradi (kechikkan/eslatma xabarlari uchun)."""
    token = settings.WORKER_BOT_TOKEN
    if not token:
        print("WORKER_BOT_TOKEN yo'q!")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
    if reply_markup:
        payload['reply_markup'] = reply_markup
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json().get('ok', False)
    except Exception as e:
        print(f"Worker bot xabar xatosi: {e}")
        return False


def send_task_updated(worker_tg_id, event_name, event_date, task_description, deadline_date):
    """Tadbir/vazifa yangilanganda ishchiga xabar."""
    token = settings.WORKER_BOT_TOKEN
    if not token:
        return False
    text = (
        "📝 <b>Tadbir yangilandi!</b>\n\n"
        f"🎉 Tadbir: <b>{event_name}</b>\n"
        f"📅 Yangi sana: <b>{event_date}</b>\n\n"
        f"📌 Sizning vazifangiz: <b>{task_description}</b>\n"
        f"⏳ Yangi deadline: <b>{deadline_date}</b>\n\n"
        "Iltimos, o'zgarishlarni hisobga oling!"
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={
            'chat_id': worker_tg_id, 'text': text, 'parse_mode': 'HTML',
        }, timeout=10)
        return r.json().get('ok', False)
    except Exception as e:
        print(f"Yangilanish xabar xatosi: {e}")
        return False


def build_member_card(profile):
    """Foydalanuvchi ma'lumot kartochkasi matni (Safarlar guruhi uchun)."""
    name = f"{profile.name or ''} {profile.surname or ''}".strip() or "—"
    lines = [f"👤 <b>{name}</b>"]

    if profile.phone:
        lines.append(f"📞 {profile.phone}")
    if profile.work_location:
        lines.append(f"📍 {profile.work_location}")

    company = profile.brand or ''
    if company and profile.industry:
        lines.append(f"🏢 {company} — {profile.industry}")
    elif company:
        lines.append(f"🏢 {company}")
    elif profile.industry:
        lines.append(f"🏢 {profile.industry}")

    if profile.instagram:
        insta = profile.instagram.strip().lstrip('@')
        lines.append(f"📷 @{insta}")

    return "\n".join(lines)


def send_member_to_trips(profile):
    """
    Bitta foydalanuvchi ma'lumotini Safarlar guruhiga yuboradi (rasm bilan).
    Qaytadi: (muvaffaqiyat, xabar) — (True, 'ok') yoki (False, 'sabab')
    """
    import os

    token = settings.CLIENT_BOT_TOKEN
    group_id = getattr(settings, 'TRIPS_GROUP_ID', '')

    if not token:
        return False, "CLIENT_BOT_TOKEN yo'q"
    if not group_id:
        return False, "TRIPS_GROUP_ID .env faylida sozlanmagan"

    text = build_member_card(profile)

    # Rasm bo'lsa — rasm bilan yuboramiz
    image_path = None
    try:
        if profile.photo and os.path.exists(profile.photo.path):
            image_path = profile.photo.path
    except Exception:
        image_path = None

    try:
        if image_path:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            with open(image_path, 'rb') as photo:
                r = requests.post(url, data={
                    'chat_id': group_id,
                    'caption': text,
                    'parse_mode': 'HTML',
                }, files={'photo': photo}, timeout=30)
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            r = requests.post(url, json={
                'chat_id': group_id,
                'text': text,
                'parse_mode': 'HTML',
            }, timeout=15)

        resp = r.json()
        if resp.get('ok'):
            return True, "ok"
        return False, resp.get('description', 'nomalum xato')
    except Exception as e:
        return False, str(e)


def get_trips_membership(tg_id):
    """Foydalanuvchi Safarlar guruhida a'zomi — tri-state qaytaradi.

    Qaytadi: 'member' | 'not_member' | 'error'
      - 'error' — tarmoq/DNS/timeout sabab TEKSHIRIB BO'LMADI (a'zo emas degani EMAS!).
    Bot guruhda admin bo'lishi shart.
    """
    token = settings.CLIENT_BOT_TOKEN
    group_id = getattr(settings, 'TRIPS_GROUP_ID', '')
    if not token or not group_id or not tg_id:
        return 'not_member'

    url = f"https://api.telegram.org/bot{token}/getChatMember"
    try:
        r = requests.get(url, params={'chat_id': group_id, 'user_id': tg_id}, timeout=10)
        resp = r.json()
        if not resp.get('ok'):
            return 'not_member'
        status = resp['result'].get('status', '')
        return 'member' if status in ('creator', 'administrator', 'member', 'restricted') else 'not_member'
    except Exception as e:
        # Tarmoq xatosi — "a'zo emas" bilan aralashtirmaymiz
        print(f"getChatMember xatosi ({tg_id}): {e}")
        return 'error'


def is_member_of_trips_group(tg_id):
    """Foydalanuvchi Safarlar guruhida a'zomi (True/False).

    Bitta yuborishдаgi ogohlantirish uchun — tarmoq xatosi ham False bo'ladi.
    """
    return get_trips_membership(tg_id) == 'member'

def resend_checklist(work_event, changes=None):
    """Tadbir tahrirlanganda: eski check-list rasmini o'chirib, tepasida "Yangilandi"
    banneri bo'lgan YANGI rasmni guruh pastiga qayta yuboradi (ko'rinishi uchun).
    Yangi message_id saqlanadi.
    """
    token = settings.WORKER_BOT_TOKEN
    group_id = getattr(settings, 'WORK_GROUP_ID', '')
    if not token or not group_id:
        return False

    # Eski check-list rasmini o'chiramiz (agar bo'lsa)
    if work_event.checklist_message_id and work_event.checklist_chat_id:
        delete_worker_bot_message(work_event.checklist_chat_id, work_event.checklist_message_id)

    note = None
    if changes:
        note = "Yangilandi · o'zgargan: " + ", ".join(changes)
    # Izohni saqlaymiz — keyingi (vazifa bajarish) yangilashlarida ham banner ko'rinib tursin
    work_event.checklist_note = note or ''

    from config.checklist_image import render_checklist_image
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        photo = render_checklist_image(work_event, update_note=note)
        r = requests.post(
            url,
            data={'chat_id': group_id},
            files={'photo': ('checklist.png', photo, 'image/png')},
            timeout=30,
        )
        resp = r.json()
        if resp.get('ok'):
            work_event.checklist_chat_id = str(group_id)
            work_event.checklist_message_id = resp['result']['message_id']
            work_event.save(update_fields=['checklist_chat_id', 'checklist_message_id', 'checklist_note'])
            return True
        print(f"[CHECKLIST RESEND XATO] {resp}")
        return False
    except Exception as e:
        print(f"Check-list qayta yuborish xatosi:{e}")
        return False


def send_worker_event_update_notice(worker_tg_id, work_event, changes):
    """Bitta ishchiga tadbir o'zgargani haqida qisqa ogohlantirish (tugmasiz).
    Faqat vaqt/sana kabi o'zgarishlarda ishlatiladi — vazifa qaytadan yuborilmaydi.
    """
    token = settings.WORKER_BOT_TOKEN
    if not token or not worker_tg_id:
        return False

    ev_date = work_event.event_date
    date_str = ev_date.strftime('%d.%m.%Y') if hasattr(ev_date, 'strftime') else str(ev_date)
    time_str = ''
    if getattr(work_event, 'event_time', None):
        t = work_event.event_time
        time_str = t.strftime('%H:%M') if hasattr(t, 'strftime') else str(t)[:5]

    lines = [
        "⚠️ <b>DIQQAT! TADBIR O'ZGARDI!</b>",
        "",
        f"🎉 Tadbir: <b>{work_event.name}</b>",
        f"📅 Sana: {date_str}" + (f"\n🕐 Vaqt: {time_str}" if time_str else ""),
    ]
    if changes:
        lines.append("")
        lines.append("O'zgargan: <b>" + ", ".join(changes) + "</b>")
    lines.append("")
    lines.append("<i>Vazifangiz o'sha-o'sha — faqat tadbir ma'lumoti yangilandi.</i>")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={
            'chat_id': worker_tg_id, 'text': "\n".join(lines), 'parse_mode': 'HTML',
        }, timeout=10)
        return r.json().get('ok', False)
    except Exception as e:
        print(f"Ishchiga ogohlantirish xatosi: {e}")
        return False


def _group_task_by_dept(work_event):
    """Tadbir vazifalarini bulimlar buyicha ajratadi"""
    from apps.workers.models import Task

    tasks = Task.objects.filter(event = work_event).prefetch_related('workers').order_by('deadline_date')
    groups = {}
    for task in tasks:
        task_workers= list(task.workers.all())
        dept = task_workers[0].department if task_workers and task_workers[0].department else 'other'
        groups.setdefault(dept,[]).append(task)
    return groups


def send_checklists(work_event):
    """Har bir bulim uchun alohida checklist RASMI yuboradi (yoki mavjudni yangilaydi)."""
    from apps.workers.models import ChecklistMessage
    from config.checklist_image import render_checklist_image

    token = settings.WORKER_BOT_TOKEN
    group_id = getattr(settings, 'WORK_GROUP_ID','')
    if not token or not group_id:
        return 0

    groups = _group_task_by_dept(work_event)
    sent=0

    for dept, tasks in groups.items():
        try:
            photo = render_checklist_image(work_event, department=dept)
        except Exception as e:
            print(f"Check-list rasm xatosi ({dept}):{e}")
            continue

        existing = ChecklistMessage.objects.filter(event=work_event,department=dept).first()

        try:
            edited = False
            if existing:
                # Mavjud rasmni yangisiga almashtiramiz
                url = f"https://api.telegram.org/bot{token}/editMessageMedia"
                media = json.dumps({'type': 'photo', 'media': 'attach://photo'})
                photo.seek(0)
                r = requests.post(
                    url,
                    data={
                        'chat_id': existing.chat_id,
                        'message_id': existing.message_id,
                        'media': media,
                    },
                    files={'photo': ('checklist.png', photo, 'image/png')},
                    timeout=30,
                )
                resp = r.json()
                if resp.get('ok'):
                    edited = True
                elif 'not modified' in resp.get('description',''):
                    edited = True
                else:
                    # Tahrirlab bo'lmadi (masalan eski xabar matn edi yoki o'chib ketgan)
                    # — eskisini o'chirib, yangi rasm yuboramiz.
                    print(f"[CHECKLIST edit o'tmadi, qayta yuboramiz] {dept}:{resp}")
                    delete_worker_bot_message(existing.chat_id, existing.message_id)
                    existing.delete()
                    existing = None

            if not edited:
                url = f"https://api.telegram.org/bot{token}/sendPhoto"
                photo.seek(0)
                r = requests.post(
                    url,
                    data={'chat_id': group_id},
                    files={'photo': ('checklist.png', photo, 'image/png')},
                    timeout=30,
                )
                resp = r.json()
                if resp.get('ok'):
                    ChecklistMessage.objects.create(
                        event=work_event,department=dept,
                        chat_id=str(group_id),message_id=resp['result']['message_id'],
                    )
                    sent+=1
                else:
                    print(f"[CHECKLIST XATO] {dept}:{resp}")

        except Exception as e:
            print(f"Check-list xatosi ({dept}):{e}")

    return sent

def update_checklists(work_event):
    """Vazifalar bajarilganda checklist yangilanadi"""
    return send_checklists(work_event)




def send_tasks_summary(worker_tg_id,event_name,event_date,task_count,event_id,is_update=False):
    """
        Ishchiga tadbir vazifalari haqida QISQA xulosa + "Hammasini ko'rish" tugmasi.
        Vazifalarning o'zi keyin, har biri o'z kunida yuboriladi.
        """
    token = settings.WORKER_BOT_TOKEN
    if not token:
        return None

    head =  "🔄 <b>Tadbir yangilandi!</b>\n\n" if is_update else "🎉 <b>Sizga yangi vazifalar biriktirildi!</b>\n\n"
    text = (
    head +
        f"🎯 Tadbir: <b>{event_name}</b>\n"
        f"📅 Sana: {event_date}\n"
        f"📋 Vazifalar soni: <b>{task_count} ta</b>\n\n"
        "<i>Har bir vazifa o'z kuni kelganda alohida yuboriladi."
        "Hoziroq hammasini ko'rish uchun quyidagi tugmani bosing 👇</i>"
    )
    keyboard = {"inline_keyboard":[[
        {"text": f"📋 Hammasini ko'rish ({task_count})", "callback_data": f"we_event_{event_id}"}
    ]]}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={
            'chat_id':worker_tg_id,'text':text,
            'parse_mode':'HTML','reply_markup': keyboard,
        },timeout=10)
        resp = r.json()
        if resp.get('ok'):
            return resp['result']['message_id']
        print(f"[XULOSA XATO] {resp}")
        return None
    except Exception as e:
        print(f"Xulosa yuborish xatosi: {e}")
        return None


def send_event_approval_request(work_event):
    """Birlashgan tadbir yaratilganda boshliq(lar)ga tasdiq so'rovini yuboradi.

    Boshliq ✅/❌ tugmasi bilan tasdiqlaydi yoki rad etadi (worker bot orqali).
    (chat_id, message_id) ro'yxatini qaytaradi.
    """
    import html
    token = settings.WORKER_BOT_TOKEN
    if not token:
        print("WORKER_BOT_TOKEN yo'q!")
        return []

    from apps.workers.models import Worker

    # Tasdiq FAQAT boshliqqa boradi (adminga emas — user shuni so'radi 2026-09-29)
    bosses = list(Worker.objects.filter(role='boss')
                  .exclude(telegram_id__isnull=True))
    if not bosses:
        print("Tasdiqlaydigan boshliq (role='boss', telegram_id li) topilmadi.")
        return []

    ev = getattr(work_event, 'client_event', None)
    task_count = work_event.tasks.count()

    def _fmt(value, fmt, cut):
        # Yangi yaratilgan obyektда maydon hali string bo'lishi mumkin (DB'dan o'qilmagan)
        if not value:
            return '—'
        try:
            return value.strftime(fmt)
        except AttributeError:
            return str(value)[:cut]

    date_str = _fmt(work_event.event_date, '%d.%m.%Y', 10)
    time_str = _fmt(work_event.event_time, '%H:%M', 5)
    tpl_part = f"  ·  🧩 {html.escape(work_event.template.name)}" if work_event.template else ""

    lines = [
        "🆕 <b>YANGI TADBIR — TASDIQ KUTILMOQDA</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"🎯 <b>{html.escape(work_event.name)}</b>",
        f"📅 {date_str}   🕒 {time_str}",
        "",
        "👥 <b>Ishchilar qismi</b>",
        f"   📋 Vazifalar: <b>{task_count} ta</b>{tpl_part}",
    ]
    if ev:
        groups = ", ".join(g.title for g in ev.send_groups.all()) or "—"
        all_txt = "ha" if ev.send_to_all_users else "yo'q"
        desc = (ev.description or "").strip()
        if len(desc) > 160:
            desc = desc[:160] + "…"
        lines += ["", "📣 <b>Mijozlar e'loni</b>"]
        if ev.theme:
            lines.append(f"   🏷 {html.escape(ev.theme)}")
        if ev.speaker:
            lines.append(f"   🎤 {html.escape(ev.speaker)}")
        if ev.location:
            lines.append(f"   📍 {html.escape(ev.location)}")
        lines.append(f"   👤 Hammaga: {all_txt}  ·  📢 {html.escape(groups)}")
        if desc:
            lines += ["", f"<i>{html.escape(desc)}</i>"]

    lines += ["", "Tasdiqlasangiz — ishchilarga vazifalar va mijozlarga e'lon yuboriladi."]
    text = "\n".join(lines)

    keyboard = {"inline_keyboard": [[
        {"text": "✅ Tasdiqlash", "callback_data": f"evapp:ok:{work_event.id}"},
        {"text": "❌ Rad etish", "callback_data": f"evapp:no:{work_event.id}"},
    ]]}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': None, 'text': text,
        'parse_mode': 'HTML', 'reply_markup': keyboard,
    }
    sent = []
    for b in bosses:
        payload['chat_id'] = b.telegram_id
        resp = None
        last_err = None
        # Tarmoq sekin bo'lsa timeout bo'lmasin — 3 marta urinamiz (connect 10s, read 30s)
        for attempt in range(3):
            try:
                r = requests.post(url, json=payload, timeout=(10, 30))
                resp = r.json()
                break
            except Exception as e:
                last_err = e
                print(f"Tasdiq so'rovi urinishi {attempt + 1}/3 muvaffaqiyatsiz ({b.telegram_id}): {e}")
                time.sleep(2)
        if resp is None:
            print(f"Tasdiq so'rovi yuborilmadi ({b.telegram_id}): {last_err}")
            continue
        if resp.get('ok'):
            sent.append((b.telegram_id, resp['result']['message_id']))
        else:
            print(f"[TASDIQ SO'ROV XATO] {resp}")
    return sent