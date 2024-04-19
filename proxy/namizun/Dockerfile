FROM python:3-slim

WORKDIR /var/www/namizun/

RUN apt update && \
    apt install -y git && \
    apt autoremove && \
    apt clean && \
    pip install redis pytz psutil colored pyfiglet prettytable

RUN git clone https://github.com/malkemit/namizun.git .

CMD ["python3", "uploader.py"]
