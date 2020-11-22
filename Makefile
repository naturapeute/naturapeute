deploy:
	ssh naturapeute "\
		cd admin && \
		git pull && \
		source venv/bin/activate && \
		pip install -r requirements.txt && \
		echo 'updated'"
	make restart-server

restart-server:
	ssh naturapeute "\
		sudo systemctl daemon-reload && \
		sudo systemctl restart admin &&\
		echo 'server restarted'"
