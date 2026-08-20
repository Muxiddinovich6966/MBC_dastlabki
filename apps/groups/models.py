"""
Telegram guruhlari.
Tadbir e'lonlari shu guruhlarga ham yuborilishi mumkin.
"""
from django.db import models


class Group(models.Model):
    """Botning a'zo bo'lgan Telegram guruhi/kanali."""

    title = models.CharField(max_length=128, verbose_name="Guruh nomi")
    tg_id = models.CharField(max_length=128, unique=True, verbose_name="Telegram guruh ID")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Guruh"
        verbose_name_plural = "Guruhlar"
        ordering = ['-created_at']
