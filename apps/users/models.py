"""
Foydalanuvchilar (mijozlar) modeli.
Bu Telegram orqali botga /start bosgan va ro'yxatdan o'tgan odamlar.
"""
from django.conf import settings
from django.db import models


class User(models.Model):
    """Botga yozilgan har bir Telegram foydalanuvchisi."""

    ROLE_CHOICES = [
        ('user', 'Foydalanuvchi'),
        ('admin', 'Admin'),
    ]

    # tg_id — admin qo'lda foydalanuvchi qo'shganda hali bo'sh bo'ladi (odam /start bosganda to'ladi).
    # Postgres da bir nechta NULL unique cheklovni buzmaydi.
    tg_id = models.CharField(max_length=64, unique=True, null=True, blank=True, verbose_name="Telegram ID")
    tg_username = models.CharField(max_length=128, null=True, blank=True, verbose_name="Telegram username")
    tg_phone = models.CharField(max_length=64, null=True, blank=True, verbose_name="Telefon raqam")

    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default='user', verbose_name="Rol")
    user_unique_code = models.CharField(max_length=32, null=True, blank=True, unique=True, verbose_name="QR kod")
    unique_id = models.CharField(max_length=4, null=True, blank=True, unique=True, verbose_name="4 xonali ID")

    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Qo'shilgan sana")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan sana")

    def __str__(self):
        return self.tg_username or self.tg_id or self.full_name or f"Foydalanuvchi #{self.pk}"

    @property
    def full_name(self):
        if hasattr(self, 'profile') and self.profile.name:
            return f"{self.profile.name} {self.profile.surname}".strip()
        return self.tg_username or self.tg_id

    @property
    def active_plan(self):
        """Hozir amal qilayotgan (muddati tugamagan) obuna — bo'lmasa None."""
        from datetime import date
        return self.plans.filter(end_date__gte=date.today()).order_by('-end_date').first()

    @property
    def has_active_plan(self):
        """Obunasi hali tugamaganmi (kamida bitta faol obuna bormi)."""
        return self.active_plan is not None

    @property
    def subscription_status(self):
        """Saytda ko'rsatish uchun holat: 'active' / 'expired' / 'none'."""
        if not self.plans.exists():
            return 'none'
        return 'active' if self.has_active_plan else 'expired'

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        ordering = ['-created_at']


class UserProfile(models.Model):
    """Ro'yxatdan o'tishda to'ldirilgan qo'shimcha ma'lumotlar (anketa)."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name="Foydalanuvchi")

    name = models.CharField(max_length=128, blank=True, verbose_name="Ism")
    surname = models.CharField(max_length=128, blank=True, verbose_name="Familiya")
    birth_date = models.CharField(max_length=10, blank=True, verbose_name="Tug'ilgan sana")
    phone = models.CharField(max_length=32, blank=True, verbose_name="Telefon")
    photo = models.ImageField(upload_to='users/photos/', null=True, blank=True, verbose_name="Rasm")

    birth_place = models.CharField(max_length=128, blank=True, verbose_name="Tug'ilgan joy")
    work_location = models.CharField(max_length=128, blank=True, verbose_name="Ish/yashash shahri")
    industry = models.CharField(max_length=128, blank=True, verbose_name="Faoliyat sohasi")
    company_role = models.CharField(max_length=128, blank=True, verbose_name="Kompaniyadagi lavozimi")

    brand = models.CharField(max_length=128, blank=True, verbose_name="Brend/kompaniya nomi")
    website = models.CharField(max_length=256, blank=True, verbose_name="Vebsayt")
    instagram = models.CharField(max_length=128, blank=True, verbose_name="Instagram")
    turnover = models.CharField(max_length=64, blank=True, verbose_name="Yillik aylanma")
    staff_count = models.CharField(max_length=64, blank=True, verbose_name="Xodimlar soni")
    goal = models.TextField(blank=True, verbose_name="Biznes maqsadi")
    join_date = models.CharField(max_length=10, blank=True, verbose_name="Klubga qo'shilgan sana")
    selected_trips = models.JSONField(default=list, blank=True, verbose_name="Safarlar")
    languages = models.JSONField(default=list, blank=True, verbose_name="Tillar")
    reason = models.TextField(blank=True, verbose_name="Qo'shilish sababi")
    problems = models.TextField(blank=True, verbose_name="Biznesdagi qiyinchiliklar")
    nda = models.CharField(max_length=50, blank=True, verbose_name="NDA roziligi")
    visit = models.CharField(max_length=50, blank=True, verbose_name="Kompaniya tashrifi")
    sent_to_trips_at = models.DateTimeField(null=True, blank=True, verbose_name = "Safarlar guruhiga yuborilgan")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} {self.surname}".strip() or str(self.user)

    class Meta:
        verbose_name = "Foydalanuvchi profili"
        verbose_name_plural = "Foydalanuvchi profillari"


class TripsSendLog(models.Model):
    """A'zo ma'lumoti Safarlar guruhiga har yuborilganda yoziladigan jurnal.

    Kim (admin) yuborgani, qachon, o'sha paytda guruhda a'zo edimi va
    muvaffaqiyatli bo'lganini saqlaydi. Bir profil bir necha marta yuborilishi
    mumkin — har biri alohida yozuv (tarix uchun).
    """

    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='trips_send_logs', verbose_name="Profil")
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='trips_sends', verbose_name="Kim yubordi")
    was_member = models.BooleanField(default=False, verbose_name="Guruhda a'zo edi")
    success = models.BooleanField(default=True, verbose_name="Muvaffaqiyatli")
    error = models.CharField(max_length=256, blank=True, verbose_name="Xato matni")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yuborilgan vaqt")

    def __str__(self):
        return f"{self.profile} → Safarlar ({self.created_at:%d.%m.%Y %H:%M})"

    class Meta:
        verbose_name = "Safarlarga yuborish jurnali"
        verbose_name_plural = "Safarlarga yuborish jurnallari"
        ordering = ['-created_at']


class UserPlan(models.Model):
    PAYMENT_CHOICES = [
        ('cash', 'Naqd'),
        ('card', 'Karta'),
        ('transfer', "O'tkazma"),
        ('other', 'Boshqa'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='plans', verbose_name="Foydalanuvchi")
    price = models.BigIntegerField(verbose_name="Narx (so'm)")
    start_date = models.DateField(verbose_name="Boshlanish sanasi")
    end_date = models.DateField(verbose_name="Tugash sanasi")
    payment_type = models.CharField(max_length=32, choices=PAYMENT_CHOICES, default='cash', verbose_name="To'lov turi")
    note = models.TextField(blank=True, verbose_name="Izoh")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.start_date} / {self.end_date}"

    @property
    def is_expired(self):
        """Shu obuna muddati tugaganmi (tugash sanasi bugundan oldinmi)."""
        from datetime import date
        return self.end_date < date.today()

    class Meta:
        verbose_name = "Obuna"
        verbose_name_plural = "Obunalar"
        ordering = ['-created_at']
