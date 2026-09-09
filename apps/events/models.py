"""
Tadbirlar (mijozlar uchun e'lonlar).
Admin sayt orqali tadbir qo'shadi, bot orqali foydalanuvchilarga yuboriladi.
"""
from django.db import models
from apps.users.models import User
from apps.groups.models import Group


class Event(models.Model):
    """Bitta tadbir: nomi, sanasi, joyi, speaker va shu kabilar."""

    CATEGORY_CHOICES = [
        ('conference', 'Konferensiya'),
        ('workshop', 'Workshop'),
        ('networking', 'Networking'),
        ('other', 'Boshqa'),
    ]

    name = models.CharField(max_length=256, verbose_name="Tadbir nomi")
    theme = models.CharField(max_length=256, blank=True, verbose_name="Mavzu")
    description = models.TextField(verbose_name="Tavsif")

    date = models.CharField(max_length=32, verbose_name="Sana")
    time = models.CharField(max_length=16, verbose_name="Vaqt")

    venue = models.ForeignKey('Venue', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Joy", related_name='events')
    location = models.CharField(max_length=256, verbose_name="Manzil")
    latitude = models.CharField(max_length=32, blank=True, verbose_name="Latitude")
    longitude = models.CharField(max_length=32, blank=True, verbose_name="Longitude")

    speaker = models.CharField(max_length=256, blank=True, verbose_name="Speaker")
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default='other', verbose_name="Kategoriya")
    image = models.ImageField(upload_to='events/', null=True, blank=True, verbose_name="Rasm")

    send_groups = models.ManyToManyField(Group, blank=True, related_name='events', verbose_name="Yuboriladigan guruhlar")
    send_to_all_users = models.BooleanField(default=True, verbose_name="Hamma foydalanuvchiga yuborilsin")

    send_at = models.DateTimeField(null=True, blank=True, verbose_name="Avtomatik yuborish vaqti")
    sent = models.BooleanField(default=False, verbose_name="Yuborilgan")

    google_calendar_event_id = models.CharField(max_length=256, null=True, blank=True)
    telegraph_url = models.CharField(max_length=256, null=True, blank=True)
    
    use_auto_template = models.BooleanField(default=False, verbose_name="Avtomatik shablon (Assalamu alaykum...)")

    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Tadbir"
        verbose_name_plural = "Tadbirlar"
        ordering = ['-created_at']


