-- =============================================================================
-- SEED DE DADOS — Marketplace (PostgreSQL / Render)
-- =============================================================================
-- Projeto Django (app: marketplace_app). Popula o banco com um conjunto
-- coerente de dados de demonstração: usuários PF e PJ, perfis, anúncios,
-- carrinhos, pedidos, pagamentos, entregas, trocas, mensagens, endereços,
-- notificações, denúncias e pedidos de verificação de loja.
--
-- SENHA de TODOS os usuários: senha123
--
-- Como rodar:
--   psql "<DATABASE_URL_DO_RENDER>" -f seed_render.sql
--   (ou cole o conteúdo no console SQL do Render / pgAdmin)
--
-- Observações:
--  * Use APÓS `python manage.py migrate` (as tabelas e as categorias padrão
--    já precisam existir).
--  * Os IDs explícitos começam em faixas altas (1000+, 2000+, ...) para não
--    colidir com dados existentes. No fim, as sequences são reajustadas.
--  * Tudo roda dentro de uma transação: ou entra tudo, ou nada.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 0) Categorias (idempotente — já criadas por migration, mas garantimos aqui)
-- -----------------------------------------------------------------------------
INSERT INTO marketplace_app_category (name, slug) VALUES
    ('Dispositivos pessoais', 'dispositivos-pessoais'),
    ('Informática',           'informatica'),
    ('Games',                 'games'),
    ('TV e audio',            'tv-e-audio'),
    ('Foto e video',          'foto-e-video'),
    ('Todos',                 'todos')
ON CONFLICT (slug) DO NOTHING;

-- =============================================================================
-- 1) USUÁRIOS
-- Hash PBKDF2 abaixo = senha "senha123"
-- =============================================================================
INSERT INTO marketplace_app_user
    (id, password, last_login, is_superuser, username, first_name, last_name,
     email, is_staff, is_active, date_joined, is_store, profile_picture, strikes)
VALUES
-- Obs.: o usuario 'admin' NAO entra aqui — ele e criado pelo comando createadmin
-- (build.sh) a partir das variaveis DJANGO_SUPERUSER_*. Evita colisao de username.

-- Pessoas Físicas (PF) ------------------------------------------------------
(1001, 'pbkdf2_sha256$600000$seedsalt12345$RXVvc3yhRnlN3kit1cXh6eHW+mNbVMl0Kq7NZRfO46Y=',
       NULL, false, 'ana.souza',     'Ana',      'Souza',     'ana.souza@email.com',     false, true, '2026-03-05 10:15:00-03', false, NULL, 0),
(1002, 'pbkdf2_sha256$600000$seedsalt12345$RXVvc3yhRnlN3kit1cXh6eHW+mNbVMl0Kq7NZRfO46Y=',
       NULL, false, 'bruno.lima',    'Bruno',    'Lima',      'bruno.lima@email.com',    false, true, '2026-03-06 11:20:00-03', false, NULL, 0),
(1003, 'pbkdf2_sha256$600000$seedsalt12345$RXVvc3yhRnlN3kit1cXh6eHW+mNbVMl0Kq7NZRfO46Y=',
       NULL, false, 'carla.dias',    'Carla',    'Dias',      'carla.dias@email.com',    false, true, '2026-03-07 14:00:00-03', false, NULL, 0),
(1004, 'pbkdf2_sha256$600000$seedsalt12345$RXVvc3yhRnlN3kit1cXh6eHW+mNbVMl0Kq7NZRfO46Y=',
       NULL, false, 'diego.alves',   'Diego',    'Alves',     'diego.alves@email.com',   false, true, '2026-03-08 16:45:00-03', false, NULL, 0),
(1005, 'pbkdf2_sha256$600000$seedsalt12345$RXVvc3yhRnlN3kit1cXh6eHW+mNbVMl0Kq7NZRfO46Y=',
       NULL, false, 'eduarda.melo',  'Eduarda',  'Melo',      'eduarda.melo@email.com',  false, true, '2026-03-09 08:30:00-03', false, NULL, 1),
(1006, 'pbkdf2_sha256$600000$seedsalt12345$RXVvc3yhRnlN3kit1cXh6eHW+mNbVMl0Kq7NZRfO46Y=',
       NULL, false, 'felipe.rocha',  'Felipe',   'Rocha',     'felipe.rocha@email.com',  false, true, '2026-03-10 19:10:00-03', false, NULL, 0),
(1007, 'pbkdf2_sha256$600000$seedsalt12345$RXVvc3yhRnlN3kit1cXh6eHW+mNbVMl0Kq7NZRfO46Y=',
       NULL, false, 'gabriela.nunes','Gabriela', 'Nunes',     'gabriela.nunes@email.com',false, true, '2026-03-11 12:05:00-03', false, NULL, 0),
(1008, 'pbkdf2_sha256$600000$seedsalt12345$RXVvc3yhRnlN3kit1cXh6eHW+mNbVMl0Kq7NZRfO46Y=',
       NULL, false, 'henrique.cruz', 'Henrique', 'Cruz',      'henrique.cruz@email.com', false, true, '2026-03-12 17:40:00-03', false, NULL, 0),

-- Pessoas Jurídicas (PJ / Lojas) -------------------------------------------
(1020, 'pbkdf2_sha256$600000$seedsalt12345$RXVvc3yhRnlN3kit1cXh6eHW+mNbVMl0Kq7NZRfO46Y=',
       NULL, false, 'techstore',  'Tech',    'Store',  'contato@techstore.com',  false, true, '2026-02-20 09:00:00-03', true, NULL, 0),
