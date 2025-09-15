venv:
	python -m venv .venv && ./.venv/Scripts/activate && pip install -r requirements.txt

db-up:
	docker compose up -d

db-init:
	docker exec -i liquidaciones_mysql mysql -uliq_user -pliq_pass liquidaciones < scripts/init_db.sql

run-cli:
	.\.venv\Scripts\activate && python -m app.cli
