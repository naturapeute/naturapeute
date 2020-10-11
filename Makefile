deploy:
	ssh naturapeute "\
		cd admin && \
		git pull && \
		echo 'updated'"
	make restart-server

restart-server:
	ssh naturapeute "\
		sudo systemctl daemon-reload && \
		sudo systemctl restart admin &&\
		echo 'server restarted'"
