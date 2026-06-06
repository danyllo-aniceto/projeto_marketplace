"""Moderação de conteúdo enviado por usuários.

Detecta termos proibidos (ofensas graves, discurso de ódio, indicadores de
conteúdo ilegal) em textos. A lista é propositalmente editável e conservadora —
o objetivo é bloquear o cadastro do conteúdo, não banir automaticamente por uma
única palavra (banimento é uma ação revisada pelo admin).

Também oferece validação de upload de imagens (tipo e tamanho).
"""
import re
import unicodedata

from django.core.exceptions import ValidationError


# Termos proibidos (edite conforme a política). Normalizados (sem acento, minúsculos).
# Mantido curto e representativo; cobre ofensas/ódio e indicadores de ilegalidade.
PROHIBITED_TERMS = {
    # ódio / ofensas graves
    'viado', 'viadinho', 'bicha', 'sapatao', 'traveco',
    'macaco', 'preto fedido', 'crioulo',
    'retardado', 'mongoloide',
    # sexual explícito / exploração
    'pornografia', 'pedofilia', 'estupro', 'zoofilia',
    # ilegalidade explícita
    'cocaina', 'maconha', 'crack', 'lsd', 'metanfetamina',
    'arma de fogo', 'pistola', 'revolver', 'fuzil', 'municao',
    'documento falso', 'cnh falsa', 'diploma falso',
}


def _normalize(text):
    text = (text or '').lower()
    # remove acentos
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    # colapsa espaços
    return re.sub(r'\s+', ' ', text)


def find_prohibited(text):
    """Retorna a lista de termos proibidos encontrados no texto (pode ser vazia)."""
    normalized = _normalize(text)
    found = []
    for term in PROHIBITED_TERMS:
        # casa o termo como palavra/expressão (com bordas) para reduzir falso positivo
        pattern = r'(?<!\w)' + re.escape(term) + r'(?!\w)'
        if re.search(pattern, normalized):
            found.append(term)
    return found


def validate_clean_text(text, field_label='conteúdo'):
    """Lança ValidationError se o texto contiver termos proibidos."""
    found = find_prohibited(text)
    if found:
        raise ValidationError(
            f'O {field_label} contém termos não permitidos. '
            'Revise o texto para seguir as regras da plataforma.'
        )
    return text


# ---------------- Strikes / banimento por reincidência ----------------

MAX_STRIKES = 3


def record_strike(user):
    """Registra uma advertência. Ao atingir MAX_STRIKES, bane a conta
    (desativa + remove anúncios). Retorna (strikes_atuais, banido)."""
    from .models import Listing

    if not user or not user.is_authenticated or user.is_superuser:
        return (0, False)

    user.strikes = (user.strikes or 0) + 1
    fields = ['strikes']
    banned = False
    if user.strikes >= MAX_STRIKES:
        user.is_active = False
        fields.append('is_active')
        banned = True
    user.save(update_fields=fields)
    if banned:
        Listing.objects.filter(seller=user).delete()
    return (user.strikes, banned)


def screen_user_text(request, *texts):
    """Verifica os textos enviados; se houver termo proibido, registra um strike.

    Retorna (flagged, strikes, banned).
    """
    joined = ' '.join(t for t in texts if t)
    if find_prohibited(joined):
        strikes, banned = record_strike(request.user)
        return (True, strikes, banned)
    return (False, getattr(request.user, 'strikes', 0), False)


# ---------------- Imagens ----------------

MAX_IMAGE_SIZE_MB = 5
ALLOWED_IMAGE_CONTENT_TYPES = {
    'image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif',
}


def validate_image_upload(uploaded_file):
    """Valida tipo e tamanho de uma imagem enviada.

    Observação: a verificação de conteúdo impróprio em imagens (NSFW/violência)
    exige um serviço externo de visão computacional. Aqui garantimos tipo/tamanho
    e contamos com denúncia + moderação do admin para o restante.
    """
    if not uploaded_file:
        return uploaded_file

    content_type = getattr(uploaded_file, 'content_type', None)
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValidationError('Formato de imagem não suportado. Use JPG, PNG, WebP ou GIF.')

    size = getattr(uploaded_file, 'size', 0)
    if size and size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise ValidationError(f'Cada imagem deve ter no máximo {MAX_IMAGE_SIZE_MB}MB.')

    return uploaded_file
