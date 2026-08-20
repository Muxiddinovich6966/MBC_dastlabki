"""
Foydalanuvchilarga ommaviy xabar yuborish.
"""
from importlib.metadata import files

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages as django_messages

from .models import SendMessage, SendMessageFile, SendMessageUser
from apps.users.models import User


@login_required(login_url='/login/')
def messages_list(request):
    """Yuborilgan xabarlar tarixi + yangi xabar yuborish formasi."""
    if request.method == 'POST':
        from config.bot_notify import send_telegram_message
        import requests
        from django.conf import settings

        title = request.POST.get('title')
        description = request.POST.get('description')
        tags = request.POST.getlist('tags')

        msg = SendMessage.objects.create(title=title, description=description, tags=tags)

        # Fayllarni saqlaymiz
        files = []
        for f in request.FILES.getlist('files'):
            file_obj = SendMessageFile.objects.create(send_message=msg, file=f)
            files.append(file_obj)

        # Kimga yuborilishini aniqlaymiz
        if 'all' in tags:
            target_users = User.objects.filter(role='user', is_active=True).exclude(tg_id__isnull=True)
        elif 'registered' in tags:
            target_users = User.objects.filter(role='user', is_active=True, user_unique_code__isnull=False)
        elif 'not_registered' in tags:
            target_users = User.objects.filter(role='user', is_active=True, user_unique_code__isnull=True)
        else:
            target_users = User.objects.none()

        # Chiroyli formatlangan xabar matni
        text = (
            f"📢 <b>{title}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{description}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<i>MBC Platform</i>"
        )

        # Birinchi rasmning to'liq path'ini olamiz (bo'lsa)
        first_image_path = None
        for f in files:
            file_url = f.file.name.lower()
            if file_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                first_image_path = f.file.path
                break

        token = settings.CLIENT_BOT_TOKEN
        sent = 0
        for user in target_users:
            ok = False
            try:
                if first_image_path:
                    # Rasm bilan yuboriladi
                    url = f"https://api.telegram.org/bot{token}/sendPhoto"
                    with open(first_image_path, 'rb') as photo:
                        r = requests.post(url, data={
                            'chat_id': user.tg_id,
                            'caption': text,
                            'parse_mode': 'HTML',
                        }, files={'photo': photo}, timeout=30)
                    ok = r.json().get('ok', False)
                else:
                    # Faqat matn
                    ok = send_telegram_message(user.tg_id, text)
            except Exception as e:
                print(f"Xabar yuborish xatosi ({user.tg_id}): {e}")
                ok = False

            SendMessageUser.objects.create(
                send_message=msg, user=user,
                status='success' if ok else 'failed',
            )
            if ok:
                sent += 1

        django_messages.success(request, f"Xabar {sent} ta foydalanuvchiga yuborildi.")
        return redirect('messages_list')

    from django.db.models import Count, Q
    all_messages = SendMessage.objects.annotate(
        total_recipients=Count('recipients'),
        success_recipients=Count('recipients', filter=Q(recipients__status='success')),
    ).order_by('-created_at')
    return render(request, 'messages/list.html', {'messages_list': all_messages})




@login_required(login_url='/login/')
def message_delete(request, pk):
    msg = get_object_or_404(SendMessage, pk=pk)
    msg.delete()
    django_messages.success(request, "Xabar o'chirildi.")
    return redirect('messages_list')


@login_required(login_url='/login/')
def message_detail(request, pk):
    """Xabar detali: kimga yetgan, kimga yetmagan."""
    msg = get_object_or_404(SendMessage, pk=pk)
    recipients = list(msg.recipients.select_related('user').order_by('-created_at'))
    files = msg.files.all()

    counts = {
        'total': len(recipients),
        'success': sum(1 for r in recipients if r.status == 'success'),
        'failed': sum(1 for r in recipients if r.status == 'failed'),
    }

    return render(request, 'messages/detail.html', {
        'msg': msg,
        'recipients': recipients,
        'files': files,
        'counts': counts,
    })