(1021, 'pbkdf2_sha256$600000$seedsalt12345$RXVvc3yhRnlN3kit1cXh6eHW+mNbVMl0Kq7NZRfO46Y=',
       NULL, false, 'gameworld',  'Game',    'World',  'contato@gameworld.com',  false, true, '2026-02-21 09:00:00-03', true, NULL, 0),
(1022, 'pbkdf2_sha256$600000$seedsalt12345$RXVvc3yhRnlN3kit1cXh6eHW+mNbVMl0Kq7NZRfO46Y=',
       NULL, false, 'fotopro',    'Foto',    'Pro',    'contato@fotopro.com',    false, true, '2026-02-22 09:00:00-03', true, NULL, 0),
(1023, 'pbkdf2_sha256$600000$seedsalt12345$RXVvc3yhRnlN3kit1cXh6eHW+mNbVMl0Kq7NZRfO46Y=',
       NULL, false, 'audiomax',   'Audio',   'Max',    'contato@audiomax.com',   false, true, '2026-02-23 09:00:00-03', true, NULL, 0),
(1024, 'pbkdf2_sha256$600000$seedsalt12345$RXVvc3yhRnlN3kit1cXh6eHW+mNbVMl0Kq7NZRfO46Y=',
       NULL, false, 'infomega',   'Info',    'Mega',   'contato@infomega.com',   false, true, '2026-02-24 09:00:00-03', true, NULL, 0),
(1025, 'pbkdf2_sha256$600000$seedsalt12345$RXVvc3yhRnlN3kit1cXh6eHW+mNbVMl0Kq7NZRfO46Y=',
       NULL, false, 'mobilezone', 'Mobile',  'Zone',   'contato@mobilezone.com', false, true, '2026-02-25 09:00:00-03', true, NULL, 0);

-- =============================================================================
-- 2) PERFIS PF (CommonProfile)
-- =============================================================================
INSERT INTO marketplace_app_commonprofile
    (id, cpf, birth_date, phone, cep, address, user_id)
VALUES
(1, '11122233344', '1995-04-12', '11988880001', '01310100', 'Av. Paulista, 1000 - São Paulo/SP', 1001),
(2, '22233344455', '1990-08-23', '21988880002', '20040002', 'Rua da Assembleia, 50 - Rio de Janeiro/RJ', 1002),
(3, '33344455566', '1998-12-01', '31988880003', '30140071', 'Av. Afonso Pena, 700 - Belo Horizonte/MG', 1003),
(4, '44455566677', '1987-06-30', '41988880004', '80010000', 'Rua XV de Novembro, 200 - Curitiba/PR', 1004),
(5, '55566677788', '2000-02-14', '51988880005', '90010150', 'Av. Borges de Medeiros, 300 - Porto Alegre/RS', 1005),
(6, '66677788899', '1993-09-05', '71988880006', '40020000', 'Av. Sete de Setembro, 400 - Salvador/BA', 1006),
(7, '77788899900', '1996-11-19', '81988880007', '50030230', 'Av. Conde da Boa Vista, 800 - Recife/PE', 1007),
(8, '88899900011', '1985-01-27', '60110110', '60110110', 'Av. Beira Mar, 900 - Fortaleza/CE', 1008);

-- =============================================================================
-- 3) PERFIS PJ (StoreProfile)
-- =============================================================================
INSERT INTO marketplace_app_storeprofile
    (id, cnpj, razao_social, fantasy_name, state_registration, responsible_name,
     responsible_cpf, phone, email, commercial_cep, commercial_address,
     verified, banner, description, user_id)
VALUES
(1, '11222333000181', 'Tech Store Comércio de Eletrônicos LTDA', 'TechStore', '123456789', 'Roberto Tech',
    '10120230340', '1133330001', 'contato@techstore.com', '01310100', 'Av. Paulista, 1500 - São Paulo/SP',
    true,  NULL, 'Loja especializada em notebooks, periféricos e componentes de informática.', 1020),
(2, '22333444000172', 'Game World Entretenimento LTDA', 'GameWorld', '234567890', 'Marina Games',
    '20230340450', '2133330002', 'contato@gameworld.com', '20040002', 'Rua do Ouvidor, 120 - Rio de Janeiro/RJ',
    false, NULL, 'Consoles, jogos e acessórios gamer com garantia.', 1021),
(3, '33444555000163', 'Foto Pro Equipamentos LTDA', 'FotoPro', '345678901', 'Paulo Foto',
    '30340450560', '3133330003', 'contato@fotopro.com', '30140071', 'Av. do Contorno, 2000 - Belo Horizonte/MG',
    true,  NULL, 'Câmeras, lentes e equipamentos profissionais de fotografia e vídeo.', 1022),
(4, '44555666000154', 'Audio Max Som e Imagem LTDA', 'AudioMax', '456789012', 'Sandra Audio',
    '40450560670', '4133330004', 'contato@audiomax.com', '80010000', 'Rua das Flores, 300 - Curitiba/PR',
    false, NULL, 'Home theater, soundbars e fones de alta fidelidade.', 1023),
(5, '55666777000145', 'Info Mega Tecnologia LTDA', 'InfoMega', '567890123', 'Carlos Mega',
    '50560670780', '5133330005', 'contato@infomega.com', '90010150', 'Av. Ipiranga, 1800 - Porto Alegre/RS',
    true,  NULL, 'Tudo em informática: monitores, teclados, mouses e hardware.', 1024),
(6, '66777888000136', 'Mobile Zone Celulares LTDA', 'MobileZone', '678901234', 'Juliana Mobile',
    '60670780890', '7133330006', 'contato@mobilezone.com', '40020000', 'Av. Tancredo Neves, 500 - Salvador/BA',
    true,  NULL, 'Smartphones, smartwatches e acessórios das melhores marcas.', 1025);

