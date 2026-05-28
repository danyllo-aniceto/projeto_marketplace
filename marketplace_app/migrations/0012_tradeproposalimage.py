from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace_app', '0011_listing_trade_suggestions_alter_commonprofile_cpf_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='TradeProposalImage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='trade_proposals/')),
                ('proposal', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='images', to='marketplace_app.tradeproposal')),
            ],
        ),
    ]
