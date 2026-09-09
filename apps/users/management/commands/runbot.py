"""
Mijozlar boti (aiogram 3.x).
Ishga tushirish:  python manage.py runbot
"""
import io
import re
import random
import asyncio
import logging
import qrcode
from dotenv import load_dotenv
from aiogram import Bot
from django.core.files.base import ContentFile

from django.core.management.base import BaseCommand
from django.conf import settings
from asgiref.sync import sync_to_async

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile,
    ChatMemberUpdated,
)

from apps.users.models import User, UserProfile
from apps.events.models import Event, UserEvent

load_dotenv()
logging.basicConfig(level=logging.INFO)

# ─── Ro'yxatlar (ish beruvchi bergan) ──────────────
REGIONS = [
    'Toshkent shahar', 'Toshkent viloyati', 'Buxoro', 'Andijon', "Farg'ona",
    'Namangan', 'Sirdaryo', 'Jizzax', 'Qashqadaryo', 'Navoiy', 'Samarqand',
    'Surxondaryo', 'Xorazm', "Qoraqalpog'iston Respublikasi",
]
INDUSTRIES = [
    "Ta'lim va ilm-fan", "Xizmat ko'rsatish", 'Bank va moliya', 'Turizm',
    "Qishloq xo'jaligi", 'Davlat sektori', 'Energetika', 'Savdo', 'IT',
    'Logistika', 'Qurilish', 'Chakana savdo', "Ko'chmas mulk", 'Oziq-ovqat',
    'Ishlab chiqarish', 'Distributsiya', 'Farmatsevtika va tibbiyot', 'Boshqa',
]
TRIPS = [
    'Phi Phi', 'Maldiv orollari', 'Seyshel', 'Shri Lanka', 'Bali-Kuala Lumpur',
    'Fukok', 'Qatar', 'Sharm-el-Sheyx', 'Nyachang', 'Trabzon','Lombok','Langkawi','Xitoy (Avatar tog\'lari)','Phuket (Tailand)'
]
LANGUAGES = [
    "O'zbek tili", 'Ingliz tili', 'Rus tili', 'Arab tili', 'Tojik tili',
    'Fransuz tili', 'Qozoq tili', 'Turk tili',
]

DATE_RE = re.compile(r'^\d{2}\.\d{2}\.\d{4}$')
PHONE_RE = re.compile(r'^\+998\d{9}$')
MONTH_YEAR_RE = re.compile(r'^(0[1-9]|1[0-2])\.\d{4}$')


from apps.users.profile_fields import (
    PROFILE_FIELDS, FIELDS_BY_KEY, normalize_phone, phone_key, missing_field_keys,
)


class Reg(StatesGroup):
    phone = State()    # telefon so'raladi (foydalanuvchini topish uchun)
    filling = State()  # bo'sh qolgan maydonlar ketma-ket to'ldiriladi
    photo = State()    # yakunida rasm (faqat yangi foydalanuvchidan)


# ─── ORM yordamchilari ──────────────
@sync_to_async
def get_or_create_user(tg_id, username):
    user, _ = User.objects.get_or_create(
        tg_id=str(tg_id), defaults={'tg_username': username, 'role': 'user'})
    return user


@sync_to_async
def is_registered(tg_id):
    """Ro'yxatni yakunlaganmi — QR (unique_id) berilgan bo'lsa 'ha'."""
    u = User.objects.filter(tg_id=str(tg_id)).first()
    return bool(u and u.unique_id)


@sync_to_async
def link_or_create_by_phone(tg_id, username, phone):
    """Telefon bo'yicha admin oldindan kiritgan yozuvni topib bog'laydi, bo'lmasa yangi yaratadi.

    Qaytaradi: {'precreated', 'missing', 'already_done'}.
    """
    pk = phone_key(phone)
    profile = None
    if pk:
        profile = (UserProfile.objects
                   .filter(phone__endswith=pk, user__tg_id__isnull=True)
                   .select_related('user').first())
    if profile:
        user = profile.user
        clash = User.objects.filter(tg_id=str(tg_id)).exclude(pk=user.pk).first()
        if clash:
            clash.plans.update(user=user)
            clash.delete()
        user.tg_id = str(tg_id)
        user.tg_username = username
        user.tg_phone = phone
        user.save()
        precreated = True
    else:
        user, _ = User.objects.get_or_create(
            tg_id=str(tg_id), defaults={'tg_username': username, 'role': 'user'})
        user.tg_phone = phone
        if username and not user.tg_username:
            user.tg_username = username
        user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if not profile.phone:
            profile.phone = phone
            profile.save()
        precreated = False
    return {
        'precreated': precreated,
        'missing': missing_field_keys(profile),
        'already_done': bool(user.unique_id),
    }


