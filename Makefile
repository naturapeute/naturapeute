REMOTE_HOST ?= sweethome
REMOTE_CONTAINER ?= naturapeute
REMOTE_APP ?= /home/ubuntu/naturapeute
SERVER_COPY ?= server-copy/$(shell date +%Y%m%d-%H%M%S)
POSTGRES_DATABASE ?= naturapeute
MONGO_URI ?= mongodb://host.docker.internal:27017/terrapeute
MONGO_DATABASE ?= terrapeute

deploy:
	ssh naturapeute "\
		cd naturapeute && \
		source venv/bin/activate && \
		git pull && \
		pip install -r requirements.txt && \
		python manage.py collectstatic --noinput && \
		python manage.py migrate && \
		echo 'updated'"
	make restart-server

restart-server:
	ssh naturapeute "\
		sudo systemctl daemon-reload && \
		sudo systemctl restart naturapeute && \
		echo 'server restarted'"

import-from-mongo:
	docker compose run --rm \
		-e MONGO_URI="$(MONGO_URI)" \
		-e MONGO_DATABASE="$(MONGO_DATABASE)" \
		web python manage.py shell -c "import mongo2pg; mongo2pg.import_all()"

import_from_mongo: import-from-mongo

download-from-server:
	mkdir -p "$(SERVER_COPY)/app" "$(SERVER_COPY)/database"
	ssh "$(REMOTE_HOST)" 'sudo lxc exec $(REMOTE_CONTAINER) -- tar -C $(REMOTE_APP) --exclude=./venv --exclude=./venv.backup --exclude=./.git --exclude=./local_settings.py -czf - .' > "$(SERVER_COPY)/app/naturapeute-server.tar.gz"
	tar -xzf "$(SERVER_COPY)/app/naturapeute-server.tar.gz" -C "$(SERVER_COPY)/app"
	ssh "$(REMOTE_HOST)" 'sudo lxc exec $(REMOTE_CONTAINER) -- sudo -u postgres pg_dump -p 5432 -Fc --no-owner --no-acl -d $(POSTGRES_DATABASE)' > "$(SERVER_COPY)/database/naturapeute.dump"

# Compatibility aliases for the historical underscore target names.
download_from_server: download-from-server
