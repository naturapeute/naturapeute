REMOTE_HOST ?= sweethome
REMOTE_CONTAINER ?= naturapeute
REMOTE_APP ?= /home/ubuntu/naturapeute
SERVER_COPY ?= server-copy/$(shell date +%Y%m%d-%H%M%S)
POSTGRES_DATABASE ?= naturapeute
MONGO_URI ?= mongodb://host.docker.internal:27017/terrapeute
MONGO_DATABASE ?= terrapeute
TEABLE_BASE_ID ?= bsed9fsIVcrGiEVRYCo
TEABLE_API_TOKEN ?=
TEABLE_ASSET_APP ?= server-copy/20260825-145618/app

deploy:
	ssh "$(REMOTE_HOST)" "\
		sudo lxc exec $(REMOTE_CONTAINER) -- sudo -u ubuntu bash -lc 'cd $(REMOTE_APP) && \
		source venv/bin/activate && \
		git pull && \
		pip install -r requirements.txt && \
		python manage.py collectstatic --noinput && \
		python manage.py migrate && \
		echo updated'"
	make restart-server

restart-server:
	ssh "$(REMOTE_HOST)" "\
		sudo lxc exec $(REMOTE_CONTAINER) -- bash -lc 'sudo systemctl daemon-reload && \
		sudo systemctl restart naturapeute && \
		echo server-restarted'"

import-from-mongo:
	docker compose run --rm \
		-e MONGO_URI="$(MONGO_URI)" \
		-e MONGO_DATABASE="$(MONGO_DATABASE)" \
		web python manage.py shell -c "import mongo2pg; mongo2pg.import_all()"

import_from_mongo: import-from-mongo

import-to-teable:
	@docker compose run --rm \
		-e TEABLE_BASE_ID="$(TEABLE_BASE_ID)" \
		-e TEABLE_API_TOKEN="$(TEABLE_API_TOKEN)" \
		-v "$(CURDIR)/$(TEABLE_ASSET_APP):/server-assets:ro" \
		web python manage.py import_to_teable \
			--asset-root /server-assets/uploads \
			--asset-root /server-assets/static/img

import_to_teable: import-to-teable

configure-teable-fields:
	@docker compose run --rm web python manage.py configure_teable_fields

configure_teable_fields: configure-teable-fields

normalize-images:
	docker compose up -d db
	docker compose run --rm --no-deps \
		-v "$(CURDIR)/$(TEABLE_ASSET_APP)/uploads:/server-assets/uploads:rw" \
		-v "$(CURDIR)/naturapeute/static/uploads:/source-static:rw" \
		-v "$(CURDIR)/uploads:/legacy-uploads:rw" \
		web python manage.py normalize_images \
			--root /app/uploads \
			--root /server-assets/uploads \
			--root /source-static \
			--root /legacy-uploads

normalize_images: normalize-images

download-from-server:
	mkdir -p "$(SERVER_COPY)/app" "$(SERVER_COPY)/database"
	ssh "$(REMOTE_HOST)" 'sudo lxc exec $(REMOTE_CONTAINER) -- tar -C $(REMOTE_APP) --exclude=./venv --exclude=./venv.backup --exclude=./.git --exclude=./local_settings.py -czf - .' > "$(SERVER_COPY)/app/naturapeute-server.tar.gz"
	tar -xzf "$(SERVER_COPY)/app/naturapeute-server.tar.gz" -C "$(SERVER_COPY)/app"
	ssh "$(REMOTE_HOST)" 'sudo lxc exec $(REMOTE_CONTAINER) -- sudo -u postgres pg_dump -p 5432 -Fc --no-owner --no-acl -d $(POSTGRES_DATABASE)' > "$(SERVER_COPY)/database/naturapeute.dump"

# Compatibility aliases for the historical underscore target names.
download_from_server: download-from-server
