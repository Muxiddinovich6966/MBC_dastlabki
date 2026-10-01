"""
Ishchilar tizimi: shablon, vazifa va ishchilarga tayinlash.
Bu sizning avvalgi Mfactor_bot loyihangizdagi tizimning Django ko'rinishi.
"""
from django.db import models


class Worker(models.Model):
    """Vazifa bajaradigan ishchi yoki boshliq (alohida Telegram bot orqali)."""

    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('worker', 'Ishchi'),
        ('boss', 'Boshliq'),
    ]

    DEPARTMENT_CHOICES = [
        ('media','📱 Media'),
        ('organizator','🎯 Organizator'),
        ('ceo','👔 CEO'),
        ('menejer','💼 Menejer'),
    ]

    department = models.CharField(max_length=20,choices=DEPARTMENT_CHOICES,blank=True,
                                  verbose_name = "Bo'lim")

    telegram_id = models.BigIntegerField(unique=True, verbose_name="Telegram ID")
    name = models.CharField(max_length=255, verbose_name="Ismi")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name="Roli")

    # Faqat CHECK-LIST uchun: shu bo'limning boshlig'i (bot ruxsatiga (role) ta'sir qilmaydi).
    is_head = models.BooleanField(
        default=False, verbose_name="Bo'lim boshlig'i (check-list uchun)",
        help_text="Belgilansa, check-listda ismi tepasida '<Bo'lim> boshlig'i' bo'lib chiqadi. "
                  "Botga kirish huquqi 'Roli' orqali belgilanadi — bunga bog'liq emas."
    )

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"

    class Meta:
        verbose_name = "Ishchi"
        verbose_name_plural = "Ishchilar"


class Template(models.Model):
    """Tadbir uchun tayyor vazifalar shabloni (masalan: 'Konferensiya shabloni')."""

    name = models.CharField(max_length=255, verbose_name="Shablon nomi")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Shablon"
        verbose_name_plural = "Shablonlar"


WHEN_CHOICES = [
    ('before', 'oldin'),
    ('after', 'keyin'),
]


class TemplateTask(models.Model):
    """Shablon ichidagi bitta vazifa namunasi."""

    template = models.ForeignKey(Template, on_delete=models.CASCADE, related_name='tasks', verbose_name="Shablon")
    workers = models.ManyToManyField(Worker, blank=True, related_name='template_tasks', verbose_name="Ishchilar")

    description = models.CharField(max_length=500, verbose_name="Vazifa nomi")
    days_before = models.IntegerField(verbose_name="Necha kun")
    when = models.CharField(max_length=8, choices=WHEN_CHOICES, default='before', verbose_name="Tadbirdan oldin/keyin")
    hours_before = models.IntegerField(
        null=True, blank=True,
        verbose_name="Necha soat oldin (ixtiyoriy)",
        help_text="Masalan: 2 — tadbirdan 2 soat oldin"
    )
    instruction = models.TextField(blank=True, null=True, verbose_name="Instruksiya")

    def __str__(self):
        return f"{self.description} ({self.days_before} kun {self.get_when_display()})"

    class Meta:
        verbose_name = "Shablon vazifasi"
        verbose_name_plural = "Shablon vazifalari"


class WorkEvent(models.Model):
    """Ishchilar tizimidagi tadbir (shablon biriktiriladigan tadbir)."""

    STATUS_CHOICES = [
        ('pending', 'Tasdiq kutilmoqda'),   # boshliq tasdig'ini kutyapti — hech narsa yuborilmagan
        ('approved', 'Tasdiqlangan'),        # boshliq tasdiqladi — vazifalar/e'lon yuborilgan
        ('rejected', 'Rad etilgan'),         # boshliq rad etdi
    ]

    name = models.CharField(max_length=255, verbose_name="Tadbir nomi")
    event_date = models.DateField(verbose_name="Tadbir sanasi")
    event_time = models.TimeField(null=True, blank=True, verbose_name="Tadbir vaqti")
    template = models.ForeignKey(Template, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Shablon")
    # Yangi birlashgan oqim: kalendardan yaratilgan tadbir boshliq tasdig'ini kutadi.
    # Eski to'g'ridan-to'g'ri yaratilganlar 'approved' (default) — xatti-harakat o'zgarmaydi.
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='approved', verbose_name="Holati")
    # Boshliq rad etganda saytda bildirishnoma chiqadi; admin ko'rib "tushundim" bosgach True bo'ladi.
    rejection_seen = models.BooleanField(default=False, verbose_name="Rad etish bildirishnomasi ko'rildi")
    checklist_message_id = models.BigIntegerField(null=True,blank=True,verbose_name="Check-list xabar ID")
    checklist_chat_id = models.CharField(max_length=64, blank=True,verbose_name="Check-list chat ID")
    checklist_note = models.CharField(max_length=200, blank=True,
                                      verbose_name="Check-list tepasidagi 'Yangilandi' izohi")

    def __str__(self):
        return f"{self.name} ({self.event_date})"

    class Meta:
        verbose_name = "Ishchilar tadbiri"
        verbose_name_plural = "Ishchilar tadbirlari"


