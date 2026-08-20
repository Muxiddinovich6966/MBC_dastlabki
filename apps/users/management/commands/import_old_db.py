"""
Eski MBC bazasidan (mbc_old) foydalanuvchilarni Django bazaga ko'chirish.
Ishga tushirish:  python manage.py import_old_db
"""
import os
import json
import random
import psycopg2
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.users.models import User, UserProfile


# Eski baza ma'lumotlari .env dan olinadi (parol kodda saqlanmaydi).
OLD_DB = {
    'dbname': os.getenv('OLD_DB_NAME', 'mbc_old'),
    'user': os.getenv('OLD_DB_USER', 'postgres'),
    'password': os.getenv('OLD_DB_PASSWORD', ''),
    'host': os.getenv('OLD_DB_HOST', 'localhost'),
    'port': os.getenv('OLD_DB_PORT', '5432'),
}


def parse_json_field(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
        return [str(parsed)]
    except (json.JSONDecodeError, TypeError):
        return [x.strip() for x in str(value).split(',') if x.strip()]


def gen_unique_id(used):
    while True:
        code = str(random.randint(1000, 9999))
        if code not in used:
            used.add(code)
            return code


class Command(BaseCommand):
    help = "Eski MBC bazasidan foydalanuvchilarni ko'chiradi"

    def handle(self, *args, **options):
        conn = psycopg2.connect(**OLD_DB)
        cur = conn.cursor()

        used_ids = set(
            User.objects.exclude(unique_id__isnull=True)
            .exclude(unique_id='')
            .values_list('unique_id', flat=True)
        )

        cur.execute("""
            SELECT id, tg_id, tg_username, tg_phone, user_unique_code, role, is_active
            FROM users
            WHERE is_deleted = false AND tg_id IS NOT NULL AND tg_id <> ''
        """)
        old_users = cur.fetchall()

        cur.execute("""
            SELECT user_id, name, surname, "birthDate", phone, instagram,
                   "birthPlace", "workLocation", industry, brand, website,
                   turnover, "staffCount", role, goal, "joinDate",
                   "selectedTrips", languages, reason, problems, nda, visit
            FROM user_data
            WHERE is_deleted = false
        """)
        data_rows = cur.fetchall()
        data_map = {}
        for r in data_rows:
            data_map[r[0]] = {
                'name': r[1] or '', 'surname': r[2] or '', 'birth_date': r[3] or '',
                'phone': r[4] or '', 'instagram': r[5] or '', 'birth_place': r[6] or '',
                'work_location': r[7] or '', 'industry': r[8] or '', 'brand': r[9] or '',
                'website': r[10] or '', 'turnover': r[11] or '', 'staff_count': r[12] or '',
                'company_role': r[13] or '', 'goal': r[14] or '', 'join_date': r[15] or '',
                'selected_trips': parse_json_field(r[16]), 'languages': parse_json_field(r[17]),
                'reason': r[18] or '', 'problems': r[19] or '', 'nda': r[20] or '', 'visit': r[21] or '',
            }

        created, updated = 0, 0

        with transaction.atomic():
            for ou in old_users:
                old_id, tg_id, tg_username, tg_phone, uniq_code, role, is_active = ou
                tg_id = str(tg_id).strip()

                user, is_new = User.objects.get_or_create(
                    tg_id=tg_id,
                    defaults={
                        'tg_username': tg_username or None,
                        'tg_phone': tg_phone or None,
                        'user_unique_code': uniq_code or None,
                        'role': role or 'user',
                        'is_active': is_active if is_active is not None else True,
                    }
                )

                if not user.unique_id:
                    user.unique_id = gen_unique_id(used_ids)
                    user.save(update_fields=['unique_id'])

                if old_id in data_map:
                    d = data_map[old_id]
                    UserProfile.objects.update_or_create(user=user, defaults=d)

                if is_new:
                    created += 1
                else:
                    updated += 1

        cur.close()
        conn.close()

        self.stdout.write(self.style.SUCCESS(
            f"Tayyor! Yangi: {created}, yangilangan: {updated}"
        ))