"""
Foydalanuvchilarga ommaviy xabar yuborish tizimi.
Admin sayt orqali xabar yozadi, teglar bo'yicha kimga yuborilishi tanlanadi.
"""
from django.db import models
from apps.users.models import User


class SendMessage(models.Model):
    """Yuborilgan/yuborilayotgan ommaviy xabar."""

    TAG_CHOICES = [
        ('all', 'Barchaga'),
        ('registered', "Ro'yxatdan to'liq o'tganlar"),
        ('not_registered', "Ro'yxatdan o'tmaganlar"),
    ]

    title = models.CharField(max_length=256, verbose_name="Sarlavha")
    description = models.TextField(verbose_name="Xabar matni")
    tags = models.JSONField(default=list, verbose_name="Kimga yuborilsin (teglar)")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Xabar"
        verbose_name_plural = "Xabarlar"
        ordering = ['-created_at']


class SendMessageFile(models.Model):
    """Xabarga qo'shilgan media fayl (rasm/video)."""

    send_message = models.ForeignKey(SendMessage, on_delete=models.CASCADE, related_name='files', verbose_name="Xabar")
    file = models.FileField(upload_to='messages/', verbose_name="Fayl")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Xabar fayli"
        verbose_name_plural = "Xabar fayllari"


class SendMessageUser(models.Model):
    """Har bir foydalanuvchiga yuborilgan xabarning holati (kuzatuv uchun)."""

    STATUS_CHOICES = [
        ('pending', 'Kutilmoqda'),
        ('success', 'Yuborildi'),
        ('failed', 'Xato'),
    ]

    send_message = models.ForeignKey(SendMessage, on_delete=models.CASCADE, related_name='recipients', verbose_name="Xabar")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Foydalanuvchi")

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending', verbose_name="Holati")
    error_message = models.TextField(null=True, blank=True, verbose_name="Xato matni")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.status}"

    class Meta:
        verbose_name = "Xabar holati"
        verbose_name_plural = "Xabar holatlari"
