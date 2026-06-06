# Roadmap de Evolução — TechHub

> Plano ativo a partir de 06/2026. Execução **uma fase por vez**, testando antes de avançar.
> Cada fase é um bloco coerente; a ordem respeita dependências entre features.

## Legenda
- ⬜ pendente · 🔄 em andamento · ✅ concluído

---

## FASE 0 — Correções rápidas (bugs ativos, sem mexer em model)
- ⬜ Snackbar/toast: fundo opaco, cor por tipo, posição abaixo do header, auto-hide ~8s (máx 10s), botão fechar. Padronizar em **todas** as telas (hoje várias usam `alert-container` inline em vez do partial de mensagens).
- ⬜ Login: botão do olho (mostrar senha) funcional.
- ⬜ Login: "lembrar de mim" estilizado e funcional (expiração de sessão).
- ⬜ Máscaras + espaçamento dos inputs de endereço (CEP, telefone, UF maiúscula) iguais aos do cadastro.
- ⬜ Inputs vazando do card na troca (box-sizing/overflow).
- ⬜ `remove_from_cart` via POST (hoje é GET).

## FASE 1 — Fluxo de venda completo ✅
Corrigiu o bug `pedidos/<id>/ 404` (hoje só o comprador acessava).
- ✅ Máquina de estados por item: `aguardando envio` → `enviado` (vendedor) → `recebido` (comprador). Pedido conclui quando todos os itens são recebidos (sai de "Pedidos", fica no Histórico).
- ✅ `order_detail`: comprador OU vendedor de algum item acessa (staff também).
- ✅ "Pedidos" com abas Minhas compras / Minhas vendas; vendedor confirma envio.
- ✅ Comprador confirma recebimento → conclui a venda automaticamente.
- ✅ Permissões nas rotas (confirm_shipment exige seller dono; confirm_receipt exige buyer).

> Decisão adotada: **vendedor confirma envio → comprador confirma recebimento**.
> Confirmação é **por item** porque um pedido pode ter vários vendedores.

## FASE 2 — Fluxo de troca redondo (diferencial do produto) ✅
- ✅ Negociação enxuta: só propostas/mensagens (entrega saiu daqui). Dica no campo de valor deixando claro que quem propõe o dinheiro é quem paga.
- ✅ Valor adicional explícito + **quem paga** (proposta aceita define o pagador); troca **sem** dinheiro suportada (pula pagamento).
- ✅ Só o pagador vê a etapa de pagamento; o outro vê "aguardando".
- ✅ Checkout da troca em **3 etapas** (stepper): (1) ambos cadastram endereço → (2) se há valor, só o pagador paga (QR) → (3) ambos confirmam entrega → troca concluída + anúncio `sold` + histórico.
- Testado end-to-end com e sem dinheiro.

## FASE 3 — Notificações (infra cross-cutting) ✅
- ✅ Model `Notification` (categoria, título, mensagem, url, ícone, lida) + admin.
- ✅ Sino no header com badge de não-lidas + dropdown das recentes (context processor).
- ✅ Página `/notificacoes/` com abas Todas/Não lidas, paginação, marcar todas como lidas, abrir (marca lida + leva ao destino).
- ✅ Disparos: venda (pedido recebido, item enviado, recebimento confirmado), troca (solicitação, proposta, contraproposta, aceite, recusa, cancelamento, pagamento, entrega confirmada, troca concluída, mensagem), comentário/resposta.
- Testado: venda, troca e comentário geram notificações corretas para o destinatário certo.

## FASE 4 — Endereços + Frete ✅
- ✅ Model `Address` + CRUD (`/enderecos/`): adicionar, editar, excluir, definir padrão; 1º vira padrão; excluir padrão promove outro. Link no menu Conta.
- ✅ Seletor de endereço salvo no checkout de **venda** e de **troca** (preenche o form via JS).
- ✅ Frete simulado por método (`shipping.py`): pickup/a combinar grátis, vendedor R$19,90, Correios R$29,90.
- ✅ Frete entra no `Order.total_amount` e em `Delivery.shipping_cost`; checkout mostra Subtotal/Frete/Total ao vivo; order_detail mostra a quebra.
- Testado: CRUD, padrão/exclusão, total com frete, picker no checkout.

