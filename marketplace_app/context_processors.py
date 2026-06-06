from django.db import models

from .models import Cart, CartItem, Notification


def cart_counts(request):
    """Adiciona contadores do carrinho ao contexto de templates.

    Retorna `cart_buy_count`, `cart_trade_count` e `cart_total_count` quando
    o usuário está autenticado. Caso contrário, retorna um dicionário vazio.
    """
    if not request.user or not request.user.is_authenticated:
        return {}

    try:
        cart, _ = Cart.objects.get_or_create(user=request.user)
    except Exception:
        return {}

    items = cart.items.all()
    buy_count = items.filter(desired_action=CartItem.BUY).count()
    trade_count = items.filter(desired_action=CartItem.TRADE).count()
    total = items.count()

    return {
        'cart_buy_count': buy_count,
        'cart_trade_count': trade_count,
        'cart_total_count': total,
    }


def notifications(request):
    """Disponibiliza no header o total de não lidas e as mais recentes."""
    if not request.user or not request.user.is_authenticated:
        return {}

    try:
        qs = Notification.objects.filter(recipient=request.user)
        unread = qs.filter(is_read=False).count()
        recent = list(qs[:8])
    except Exception:
        return {}

    return {
        'notifications_unread_count': unread,
        'notifications_recent': recent,
    }
