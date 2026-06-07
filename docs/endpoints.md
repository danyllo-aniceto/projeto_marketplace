# Mapa De Endpoints

## Convenções

- Endpoints web retornam HTML e, quando há sucesso, normalmente redirecionam com `302`.
- Endpoints `login_required` redirecionam para login quando o usuário não está autenticado.
- Endpoints de API retornam JSON.
- Em formulários com erro, a resposta costuma ser `200` com a página renderizada novamente e mensagens de erro.

## 1. Endpoints Web Do Marketplace

### `GET /`
Home do marketplace.

Envia:

- query string opcional `q`
- query string opcional `categoria`

Retorna em sucesso:

- `200` com HTML da home
- contexto com `carousel_products`, `featured_products`, `anuncios`, `categories`, `selected_category`, `search_query`

Erros comuns:

- `200` vazio se não houver anúncios
- `404` apenas se a URL não existir

### `GET|POST /criar-anuncio/`
Criar anúncio.

Autenticação:

- obrigatório estar logado

Envia no POST:

- `title`
- `description`
- `price`
- `category`
- `listing_type`
- `condition`
- `image` opcional

Retorna em sucesso:

- `302` para `/` depois de criar o anúncio

Erros comuns:

- `302` para login se não estiver autenticado
- `200` com formulário e erros de validação

### `GET /meus-anuncios/`
Lista anúncios do usuário logado.

Autenticação:

- obrigatório estar logado

Retorna em sucesso:

- `200` com lista de anúncios do vendedor

Erros comuns:

- `302` para login se não estiver autenticado

### `GET|POST /editar-anuncio/<int:pk>/`
Edita um anúncio do usuário logado.

Autenticação:

- obrigatório estar logado

Envia no POST:

- mesmos campos do formulário de criação
- `image` opcional para adicionar nova imagem

Retorna em sucesso:

- `302` para `/meus-anuncios/`

Erros comuns:

- `404` se o anúncio não existir ou não pertencer ao usuário
- `200` com formulário e erros de validação

### `POST /excluir-anuncio/<int:pk>/`
Exclui um anúncio do usuário logado.

Autenticação:

- obrigatório estar logado

Retorna em sucesso:

- `302` para `/meus-anuncios/`

Erros comuns:

- `404` se o anúncio não existir ou não pertencer ao usuário
- `302` para a tela de edição quando a requisição não for `POST`

### `GET|POST /anuncio/<int:pk>/`
Detalhe do anúncio e comentários.

Envia no POST:

- `content` do comentário

Retorna em sucesso:

- `200` com detalhe do anúncio
- comentário salvo e redirecionamento para o próprio detalhe

Erros comuns:

- `302` para login se tentar comentar sem autenticação
- `404` se o anúncio não existir

### `GET /carrinho/`
Mostra o carrinho do usuário.

Autenticação:

- obrigatório estar logado

Retorna em sucesso:

- `200` com itens e total

Envia em contexto:

- `buy_items`
- `trade_items`
- `total`

Erros comuns:

- `302` para login se não estiver autenticado

### `POST /carrinho/item/<int:pk>/acao/`
Atualiza a intenção de um item do carrinho entre compra e troca.

Autenticação:

- obrigatório estar logado

Envia no POST:

- `desired_action`

Retorna em sucesso:

- `302` para `/carrinho/`

Erros comuns:

- `302` para login se não estiver autenticado

### `GET /adicionar-carrinho/<int:pk>/`
Adiciona um anúncio ao carrinho.

Autenticação:

- obrigatório estar logado

Retorna em sucesso:

- `302` para `/carrinho/`

Query string opcional:

- `action=buy|trade`
- `next=/url/de/retorno`

Erros comuns:

- `404` se o anúncio não existir ou não estiver ativo
- `302` para login se não estiver autenticado

### `GET|POST /checkout/`
Finaliza o carrinho.

Autenticação:

- obrigatório estar logado

Envia no POST quando houver itens de compra:

- `payment_method`
- `delivery_method`
- `notes` opcional

Retorna em sucesso:

- `302` para o pedido criado quando houver compra
- `302` para `/trocas/` quando houver apenas trocas
- `302` para o gateway de pagamento quando houver gateway configurado

