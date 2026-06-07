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


# Termos proibidos (edite conforme a política). São comparados já normalizados
# (sem acento, minúsculos, ver _normalize). Mantemos termos específicos e, quando
# possível, em expressão (duas+ palavras) para reduzir falso positivo — o objetivo
# é bloquear o cadastro do conteúdo, não banir por uma única palavra ambígua.
PROHIBITED_TERMS = {
    # ----- discurso de ódio / ofensas graves: homofobia/transfobia -----
    'viado', 'viadinho', 'viadao', 'bicha', 'bichinha', 'sapatao',
    'traveco', 'travecao', 'baitola', 'boiola',
    # ----- racismo -----
    'macaco preto', 'preto fedido', 'crioulo', 'nego fedido',
    'volta pra senzala', 'quadrilha de preto',
    # ----- capacitismo / ofensa a deficiência -----
    'retardado', 'retardada', 'mongoloide', 'mongol', 'aleijado debiloide',
    'debil mental',
    # ----- xenofobia / intolerância religiosa -----
    'nordestino burro', 'macumbeiro do capeta',
    # ----- sexual explícito / exploração (ilegal) -----
    'pornografia', 'pornografia infantil', 'pedofilia', 'pedofilo',
    'estupro', 'estuprar', 'zoofilia', 'sexo com menor', 'menor de idade nu',
    'nudes de menor', 'conteudo adulto infantil',
    # ----- drogas ilícitas -----
    'cocaina', 'maconha', 'skunk', 'haxixe', 'crack', 'lsd',
    'metanfetamina', 'ecstasy', 'mdma', 'heroina', 'merla', 'oxi',
    'lanca perfume', 'cogumelo alucinogeno', 'folha de coca',
    'comprar droga', 'vendo droga', 'tabua de maconha',
    # ----- armas e munição (venda proibida na plataforma) -----
    'arma de fogo', 'pistola', 'revolver', 'fuzil', 'espingarda',
    'submetralhadora', 'municao', 'cartucho calibre', 'silenciador de arma',
    'granada', 'explosivo caseiro', 'arma artesanal', 'arma 3d',
    # ----- documentos / itens falsos ou fraudulentos -----
    'documento falso', 'documentos falsos', 'cnh falsa', 'rg falso',
    'diploma falso', 'certificado falso', 'nota fiscal falsa',
    'dinheiro falso', 'cedula falsa',
    # ----- produtos roubados / desbloqueio ilícito (golpe comum no e-commerce) -----
    'produto roubado', 'celular roubado', 'aparelho roubado',
    'imei bloqueado', 'desbloqueio de imei', 'desbloquear imei roubado',
    'cartao clonado', 'cartao de credito clonado', 'chip clonado',
    'conta bancaria hackeada', 'cvv roubado', 'gerador de cartao',
    # ----- pirataria / acesso ilícito -----
    'conta netflix hackeada', 'iptv pirata', 'gerador de licenca pirata',
}


# Substituições de "leetspeak" para dificultar burlas simples (v1@d0 -> viado).
# Conservador: só mapeamos símbolos/dígitos que viram letras. Como a busca exige
# bordas de palavra e termos específicos, a chance de falso positivo é baixa.
_LEET_MAP = {
    '@': 'a', '4': 'a',
    '$': 's', '5': 's',
    '0': 'o',
    '1': 'i', '!': 'i',
    '3': 'e',
    '7': 't',
    '9': 'g',
}
_LEET_TABLE = str.maketrans(_LEET_MAP)


def _normalize(text, *, leet=False):
    text = (text or '').lower()
    # remove acentos
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    if leet:
        text = text.translate(_LEET_TABLE)
    # colapsa 3+ repetições da mesma letra (viaaaado -> viado); preserva duplas reais
    text = re.sub(r'(.)\1{2,}', r'\1', text)
    # colapsa espaços
    return re.sub(r'\s+', ' ', text)


def find_prohibited(text):
    """Retorna a lista de termos proibidos encontrados no texto (pode ser vazia).

    Verifica o texto normalizado e também uma variante com 'leetspeak' resolvido
    (v1@d0 -> viado), pegando burlas simples sem aumentar o falso positivo: um
    termo só é flagrado se casar exatamente com a palavra/expressão proibida.
    """
    variants = {_normalize(text), _normalize(text, leet=True)}
    found = []
    for term in PROHIBITED_TERMS:
        # casa o termo como palavra/expressão (com bordas) para reduzir falso positivo
        pattern = r'(?<!\w)' + re.escape(term) + r'(?!\w)'
        if any(re.search(pattern, v) for v in variants):
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

    # Moderadores (staff) e superusuários não levam strike/ban automático.
    if not user or not user.is_authenticated or user.is_staff or user.is_superuser:
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
