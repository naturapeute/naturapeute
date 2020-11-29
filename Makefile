deploy:
	ssh naturapeute "\
		cd admin && \
		source venv/bin/activate && \
		git pull && \
		pip install -r requirements.txt && \
		python manage.py migrate && \
		echo 'updated'"
	make restart-server

restart-server:
	ssh naturapeute "\
		sudo systemctl daemon-reload && \
		sudo systemctl restart admin &&\
		echo 'server restarted'"
