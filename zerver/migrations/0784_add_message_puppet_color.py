# Generated manually for puppet_color field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0783_agent_claim"),
    ]

    operations = [
        migrations.AddField(
            model_name="archivedmessage",
            name="puppet_color",
            field=models.CharField(default=None, max_length=10, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="puppet_color",
            field=models.CharField(default=None, max_length=10, null=True),
        ),
    ]
