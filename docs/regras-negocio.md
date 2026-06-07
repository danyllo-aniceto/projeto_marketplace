# Regras De Negócio E Validações

## Autenticação

- o sistema usa um `User` customizado
- login depende de usuário e senha
- usuários precisam estar autenticados para comprar, comentar e anunciar

## Cadastro de PF

Campos principais:

- nome
- sobrenome
- usuário
- e-mail
- senha
- CPF
- data de nascimento
- telefone
- CEP
- endereço

Validações:

- CPF precisa ser real, não só formatado
- senha precisa obedecer às regras do Django
- CPF deve ser único

## Cadastro de PJ

Campos principais:

- usuário
- e-mail
- senha
- CNPJ
- razão social
- nome fantasia
- inscrição estadual
- responsável legal
- CPF do responsável
- telefone
- CEP comercial
- endereço comercial

Validações:

- CNPJ precisa ser real
- CPF do responsável precisa ser real
- CNPJ precisa ser único
- senha precisa obedecer às regras do Django

## Regras de anúncio

- anúncio só pode ser criado por usuário autenticado
- anúncio pertence ao vendedor que o criou
- usuário comum pode vender, trocar ou ambos
- loja só pode vender
- loja só pode anunciar produto novo
- preço precisa ser maior que zero
- anúncio pode ter imagem principal e outras imagens adicionais

## Regras de comentários

- só usuário autenticado pode comentar
- comentário pertence ao anúncio e ao autor
- comentários não devem existir sem anúncio

## Regras de carrinho

- carrinho é único por usuário
- um mesmo anúncio não deve entrar duplicado no carrinho
- carrinho precisa separar futuramente itens de venda e itens de troca

## Regras de loja verificada

- o campo `verified` indica selo de confiança
- o selo é controlado pelo admin no painel de moderação
- a loja **não** se autoaprova: envia `StoreVerificationRequest` com documento e aguarda análise
- lojas verificadas aparecem primeiro no hub de lojas

## Regras de estoque

- todo anúncio de venda tem `stock` (quantidade)
- `stock = 0` marca o anúncio como **esgotado** (não pode ser comprado)
- "repor estoque" reativa o anúncio; vender o último item esgota automaticamente
- a compra reduz o estoque; concluir o pedido confirma a baixa

## Regras de pedido e entrega

- após a compra, o vendedor confirma o **envio** (`shipped`)
- depois o comprador confirma o **recebimento** (`received`)
- quando todos os itens são recebidos, o pedido é **concluído** e entra no financeiro
- o frete é simulado e exibido no checkout; endereço vem do livro de endereços

## Regras de moderação e segurança

- **conteúdo proibido** (ofensa, ódio, itens ilegais) é bloqueado automaticamente no cadastro de anúncios, comentários e perfil — comparação normalizada (sem acento, por palavra)
- conteúdo proibido removido ou anúncio derrubado pela moderação gera **strike**
- ao atingir **3 strikes**, a conta é suspensa automaticamente (`is_active=False`) e os anúncios são removidos
- usuários podem **denunciar** anúncios (`ListingReport`); a fila vai para o painel do admin
- **rate limiting** no login: após 5 tentativas erradas, bloqueio temporário (anti força-bruta)
- o usuário vê suas advertências e dicas em "Segurança da conta"

## O que depende de serviço externo / IA

- **moderação de imagens** (conteúdo impróprio em fotos): exige serviço de visão computacional (ex.: AWS Rekognition, Google Vision, OpenAI) — não é viável só com código local
- **detecção de anúncio fora do tema** (não-eletrônico): por palavras-chave gera falsos positivos (ex.: "carregador para carro"); o ideal seria classificação por IA/embeddings
- pagamento real (hoje é simulado com QR fictício)

## O que ainda poderia evoluir

- chat persistente para negociação de troca
- filtros avançados de busca
- integração de pagamento real (gateway)
