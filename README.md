# MBC Platform

MBC klubi uchun boshqaruv platformasi: foydalanuvchilar (mijozlar), tadbirlar,
obunalar, ishchilar/vazifalar tizimi va 2 ta Telegram bot (mijoz boti + ishchi boti).

## Texnologiyalar
- Python 3.11+, Django 5
- PostgreSQL
- aiogram (Telegram botlar)
- APScheduler (avtomatik vazifalar)

## Loyiha tuzilishi
```
apps/
  users/        — foydalanuvchilar, profil, obunalar, mijoz boti (runbot)
  events/       — tadbirlar, RSVP, leadlar, Safarlar guruhiga yuborish
  groups/       — Telegram guruh/kanallar (bazada saqlanadi)
  workers/      — ishchilar, vazifalar, shablonlar, ishchi boti, scheduler
  messages_app/ — ommaviy xabarlar
config/         — settings, urls, bot_notify (Telegram yordamchilari)
templates/      — admin sayt HTML shablonlari
```

## Lokal ishga tushirish

1. Virtual muhit va kutubxonalar:
   ```bash
   python -m venv venv
   venv\Scripts\activate            # Windows
   pip install -r requirements.txt
   ```

2. `.env` faylini yarating (namuna: `.env.example`):
   ```bash
   copy .env.example .env           # Windows
   # keyin .env ichini to'ldiring (SECRET_KEY, DB_*, bot tokenlar, ID lar)
   ```

3. Bazani tayyorlash:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

4. Ishga tushirish (har biri alohida terminalda):
   ```bash
   python manage.py runserver          # admin sayt
   python manage.py runbot             # mijoz boti
   python manage.py runworkerbot       # ishchi boti
   python manage.py runscheduler       # avtomatik vazifalar/eslatmalar
   ```

## Muhit o'zgaruvchilari (.env)
Barcha sozlamalar `.env` da. To'liq ro'yxat — `.env.example` da.
- **Serverga o'tkazganda o'zgaradi:** `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`,
  `CSRF_TRUSTED_ORIGINS`, `DB_*`.
- **O'zgarmaydi (bir xil qiymat):** bot tokenlar va kanal/guruh ID lari
  (`PRIVATE_CHANNEL_ID`, `PRIVATE_GROUP_ID`, `TRIPS_GROUP_ID`) — Telegram ID lari
  global, server va lokalda bir xil.

> `.env`, `media/`, `database-dump/` — Git'ga **yuklanmaydi** (`.gitignore` da).

## Serverga joylash (deploy) — qisqacha

1. Kodni serverga oling (git clone).
2. `venv` yarating, `pip install -r requirements.txt`.
3. `.env` ni serverda yarating:
   - `DEBUG=False`
   - `ALLOWED_HOSTS=sizning-domen.uz`
   - `CSRF_TRUSTED_ORIGINS=https://sizning-domen.uz`
   - yangi kuchli `SECRET_KEY`
   - server bazasining `DB_*` qiymatlari
   - bot tokenlar va kanal/guruh ID lari (lokaldagi bilan bir xil)
4. Baza:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py createsuperuser
   ```
   Mavjud ma'lumotlarni ko'chirish kerak bo'lsa — lokal bazani dump qilib
   serverga restore qiling (guruhlar, foydalanuvchilar bazada saqlanadi).
5. Web: Gunicorn + Nginx (yoki shu kabi). Botlar va scheduler doimiy
   ishlab turishi uchun `systemd` xizmatlari sifatida yuriting
   (`runbot`, `runworkerbot`, `runscheduler`).

> Media (foydalanuvchi rasmlari) server diskida saqlanadi — `media/` papkasi
> uchun doimiy joy va zaxira (backup) ni unutmang.
