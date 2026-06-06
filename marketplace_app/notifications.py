"""Helpers centrais para criar notificações no sistema.

Uso típico:
    from marketplace_app.notifications import notify
    notify(recipient, 'Título', 'mensagem', url='/pedidos/1/', category=Notification.SALE, icon='sell', actor=request.user)
"""
from .models import Notification


def notify(recipient, title, message='', url='', category=Notification.SYSTEM,
           icon='notifications', actor=None):
    """Cria uma notificação para `recipient`.

    - Não notifica o próprio usuário quando ele é o autor da ação.
    - Retorna a Notification criada (ou None se ignorada).
    """
    if recipient is None:
        return None
    if actor is not None and getattr(actor, 'id', None) == recipient.id:
        return None

    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        title=title,
        message=message or '',
        url=url or '',
        category=category,
        icon=icon,
    )