-- =============================================================================
-- 4) ANÚNCIOS (Listing)
--  Lojas (PJ): apenas 'new' e tipo venda/ambos (nunca troca).
--  PF: podem vender/trocar produtos usados ou novos.
-- =============================================================================
INSERT INTO marketplace_app_listing
    (id, title, description, trade_suggestions, price, listing_type, condition,
     status, stock, is_featured, is_store_featured, created_at, category_id, seller_id)
VALUES
-- ---- Lojas (venda, novo) --------------------------------------------------
(2001, 'Notebook Dell Inspiron 15 i7 16GB', 'Notebook Dell Inspiron 15, Intel Core i7, 16GB RAM, SSD 512GB. Lacrado, nota fiscal e garantia.', '', 4200.00, 'sale', 'new', 'active', 8,  true,  true,  '2026-04-01 10:00:00-03', (SELECT id FROM marketplace_app_category WHERE slug='informatica'), 1020),
(2002, 'SSD NVMe 1TB Kingston', 'SSD NVMe M.2 1TB, leitura até 3500MB/s. Novo, lacrado.', '', 480.00, 'sale', 'new', 'active', 25, false, false, '2026-04-02 11:00:00-03', (SELECT id FROM marketplace_app_category WHERE slug='informatica'), 1020),
(2003, 'Teclado Mecânico RGB Switch Blue', 'Teclado mecânico gamer com iluminação RGB e switches azuis. ABNT2.', '', 350.00, 'sale', 'new', 'active', 15, false, true,  '2026-04-03 09:30:00-03', (SELECT id FROM marketplace_app_category WHERE slug='informatica'), 1024),
(2004, 'Monitor 27" 165Hz IPS Full HD', 'Monitor gamer 27 polegadas, 165Hz, painel IPS, 1ms. Ideal para jogos.', '', 1500.00, 'sale', 'new', 'active', 6,  true,  false, '2026-04-04 14:20:00-03', (SELECT id FROM marketplace_app_category WHERE slug='informatica'), 1024),
(2005, 'PlayStation 5 Slim 1TB', 'Console PS5 Slim 1TB, edição com leitor de disco. Lacrado com nota fiscal.', '', 3800.00, 'sale', 'new', 'active', 10, true,  true,  '2026-04-05 16:00:00-03', (SELECT id FROM marketplace_app_category WHERE slug='games'), 1021),
(2006, 'Controle Xbox Series Wireless', 'Controle sem fio Xbox Series X/S, cor Carbon Black. Novo.', '', 420.00, 'sale', 'new', 'active', 30, false, false, '2026-04-06 13:10:00-03', (SELECT id FROM marketplace_app_category WHERE slug='games'), 1021),
(2007, 'Câmera Canon EOS R50 + Lente Kit', 'Câmera mirrorless Canon EOS R50 com lente 18-45mm. Nova, garantia Canon Brasil.', '', 6500.00, 'sale', 'new', 'active', 4,  true,  true,  '2026-04-07 10:45:00-03', (SELECT id FROM marketplace_app_category WHERE slug='foto-e-video'), 1022),
(2008, 'Tripé Profissional de Alumínio 1,7m', 'Tripé profissional para câmera, altura máxima 1,7m, cabeça fluida.', '', 280.00, 'sale', 'new', 'active', 18, false, false, '2026-04-08 15:30:00-03', (SELECT id FROM marketplace_app_category WHERE slug='foto-e-video'), 1022),
(2009, 'Soundbar 2.1 200W com Subwoofer', 'Soundbar 2.1 canais, 200W RMS, subwoofer sem fio, Bluetooth e HDMI ARC.', '', 1200.00, 'sale', 'new', 'active', 7,  false, true,  '2026-04-09 11:50:00-03', (SELECT id FROM marketplace_app_category WHERE slug='tv-e-audio'), 1023),
(2010, 'Fone Bluetooth com Cancelamento de Ruído', 'Headphone over-ear, ANC, até 30h de bateria. Novo, lacrado.', '', 350.00, 'sale', 'new', 'active', 22, false, false, '2026-04-10 09:00:00-03', (SELECT id FROM marketplace_app_category WHERE slug='tv-e-audio'), 1023),
(2011, 'iPhone 14 128GB', 'iPhone 14 128GB, novo e lacrado, garantia Apple. Cor meia-noite.', '', 5200.00, 'sale', 'new', 'active', 12, true,  true,  '2026-04-11 17:20:00-03', (SELECT id FROM marketplace_app_category WHERE slug='dispositivos-pessoais'), 1025),
(2012, 'Smartwatch Galaxy Watch6 44mm', 'Smartwatch Samsung Galaxy Watch6, GPS, monitor cardíaco. Novo.', '', 1100.00, 'sale', 'new', 'active', 14, false, false, '2026-04-12 10:30:00-03', (SELECT id FROM marketplace_app_category WHERE slug='dispositivos-pessoais'), 1025),

