"""
Ishchilar tizimi: ishchilar, shablonlar, tadbirlar va vazifalar bilan ishlash.
Bu sizning avvalgi Mfactor_bot loyihangizdagi tizimning sayt qismi.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import timedelta, datetime
from .models import Worker,Template,TemplateTask,WorkEvent,Task


def _compute_deadline(event_date, days, when):
    """Deadline sanasini hisoblaydi: 'before' → tadbirdan oldin, 'after' → tadbirdan keyin."""
    if isinstance(event_date, str):
        event_date = datetime.strptime(event_date, '%Y-%m-%d').date()
    delta = timedelta(days=days or 0)
    return event_date + delta if when == 'after' else event_date - delta


def _create_tasks_from_template(work_event, template):
    """Shablon vazifalaridan tadbir vazifalarini yaratadi.

    Har bir shablon vazifasi — bitta Task bo'ladi. Vazifaga bir nechta ishchi
    biriktirilgan bo'lsa, hammasi shu bitta Task ga bog'lanadi. Ulardan biri
    bajarsa — vazifa hamma uchun 'Bajarildi' bo'ladi.
    """
    created_tasks = []
    for tt in template.tasks.all():
        deadline = _compute_deadline(work_event.event_date, tt.days_before, tt.when)
        task = Task.objects.create(
            event=work_event,
            description=tt.description,
            days_before=tt.days_before,
            when=tt.when,
            hours_before=tt.hours_before,
            deadline_date=deadline,
            instruction=tt.instruction,
        )
        task.workers.set(tt.workers.all())
        created_tasks.append(task)
    return created_tasks

@login_required(login_url='/login/')
def workers_list(request):
    """Ishchilar ruyxati"""
    if request.method == 'POST':
        Worker.objects.create(
            telegram_id = request.POST.get('telegram_id'),
            name = request.POST.get('name'),
            role = request.POST.get('role'),
        )
        messages.success(request, "Ishchi qo'shildi.")
        return redirect('workers_list')

    workers = Worker.objects.all().order_by('name')
    return render(request,'workers/list.html',{'workers':workers})

@login_required(login_url='/login/')
def worker_delete(request,pk):
    worker = get_object_or_404(Worker,pk=pk)
    worker.delete()
    messages.success(request,"Ishchi o'chirildi.")
    return redirect('workers_list')

@login_required(login_url= '/login/')
def worker_edit(request, pk):
    """Mavjud ishchini tahrirlash."""
    worker = get_object_or_404(Worker, pk=pk)

    if request.method =='POST':
        worker.name = request.POST.get('name')
        worker.telegram_id = request.POST.get('telegram_id')
        worker.role = request.POST.get('role')
        worker.save()
        messages.success(request,"Ishchi ma'lumotlari yangilandi.")
        return redirect('workers_list')
    return render(request,'workers/edit.html',{'worker':worker})



@login_required(login_url = '/login/')
def templates_list(request):
    """Shablonlar ruyxati."""
    if request.method == 'POST':
        Template.objects.create(name=request.POST.get('name'))
        messages.success(request,"Shablon qo'shildi.")
        return redirect('templates_list')

    templates_list = Template.objects.all().order_by('name')
    return render(request,'workers/templates_list.html',{'templates':templates_list})

@login_required(login_url='/login/')
def template_detail(request,pk):
    """Bitta shablon va uning ichidagi vazifalar."""
    template=get_object_or_404(Template,pk=pk)
    workers = Worker.objects.filter(role__in=['worker','boss'])

    if request.method == 'POST':
        task = TemplateTask.objects.create(
            template=template,
            description=request.POST.get('description'),
            days_before=request.POST.get('days_before'),
            when=request.POST.get('when', 'before'),
            hours_before=request.POST.get('hours_before') or None,
            instruction=request.POST.get('instruction',''),
        )
        task.workers.set(request.POST.getlist('workers'))
        messages.success(request,"Vazifa shablonga qo'shildi.")
        return redirect('template_detail',pk=template.pk)

    tasks = template.tasks.prefetch_related('workers').all()
    return render(request,"workers/template_detail.html",{
        'template':template,
        'tasks': tasks,
        'workers': workers,
    })

@login_required(login_url = '/login/')
def template_task_delete(request, pk):
    task = get_object_or_404(TemplateTask, pk=pk)
    template_pk = task.template.pk
    task.delete()
    messages.success(request,"Vazifa o'chirildi.")
    return redirect('template_detail',pk=template_pk)


@login_required(login_url='/login/')
def template_task_edit(request, pk):
    """Shablonni ichidagi vazifalarni tahrirlash"""
    task = get_object_or_404(TemplateTask,pk=pk)
    workers = Worker.objects.filter(role__in=['worker','boss'])

    if request.method == 'POST':
        task.description = request.POST.get('description')
        task.days_before = request.POST.get('days_before')
        task.when = request.POST.get('when','before')
        task.hours_before = request.POST.get('hours_before') or None
        task.instruction = request.POST.get('instruction','')
        task.save()
        task.workers.set(request.POST.getlist('workers'))
        messages.success(request,"Vazifa yangilandi.")
        return redirect('template_detail',pk=task.template.pk)

    return render(request,'workers/template_task_edit.html',{
        'task':task,
        'workers':workers,
    })

@login_required(login_url='/login/')
def template_delete(request, pk):
    template = get_object_or_404(Template, pk=pk)
    template.delete()
    messages.success(request, "Shablon o'chirildi.")
    return redirect('templates_list')


@login_required(login_url='/login/')
def template_edit(request,pk):
    """Shablon nomini tahrirlash."""
    template= get_object_or_404(Template, pk=pk)

    if request.method == 'POST':
        template.name = request.POST.get('name')
        template.save()
        messages.success(request,"Shablon nomi yangilandi.")
        return redirect('templates_list')
    return render(request,'workers/template_edit.html',{'template':template})



def work_events_list(request):
    """Ishchilar tizimidagi tadbirlar — shablon biriktirilganda vazifalar avtomatik yaratiladi."""
    if request.method == 'POST':
        # Vaqt majburiy
        event_time = (request.POST.get('event_time') or '').strip()
        if not event_time:
            messages.error(request, "Iltimos, tadbir vaqtini (soatini) kiriting.")
            return redirect('work_events_list')

        template_id = request.POST.get('template') or None
        work_event = WorkEvent.objects.create(
            name=request.POST.get('name'),
            event_date=request.POST.get('event_date'),
            event_time=event_time,
            template_id=template_id,
        )

        created_tasks = []
        if template_id:
            template = Template.objects.get(pk=template_id)
            created_tasks = _create_tasks_from_template(work_event, template)

        # Ishchilarga va boshliqqa xabar yuboramiz
        _notify_new_tasks(work_event, created_tasks)

        messages.success(request, "Tadbir qo'shildi, vazifalar yaratildi va yuborildi.")
        return redirect('work_events_list')

    work_events = WorkEvent.objects.select_related('template').prefetch_related('tasks').order_by('-event_date')
    templates = Template.objects.all()

    return render(request, 'workers/events_list.html', {
        'work_events': work_events,
        'templates': templates,
    })

def _notify_new_tasks(work_event, tasks, is_update=False):
    """
    Yangi vazifalarni ishchiga (Bajardim tugmasi bilan) va boshliqqa (har biri alohida, Kutilmoqda) yuboradi.
    Admin — o'zi qo'shgani uchun xabar olmaydi.
    is_update=True bo'lsa — 'tadbir o'zgardi' deb yuboriladi (tahrirlashda).
    """
    from config.bot_notify import send_worker_task, send_boss_task_pending
    from apps.workers.models import Worker, NotificationLog

    event_date_str = (
        work_event.event_date.strftime('%d.%m.%Y')
        if not isinstance(work_event.event_date, str) else work_event.event_date
    )

    # Faqat BOSHLIQ (admin emas)
    bosses = list(Worker.objects.filter(role='boss').exclude(telegram_id__isnull=True))

    for task in tasks:
        task_workers = list(task.workers.all())
        worker_name = ", ".join(w.name for w in task_workers) if task_workers else "Biriktirilmagan"
        deadline_str = (
            task.deadline_date.strftime('%d.%m.%Y')
            if not isinstance(task.deadline_date, str) else task.deadline_date
        )

        # 1. Har bir biriktirilgan ishchiga o'z vazifasi (Bajardim tugmasi bilan)
        #    — barchasi bitta task.id ga bog'lanadi, biri bajarsa hammasi yopiladi.
        for worker in task_workers:
            if not worker.telegram_id:
                continue
            w_msg_id = send_worker_task(
                worker.telegram_id, work_event.name, event_date_str,
                task.description, deadline_str, task.days_before, task.id,
                is_update=is_update,
            )
            if w_msg_id:
                NotificationLog.objects.create(
                    task=task, chat_id=worker.telegram_id, message_id=w_msg_id
                )

        # 2. Har boshliqqa shu vazifa alohida (Kutilmoqda) — va message_id ni saqlaymiz
        for boss in bosses:
            msg_id = send_boss_task_pending(
                boss.telegram_id, worker_name, work_event.name, event_date_str,
                task.description, deadline_str, is_update=is_update,
            )
            if msg_id:
                NotificationLog.objects.create(
                    task=task, chat_id=boss.telegram_id, message_id=msg_id
                )

def _delete_event_task_messages(work_event):
    """Tadbirning barcha vazifa xabarlarini (ishchi + boshliq) Telegramdan o'chiradi."""
    from config.bot_notify import delete_worker_bot_message
    from apps.workers.models import NotificationLog

    logs = NotificationLog.objects.filter(task__event=work_event)
    for lg in logs:
        delete_worker_bot_message(lg.chat_id, lg.message_id)
    logs.delete()


