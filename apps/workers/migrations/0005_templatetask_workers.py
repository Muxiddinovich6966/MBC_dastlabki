from django.db import migrations, models


def copy_worker_to_workers(apps, schema_editor):
    """Eski bitta `worker` qiymatini yangi `workers` (M2M) ga ko'chiradi."""
    TemplateTask = apps.get_model('workers', 'TemplateTask')
    for tt in TemplateTask.objects.exclude(worker__isnull=True):
        tt.workers.add(tt.worker_id)


def reverse_copy(apps, schema_editor):
    """Orqaga qaytarilsa — birinchi ishchini eski `worker` ga qaytaradi."""
    TemplateTask = apps.get_model('workers', 'TemplateTask')
    for tt in TemplateTask.objects.all():
        first = tt.workers.first()
        if first:
            tt.worker = first
            tt.save(update_fields=['worker'])


class Migration(migrations.Migration):

    dependencies = [
        ('workers', '0004_notificationlog_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='templatetask',
            name='workers',
            field=models.ManyToManyField(blank=True, related_name='template_tasks', to='workers.worker', verbose_name='Ishchilar'),
        ),
        migrations.RunPython(copy_worker_to_workers, reverse_copy),
        migrations.RemoveField(
            model_name='templatetask',
            name='worker',
        ),
    ]
