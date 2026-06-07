# Guia do Projeto Marketplace — Tech Hub

Este diretório documenta o marketplace de eletrônicos/TI **Tech Hub** (Django + PostgreSQL):
o que existe, como funciona e como publicar.

## Objetivo do sistema

Marketplace para produtos eletrônicos/TI com dois perfis principais:

- **Pessoa física**: compra, vende e propõe troca (produtos novos ou usados).
- **Loja/PJ**: vende apenas produtos novos, tem catálogo, banner e selo de verificação.

O pagamento é **simulado** (QR Code ilustrativo). O diferencial é o sistema completo de **troca com negociação**.

## Funcionalidades implementadas

- **Autenticação**: cadastro PF/PJ com validação (CPF/CNPJ, maioridade), login com "lembrar de mim" e **rate limiting** (anti força-bruta).
- **Anúncios**: CRUD, múltiplas imagens, galeria, comentários com respostas, **estoque** (esgotado/repor), busca e filtros.
- **Carrinho e checkout** de venda: endereço salvo, **frete simulado**, QR fictício, confirmação.
- **Pedidos**: vendedor confirma envio → comprador confirma recebimento → concluído.
- **Troca**: negociação por propostas/contrapropostas, escolha de **quem paga** o valor adicional, checkout em etapas (endereço → pagamento → confirmação).
- **Notificações** em tempo real (sino + feed), lidas/não lidas.
- **Endereços**: livro de endereços reutilizável no checkout.
- **Financeiro**: painel Gastei × Ganhei × Saldo.
- **Lojas**: hub (verificadas primeiro), vitrine/catálogo, solicitação de verificação por documento.
- **Moderação**: filtro de conteúdo proibido, **strikes** (3 → banimento), denúncia de anúncios, **painel de moderação** do admin (verificações, denúncias, usuários, anúncios).
- **Segurança da conta** visível ao usuário (strikes, dicas).
- **Páginas institucionais**: Sobre, Contato, Ajuda, Privacidade, Termos. Erros 404/500 customizados.

## Arquivos do guia

- [Entidades e relacionamentos](entidades.md) · [Modelo ER](modelo_entidade_relacionamento.md)
- [Fluxos do sistema](fluxos.md) · [Fluxo de troca](trade-flow.md) · [Pagamento e entrega](payment-delivery.md)
- [Regras de negócio e validações](regras-negocio.md)
- [Mapa de endpoints](endpoints.md) · API: [openapi.yaml](openapi.yaml) / [swagger.html](swagger.html)
- [Roadmap](roadmap.md) · [Segurança](security.md) · [Deploy](deploy.md)
- Apresentação: [Tech_Hub_Apresentacao.pptx](Tech_Hub_Apresentacao.pptx) (gerada por `gerar_apresentacao.py`)

## Como rodar (resumo)

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Para produção, veja [deploy.md](deploy.md). Para segurança/moderação, veja [security.md](security.md).
