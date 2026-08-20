"""
Telegram guruhlari bilan ishlash.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError

from .models import Group


@login_required(login_url='/login/')
def groups_list(request):
    if request.method == 'POST':
        from config.bot_notify import get_telegram_chat

        tg_id = (request.POST.get('tg_id') or '').strip()
        title = (request.POST.get('title') or '').strip()

        # Bot bu chatni ko'ra oladimi — qo'shishдан oldin tekshiramiz
        ok, info = get_telegram_chat(tg_id)
        if not ok:
            messages.error(
                request,
                f"Guruh qo'shilmadi: bot bu chatni topa olmadi ({info}). "
                "Botni guruh/kanalga ADMIN qilib qo'shganingizni va ID to'g'riligini tekshiring."
            )
            return redirect('groups_list')

        # Nom kiritilmagan bo'lsa — Telegramдан olamiz
        if not title:
            title = info

        try:
            Group.objects.create(title=title, tg_id=tg_id)
            messages.success(request, f"Guruh qo'shildi: {title}")
        except IntegrityError:
            messages.error(request, "Bu Telegram ID allaqachon mavjud.")
        return redirect('groups_list')

    groups = Group.objects.order_by('-created_at')
    return render(request, 'groups/list.html', {'groups': groups})


@login_required(login_url='/login/')
def group_edit(request, pk):
    """Guruh nomi/ID sini tahrirlash (o'chirmasдан to'g'rilash uchun)."""
    group = get_object_or_404(Group, pk=pk)
    if request.method == 'POST':
        from config.bot_notify import get_telegram_chat

        tg_id = (request.POST.get('tg_id') or '').strip()
        title = (request.POST.get('title') or '').strip()

        ok, info = get_telegram_chat(tg_id)
        if not ok:
            messages.error(
                request,
                f"Saqlanmadi: bot bu chatni topa olmadi ({info}). "
                "Botni chatga ADMIN qilib qo'shing va ID to'g'riligini tekshiring."
            )
            return redirect('groups_list')

        if not title:
            title = info

        group.title = title
        group.tg_id = tg_id
        try:
            group.save()
            messages.success(request, f"Guruh yangilandi: {title}")
        except IntegrityError:
            messages.error(request, "Bu Telegram ID boshqa guruhда mavjud.")
    return redirect('groups_list')


@login_required(login_url='/login/')
def group_delete(request, pk):
    group = get_object_or_404(Group, pk=pk)
    group.delete()
    messages.success(request, "Guruh o'chirildi.")
    return redirect('groups_list')
