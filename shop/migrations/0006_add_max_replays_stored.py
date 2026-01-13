from django.db import migrations

def addMaxReplaysStored(apps, schema_editor):
    SystemSettings = apps.get_model('shop', 'SystemSettings')
    SystemSettings.objects.get_or_create(
        settingKey='maxReplaysStored',
        defaults={
            'settingValue': '50',
            'description': 'Maximum number of match replays to keep in database'
        }
    )

class Migration(migrations.Migration):
    dependencies = [
        ('shop', '0005_alter_transaction_transactiontype'),
    ]

    operations = [
        migrations.RunPython(addMaxReplaysStored),
    ]
