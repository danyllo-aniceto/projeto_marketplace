from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace_app', '0012_tradeproposalimage'),
    ]

    operations = [
        migrations.CreateModel(
            name='TradeDelivery',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('delivery_method', models.CharField(choices=[('pickup', 'Retirada presencial'), ('seller_shipping', 'Frete do vendedor'), ('platform_shipping', 'Frete da plataforma'), ('to_agree', 'A combinar')], default='to_agree', max_length=20)),
                ('recipient_name', models.CharField(blank=True, max_length=255)),
                ('recipient_phone', models.CharField(blank=True, max_length=20)),
                ('postal_code', models.CharField(blank=True, max_length=9)),
                ('street', models.CharField(blank=True, max_length=255)),
                ('number', models.CharField(blank=True, max_length=20)),
                ('complement', models.CharField(blank=True, max_length=100)),
                ('neighborhood', models.CharField(blank=True, max_length=120)),
                ('city', models.CharField(blank=True, max_length=120)),
                ('state', models.CharField(blank=True, max_length=2)),
                ('notes', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('draft', 'Rascunho'), ('sent', 'Enviado'), ('delivered', 'Entregue'), ('cancelled', 'Cancelada')], default='draft', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('trade_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deliveries', to='marketplace_app.traderequest')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='trade_deliveries', to='marketplace_app.user')),
            ],
        ),
    ]
