from django.db import migrations, models
import django.db.models.deletion


def copy_worker_to_workers(apps, schema_editor):
    """Eski bitta `worker` qiymatini yangi `workers` (M2M) ga ko'chiradi."""
    Task = apps.get_model('workers', 'Task')
    for task in Task.objects.exclude(worker__isnull=True):
        task.workers.add(task.worker_id)


def reverse_copy(apps, schema_editor):
    """Orqaga qaytarilsa — birinchi ishchini eski `worker` ga qaytaradi."""
    Task = apps.get_model('workers', 'Task')
    for task in Task.objects.all():
        first = task.workers.first()
        if first:
            task.worker = first
            task.save(update_fields=['worker'])


class Migration(migrations.Migration):

    dependencies = [
        ('workers', '0005_templatetask_workers'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='workers',
            field=models.ManyToManyField(blank=True, related_name='tasks', to='workers.worker', verbose_name='Ishchilar'),
        ),
        migrations.AddField(
            model_name='task',
            name='completed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='completed_tasks', to='workers.worker', verbose_name='Kim bajardi'),
        ),
        migrations.RunPython(copy_worker_to_workers, reverse_copy),
        migrations.RemoveField(
            model_name='task',
            name='worker',
        ),
    ]