@sync_to_async
def save_dynamic_profile(tg_id, answers, unique_id, photo_bytes=None):
    """Bot so'ragan javoblarni profilga yozadi va QR (unique_id) beradi."""
    user = User.objects.get(tg_id=str(tg_id))
    profile, _ = UserProfile.objects.get_or_create(user=user)
    for key, val in answers.items():
        setattr(profile, key, val)
    if photo_bytes:
        profile.photo.save(f"user_{user.id}.jpg", ContentFile(photo_bytes), save=False)
    profile.save()
    if not user.unique_id:
        user.unique_id = unique_id
    if profile.phone:
        user.tg_phone = profile.phone
    user.user_unique_code = f"MBC-{user.id}"
    user.save()
    return user.unique_id


@sync_to_async
def gen_unique_id():
    while True:
        code = str(random.randint(1000, 9999))
        if not User.objects.filter(unique_id=code).exists():
            return code


@sync_to_async
def get_user_unique_id(tg_id):
    u = User.objects.filter(tg_id=str(tg_id)).first()
    return u.unique_id if u else None


@sync_to_async
def save_rsvp(tg_id, event_id, choice):
    try:
        user = User.objects.get(tg_id=str(tg_id))
        event = Event.objects.get(id=event_id)
    except (User.DoesNotExist, Event.DoesNotExist):
        return None
    ue, _ = UserEvent.objects.get_or_create(user=user, event=event)
    ue.rsvp_choice = choice
    ue.save()
    
    # Telegraph ro'yxatini yangilash
    try:
        from config.telegraph_utils import update_event_telegraph
        update_event_telegraph(event_id)
    except Exception as e:
        print("Telegraphni yangilashda xatolik:", e)
        
    return choice


# ─── Guruh a'zoligini tekshirish yordamchilari ──────────────
@sync_to_async
def get_admin_tg_ids():
    """Xabar oladigan adminlar: bazadagi role='admin' + .env dagi ADMIN_IDS."""
    db_ids = list(
        User.objects.filter(role='admin', is_active=True)
        .exclude(tg_id__isnull=True).exclude(tg_id='')
        .values_list('tg_id', flat=True)
    )
    env_ids = list(getattr(settings, 'ADMIN_IDS', []))
    # Takrorlanmasin uchun birlashtiramiz (tartibni saqlab)
    seen, result = set(), []
    for i in [str(x) for x in db_ids + env_ids]:
        if i and i not in seen:
            seen.add(i)
            result.append(i)
    return result


@sync_to_async
def get_join_check_info(tg_id):
    """Guruhga kirgan odam haqida: ro'yxatdan o'tganmi, faol obunasi bormi, ismi."""
    from apps.users.models import UserPlan
    from datetime import date
    today = date.today()
    user = User.objects.filter(tg_id=str(tg_id)).select_related('profile').first()
    if not user:
        return {'registered': False, 'has_active': False, 'name': ''}
    has_active = UserPlan.objects.filter(user=user, end_date__gte=today).exists()
    name = ''
    if hasattr(user, 'profile') and user.profile.name:
        name = f"{user.profile.name} {user.profile.surname}".strip()
    return {'registered': True, 'has_active': has_active, 'name': name}


# Nazorat qilinadigan chatlar (yopiq guruh + yopiq kanal)
MONITORED_CHATS = {c for c in {str(settings.PRIVATE_GROUP_ID), str(settings.PRIVATE_CHANNEL_ID)} if c and c != 'None'}


