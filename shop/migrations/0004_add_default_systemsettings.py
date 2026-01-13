from django.db import migrations

def add_default_systemsettings(apps, schema_editor):
    SystemSettings = apps.get_model('shop', 'SystemSettings')
    defaults = [
        ('soloReplayCost', '1', 'Cost to view solo replay'),
        ('progressiveReplayCost', '2', 'Cost to view progressive replay'),
        ('multiplayerReplayCost', '3', 'Cost to view multiplayer replay'),
        ('replayViewCostOwn', '0', 'Cost to view your own replay'),
        ('replayViewCostOther', '50', 'Cost to view others replay'),
    ]
    for key, value, desc in defaults:
        SystemSettings.objects.get_or_create(settingKey=key, defaults={
            'settingValue': value,
            'description': desc
        })

class Migration(migrations.Migration):
    dependencies = [
        ('shop', '0003_alter_transaction_transactiontype'),
    ]

    operations = [
        migrations.RunPython(add_default_systemsettings),
    ]
