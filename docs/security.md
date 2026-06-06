# Checklist de Segurança — TechHub

Estado dos controles de segurança da aplicação. ✅ implementado · 🟡 parcial · ⬜ recomendado (futuro).

## 1. Autenticação e sessão
- ✅ Senhas com hash (PBKDF2 do Django) — nunca em texto puro.
- ✅ Validação de força de senha no cadastro/alteração.
- ✅ CSRF em todos os formulários POST (middleware + `{% csrf_token %}`).
- ✅ "Lembrar de mim" controla expiração da sessão.
- ✅ Cookies de sessão/CSRF `Secure` quando `DEBUG=False`.
- 🟡 Rate limiting de login (proteção contra força bruta) — recomendado adicionar (ex: django-axes).

## 2. Autorização (acesso a dados)
- ✅ Rotas sensíveis com `@login_required`.
- ✅ Object-level checks: pedido só visível a comprador/vendedor/staff; endereço/notificação/anúncio só do dono; troca só aos participantes; ações `@require_POST`.
- ✅ Ações destrutivas (excluir anúncio, remover do carrinho, marcar lida) via POST + checagem de dono.
- ✅ Edição/transição de estado via `.update()` evitando efeitos colaterais.

## 3. Vazamento de dados nas respostas
- ✅ Serializers da API expõem só campos públicos; senha é `write_only`.
- ✅ Templates não renderizam dados de terceiros (CPF/CNPJ/endereço aparecem só para o próprio dono ou partes envolvidas na transação).
- ✅ `get_object_or_404` + filtros por usuário evitam IDOR (acesso por id de outro usuário) — retorna 404.
- 🟡 Revisar a API REST pública (`/api/listings/`) — hoje expõe `seller` (id). Sem dado sensível, mas vale limitar campos.

## 4. Proteções de plataforma (produção)
- ✅ `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS` por variável de ambiente.
- ✅ Erro de boot se `SECRET_KEY` insegura ou `ALLOWED_HOSTS` vazio em produção.
- ✅ `SECURE_SSL_REDIRECT`, HSTS, `X_FRAME_OPTIONS=DENY` quando `DEBUG=False`.
- ✅ Páginas 404/500 customizadas (não vazam stack trace).
- ⬜ Backups do banco e rotação de logs (infra de deploy).

## 5. Upload de arquivos
- ✅ Validação de **tipo** (JPG/PNG/WebP/GIF) e **tamanho** (≤5MB) em imagens de anúncio, perfil, banner e propostas.
- 🟡 Verificação de conteúdo impróprio (NSFW/violência) em imagens exige serviço externo de visão computacional (ex: AWS Rekognition / Google Vision). Hoje: validação técnica + denúncia + moderação do admin.
- ⬜ Reprocessar/normalizar imagens (remover metadados EXIF) — recomendado.

## 6. Moderação de conteúdo do usuário
- ✅ Filtro de **termos proibidos** (ofensa/ódio/indicadores ilegais) em título, descrição, sugestões de troca, comentários, propostas e mensagens → bloqueia o envio (`marketplace_app/moderation.py`, lista editável).
- ✅ **Denúncia de anúncio** pelo usuário (motivo + detalhe) → fila no admin.
- ✅ Admin: excluir anúncio, **banir vendedor** (desativa conta + remove anúncios), resolver/descartar denúncia.
- ✅ Admin: banir/reativar usuário direto na lista de usuários.
- ✅ Escopo de produto restrito às **categorias predefinidas** (eletrônicos/TI) — o usuário não cria categorias livres.
- 🟡 Detecção automática de item "fora do escopo" (ex: comida, carro) por texto é não confiável → tratado por denúncia + moderação do admin.
- ⬜ Banimento automático por reincidência (sistema de "strikes") — recomendado.

## 7. Boas práticas já presentes
- ✅ ORM (Django) → proteção contra SQL injection.
- ✅ Autoescape de templates → proteção contra XSS.
- ✅ Validação server-side em todos os formulários (não confia só no front).

## Prioridades recomendadas antes do deploy
1. Rate limiting no login.
2. Revisar campos expostos na API REST pública.
3. (Se houver verba) serviço de moderação de imagem por IA.