# ─── Yordamchi: inline klaviatura yasash ──────────────
def list_keyboard(items, prefix):
    rows = [[InlineKeyboardButton(text=x, callback_data=f"{prefix}:{i}")]
            for i, x in enumerate(items)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def multi_keyboard(items, selected, prefix):
    rows = []
    for i, x in enumerate(items):
        mark = "✅ " if i in selected else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{x}", callback_data=f"{prefix}:{i}")])
    rows.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"{prefix}:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


CANCEL_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Bekor qilish")]], resize_keyboard=True, one_time_keyboard=True)

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Mening QR kodim")]],
    resize_keyboard=True)

ADMIN_USERNAME = "Muxiddinivich"  # bu yerga haqiqiy admin username (@ siz)


async def _safe_edit(cb, new_text):
    """Callback xabarini xavfsiz tahrirlaydi — xato bo'lsa faqat log yozadi, tizimni buzmaydi."""
    try:
        await cb.message.edit_text(new_text, parse_mode="HTML")
    except Exception as e:
        logging.warning(f"Xabarni tahrirlashda xato: {e}")


async def qr_photo(unique_id):
    img = qrcode.make(unique_id)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return BufferedInputFile(buf.read(), filename="qr.png")


# ─── Dinamik anketa: faqat bo'sh qolgan maydonlarni so'rash ──────────────
def dyn_list_kb(options):
    rows = [[InlineKeyboardButton(text=x, callback_data=f"f:c:{i}")] for i, x in enumerate(options)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dyn_yesno_kb(options):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=options[0], callback_data="f:y:yes"),
        InlineKeyboardButton(text=options[1], callback_data="f:y:no"),
    ]])


def dyn_multi_kb(options, selected):
    rows = []
    for i, x in enumerate(options):
        mark = "✅ " if i in selected else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{x}", callback_data=f"f:m:{i}")])
    rows.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="f:m:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_field_prompt(target, state, key):
    """Navbatdagi bo'sh maydon uchun mos savol/klaviaturani yuboradi."""
    f = FIELDS_BY_KEY[key]
    await state.update_data(current=key)
    t = f['type']
    if t in ('text', 'number', 'date', 'monthyear'):
        await target.answer(f['prompt'], reply_markup=CANCEL_KB)
    elif t == 'choice':
        await target.answer(f['prompt'], reply_markup=dyn_list_kb(f['options']))
    elif t == 'yesno':
        await target.answer(f['prompt'], reply_markup=dyn_yesno_kb(f['options']))
    elif t == 'multi':
        await state.update_data(multi_sel=[])
        await target.answer(f['prompt'], reply_markup=dyn_multi_kb(f['options'], set()))
    await state.set_state(Reg.filling)


async def store_and_advance(target, state, value):
    """Joriy maydon javobini saqlaydi va keyingisiga o'tadi (yoki yakunlaydi)."""
    data = await state.get_data()
    answers = data.get('answers', {})
    answers[data['current']] = value
    idx = data['idx'] + 1
    await state.update_data(answers=answers, idx=idx)
    missing = data['missing']
    if idx >= len(missing):
        await finish_registration_flow(target, state)
    else:
        await send_field_prompt(target, state, missing[idx])


async def finish_registration_flow(target, state):
    """Maydonlar tugadi. Precreated bo'lsa darrov QR, yangi bo'lsa avval rasm so'raladi."""
    data = await state.get_data()
    if data.get('precreated'):
        await complete_and_send_qr(target, state, photo_bytes=None)
    else:
        await target.answer("Deyarli tayyor! Shaxsiy suratingizni yuboring (📷).")
        await state.set_state(Reg.photo)


async def complete_and_send_qr(target, state, photo_bytes):
    """Javoblarni saqlaydi, QR yasaydi va yuboradi."""
    data = await state.get_data()
    answers = data.get('answers', {})
    tg_id = data['tg_id']
    unique_id = await gen_unique_id()
    final_uid = await save_dynamic_profile(tg_id, answers, unique_id, photo_bytes)
    qr = await qr_photo(final_uid)
    await target.answer_photo(
        photo=qr,
        caption=(f"✅ Rahmat! Ma'lumotlaringiz qabul qilindi.\n\n"
                 f"Sizning shaxsiy ID raqamingiz: <b>{final_uid}</b>\n\n"
                 f"Tadbirlarga kirishda shu QR yoki ID ishlatiladi."),
        parse_mode="HTML", reply_markup=MAIN_KB)
    await state.clear()


