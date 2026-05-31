from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace_app', '0014_alter_commonprofile_cpf_alter_storeprofile_cnpj_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='listing',
            name='price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]