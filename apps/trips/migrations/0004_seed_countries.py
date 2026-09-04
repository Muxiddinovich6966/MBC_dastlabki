from django.db import migrations


def seed_countries(apps, schema_editor):
    TripCountry = apps.get_model('trips', 'TripCountry')
    Trip = apps.get_model('trips', 'Trip')

    # Botdagi tayyor safar ro'yxati (apps.users.profile_fields.TRIPS bilan bir xil)
    base = [
        'Phi Phi', 'Maldiv orollari', 'Seyshel', 'Shri Lanka', 'Bali-Kuala Lumpur',
        'Fukok', 'Qatar', 'Sharm-el-Sheyx', 'Nyachang', 'Trabzon', 'Lombok',
        'Langkawi', "Xitoy (Avatar tog'lari)",
    ]
    names = set(base)
    # Mavjud safarlarda kiritilgan davlatlarni ham qo'shamiz
    for c in Trip.objects.exclude(country='').values_list('country', flat=True):
        if c:
            names.add(c.strip())

    for name in names:
        TripCountry.objects.get_or_create(name=name)


def unseed(apps, schema_editor):
    # Orqaga qaytarilsa hech narsa o'chirmaymiz (ma'lumot saqlansin)
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0003_tripcountry'),
    ]

    operations = [
        migrations.RunPython(seed_countries, unseed),
    ]
