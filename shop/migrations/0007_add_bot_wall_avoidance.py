from django.db import migrations

def add_bot_wall_avoidance(apps, schema_editor):
    SystemSettings = apps.get_model('shop', 'SystemSettings')
    SystemSettings.objects.get_or_create(
        settingKey='botWallAvoidance',
        defaults={
            'settingValue': '80',
            'description': 'Bot wall avoidance accuracy for multiplayer (0-100, higher = better avoidance, 100 = always avoid)'
        }
    )

class Migration(migrations.Migration):
    dependencies = [
        ('shop', '0006_add_max_replays_stored'),
    ]

    operations = [
        migrations.RunPython(add_bot_wall_avoidance),
    ]