Erros comuns:

- `200` com formulário e erros de validação
- `302` para login se não estiver autenticado

### `GET /pedidos/`
Lista os pedidos do usuário.

Autenticação:

- obrigatório estar logado

Retorna em sucesso:

- `200` com a lista de pedidos

### `GET /pedidos/<int:pk>/`
Mostra o detalhe de um pedido.

Autenticação:

- obrigatório estar logado e ser o comprador

Retorna em sucesso:

- `200` com detalhes do pedido e itens

Erros comuns:

- `404` se o pedido não existir ou não pertencer ao usuário

### `GET|POST /pedidos/<int:pk>/entrega/`
Atualiza os dados de entrega do pedido.

Autenticação:

- obrigatório estar logado como admin

Envia no POST:

- `method`
- `shipping_cost`
- `carrier_name`
- `tracking_code`
- `estimated_delivery_date`
- `notes`

Retorna em sucesso:

- `302` para `/pedidos/<int:pk>/`

Erros comuns:

- `302` para o detalhe do pedido se não for admin

### `GET /trocas/`
Lista as negociações de troca do usuário.

Autenticação:

- obrigatório estar logado

Retorna em sucesso:

- `200` com lista de negociações

### `GET /trocas/<int:pk>/`
Mostra o detalhe de uma negociação.

Autenticação:

- obrigatório estar logado e ser participante

Retorna em sucesso:

- `200` com detalhes, mensagens e status

### `POST /trocas/<int:pk>/mensagem/`
Envia mensagem para a negociação.

Autenticação:

- obrigatório estar logado e ser participante

Envia no POST:

- `content`

Retorna em sucesso:

- `302` para o detalhe da negociação

### `POST /trocas/<int:pk>/status/`
Atualiza o status da negociação.

Autenticação:

- obrigatório estar logado e ser participante

Envia no POST:

- `status`

Retorna em sucesso:

- `302` para o detalhe da negociação

### `GET /remover-carrinho/<int:pk>/`
Remove um item do carrinho.

Autenticação:

- obrigatório estar logado

Retorna em sucesso:

- `302` para `/carrinho/`

Erros comuns:

- `302` para login se não estiver autenticado

### `GET|POST /editar-perfil/`
Edita dados do usuário e do perfil PF/PJ.

Autenticação:

- obrigatório estar logado

Envia no POST:

- campos do `UserProfileForm`
- campos do perfil PF ou PJ exibidos na tela

Retorna em sucesso:

- `302` para a própria página com mensagem de sucesso

Erros comuns:

- `302` para login se não estiver autenticado
- `200` com erros de validação nos campos

### `GET|POST /alterar-senha/`
Troca a senha do usuário.

Autenticação:

- obrigatório estar logado

Envia no POST:

- `old_password`
- `new_password`
- `confirm_password`

Retorna em sucesso:

- `302` para `/editar-perfil/`

Erros comuns:

- senha atual incorreta
- nova senha fraca ou inválida
- `200` com formulário e mensagens de erro

### `GET /perfil/<str:username>/`
Exibe o perfil público do usuário.

Retorna em sucesso:

- `200` com dados públicos e anúncios ativos do usuário

Erros comuns:

- `404` se o usuário não existir

### `GET|POST /login/`
Login customizado da aplicação.

Envia no POST:

- `username`
- `password`
- `remember` opcional

Retorna em sucesso:

- `302` para `/`

Erros comuns:

- `200` com mensagem de credenciais inválidas

### `GET /logout/`
Logout do usuário.

Retorna em sucesso:

- `302` para `/`

### `GET|POST /register/`
Cadastro customizado da aplicação.

Envia no POST:

- `account_type`
- dados PF ou dados PJ conforme o tipo

Retorna em sucesso:

- `302` para `/login/`

Erros comuns:

- documento inválido
- senha inválida
- usuário já existente
- campos obrigatórios ausentes
- `200` com mensagens de erro

## 2. Endpoints Web Do Django Auth

Esses endpoints entram por `/accounts/` via `include('django.contrib.auth.urls')`.

### `GET|POST /accounts/login/`
Login padrão do Django.

