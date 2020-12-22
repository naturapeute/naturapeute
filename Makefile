deploy:
	ssh naturapeute "\
		cd prod && \
		source venv/bin/activate && \
		git pull && \
		pip install -r requirements.txt && \
		python manage.py migrate && \
		echo 'updated'"
	make restart-server

restart-server:
	ssh naturapeute "\
		sudo systemctl daemon-reload && \
		sudo systemctl restart naturapeute &&\
		echo 'server restarted'"