-- ---- PF (usado, venda/troca/ambos) ---------------------------------------
(2013, 'iPhone 11 64GB Usado', 'iPhone 11 64GB, bateria em 87%, sem marcas de uso. Acompanha caixa.', '', 2100.00, 'sale', 'used', 'active', 1, false, false, '2026-04-15 12:00:00-03', (SELECT id FROM marketplace_app_category WHERE slug='dispositivos-pessoais'), 1001),
(2014, 'Nintendo Switch Modelo OLED', 'Switch OLED branco, pouco uso, com 2 jogos. Aceito venda ou troca.', 'Aceito troca por PS4 ou Xbox One + volta.', 1600.00, 'both', 'used', 'active', 1, false, false, '2026-04-16 13:30:00-03', (SELECT id FROM marketplace_app_category WHERE slug='games'), 1002),
(2015, 'Notebook Lenovo IdeaPad (somente troca)', 'Notebook Lenovo IdeaPad i5, 8GB, SSD 256GB. Funcionando perfeitamente.', 'Troco por desktop gamer ou monitor ultrawide.', NULL, 'trade', 'used', 'active', 1, false, false, '2026-04-17 09:15:00-03', (SELECT id FROM marketplace_app_category WHERE slug='informatica'), 1003),
(2016, 'Lente Canon 50mm f/1.8 STM', 'Lente Canon 50mm f/1.8, ótima para retratos. Sem fungos, vidro impecável.', '', 600.00, 'sale', 'used', 'active', 1, false, false, '2026-04-18 14:40:00-03', (SELECT id FROM marketplace_app_category WHERE slug='foto-e-video'), 1004),
(2017, 'Smart TV 50" 4K Usada', 'Smart TV 50 polegadas 4K, 2 anos de uso, controle e suporte inclusos.', '', 1400.00, 'sale', 'used', 'active', 1, false, false, '2026-04-19 16:10:00-03', (SELECT id FROM marketplace_app_category WHERE slug='tv-e-audio'), 1005),
(2018, 'Xbox Series S 512GB (troca)', 'Xbox Series S, estado de novo, na caixa. Somente troca.', 'Troco por Nintendo Switch ou celular intermediário.', NULL, 'trade', 'used', 'active', 1, false, false, '2026-04-20 11:25:00-03', (SELECT id FROM marketplace_app_category WHERE slug='games'), 1006),
(2019, 'Tablet Samsung Galaxy Tab A8', 'Tablet Samsung Tab A8 64GB, com capa e película. Vendo ou troco.', 'Aceito troca por fone premium ou smartwatch.', 900.00, 'both', 'used', 'active', 1, false, false, '2026-04-21 10:05:00-03', (SELECT id FROM marketplace_app_category WHERE slug='dispositivos-pessoais'), 1007),
(2020, 'Placa de Vídeo RTX 3060 12GB', 'Placa de vídeo RTX 3060 12GB, usada para jogos casuais, nunca em mineração.', '', 1800.00, 'sale', 'used', 'active', 1, false, false, '2026-04-22 15:50:00-03', (SELECT id FROM marketplace_app_category WHERE slug='informatica'), 1008),
(2021, 'Lote de Jogos PS4 (5 jogos)', 'Lote com 5 jogos de PS4 originais, mídia física, todos funcionando.', '', 250.00, 'sale', 'used', 'active', 1, false, false, '2026-04-23 09:40:00-03', (SELECT id FROM marketplace_app_category WHERE slug='games'), 1001),
(2022, 'GoPro Hero 10 Black', 'GoPro Hero 10 com 2 baterias e bastão. Pouco uso, tudo funcionando.', 'Aceito troca por drone com câmera.', 1300.00, 'both', 'used', 'active', 1, false, false, '2026-04-24 13:00:00-03', (SELECT id FROM marketplace_app_category WHERE slug='foto-e-video'), 1002),
(2023, 'Kindle Paperwhite 11ª Geração', 'Kindle Paperwhite à prova d''água, com luz ajustável. Anúncio pausado temporariamente.', '', 350.00, 'sale', 'used', 'paused', 1, false, false, '2026-04-25 17:30:00-03', (SELECT id FROM marketplace_app_category WHERE slug='dispositivos-pessoais'), 1004),
(2024, 'Cadeira Gamer (VENDIDA)', 'Cadeira gamer reclinável, já vendida — mantida no histórico.', '', 700.00, 'sale', 'used', 'sold', 0, false, false, '2026-04-10 18:00:00-03', (SELECT id FROM marketplace_app_category WHERE slug='informatica'), 1005);

-- =============================================================================
-- 5) IMAGENS DE ANÚNCIO (ListingImage) — caminhos de exemplo
-- =============================================================================
INSERT INTO marketplace_app_listingimage (id, image, listing_id) VALUES
(1, 'listings/notebook-dell.jpg',   2001),
(2, 'listings/ssd-kingston.jpg',    2002),
(3, 'listings/ps5-slim.jpg',        2005),
(4, 'listings/canon-r50.jpg',       2007),
(5, 'listings/iphone14.jpg',        2011),
(6, 'listings/iphone11-usado.jpg',  2013),
(7, 'listings/switch-oled.jpg',     2014),
(8, 'listings/rtx3060.jpg',         2020);