def register_handlers(dp: Dispatcher):

    PHONE_KB = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)],
                  [KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True, one_time_keyboard=True)

    @dp.message(CommandStart())
    async def cmd_start(message: types.Message, state: FSMContext):
        await state.clear()
        if await is_registered(message.from_user.id):
            await message.answer("Assalomu alaykum! Siz allaqachon ro'yxatdan o'tgansiz. 🎉", reply_markup=MAIN_KB)
            return
        await state.update_data(tg_id=message.from_user.id, username=message.from_user.username)
        await message.answer(
            "Assalomu alaykum! MBC platformasiga xush kelibsiz.\n\n"
            "Davom etish uchun telefon raqamingizni yuboring 👇",
            reply_markup=PHONE_KB)
        await state.set_state(Reg.phone)

    async def _handle_phone(message: types.Message, state: FSMContext, phone_raw: str):
        phone = normalize_phone(phone_raw)
        tg_id = message.from_user.id
        info = await link_or_create_by_phone(tg_id, message.from_user.username, phone)
        await state.update_data(tg_id=tg_id, precreated=info['precreated'],
                                missing=info['missing'], idx=0, answers={})
        if info['already_done']:
            await message.answer("Siz allaqachon ro'yxatdan o'tgansiz. 🎉", reply_markup=MAIN_KB)
            await state.clear()
            return
        if not info['missing']:
            # Admin hamma ma'lumotni to'ldirgan — darrov QR
            await message.answer("Ma'lumotlaringiz to'liq ✅", reply_markup=ReplyKeyboardRemove())
            await complete_and_send_qr(message, state, photo_bytes=None)
            return
        await message.answer(
            f"Rahmat! Ro'yxatni yakunlash uchun yana {len(info['missing'])} ta savolga javob bering.",
            reply_markup=ReplyKeyboardRemove())
        await send_field_prompt(message, state, info['missing'][0])

    @dp.message(F.text == "❌ Bekor qilish")
    async def cancel(message: types.Message, state: FSMContext):
        await state.clear()
        await message.answer("Bekor qilindi. Qaytadan boshlash uchun /start bosing.",
                             reply_markup=ReplyKeyboardRemove())

    # ─── Telefon (foydalanuvchini topish) ──────────────
    @dp.message(Reg.phone, F.contact)
    async def phone_contact(message: types.Message, state: FSMContext):
        await _handle_phone(message, state, message.contact.phone_number)

    @dp.message(Reg.phone, F.text)
    async def phone_text(message: types.Message, state: FSMContext):
        if message.text == "❌ Bekor qilish":
            return
        if not PHONE_RE.match((message.text or "").strip()):
            await message.answer("❌ Noto'g'ri raqam. +998901234567 ko'rinishida yozing yoki tugma orqali yuboring.")
            return
        await _handle_phone(message, state, message.text.strip())

    # ─── Bo'sh maydonlarni to'ldirish (matn) ──────────────
    @dp.message(Reg.filling, F.text)
    async def filling_text(message: types.Message, state: FSMContext):
        if message.text == "❌ Bekor qilish":
            return
        data = await state.get_data()
        f = FIELDS_BY_KEY.get(data.get('current'))
        if not f:
            return
        if f['type'] not in ('text', 'number', 'date', 'monthyear'):
            await message.answer("Iltimos, yuqoridagi tugmalardan tanlang 👆")
            return
        val = (message.text or "").strip()
        if f['type'] == 'number' and not val.replace(" ", "").isdigit():
            await message.answer("❌ Faqat raqam kiriting.")
            return
        if f['type'] == 'date' and not DATE_RE.match(val):
            await message.answer("❌ Noto'g'ri format. DD.MM.YYYY (masalan 02.05.2007).")
            return
        if f['type'] == 'monthyear' and not MONTH_YEAR_RE.match(val):
            await message.answer("❌ Noto'g'ri format. MM.YYYY (masalan 07.2023).")
            return
        await store_and_advance(message, state, val)

    # ─── Bo'sh maydonlarni to'ldirish (tugmalar) ──────────────
    @dp.callback_query(Reg.filling, F.data.startswith("f:"))
    async def filling_cb(cb: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        f = FIELDS_BY_KEY.get(data.get('current'))
        if not f:
            await cb.answer()
            return
        parts = cb.data.split(":")
        kind = parts[1]
        if kind == 'c':  # bitta tanlov (viloyat/soha)
            val = f['options'][int(parts[2])]
            await cb.answer("Tanlandi ✅")
            await cb.message.edit_reply_markup(reply_markup=None)
            await store_and_advance(cb.message, state, val)
        elif kind == 'y':  # ha/yo'q
            await cb.answer("Tanlandi ✅")
            await cb.message.edit_reply_markup(reply_markup=None)
            await store_and_advance(cb.message, state, 'yes' if parts[2] == 'yes' else 'no')
        elif kind == 'm':  # ko'p tanlov (safarlar/tillar)
            sel = set(data.get('multi_sel', []))
            if parts[2] == 'done':
                chosen = [f['options'][i] for i in sorted(sel)]
                await cb.answer("Qabul qilindi ✅")
                await cb.message.edit_reply_markup(reply_markup=None)
                await store_and_advance(cb.message, state, chosen)
            else:
                i = int(parts[2])
                sel.discard(i) if i in sel else sel.add(i)
                await state.update_data(multi_sel=list(sel))
                await cb.message.edit_reply_markup(reply_markup=dyn_multi_kb(f['options'], sel))
                await cb.answer()

    # ─── Rasm (faqat yangi foydalanuvchi uchun) → yakun ──────────────
    @dp.message(Reg.photo, F.photo)
    async def s_photo(message: types.Message, state: FSMContext, bot: Bot):
        photo_id = message.photo[-1].file_id
        file = await bot.get_file(photo_id)
        buf = io.BytesIO()
        await bot.download_file(file.file_path, buf)
        await complete_and_send_qr(message, state, photo_bytes=buf.getvalue())

    @dp.message(Reg.photo)
    async def s_photo_invalid(message: types.Message, state: FSMContext):
        await message.answer("Iltimos, rasm yuboring (📷).")

    # ─── QR qayta ko'rish ──────────────
    @dp.message(F.text == "📱 Mening QR kodim")
    async def my_qr(message: types.Message):
        uid = await get_user_unique_id(message.from_user.id)
        if not uid:
            await message.answer("Avval ro'yxatdan o'ting: /start")
            return
        qr = await qr_photo(uid)
        await message.answer_photo(photo=qr, caption=f"Sizning ID: <b>{uid}</b>", parse_mode="HTML")

    # ─── RSVP ──────────────
    @dp.callback_query(F.data.startswith("rsvp:"))
    async def process_rsvp(cb: CallbackQuery):
        parts = cb.data.split(":")
        choice = parts[1]
        event_id = parts[2]
        result = await save_rsvp(cb.from_user.id, int(event_id), choice)
        if result is None:
            await cb.answer("Xatolik yuz berdi.", show_alert=True)
            return
        msgs = {
            'boraman': "✅ Boraman",
            'balki_borarman': "🤔 Balki borarman",
            'balki_bormasman': "😐 Balki bormasman",
            'bormayman': "❌ Bormayman",
        }
        msg_text = msgs.get(choice, "Qabul qilindi")
        await cb.answer(f"Javobingiz saqlandi: {msg_text}", show_alert=False)

        # Tugmalar UCHMAYDI — tanlangan javob belgilanadi, foydalanuvchi
        # istagan payt boshqa tugmani bosib javobini o'zgartira oladi.
        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            def rsvp_btn(key, label):
                # Tanlangan javob « » ichida ajralib turadi
                text = f"« {label} »" if key == choice else label
                return InlineKeyboardButton(text=text, callback_data=f"rsvp:{key}:{event_id}")

            info_row = [InlineKeyboardButton(
                text="ℹ️ Rejangiz o'zgardimi? Yangilang",
                callback_data="rsvp_info",
            )]
            row1 = [rsvp_btn('boraman', '✅ Albatta boraman'), rsvp_btn('balki_borarman', '🤔 Harakat qilaman')]
            row2 = [rsvp_btn('balki_bormasman', '😔 Rejalarim o\'zgardi'), rsvp_btn('bormayman', '🙏 Bu safar yo\'q')]

            rows = [info_row, row1, row2]

            # Oxirgi qatorni (Ovozlarni ko'rish / Ro'yxatdan o'tish) saqlab qolamiz
            markup = getattr(cb.message, 'reply_markup', None)
            if markup and markup.inline_keyboard:
                last_row = markup.inline_keyboard[-1]
                # Agar oxirgi qator RSVP tugmalari bo'lmasa (url tugmalar bo'lsa) — qo'shamiz
                if last_row and getattr(last_row[0], 'callback_data', None) is None:
                    rows.append(last_row)

            new_markup = InlineKeyboardMarkup(inline_keyboard=rows)
            await cb.message.edit_reply_markup(reply_markup=new_markup)
        except Exception as e:
            print("Edit xatoligi:", e)

    @dp.callback_query(F.data == "rsvp_info")
    async def process_rsvp_info(cb: CallbackQuery):
        await cb.answer(
            "Rejalaringiz o'zgarsa, tepadagi tugmalardan boshqasini bossangiz — "
            "javobingiz avtomatik yangilanadi. ✅",
            show_alert=True,
        )

    @dp.callback_query(F.data.startswith("sub_extend:"))
    async def process_sub_extend(cb: CallbackQuery):
        choice = cb.data.split(":")[1]
        if choice == "yes":
            await cb.answer()
            await cb.message.edit_reply_markup(reply_markup=None)
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✍️ Administratorga yozish", url=f"https://t.me/{ADMIN_USERNAME}"),
            ]])
            await cb.message.answer(
                "Obunani uzaytirish uchun administrator bilan bog'laning 👇",
                reply_markup=kb
            )
        else:
            await cb.answer("Javobingiz uchun rahmat!", show_alert=True)
            await cb.message.edit_reply_markup(reply_markup=None)
            await cb.message.answer(
                "Javobingiz uchun rahmat. 🙏\n"
                "Agar fikringiz o'zgarsa, administrator bilan bog'lanishingiz mumkin."
            )

    # ─── Guruh/kanalga yangi a'zo qo'shilganda tekshirish ──────────────
    @dp.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
    async def on_new_member(event: ChatMemberUpdated, bot: Bot):
        chat_id = str(event.chat.id)
        if chat_id not in MONITORED_CHATS:
            return

        new_user = event.new_chat_member.user
        if new_user.is_bot:
            return

        info = await get_join_check_info(new_user.id)
        if info['has_active']:
            return  # Faol obunasi bor — qonuniy a'zo, tegilmaydi

        admin_ids = await get_admin_tg_ids()
        # Qo'shilgan odamning o'zi admin bo'lsa — so'ramaymiz
        admin_ids = [a for a in admin_ids if str(a) != str(new_user.id)]
        if not admin_ids:
            logging.warning(
                "Guruhga obunasiz odam qo'shildi, lekin role='admin' foydalanuvchi topilmadi! "
                f"(user_id={new_user.id})"
            )
            return

        chat_title = event.chat.title or chat_id
        uname = f"@{new_user.username}" if new_user.username else "—"
        person_link = f'<a href="tg://user?id={new_user.id}">{new_user.full_name}</a>'
        status_line = (
            "✅ Botda ro'yxatdan o'tgan, lekin <b>faol obunasi yo'q</b>"
            if info['registered'] else
            "❌ Botda umuman <b>ro'yxatdan o'tmagan</b>"
        )

        # Kim qo'shdi: event.from_user — amalni bajargan odam.
        actor = event.from_user
        if actor and actor.id != new_user.id:
            adder = f'<a href="tg://user?id={actor.id}">{actor.full_name}</a>'
            if actor.username:
                adder += f" (@{actor.username})"
            added_by_line = f"➕ Qo'shdi: {adder}\n"
        elif event.invite_link:
            link_label = event.invite_link.name or event.invite_link.invite_link
            added_by_line = f"➕ Qo'shildi: taklif havolasi orqali ({link_label})\n"
        else:
            added_by_line = "➕ Qo'shildi: o'zi kirdi (havola yoki qidiruv orqali)\n"

        text = (
            "⚠️ <b>Diqqat! Guruhga obunasiz odam qo'shildi</b>\n\n"
            f"👤 Ism: {person_link}\n"
            f"🔗 Username: {uname}\n"
            f"🆔 Telegram ID: <code>{new_user.id}</code>\n"
            f"📍 Joy: <b>{chat_title}</b>\n"
            f"{added_by_line}"
            f"📋 Holati: {status_line}\n\n"
            "Uni tekshirib ko'ring (yuqoridagi ismga bosib profiliga o'ting), "
            "so'ng qoldirish yoki chiqarib yuborishni tanlang 👇"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🚫 Chiqarib yuborilsin", callback_data=f"gm:kick:{chat_id}:{new_user.id}"),
            InlineKeyboardButton(text="✅ Qolsin", callback_data=f"gm:keep:{chat_id}:{new_user.id}"),
        ]])

        for admin_id in admin_ids:
            try:
                await bot.send_message(admin_id, text, parse_mode="HTML", reply_markup=kb)
            except Exception as e:
                logging.error(f"Adminga a'zolik so'rovi yuborishda xato ({admin_id}): {e}")

    # ─── Admin qarori: chiqarib yuborish / qoldirish ──────────────
    @dp.callback_query(F.data.startswith("gm:"))
    async def on_gm_decision(cb: CallbackQuery, bot: Bot):
        try:
            _, action, chat_id, user_id = cb.data.split(":")
        except ValueError:
            await cb.answer("Xato ma'lumot.", show_alert=True)
            return

        base_text = cb.message.html_text if cb.message else ""

        if action == "kick":
            try:
                # Chiqaramiz (ban) — bu barcha turdagi chatlarda ishlaydi.
                await bot.ban_chat_member(chat_id=int(chat_id), user_id=int(user_id))
            except Exception as e:
                # USER_NOT_PARTICIPANT — odam allaqachon guruhda emas (o'zi chiqib ketgan yoki
                # avvalroq chiqarilgan/scheduler chiqargan). Bu xatolik emas — maqsad bajarilgan.
                if "USER_NOT_PARTICIPANT" in str(e):
                    await cb.answer("Bu odam allaqachon guruhda emas ✅")
                    await _safe_edit(cb, base_text + "\n\nℹ️ <b>Natija:</b> allaqachon guruhda emas edi.")
                    return
                logging.error(f"A'zoni chiqarish xatosi (chat={chat_id}, user={user_id}): {e}")
                await cb.answer(f"❌ Chiqarishda xatolik: {e}", show_alert=True)
                return
            # Ban muvaffaqiyatli — DARROV javob beramiz (tugma aylanib qotmasin).
            await cb.answer("Chiqarib yuborildi ✅")
            # Supergroup/kanalda banni yechamiz (odam keyin qonuniy taklif bilan qayta kira oladi).
            # Supergroup/kanal ID lari "-100" bilan boshlanadi; oddiy guruhda unban QILMAYMIZ
            # (u yerda darhol unban odamni qayta qo'shib yuboradi). get_chat so'rovi shart emas.
            if str(chat_id).startswith("-100"):
                try:
                    await bot.unban_chat_member(chat_id=int(chat_id), user_id=int(user_id), only_if_banned=True)
                except Exception as e:
                    logging.warning(f"Unban ogohlantirish (chat={chat_id}, user={user_id}): {e}")
            await _safe_edit(cb, base_text + f"\n\n🚫 <b>Natija:</b> chiqarib yuborildi ({cb.from_user.full_name}).")
        else:  # keep
            await cb.answer("Guruhda qoldirildi ✅")
            await _safe_edit(cb, base_text + f"\n\n✅ <b>Natija:</b> guruhda qoldirildi ({cb.from_user.full_name}).")


class Command(BaseCommand):
    help = "Mijozlar botini ishga tushiradi (aiogram)"

    def handle(self, *args, **options):
        token = settings.CLIENT_BOT_TOKEN
        if not token:
            self.stderr.write(self.style.ERROR("CLIENT_BOT_TOKEN .env faylida yo'q!"))
            return
        bot = Bot(token=token)
        dp = Dispatcher(storage=MemoryStorage())
        register_handlers(dp)
        self.stdout.write(self.style.SUCCESS("Mijozlar boti ishga tushdi..."))
        # allowed_updates — 'chat_member' yangilanishini ham olish uchun majburiy
        # (guruhga yangi a'zo qo'shilganini kuzatish shu orqali ishlaydi).
        asyncio.run(dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()))