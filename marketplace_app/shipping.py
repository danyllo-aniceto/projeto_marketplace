"""Simulação simples de frete por método de entrega.

Projeto acadêmico: valores fixos por serviço, apenas para ilustrar o impacto
do frete no total do pedido. Não há integração real com transportadoras.
"""
from decimal import Decimal

from .models import Order


SHIPPING_INFO = {
    Order.PICKUP: {
        'label': 'Retirada presencial',
        'cost': Decimal('0.00'),
        'eta': 'Combinar com o vendedor',
    },
    Order.SELLER_SHIPPING: {
        'label': 'Frete do vendedor',
        'cost': Decimal('19.90'),
        'eta': '5 a 9 dias úteis',
    },
    Order.PLATFORM_SHIPPING: {
        'label': 'Correios (plataforma)',
        'cost': Decimal('29.90'),
        'eta': '3 a 7 dias úteis',
    },
    Order.TO_AGREE: {
        'label': 'A combinar',
        'cost': Decimal('0.00'),
        'eta': 'Frete definido depois',
    },
}


def calculate_shipping(method):
    info = SHIPPING_INFO.get(method)
    return info['cost'] if info else Decimal('0.00')