-- =============================================================================
-- 6) COMENTÁRIOS (Comment) — inclui respostas (parent_id)
-- =============================================================================
INSERT INTO marketplace_app_comment (id, content, created_at, listing_id, user_id, parent_id) VALUES
(1, 'Esse notebook acompanha mochila?', '2026-04-26 10:00:00-03', 2001, 1002, NULL),
(2, 'Olá! Não acompanha mochila, apenas o carregador original.', '2026-04-26 10:30:00-03', 2001, 1020, 1),
(3, 'Tem desconto para pagamento à vista no PIX?', '2026-04-26 11:00:00-03', 2005, 1003, NULL),
(4, 'Sim! 5% de desconto no PIX. :)', '2026-04-26 11:15:00-03', 2005, 1021, 3),
(5, 'A bateria do iPhone 11 está com quantos %?', '2026-04-27 09:20:00-03', 2013, 1004, NULL),
(6, 'Está com 87% de saúde de bateria.', '2026-04-27 09:45:00-03', 2013, 1001, 5),
(7, 'Aceita troca por um monitor ultrawide de 34"?', '2026-04-27 14:00:00-03', 2015, 1008, NULL),
(8, 'Aceito sim, dependendo do modelo. Pode me chamar no chat.', '2026-04-27 14:20:00-03', 2015, 1003, 7),
(9, 'A lente tem fungos ou riscos?', '2026-04-28 16:30:00-03', 2016, 1007, NULL),
(10,'Sem fungos e sem riscos, vidro impecável!', '2026-04-28 16:50:00-03', 2016, 1004, 9),
(11,'Esse Switch ainda está disponível?', '2026-04-29 10:10:00-03', 2014, 1006, NULL),
(12,'A RTX 3060 foi usada em mineração?', '2026-04-29 13:40:00-03', 2020, 1002, NULL);

-- =============================================================================
-- 7) CARRINHOS (Cart) e ITENS (CartItem)
-- =============================================================================
INSERT INTO marketplace_app_cart (id, created_at, user_id) VALUES
(1, '2026-05-01 09:00:00-03', 1001),
(2, '2026-05-01 10:00:00-03', 1002),
(3, '2026-05-01 11:00:00-03', 1007);

INSERT INTO marketplace_app_cartitem (id, desired_action, added_at, cart_id, listing_id) VALUES
(1, 'buy', '2026-05-01 09:05:00-03', 1, 2004),  -- Ana quer Monitor (InfoMega)
(2, 'buy', '2026-05-01 09:10:00-03', 1, 2005),  -- Ana quer PS5 (GameWorld)
(3, 'buy', '2026-05-01 10:05:00-03', 2, 2007),  -- Bruno quer Canon (FotoPro)
(4, 'buy', '2026-05-01 11:05:00-03', 3, 2013);  -- Gabriela quer iPhone 11 (Ana)

-- =============================================================================
-- 8) PEDIDOS (Order), ITENS, PAGAMENTOS e ENTREGAS
-- =============================================================================
INSERT INTO marketplace_app_order
    (id, payment_method, delivery_method, status, total_amount, notes, created_at, updated_at, buyer_id)
VALUES
(3001, 'pix',         'platform_shipping', 'paid',            480.00,  '', '2026-05-02 10:00:00-03', '2026-05-02 10:05:00-03', 1001),
(3002, 'credit_card', 'seller_shipping',   'pending_payment', 420.00,  'Favor enviar com nota fiscal.', '2026-05-03 14:00:00-03', '2026-05-03 14:00:00-03', 1002),
(3003, 'pix',         'platform_shipping', 'paid',            1450.00, '', '2026-05-04 16:30:00-03', '2026-05-04 16:35:00-03', 1003),
(3004, 'debit_card',  'pickup',            'completed',       280.00,  '', '2026-05-05 09:15:00-03', '2026-05-06 18:00:00-03', 1004);

INSERT INTO marketplace_app_orderitem
    (id, title_snapshot, unit_price_snapshot, quantity, status, shipped_at, received_at, listing_id, order_id, seller_id)
VALUES
(1, 'SSD NVMe 1TB Kingston',                480.00,  1, 'shipped',  '2026-05-02 15:00:00-03', NULL, 2002, 3001, 1020),
(2, 'Controle Xbox Series Wireless',        420.00,  1, 'pending_shipment', NULL, NULL,            2006, 3002, 1021),
(3, 'Smartwatch Galaxy Watch6 44mm',        1100.00, 1, 'shipped',  '2026-05-04 18:00:00-03', NULL, 2012, 3003, 1025),
(4, 'Fone Bluetooth com Cancelamento de Ruído', 350.00, 1, 'shipped', '2026-05-04 18:00:00-03', NULL, 2010, 3003, 1023),
(5, 'Tripé Profissional de Alumínio 1,7m',  280.00,  1, 'received', '2026-05-05 10:00:00-03', '2026-05-06 17:30:00-03', 2008, 3004, 1022);

INSERT INTO marketplace_app_paymenttransaction
    (id, gateway, status, external_reference, preference_id, checkout_url, amount, payload, created_at, updated_at, order_id)
VALUES
(1, 'mercado_pago', 'approved',   'REF-3001', 'PREF-3001', 'https://mp.example.com/checkout/3001', 480.00,  '{}', '2026-05-02 10:01:00-03', '2026-05-02 10:05:00-03', 3001),
(2, 'mercado_pago', 'pending',    'REF-3002', 'PREF-3002', 'https://mp.example.com/checkout/3002', 420.00,  '{}', '2026-05-03 14:01:00-03', '2026-05-03 14:01:00-03', 3002),
(3, 'mercado_pago', 'approved',   'REF-3003', 'PREF-3003', 'https://mp.example.com/checkout/3003', 1450.00, '{}', '2026-05-04 16:31:00-03', '2026-05-04 16:35:00-03', 3003),
(4, 'mercado_pago', 'approved',   'REF-3004', 'PREF-3004', 'https://mp.example.com/checkout/3004', 280.00,  '{}', '2026-05-05 09:16:00-03', '2026-05-05 09:20:00-03', 3004);

INSERT INTO marketplace_app_delivery
    (id, method, recipient_name, recipient_phone, postal_code, street, number, complement,
     neighborhood, city, state, shipping_cost, carrier_name, tracking_code, status,
     estimated_delivery_date, delivered_at, notes, created_at, updated_at, order_id)