## FASE 5 — Estoque ✅
- ✅ `Listing.stock` + `is_available`/`is_sold_out`. Disponível = active e stock>0.
- ✅ Decremento na compra (`process_buy_checkout`) e na troca concluída; ao zerar vira `SOLD`/esgotado.
- ✅ Campo estoque no criar/editar com botões +1/+5; repor estoque reativa anúncio esgotado (SOLD→active).
- ✅ Guardas: add_to_cart bloqueia esgotado; listing_detail mostra estoque e desabilita compra; my_listings mostra estoque + selo "Esgotado".
- Testado: decremento, esgotamento, bloqueio, reposição.
- ⚠️ Nota: anúncio com pedido em andamento fica travado para edição (regra existente). Revisar para lojas multi-unidade na Fase 6.

## FASE 6 — Diferencial das lojas ✅
- ✅ Hub `/lojas/` (verificadas primeiro), com busca e contagem de anúncios. Link "Lojas" no nav.
- ✅ Vitrine da loja (user_profile): selo verificada + **catálogo** mostrando produtos ativos e esgotados (overlay "Esgotado"); loja repõe estoque em vez de recriar anúncio.
- ✅ Solicitação de verificação (`StoreVerificationRequest`): upload de documento + status, página `/loja/verificacao/`.
- ✅ Admin aprova/recusa por ação em lote → marca `verified` e **notifica** a loja.
- Testado: ordem do hub, catálogo com esgotado, criação da solicitação, aprovar/recusar com notificação.

> Catálogo interpretado como os anúncios da loja persistentes (com estoque/esgotado), não um model separado.

## FASE 7 — Financeiro / Pagamentos ✅
- ✅ Página `/financeiro/`: cards Gastei × Ganhei × Saldo.
- ✅ Agrega compras pagas (saída, com frete), vendas recebidas (entrada), e trocas com dinheiro (saída p/ pagador, entrada p/ quem recebe).
- ✅ Abas Tudo/Entradas/Saídas, paginação, cada item referencia o pedido/anúncio com link.
- Testado: gastei R$229,90 (compra+frete), ganhei R$120,00 (venda).

## FASE 8 — Footer, páginas institucionais e pré-deploy ✅
- ✅ Footer reorganizado com links funcionais (Início, Lojas, Anunciar, Ajuda, Contato, Sobre, Privacidade, Termos).
- ✅ Páginas: Sobre (projeto + autores com LinkedIn — editar nomes/links), Contato (form simulado), Ajuda (FAQ), Privacidade, Termos.
- ✅ Páginas de erro 404 (estende base) e 500 (standalone) customizadas.
- ✅ Settings já env-driven com hardening; `docs/deploy.md` com checklist. `check --deploy` sem issues com DEBUG=False + SECRET_KEY + ALLOWED_HOSTS.

> Editar os nomes e links de LinkedIn dos integrantes em `templates/pages/about.html`.

---

## PÓS-ROADMAP — Segurança & Moderação ✅
- ✅ Filtro de termos proibidos (`moderation.py`) em anúncios, comentários, propostas e mensagens.
- ✅ Validação de upload de imagem (tipo + tamanho ≤5MB) em anúncio/perfil/banner/proposta.
- ✅ Denúncia de anúncio (usuário) + fila no admin.
- ✅ Admin: excluir anúncio, banir vendedor (desativa + remove anúncios), banir/reativar usuário.
- ✅ Checklist completo em `docs/security.md`.

## Ideias opcionais (fora do caminho crítico)
- Favoritos/wishlist.
- Filtro de busca por loja.
- Rate limiting de login (django-axes).
- Moderação de imagem por IA (visão computacional).