class Task(models.Model):
    """Shablondan tadbirga ko'chirilgan, ishchiga tayinlangan aniq vazifa."""

    STATUS_CHOICES = [
        ('pending', 'Kutilmoqda'),
        ('completed', 'Bajarildi'),
        ('overdue', 'Kechikdi'),      # deadline o'tdi, lekin hali bajarilishi mumkin
        ('not_done', 'Bajarilmadi'),  # umuman bajarilmay yopildi (yakuniy)
    ]

    SOURCE_CHOICES = [
        ('site', 'Sayt (tadbir)'),
        ('boss', 'Boshliq topshirig\'i'),
    ]

    # Boshliq topshirig'ida tadbir bo'lmaydi — shu bois event ixtiyoriy (null)
    event = models.ForeignKey(WorkEvent, on_delete=models.CASCADE, null=True, blank=True, related_name='tasks', verbose_name="Tadbir")
    workers = models.ManyToManyField(Worker, blank=True, related_name='tasks', verbose_name="Ishchilar")
    completed_by = models.ForeignKey(
        Worker, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='completed_tasks', verbose_name="Kim bajardi"
    )

    # Vazifa manbasi: sayt/tadbir orqali yoki boshliq bot orqali qo'lda
    source = models.CharField(max_length=8, choices=SOURCE_CHOICES, default='site', verbose_name="Manba")
    assigned_by = models.ForeignKey(
        Worker, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_tasks', verbose_name="Kim biriktirdi (boshliq)"
    )

    description = models.CharField(max_length=500, verbose_name="Vazifa nomi")
    days_before = models.IntegerField(default=0, verbose_name="Necha kun")
    when = models.CharField(max_length=8, choices=WHEN_CHOICES, default='before', verbose_name="Tadbirdan oldin/keyin")
    hours_before = models.IntegerField(null=True, blank=True, verbose_name="Necha soat oldin")
    deadline_date = models.DateField(verbose_name="Deadline sanasi")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Holati")
    reminder_sent = models.BooleanField(default=False, verbose_name="Deadline eslatmasi yuborilgan")
    time_reminder_sent = models.BooleanField(default=False, verbose_name="Tadbir vaqti (2 soat) eslatmasi yuborilgan")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Bajarilgan vaqt")
    instruction = models.TextField(blank=True, null=True, verbose_name="Instruksiya")

    def __str__(self):
        ev = self.event.name if self.event else "Boshliq topshirig'i"
        return f"{self.description} — {ev}"

    class Meta:
        verbose_name = "Vazifa"
        verbose_name_plural = "Vazifalar"


class NotificationLog(models.Model):
    """Yuborilgan xabar ID sini saqlash (keyin yangilash/o'chirish uchun)."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='notification_logs')
    chat_id = models.BigIntegerField()
    message_id = models.BigIntegerField()
    role = models.CharField(
        max_length=10,
        choices=[('worker', 'Ishchi'), ('boss', 'Boshliq')],
        default='boss',
        verbose_name="Kimga yuborilgan"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Xabar logi"
        verbose_name_plural = "Xabar loglari"


class ChecklistMessage(models.Model):
    """Har bo'lim uchun guruxga yuborilgan check-list xabari."""

    event = models.ForeignKey(WorkEvent,on_delete=models.CASCADE, related_name='checklist_messages',verbose_name="Tadbir")
    department = models.CharField(max_length=20, verbose_name="Bo'lim")
    chat_id = models.CharField(max_length=64, verbose_name="Chat ID")
    message_id = models.BigIntegerField(verbose_name="Xabar ID")
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.event.name} - {self.department}"

    class Meta:
        verbose_name = "Check-list xabari"
        verbose_name_plural = "Check-list xabarlari"
        unique_together = ['event', 'department']