.PHONY: init dev-up dev-down migrate preflight test build logs clean-expired audit backfill-players
init:
	python3 scripts/init_env.py
dev-up: init
	docker compose up --build -d --wait frontend api
migrate: init
	docker compose run --build --rm migrate
backfill-players: migrate
	docker compose run --no-deps --rm migrate python -m app.backfill_players
dev-down:
	docker compose down
preflight: init
	docker compose config --quiet
	docker compose --profile test run --build --rm preflight
	docker compose run --build --no-deps --rm frontend npm run build
test: preflight
build:
	docker compose build
logs:
	docker compose logs -f --tail=100 api frontend
clean-expired:
	docker compose exec api python -m app.cleanup
audit:
	docker compose run --rm api pip-audit -r requirements.lock
	docker compose run --rm frontend npm audit