VALUES
(1, 'platform_shipping', 'Ana Souza',   '11988880001', '01310100', 'Av. Paulista',        '1000', 'Apto 52', 'Bela Vista',  'São Paulo',     'SP', 25.00, 'Correios',  'BR123456789BR', 'in_transit', '2026-05-08', NULL,                     '', '2026-05-02 10:10:00-03', '2026-05-02 15:05:00-03', 3001),
(2, 'seller_shipping',   'Bruno Lima',  '21988880002', '20040002', 'Rua da Assembleia',   '50',   '',        'Centro',      'Rio de Janeiro','RJ', 30.00, '',          '',              'pending',    NULL,         NULL,                     '', '2026-05-03 14:05:00-03', '2026-05-03 14:05:00-03', 3002),
(3, 'platform_shipping', 'Carla Dias',  '31988880003', '30140071', 'Av. Afonso Pena',     '700',  'Casa',    'Funcionários','Belo Horizonte','MG', 28.00, 'Correios',  'BR987654321BR', 'in_transit', '2026-05-09', NULL,                     '', '2026-05-04 16:40:00-03', '2026-05-04 18:05:00-03', 3003),
(4, 'pickup',            'Diego Alves', '41988880004', '80010000', 'Rua XV de Novembro',  '200',  '',        'Centro',      'Curitiba',      'PR', 0.00,  '',          '',              'delivered',  '2026-05-06', '2026-05-06 17:30:00-03', 'Retirada na loja física.', '2026-05-05 09:20:00-03', '2026-05-06 18:00:00-03', 3004);

-- =============================================================================
-- 9) MENSAGENS DIRETAS (Message)
-- =============================================================================
INSERT INTO marketplace_app_message (id, content, created_at, listing_id, receiver_id, sender_id) VALUES
(1, 'Olá, o notebook ainda está disponível?', '2026-04-26 09:00:00-03', 2001, 1020, 1002),
(2, 'Sim, temos em estoque! Posso ajudar com algo?', '2026-04-26 09:05:00-03', 2001, 1002, 1020),
(3, 'Tem interesse em trocar a lente por um flash?', '2026-04-28 10:00:00-03', 2016, 1004, 1007),
(4, 'O iPhone 11 acompanha carregador?', '2026-04-27 11:00:00-03', 2013, 1001, 1007),
(5, 'Acompanha cabo, mas não a fonte. :)', '2026-04-27 11:10:00-03', 2013, 1007, 1001),
(6, 'Faz por 1700 no Switch?', '2026-04-29 12:00:00-03', 2014, 1002, 1006);

-- =============================================================================
-- 10) FLUXO DE TROCAS (TradeRequest / Proposal / Message / Fulfillment / Delivery)
-- =============================================================================
-- Negociação 6001: Felipe quer o Switch do Bruno (anúncio 2014)
-- Negociação 6002: Ana quer o notebook da Carla (anúncio 2015, só troca)
INSERT INTO marketplace_app_traderequest
    (id, status, initial_message, created_at, updated_at, counterparty_id, listing_id, requester_id)
VALUES
(6001, 'negotiating', 'Oi Bruno! Tenho um Xbox Series S, topa trocar pelo Switch?', '2026-05-07 10:00:00-03', '2026-05-07 12:00:00-03', 1002, 2014, 1006),
(6002, 'approved',    'Carla, tenho um desktop gamer para trocar pelo seu notebook.', '2026-05-08 09:00:00-03', '2026-05-09 15:00:00-03', 1003, 2015, 1001);

INSERT INTO marketplace_app_tradeproposal
    (id, item_description, cash_amount, cash_payer, note, created_at, proposer_id, trade_request_id)
VALUES
(1, 'Xbox Series S 512GB na caixa, estado de novo.', 0.00,   '',          'Troca limpa, sem volta.', '2026-05-07 10:30:00-03', 1006, 6001),
(2, 'Switch OLED + 200 de volta para fechar.',        200.00, 'requester', 'Topo, mas com volta sua.', '2026-05-07 11:30:00-03', 1002, 6001),
(3, 'Desktop gamer Ryzen 5 + RX 6600.',               0.00,   '',          'Troca direta pelo notebook.', '2026-05-08 09:30:00-03', 1001, 6002);

INSERT INTO marketplace_app_trademessage (id, content, created_at, sender_id, trade_request_id) VALUES
(1, 'Bora fechar? Posso enviar amanhã.', '2026-05-07 11:45:00-03', 1006, 6001),
(2, 'Fechado, te mando os dados de envio.', '2026-05-07 12:00:00-03', 1002, 6001),
(3, 'Combinado! Fico com o desktop então.', '2026-05-09 15:00:00-03', 1003, 6002);

-- Execução da troca aprovada (6002)
INSERT INTO marketplace_app_tradefulfillment
    (id, payment_amount, payment_method, payment_status, payment_checkout_token, payment_payload,
     payment_confirmed_at, delivery_method, recipient_name, recipient_phone, postal_code, street,
     number, complement, neighborhood, city, state, notes, confirmed_at, created_at, updated_at,
     agreed_proposal_id, trade_request_id)
VALUES
(1, 0.00, '', 'payment_confirmed', '', '{}', '2026-05-09 16:00:00-03', 'to_agree',
   'Carla Dias', '31988880003', '30140071', 'Av. Afonso Pena', '700', 'Casa', 'Funcionários',
   'Belo Horizonte', 'MG', 'Troca sem valores adicionais.', '2026-05-09 16:05:00-03',
   '2026-05-09 15:30:00-03', '2026-05-09 16:05:00-03', 3, 6002);

