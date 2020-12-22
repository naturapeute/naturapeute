deploy:
	ssh naturapeute "\
		cd prod && \
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
		sudo systemctl restart naturapeute &&\
		echo 'server restarted'"

import_from_mongo:
	source venv/bin/activate && \
	python manage.py shell -c "import mongo2pg; mongo2pg.import_all()"
