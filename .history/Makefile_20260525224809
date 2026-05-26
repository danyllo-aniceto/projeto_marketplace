.PHONY: up down logs migrate makemigrations createsuperuser test shell

up:
	docker-compose up -d --build

down:
	docker-compose down

logs:
	docker-compose logs -f

migrate:
	docker-compose run --rm web python manage.py migrate

makemigrations:
	docker-compose run --rm web python manage.py makemigrations

createsuperuser:
	docker-compose run --rm web python manage.py createsuperuser

test:
	docker-compose run --rm web python manage.py test

shell:
	docker-compose run --rm web python manage.py shell