-- Entregas da troca (cada parte registra a sua)
INSERT INTO marketplace_app_tradedelivery
    (id, delivery_method, recipient_name, recipient_phone, postal_code, street, number, complement,
     neighborhood, city, state, notes, status, created_at, updated_at, trade_request_id, user_id)
VALUES
(1, 'platform_shipping', 'Carla Dias', '31988880003', '30140071', 'Av. Afonso Pena', '700', 'Casa', 'Funcionários', 'Belo Horizonte', 'MG', 'Envio do notebook.', 'sent', '2026-05-10 09:00:00-03', '2026-05-10 09:00:00-03', 6002, 1003),
(2, 'platform_shipping', 'Ana Souza',  '11988880001', '01310100', 'Av. Paulista',    '1000', 'Apto 52', 'Bela Vista', 'São Paulo', 'SP', 'Envio do desktop.', 'sent', '2026-05-10 09:30:00-03', '2026-05-10 09:30:00-03', 6002, 1001);

-- =============================================================================
-- 11) ENDEREÇOS (Address)
-- =============================================================================
INSERT INTO marketplace_app_address
    (id, label, recipient_name, recipient_phone, postal_code, street, number, complement,
     neighborhood, city, state, is_default, created_at, user_id)
VALUES
(1, 'Casa',     'Ana Souza',      '11988880001', '01310100', 'Av. Paulista',       '1000', 'Apto 52', 'Bela Vista',   'São Paulo',      'SP', true,  '2026-03-05 10:20:00-03', 1001),
(2, 'Trabalho', 'Ana Souza',      '11988880001', '04538133', 'Av. Brigadeiro Faria Lima', '3477', '12º andar', 'Itaim Bibi', 'São Paulo', 'SP', false, '2026-03-15 14:00:00-03', 1001),
(3, 'Casa',     'Bruno Lima',     '21988880002', '20040002', 'Rua da Assembleia',  '50',   '',        'Centro',       'Rio de Janeiro', 'RJ', true,  '2026-03-06 11:25:00-03', 1002),
(4, 'Casa',     'Carla Dias',     '31988880003', '30140071', 'Av. Afonso Pena',    '700',  'Casa',    'Funcionários', 'Belo Horizonte', 'MG', true,  '2026-03-07 14:10:00-03', 1003),
(5, 'Casa',     'Diego Alves',    '41988880004', '80010000', 'Rua XV de Novembro', '200',  '',        'Centro',       'Curitiba',       'PR', true,  '2026-03-08 16:50:00-03', 1004),
(6, 'Casa',     'Eduarda Melo',   '51988880005', '90010150', 'Av. Borges de Medeiros', '300', '',     'Centro',       'Porto Alegre',   'RS', true,  '2026-03-09 08:35:00-03', 1005),
(7, 'Casa',     'Gabriela Nunes', '81988880007', '50030230', 'Av. Conde da Boa Vista', '800', 'Bloco B', 'Boa Vista', 'Recife',         'PE', true,  '2026-03-11 12:10:00-03', 1007);

-- =============================================================================
-- 12) NOTIFICAÇÕES (Notification)
-- =============================================================================
INSERT INTO marketplace_app_notification
    (id, category, title, message, url, icon, is_read, created_at, actor_id, recipient_id)
VALUES
(1, 'sale',     'Você fez uma venda!',        'Seu SSD NVMe 1TB foi vendido para Ana Souza.', '/pedidos/3001/', 'sell',          false, '2026-05-02 10:02:00-03', 1001, 1020),
(2, 'purchase', 'Pedido confirmado',          'Seu pagamento do pedido #3001 foi aprovado.',  '/pedidos/3001/', 'shopping_bag',  true,  '2026-05-02 10:06:00-03', NULL, 1001),
(3, 'comment',  'Novo comentário no anúncio', 'Bruno comentou no seu anúncio "Notebook Dell".', '/anuncios/2001/', 'comment',     false, '2026-04-26 10:01:00-03', 1002, 1020),
(4, 'trade',    'Nova proposta de troca',     'Felipe enviou uma proposta de troca pelo seu Switch.', '/trocas/6001/', 'swap_horiz', false, '2026-05-07 10:31:00-03', 1006, 1002),
(5, 'trade',    'Troca aprovada',             'Sua troca com a Carla foi aprovada!',          '/trocas/6002/',  'swap_horiz',    true,  '2026-05-09 15:01:00-03', 1003, 1001),
(6, 'purchase', 'Produto a caminho',          'Seu pedido #3003 está em trânsito.',           '/pedidos/3003/', 'local_shipping',false, '2026-05-04 18:06:00-03', NULL, 1003),
(7, 'system',   'Bem-vindo ao Marketplace',   'Complete seu perfil para começar a vender.',   '/perfil/',       'notifications', true,  '2026-03-05 10:16:00-03', NULL, 1001),
(8, 'sale',     'Você fez uma venda!',        'Seu Smartwatch Galaxy Watch6 foi vendido.',    '/pedidos/3003/', 'sell',          false, '2026-05-04 16:36:00-03', 1003, 1025),
(9, 'comment',  'Resposta ao seu comentário', 'A loja respondeu sua dúvida sobre o PS5.',     '/anuncios/2005/','comment',       false, '2026-04-26 11:16:00-03', 1021, 1003),
(10,'system',   'Conta verificada',           'Sua loja foi verificada com sucesso!',         '/perfil/loja/',  'verified',      true,  '2026-03-01 12:00:00-03', NULL, 1020);

-- =============================================================================
-- 13) DENÚNCIAS (ListingReport)
-- =============================================================================
INSERT INTO marketplace_app_listingreport
    (id, reason, detail, status, created_at, listing_id, reporter_id)
