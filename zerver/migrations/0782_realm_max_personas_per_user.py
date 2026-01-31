from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0781_add_personas"),
    ]

    operations = [
        migrations.AddField(
            model_name="realm",
            name="max_personas_per_user",
            field=models.IntegerField(default=20),
        ),
    ]
