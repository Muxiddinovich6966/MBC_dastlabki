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

    telegram_id = models.BigIntegerField(unique=True, verbose_name="Telegram ID")
    name = models.CharField(max_length=255, verbose_name="Ismi")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name="Roli")

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

    name = models.CharField(max_length=255, verbose_name="Tadbir nomi")
    event_date = models.DateField(verbose_name="Tadbir sanasi")
    event_time = models.TimeField(null=True, blank=True, verbose_name="Tadbir vaqti")
    template = models.ForeignKey(Template, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Shablon")

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
        ('overdue', 'Kechikdi'),
    ]

    event = models.ForeignKey(WorkEvent, on_delete=models.CASCADE, related_name='tasks', verbose_name="Tadbir")
    workers = models.ManyToManyField(Worker, blank=True, related_name='tasks', verbose_name="Ishchilar")
    completed_by = models.ForeignKey(
        Worker, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='completed_tasks', verbose_name="Kim bajardi"
    )

    description = models.CharField(max_length=500, verbose_name="Vazifa nomi")
    days_before = models.IntegerField(verbose_name="Necha kun")
    when = models.CharField(max_length=8, choices=WHEN_CHOICES, default='before', verbose_name="Tadbirdan oldin/keyin")
    hours_before = models.IntegerField(null=True, blank=True, verbose_name="Necha soat oldin")
    deadline_date = models.DateField(verbose_name="Deadline sanasi")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Holati")
    reminder_sent = models.BooleanField(default=False, verbose_name="Deadline eslatmasi yuborilgan")
    time_reminder_sent = models.BooleanField(default=False, verbose_name="Tadbir vaqti (2 soat) eslatmasi yuborilgan")
    instruction = models.TextField(blank=True, null=True, verbose_name="Instruksiya")

    def __str__(self):
        return f"{self.description} — {self.event.name}"

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