VALUES
(1, 'scam',     'Preço muito abaixo do mercado, parece golpe.', 'open',     '2026-05-03 10:00:00-03', 2023, 1002),
(2, 'off_topic','Produto não parece ser da categoria correta.', 'dismissed','2026-05-04 11:00:00-03', 2021, 1008);

-- =============================================================================
-- 14) PEDIDOS DE VERIFICAÇÃO DE LOJA (StoreVerificationRequest)
-- =============================================================================
INSERT INTO marketplace_app_storeverificationrequest
    (id, document, message, status, review_note, created_at, reviewed_at, store_id)
VALUES
(1, 'verification_docs/gameworld_contrato_social.pdf', 'Segue contrato social para verificação.', 'pending',  '', '2026-05-01 09:00:00-03', NULL, 1021),
(2, 'verification_docs/fotopro_cnpj.pdf',              'Documentos da empresa em anexo.',          'approved', 'Documentação conferida e aprovada.', '2026-04-15 09:00:00-03', '2026-04-16 14:00:00-03', 1022);

-- =============================================================================
-- 15) REAJUSTE DAS SEQUENCES (para não colidir com inserts futuros do app)
-- =============================================================================
SELECT setval(pg_get_serial_sequence('marketplace_app_category','id'),               (SELECT COALESCE(MAX(id),1) FROM marketplace_app_category));
SELECT setval(pg_get_serial_sequence('marketplace_app_user','id'),                   (SELECT COALESCE(MAX(id),1) FROM marketplace_app_user));
SELECT setval(pg_get_serial_sequence('marketplace_app_commonprofile','id'),          (SELECT COALESCE(MAX(id),1) FROM marketplace_app_commonprofile));
SELECT setval(pg_get_serial_sequence('marketplace_app_storeprofile','id'),           (SELECT COALESCE(MAX(id),1) FROM marketplace_app_storeprofile));
SELECT setval(pg_get_serial_sequence('marketplace_app_listing','id'),                (SELECT COALESCE(MAX(id),1) FROM marketplace_app_listing));
SELECT setval(pg_get_serial_sequence('marketplace_app_listingimage','id'),           (SELECT COALESCE(MAX(id),1) FROM marketplace_app_listingimage));
SELECT setval(pg_get_serial_sequence('marketplace_app_comment','id'),                (SELECT COALESCE(MAX(id),1) FROM marketplace_app_comment));
SELECT setval(pg_get_serial_sequence('marketplace_app_cart','id'),                   (SELECT COALESCE(MAX(id),1) FROM marketplace_app_cart));
SELECT setval(pg_get_serial_sequence('marketplace_app_cartitem','id'),               (SELECT COALESCE(MAX(id),1) FROM marketplace_app_cartitem));
SELECT setval(pg_get_serial_sequence('marketplace_app_order','id'),                  (SELECT COALESCE(MAX(id),1) FROM marketplace_app_order));
SELECT setval(pg_get_serial_sequence('marketplace_app_orderitem','id'),              (SELECT COALESCE(MAX(id),1) FROM marketplace_app_orderitem));
SELECT setval(pg_get_serial_sequence('marketplace_app_paymenttransaction','id'),     (SELECT COALESCE(MAX(id),1) FROM marketplace_app_paymenttransaction));
SELECT setval(pg_get_serial_sequence('marketplace_app_delivery','id'),               (SELECT COALESCE(MAX(id),1) FROM marketplace_app_delivery));
SELECT setval(pg_get_serial_sequence('marketplace_app_message','id'),                (SELECT COALESCE(MAX(id),1) FROM marketplace_app_message));
SELECT setval(pg_get_serial_sequence('marketplace_app_traderequest','id'),           (SELECT COALESCE(MAX(id),1) FROM marketplace_app_traderequest));
SELECT setval(pg_get_serial_sequence('marketplace_app_tradeproposal','id'),          (SELECT COALESCE(MAX(id),1) FROM marketplace_app_tradeproposal));
SELECT setval(pg_get_serial_sequence('marketplace_app_trademessage','id'),           (SELECT COALESCE(MAX(id),1) FROM marketplace_app_trademessage));
SELECT setval(pg_get_serial_sequence('marketplace_app_tradefulfillment','id'),       (SELECT COALESCE(MAX(id),1) FROM marketplace_app_tradefulfillment));
SELECT setval(pg_get_serial_sequence('marketplace_app_tradedelivery','id'),          (SELECT COALESCE(MAX(id),1) FROM marketplace_app_tradedelivery));
SELECT setval(pg_get_serial_sequence('marketplace_app_address','id'),                (SELECT COALESCE(MAX(id),1) FROM marketplace_app_address));
SELECT setval(pg_get_serial_sequence('marketplace_app_notification','id'),           (SELECT COALESCE(MAX(id),1) FROM marketplace_app_notification));
SELECT setval(pg_get_serial_sequence('marketplace_app_listingreport','id'),          (SELECT COALESCE(MAX(id),1) FROM marketplace_app_listingreport));
SELECT setval(pg_get_serial_sequence('marketplace_app_storeverificationrequest','id'),(SELECT COALESCE(MAX(id),1) FROM marketplace_app_storeverificationrequest));

COMMIT;

-- =============================================================================
-- FIM DO SEED
-- Usuários criados (senha de todos = senha123):
--   admin / ana.souza / bruno.lima / carla.dias / diego.alves / eduarda.melo
--   felipe.rocha / gabriela.nunes / henrique.cruz
--   Lojas: techstore / gameworld / fotopro / audiomax / infomega / mobilezone
-- =============================================================================