Retorna em sucesso:

- `302` para a URL pós-login configurada

### `GET /accounts/logout/`
Logout padrão do Django.

### `GET|POST /accounts/password_change/`
Troca de senha do Django.

### `GET /accounts/password_change/done/`
Página de confirmação de troca de senha.

### `GET|POST /accounts/password_reset/`
Solicitação de redefinição de senha por e-mail.

### `GET /accounts/password_reset/done/`
Confirmação de envio do e-mail de redefinição.

### `GET|POST /accounts/reset/<uidb64>/<token>/`
Redefinição da senha com token.

### `GET /accounts/reset/done/`
Confirmação final de redefinição.

## 3. Endpoints De API

### `GET /api/listings/`
Lista anúncios ativos e inativos em JSON.

Autenticação:

- pública hoje

Retorna em sucesso:

- `200` com lista de anúncios serializada

Estrutura de resposta:

- `id`
- `seller`
- `seller_name`
- `category`
- `title`
- `description`
- `price`
- `listing_type`
- `condition`
- `status`
- `is_featured`
- `is_store_featured`
- `created_at`
- `images`

Erros comuns:

- `500` se houver falha interna

### `POST /api/register/`
Cadastro de usuário via API.

Autenticação:

- pública hoje

Envia no JSON:

- `username`
- `email`
- `password`
- `is_store`
- campos PF ou PJ correspondentes

Retorna em sucesso:

- `201` com `{"message": "Usuário criado com sucesso!"}`

Erros comuns:

- `400` com erros de validação do serializer

### `POST /api/token/`
Cria par JWT.

Autenticação:

- pública

Envia no JSON:

- credenciais do usuário configuradas pelo SimpleJWT

Retorna em sucesso:

- `200` com `access` e `refresh`

### `POST /api/token/refresh/`
Renova o token de acesso.

Autenticação:

- pública com `refresh` válido

Retorna em sucesso:

- `200` com novo `access`

## 4. Endpoints adicionais (módulos implementados)

> A especificação completa e canônica está em [openapi.yaml](openapi.yaml) (64 paths, 14 tags),
> navegável em [swagger.html](swagger.html). Resumo das rotas novas:

### Notificações
- `GET /notificacoes/` — página de notificações
- `GET /notificacoes/feed/` — feed JSON para o sino (polling)
- `POST /notificacoes/<id>/abrir/` — abre e marca como lida (redireciona à `url`)
- `POST /notificacoes/<id>/marcar-lida/` — marca uma como lida
- `POST /notificacoes/marcar-todas/` — marca todas como lidas

### Pedidos e entrega
- `POST /pedidos/<id>/enviar/` — vendedor confirma envio
- `POST /pedidos/<id>/receber/` — comprador confirma recebimento

### Endereços
- `GET/POST /enderecos/` — livro de endereços (listar/criar)
- `POST /enderecos/<id>/padrao/` — definir como padrão
- `POST /enderecos/<id>/excluir/` — remover

### Lojas
- `GET /lojas/` — hub de lojas (verificadas primeiro)
- `GET /minha-loja/` — catálogo/insights da própria loja (PJ)
- `GET/POST /loja/verificacao/` — solicitar selo de verificação

### Financeiro e segurança
- `GET /financeiro/` — Gastei × Ganhei × Saldo
- `GET /conta/seguranca/` — strikes e dicas de segurança
- `POST /anuncio/<id>/denunciar/` — denunciar anúncio

### Painel de moderação (somente staff)
- `GET /painel-moderacao/` — visão geral (verificações, denúncias, usuários, anúncios)
- gerenciar verificações de loja, denúncias, usuários (banir) e anúncios (remover com motivo + strike)

### Páginas institucionais
- `GET /sobre/`, `/contato/`, `/ajuda/`, `/privacidade/`, `/termos/`

## 5. Resumo Rápido De Respostas

- sucesso web: geralmente `200` ou `302`
- sucesso API: `200` ou `201`
- erro de login/autenticação: `302` para login ou `401/403` em endpoints de API futuros
- erro de validação: `200` com mensagem na tela ou `400` em API
- erro de objeto inexistente: `404`
