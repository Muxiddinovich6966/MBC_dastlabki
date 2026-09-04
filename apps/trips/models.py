"""
Safarlar (trips) — to'lovlarni kuzatish uchun Google Sheets uslubidagi jadval.

Har bir Safar (Trip) — alohida jadval (masalan "Phuket (Thailand)").
Har bir qator — TripParticipant (safarga qatnashuvchi; saytdagi foydalanuvchi
yoki qo'lda qo'shilgan mehmon).
"""
from django.db import models
from apps.users.models import User


class TripCountry(models.Model):
    """Safar yaratishda tanlanadigan davlatlar/yo'nalishlar ro'yxati (bazada).

    Yangi davlat kiritilsa shu yerga qo'shiladi va keyingi safar ham chiqadi.
    """
    name = models.CharField(max_length=128, unique=True, verbose_name="Davlat / yo'nalish")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Davlat (safar)"
        verbose_name_plural = "Davlatlar (safar)"
        ordering = ['name']


class Trip(models.Model):
    """Bitta safar = bitta jadval."""

    name = models.CharField(max_length=256, verbose_name="Safar nomi")
    country = models.CharField(max_length=128, blank=True, verbose_name="Davlat / yo'nalish",
                               help_text="Profilga yoziladigan nom (masalan: Fukok). Bo'sh bo'lsa safar nomi ishlatiladi.")
    note = models.CharField(max_length=256, blank=True, verbose_name="Izoh")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def trip_label(self):
        """Profilda ko'rsatiladigan nom — davlat, bo'lmasa safar nomi."""
        return self.country or self.name

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Safar"
        verbose_name_plural = "Safarlar"
        ordering = ['-created_at']


class TripParticipant(models.Model):
    """Safar jadvalidagi bitta qator."""

    # Statusi (a'zo turi)
    STATUS_CHOICES = [
        ('mlp', 'MLP'),
        ('mbc', 'MBC'),
        ('yangi', 'Yangi'),
        ('org_team', 'ORG Team'),
        ('pul_ilmi', 'Yangi / Pul ilmi'),
        ('mehmon', 'Mehmon'),
        ('speaker', 'Speaker'),
    ]

    # Safarga borish statusi
    TRAVEL_CHOICES = [
        ('confirmed', 'Confirmed'),
        ('80_20', '80/20'),
        ('50_50', '50/50'),
        ('declined', 'Declined'),
        ('self', 'Self'),
        ('51_49', '51/49'),
    ]

    # Yillik podpiska
    SUB_CHOICES = [
        ('bor', 'Bor'),
        ('yoq', "Yo'q"),
        ('kelib', 'Kelib oladilar'),
    ]

    # To'lov
    PAYMENT_CHOICES = [
        ('berdi', 'Berdi'),
        ('avans', 'Avans berdi'),
        ('kutilmoqda', 'Kutilmoqda'),
        ('otkaz', 'Otkaz'),
        ('self', 'Self'),
        ('omonatdan', 'Omonatdan'),
        ('rasxod', 'Rasxod'),
    ]

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='participants', verbose_name="Safar")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='trip_participations', verbose_name="Foydalanuvchi")

    full_name = models.CharField(max_length=256, blank=True, verbose_name="F.I.O.")

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, blank=True, verbose_name="Statusi")
    travel_status = models.CharField(max_length=16, choices=TRAVEL_CHOICES, blank=True, verbose_name="Safarga borish")
    subscription = models.CharField(max_length=16, choices=SUB_CHOICES, blank=True, verbose_name="Yillik podpiska")
    payment_status = models.CharField(max_length=16, choices=PAYMENT_CHOICES, blank=True, verbose_name="To'lov")

    entry_sum = models.BigIntegerField(default=0, verbose_name="Vxodnoy summasi")
    trip_sum = models.BigIntegerField(default=0, verbose_name="Safar summasi (umumiy)")
    deposit = models.BigIntegerField(default=0, verbose_name="Omonatdan")
    paid = models.BigIntegerField(default=0, verbose_name="Berdi")

    comment = models.TextField(blank=True, verbose_name="Kommentariya")
    went = models.BooleanField(default=False, verbose_name="Bordi")

    order = models.IntegerField(default=0, verbose_name="Tartib")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        """Ko'rsatiladigan ism — qo'lda kiritilgani, bo'lmasa foydalanuvchi profili."""
        if self.full_name:
            return self.full_name
        if self.user:
            return self.user.full_name or str(self.user)
        return f"Qator #{self.pk}"

    @property
    def must_pay(self):
        """Berishi kerak = Vxodnoy summasi + Safar summasi."""
        return (self.entry_sum or 0) + (self.trip_sum or 0)

    @property
    def remaining(self):
        """Qoldiq = Berishi kerak − Omonatdan − Berdi."""
        return self.must_pay - (self.deposit or 0) - (self.paid or 0)

    @property
    def counts_as_went(self):
        """Prfofiliga bordi deb belgilanadi admin qulda belgilagandan keyin"""
        return self.went

    class Meta:
        verbose_name = "Safar qatnashuvchisi"
        verbose_name_plural = "Safar qatnashuvchilari"
        ordering = ['order', 'id']
