from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_userprofile_goal_userprofile_instagram_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('price', models.BigIntegerField(verbose_name="Narx (so'm)")),
                ('start_date', models.DateField(verbose_name='Boshlanish sanasi')),
                ('end_date', models.DateField(verbose_name='Tugash sanasi')),
                ('payment_type', models.CharField(choices=[('cash', 'Naqd'), ('card', 'Karta'), ('transfer', "O'tkazma"), ('other', 'Boshqa')], default='cash', max_length=32, verbose_name="To'lov turi")),
                ('note', models.TextField(blank=True, verbose_name='Izoh')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='plans', to='users.user', verbose_name='Foydalanuvchi')),
            ],
            options={
                'verbose_name': 'Obuna',
                'verbose_name_plural': 'Obunalar',
                'ordering': ['-created_at'],
            },
        ),
    ]
