# Tutorial completo para rodar o projeto com Docker

Este guia mostra, em detalhes, o que você precisa fazer para baixar o projeto em outro computador e colocá-lo para rodar usando Docker.

## 1. O que precisa estar instalado no outro computador

Antes de começar, confirme que o PC novo tem:

- Git
- Docker Desktop
- Docker Compose
- Um editor de texto, como VS Code
- Acesso ao repositório no GitHub

Se o projeto for rodado sem Docker, aí também seriam necessários Python e PostgreSQL instalados manualmente. Neste tutorial, porém, o caminho recomendado é com Docker.

## 2. Baixar o projeto do GitHub

Abra o PowerShell ou o terminal desejado e rode:

```powershell
git clone https://github.com/Amaraldavi/projeto_marketplace.git
cd projeto_marketplace
```

Se o repositório for privado, será necessário fazer login no GitHub ou usar um token de acesso.

## 3. Conferir se os arquivos principais estão no projeto

Depois do clone, verifique se o projeto contém estes arquivos:

- `docker-compose.yml`
- `Dockerfile`
- `Makefile`
- `.env.example`
- `README.md`
- `DOCKER.md`

Esses arquivos são o suficiente para subir o ambiente com Docker.

## 4. Criar o arquivo `.env`

O projeto usa variáveis de ambiente. Então, no novo computador, você deve criar o arquivo `.env` a partir do `.env.example`.

No PowerShell:

```powershell
Copy-Item .env.example .env
```

Depois, abra o `.env` e ajuste os valores principais.

### Valores importantes no `.env`

- `SECRET_KEY`: chave do Django
- `DEBUG=True`: para ambiente de desenvolvimento
- `ALLOWED_HOSTS=localhost,127.0.0.1`
- `DB_NAME=marketplace_db`
- `DB_USER=postgres`
- `DB_PASSWORD=1234` ou outra senha que você definir
- `DB_HOST=db`: importante quando estiver usando Docker
- `DB_PORT=5432`
- `MERCADO_PAGO_ACCESS_TOKEN`: somente se for testar pagamento real
- Variáveis de email: se não for usar, pode deixar vazio ou usar o backend de console

### Observação importante sobre `DB_HOST`

- Quando usar Docker, `DB_HOST` deve ser `db`
- Quando não usar Docker e for conectar no PostgreSQL local, `DB_HOST` deve ser `localhost`

## 5. Ligar o Docker Desktop

Antes de rodar qualquer comando do projeto, abra o Docker Desktop e confirme que o daemon está ativo.

Você pode verificar com:

```powershell
docker version
docker info
```

Se esses comandos retornarem informações do servidor, o Docker está pronto.

## 6. Subir os containers

Com o terminal aberto na pasta do projeto, execute:

```powershell
docker-compose up -d --build
```

O que esse comando faz:

- baixa a imagem do Python
- instala as dependências
- cria o container da aplicação
- cria o container do PostgreSQL
- deixa tudo rodando em segundo plano

Se você tiver `make` instalado, também pode usar:

```powershell
make up
```

Se `make` não existir no seu Windows, tudo bem: use os comandos `docker-compose` diretamente.

## 7. Verificar se os containers subiram

Para confirmar o estado dos containers:

```powershell
docker-compose ps
```

Para ver logs gerais:

```powershell
docker-compose logs -f
```

Para ver apenas os logs do banco:

```powershell
docker-compose logs db
```

Se aparecer erro de inicialização, os logs vão ajudar a descobrir o motivo.

## 8. Rodar as migrações

Depois que o container estiver no ar, você precisa criar as tabelas do banco:

```powershell
docker-compose run --rm web python manage.py migrate
```

Esse passo é obrigatório no primeiro uso do projeto em outro computador.

Se estiver usando `make`:

```powershell
make migrate
```

## 9. Criar o superuser

Agora crie o usuário administrador do Django:

```powershell
docker-compose run --rm web python manage.py createsuperuser
```

Se estiver usando `make`:

```powershell
make createsuperuser
```

Esse usuário será usado no painel admin do Django.

## 10. Abrir a aplicação no navegador

Depois que tudo estiver pronto, acesse:

- Aplicação: http://localhost:8000
- Admin do Django: http://localhost:8000/admin

Use o usuário e a senha criados no passo anterior para entrar no admin.

## 11. Testar o projeto

Você pode rodar os testes do Django dentro do container com:

```powershell
docker-compose run --rm web python manage.py test
```

Se usar `make`:

```powershell
make test
```

## 12. Abrir o shell do Django

Se quiser inspecionar dados ou testar alguma coisa manualmente:

```powershell
docker-compose run --rm web python manage.py shell
```

Se usar `make`:

```powershell
make shell
```

## 13. Parar e limpar o ambiente

Para parar os containers:

```powershell
docker-compose down
```

Se quiser parar e apagar também o volume do banco, use:

```powershell
docker-compose down -v
```

Use `-v` com cuidado, porque isso apaga os dados persistidos no banco do container.

## 14. Problemas comuns e como resolver

### Erro de conexão com o Docker

Se o `docker-compose` reclamar que não consegue acessar o daemon, confira se o Docker Desktop está aberto.

### Erro de build por dependência

Se a imagem falhar ao instalar pacotes, rode novamente o build e confira o log. O projeto está preparado para Python 3.12+, que é compatível com o Django usado aqui.

### Erro no banco de dados

Se o PostgreSQL ainda não estiver pronto, espere alguns segundos e rode a migração novamente.

### Porta ocupada

Se a porta `8000` já estiver em uso, pare o processo que está usando essa porta ou altere o mapeamento no `docker-compose.yml`.

### Arquivo `.env` com problemas

O `.env` não deve ser commitado no Git. Ele precisa existir no computador novo, criado a partir do `.env.example`.

## 15. O que o computador novo precisa ter, em resumo

- Git instalado
- Docker Desktop instalado e aberto
- Docker Compose disponível
- Repositório clonado
- Arquivo `.env` criado a partir do `.env.example`
- `docker-compose up -d --build`
- `docker-compose run --rm web python manage.py migrate`
- `docker-compose run --rm web python manage.py createsuperuser`

## 16. Fluxo curto de execução

Se quiser um resumo rápido, a ordem é esta:

```powershell
git clone https://github.com/Amaraldavi/projeto_marketplace.git
cd projeto_marketplace
Copy-Item .env.example .env
docker-compose up -d --build
docker-compose run --rm web python manage.py migrate
docker-compose run --rm web python manage.py createsuperuser
```

Depois disso, abra:

- http://localhost:8000
- http://localhost:8000/admin

## 17. Observação final

Se você quiser rodar o projeto sem Docker, será necessário instalar Python, PostgreSQL e configurar o ambiente manualmente. Como você já validou o Docker, esta é a forma mais simples e reproduzível para outro computador.