@login_required(login_url='/login/')
def work_event_detail(request, pk):
    """Bitta tadbirning vazifalari va ularning holati."""
    work_event = get_object_or_404(WorkEvent, pk=pk)
    tasks = work_event.tasks.prefetch_related('workers').order_by('deadline_date')

    return render(request, 'workers/event_detail.html', {
        'work_event': work_event,
        'tasks': tasks,
    })


@login_required(login_url='/login/')
def work_event_delete(request, pk):
    work_event = get_object_or_404(WorkEvent, pk=pk)
    work_event.delete()
    messages.success(request, "Tadbir o'chirildi.")
    return redirect('work_events_list')



@login_required(login_url='/login/')
def work_event_edit(request, pk):
    """Ishchilar tadbirini tahrirlash.

    O'zgarish bo'lsa — mijozlar tizimidagidek: eski vazifa xabarlari Telegramdan
    o'chiriladi, o'rniga yangi xabarlar ('Bajardim' tugmasi bilan) yuboriladi.
    """
    work_event = get_object_or_404(WorkEvent, pk=pk)

    if request.method == 'POST':
        # Vaqt majburiy
        event_time = (request.POST.get('event_time') or '').strip()
        if not event_time:
            messages.error(request, "Iltimos, tadbir vaqtini (soatini) kiriting.")
            return redirect('work_event_edit', pk=work_event.pk)

        old_template_id = work_event.template_id
        old_date = work_event.event_date
        old_name = work_event.name

        new_template_id = request.POST.get('template') or None
        work_event.name = request.POST.get('name')
        work_event.event_date = request.POST.get('event_date')
        work_event.event_time = event_time
        work_event.template_id = new_template_id
        work_event.save()

        template_changed = str(old_template_id) != str(new_template_id)
        date_changed = str(old_date) != str(work_event.event_date)
        name_changed = old_name != work_event.name

        if template_changed or date_changed or name_changed:
            # 1) Eski vazifa xabarlarini (ishchi + boshliq) Telegramdan o'chiramiz
            _delete_event_task_messages(work_event)

            if template_changed:
                # Shablon o'zgargan — vazifalarni butunlay qayta yaratamiz
                work_event.tasks.all().delete()
                if new_template_id:
                    template = Template.objects.get(pk=new_template_id)
                    _create_tasks_from_template(work_event, template)
            else:
                # Shablon o'zgarmagan (sana yoki nomi o'zgargan) — mavjud vazifalarni
                # yangilab, qayta faollashtiramiz (deadline qayta hisoblanadi, holat pending)
                for task in work_event.tasks.all():
                    task.deadline_date = _compute_deadline(work_event.event_date, task.days_before, task.when)
                    task.status = 'pending'
                    task.reminder_sent = False
                    task.time_reminder_sent = False
                    task.completed_by = None
                    task.save(update_fields=['deadline_date', 'status', 'reminder_sent',
                                             'time_reminder_sent', 'completed_by'])

            # 2) Yangi xabarlarni yuboramiz ('Bajardim' tugmasi bilan) — 'tadbir o'zgardi' ogohlantirishi bilan
            _notify_new_tasks(work_event, list(work_event.tasks.all()), is_update=True)

        messages.success(request, "Tadbir yangilandi, vazifalar qayta yuborildi.")
        return redirect('work_events_list')

    templates = Template.objects.all()
    return render(request, 'workers/event_edit.html', {
        'work_event': work_event,
        'templates': templates,
    })