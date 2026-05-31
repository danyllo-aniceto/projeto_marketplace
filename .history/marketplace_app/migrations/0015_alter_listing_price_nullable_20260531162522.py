from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace_app', '0016_alter_category_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='listing',
            name='price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]