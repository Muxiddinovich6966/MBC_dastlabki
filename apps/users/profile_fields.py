"""
Foydalanuvchi anketasi maydonlari — bitta joyda.

Ham mijozlar boti (runbot), ham sayt (admin qo'lda qo'shish) shu ro'yxatdan
foydalanadi. Shunda bot faqat "bo'sh qolgan" maydonlarni so'raydi.
"""

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
    'Fukok', 'Qatar', 'Sharm-el-Sheyx', 'Nyachang', 'Trabzon', 'Lombok',
    'Langkawi', "Xitoy (Avatar tog'lari)",'Phuket (Tailand)',
]
LANGUAGES = [
    "O'zbek tili", 'Ingliz tili', 'Rus tili', 'Arab tili', 'Tojik tili',
    'Fransuz tili', 'Qozoq tili', 'Turk tili',
]

# Anketa maydonlari tartibi. type: text/number/date/monthyear/choice/multi/yesno
# 'phone' va 'photo' bu ro'yxatda YO'Q — ular alohida ishlanadi (kontakt / rasm).
PROFILE_FIELDS = [
    {'key': 'name', 'label': 'Ism', 'prompt': 'Ismingiz?', 'type': 'text'},
    {'key': 'surname', 'label': 'Familiya', 'prompt': 'Familiyangiz?', 'type': 'text'},
    {'key': 'birth_date', 'label': "Tug'ilgan sana", 'prompt': "Tug'ilgan sanangiz? (masalan: 02.05.2007)", 'type': 'date'},
    {'key': 'instagram', 'label': 'Instagram', 'prompt': "Instagram nikingiz? (yo'q bo'lsa \"Yo'q\" deb yozing)", 'type': 'text'},
    {'key': 'birth_place', 'label': "Tug'ilgan viloyat", 'prompt': "Qaysi viloyatda tug'ilgansiz?", 'type': 'choice', 'options': REGIONS},
    {'key': 'work_location', 'label': 'Faoliyat manzili', 'prompt': 'Faoliyat manzilingiz?', 'type': 'choice', 'options': REGIONS},
    {'key': 'industry', 'label': 'Soha', 'prompt': 'Sohangizni tanlang:', 'type': 'choice', 'options': INDUSTRIES},
    {'key': 'brand', 'label': 'Brend/kompaniya', 'prompt': 'Brendingiz (yoki kompaniyangiz) nomi?', 'type': 'text'},
    {'key': 'website', 'label': 'Vebsayt', 'prompt': 'Biznesingiz vebsayti va ijtimoiy sahifalari?', 'type': 'text'},
    {'key': 'turnover', 'label': 'Yillik aylanma', 'prompt': 'Yillik aylanmangiz (raqamda)?', 'type': 'number'},
    {'key': 'staff_count', 'label': 'Xodimlar soni', 'prompt': 'Xodimlar soni?', 'type': 'number'},
    {'key': 'company_role', 'label': 'Kompaniyadagi maqom', 'prompt': 'Kompaniyadagi maqomingiz?', 'type': 'text'},
    {'key': 'goal', 'label': 'Biznes maqsad', 'prompt': 'Asosiy biznes maqsadingiz?', 'type': 'text'},
    {'key': 'join_date', 'label': "Klubga qo'shilgan sana", 'prompt': "Klubga qachon qo'shilgansiz? (MM.YYYY, masalan: 07.2023)", 'type': 'monthyear'},
    {'key': 'selected_trips', 'label': 'Safarlar', 'prompt': "Qaysi safarlarga borgan edingiz? Tanlab, 'Tasdiqlash' bosing.", 'type': 'multi', 'options': TRIPS},
    {'key': 'languages', 'label': 'Tillar', 'prompt': "Qaysi tillarni bilasiz? Tanlab, 'Tasdiqlash' bosing.", 'type': 'multi', 'options': LANGUAGES},
    {'key': 'reason', 'label': "Qo'shilish sababi", 'prompt': "Klubga nima sababdan qo'shilgansiz?", 'type': 'text'},
    {'key': 'problems', 'label': 'Qiyinchiliklar', 'prompt': 'Hozirda biznesingizda qanday qiyinchiliklar bor?', 'type': 'text'},
    {'key': 'nda', 'label': 'NDA roziligi', 'prompt': 'NDA va maxfiylik siyosatiga rozimisiz?', 'type': 'yesno', 'options': ['Roziman', 'Rozi emasman']},
    {'key': 'visit', 'label': 'Kompaniya tashrifi', 'prompt': 'Kompaniyangizga tashrif foydalimi?', 'type': 'yesno', 'options': ['Ha', "Hozircha yo'q"]},
]

# key -> field dict (tez qidirish uchun)
FIELDS_BY_KEY = {f['key']: f for f in PROFILE_FIELDS}


def normalize_phone(raw):
    """Telefon raqamni +998XXXXXXXXX ko'rinishiga keltiradi."""
    digits = ''.join(ch for ch in (raw or '') if ch.isdigit())
    if not digits:
        return ''
    if digits.startswith('998'):
        digits = digits[3:]
    return '+998' + digits


def phone_key(raw):
    """Taqqoslash uchun raqamning oxirgi 9 xonasi (formatdan qat'i nazar)."""
    digits = ''.join(ch for ch in (raw or '') if ch.isdigit())
    return digits[-9:] if len(digits) >= 9 else digits


def is_field_empty(profile, key):
    """profile dagi shu maydon bo'shmi (to'ldirilmaganmi)."""
    val = getattr(profile, key, None)
    if key in ('selected_trips', 'languages'):
        return not val  # bo'sh ro'yxat [] ham bo'sh hisoblanadi
    return val in (None, '')


def missing_field_keys(profile):
    """profile da bo'sh qolgan anketa maydonlari kalitlari (tartib bilan)."""
    return [f['key'] for f in PROFILE_FIELDS if is_field_empty(profile, f['key'])]