class EventReminder(models.Model):
    """Tadbirdan oldin avtomatik yuboriladigan eslatma."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='reminders', verbose_name="Tadbir")
    remind_at = models.DateTimeField(verbose_name="Eslatma vaqti")
    label = models.CharField(max_length=256, default='Eslatma', verbose_name="Eslatma matni")
    sent = models.BooleanField(default=False, verbose_name="Yuborilgan")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event.name} — {self.remind_at}"

    class Meta:
        verbose_name = "Tadbir eslatmasi"
        verbose_name_plural = "Tadbir eslatmalari"


class UserEvent(models.Model):
    """Foydalanuvchining tadbirga bergan javobi (boraman/bormayman)."""

    RSVP_CHOICES = [
        ('boraman', 'Boraman'),
        ('balki_borarman', 'Balki borarman'),
        ('balki_bormasman', 'Balki bormasman'),
        ('bormayman', 'Bormayman'),
        ('unknown', "Javob bermagan"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_responses', verbose_name="Foydalanuvchi")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='responses', verbose_name="Tadbir")

    rsvp_choice = models.CharField(max_length=16, choices=RSVP_CHOICES, default='unknown', verbose_name="Javobi")
    is_attendance = models.BooleanField(default=False, verbose_name="Tadbirga keldi (QR skan)")
    message_id = models.BigIntegerField(null=True, blank=True, verbose_name="Botda yuborilgan xabar ID")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.event} ({self.rsvp_choice})"

    class Meta:
        verbose_name = "Foydalanuvchi javobi"
        verbose_name_plural = "Foydalanuvchi javoblari"
        unique_together = ['user', 'event']


class Venue(models.Model):
    """Doimiy joy va manzil"""
    name= models.CharField(max_length=256, verbose_name="Joy nomi")
    address = models.CharField(max_length=512,blank=True, verbose_name="To'liq manzil")
    latitude = models.CharField(max_length=32,blank=True,verbose_name="Latitude")
    longitude = models.CharField(max_length=32,blank=True,verbose_name="Longitude")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name="Manzil"
        verbose_name_plural="Manzillar"
        ordering = ['name']


class Lead(models.Model):
    """Tadbirga kelgan, lekin tizimda ro'yxatdan o'tmagan mehmon (lead).

    QR/ID nazorati sahifasida qo'lda kiritiladi: ism-familiya + telefon.
    Qaysi tadbirga kelgani ham saqlanadi. Keyin lead bilan ishlanadi va uning
    holati (status) o'zgaradi — har o'zgarish LeadStatusLog da yoziladi.
    """

    STATUS_CHOICES = [
        ('new', 'Yangi'),
        ('contacted', "Bog'lanildi"),
        ('follow_up', "Qayta aloqaga chiqish"),
        ('thinking', "O'ylayapti"),
        ('joined', "Mijoz bo'ldi"),
        ('rejected', 'Rad etdi'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='leads', verbose_name="Tadbir")
    full_name = models.CharField(max_length=256, verbose_name="Ism familiya")
    phone = models.CharField(max_length=32, verbose_name="Telefon raqam")
    note = models.CharField(max_length=256, blank=True, verbose_name="Izoh")

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='new', verbose_name="Holat")
    status_changed_at = models.DateTimeField(null=True, blank=True, verbose_name="Holat o'zgargan vaqt")
    follow_up_at = models.DateTimeField(null=True, blank=True, verbose_name= "Qayta aloqa eslatmasi")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} ({self.phone})"

    @property
    def status_badge_class(self):
        return {
            'new': 'badge-info',
            'contacted': 'badge-warning',
            'thinking': 'badge-warning',
            'joined': 'badge-success',
            'rejected': 'badge-danger',
        }.get(self.status, 'badge-info')

    class Meta:
        verbose_name = "Lead"
        verbose_name_plural = "Ledlar"
        ordering = ['-created_at']


class LeadStatusLog(models.Model):
    """Lead holati har safar o'zgarganda yoziladigan tarix (kim, qachon, qaysidan qaysiga)."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='status_logs', verbose_name="Lead")
    old_status = models.CharField(max_length=16, blank=True, verbose_name="Eski holat")
    new_status = models.CharField(max_length=16, verbose_name="Yangi holat")
    changed_by = models.CharField(max_length=128, blank=True, verbose_name="Kim o'zgartirdi")
    note = models.CharField(max_length=256, blank=True, verbose_name="Izoh")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Vaqt")

    def get_old_status_display(self):
        return dict(Lead.STATUS_CHOICES).get(self.old_status, self.old_status or '—')

    def get_new_status_display(self):
        return dict(Lead.STATUS_CHOICES).get(self.new_status, self.new_status)

    def __str__(self):
        return f"{self.lead} — {self.new_status} ({self.created_at:%d.%m.%Y %H:%M})"

    class Meta:
        verbose_name = "Lead holat tarixi"
        verbose_name_plural = "Lead holat tarixlari"
        ordering = ['-created_at']


class EventSendLog(models.Model):
    """Tadbir xabari har bir guruh/foydalanuvchiga yuborilganini kuzatish.

    Bitta (tadbir, guruh) yoki (tadbir, foydalanuvchi) uchun bitta yozuv bo'ladi.
    Qayta yuborilganda shu yozuv yangilanadi. Tahrirlashda eski xabarni
    o'chirish uchun message_id shu yerda saqlanadi.
    """

    TARGET_CHOICES = [
        ('user', 'Foydalanuvchi'),
        ('group', 'Guruh'),
    ]
    STATUS_CHOICES = [
        ('success', 'Yuborildi'),
        ('failed', 'Xato'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='send_logs', verbose_name="Tadbir")
    target_type = models.CharField(max_length=8, choices=TARGET_CHOICES, verbose_name="Kimga")

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='event_send_logs', verbose_name="Foydalanuvchi")
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.CASCADE, related_name='event_send_logs', verbose_name="Guruh")

    chat_id = models.CharField(max_length=64, verbose_name="Chat ID")
    message_id = models.BigIntegerField(null=True, blank=True, verbose_name="Xabar ID")

    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default='failed', verbose_name="Holati")
    error = models.TextField(blank=True, verbose_name="Xato matni")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        target = self.group or self.user or self.chat_id
        return f"{self.event.name} → {target} ({self.status})"

    class Meta:
        verbose_name = "Yuborish jurnali"
        verbose_name_plural = "Yuborish jurnallari"
        constraints = [
            models.UniqueConstraint(fields=['event', 'user'], name='uniq_event_user_log',
                                    condition=models.Q(user__isnull=False)),
            models.UniqueConstraint(fields=['event', 'group'], name='uniq_event_group_log',
                                    condition=models.Q(group__isnull=False)),
        ]

