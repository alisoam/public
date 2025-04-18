FROM python:3.11-slim

WORKDIR /var/www/namizun/
ARG REDIS_SOCKET

RUN \
    apt update && \
    apt install -y git && \
    apt autoremove && \
    apt clean

RUN \
    pip install --upgrade pip && \
    pip install pytz "redis~=5.2.1" psutil colored pyfiglet prettytable

RUN \
    git clone --depth 1 https://github.com/malkemit/namizun.git . && \
    git fetch --depth=1 origin 02cf17d91cabda163f7a0a605b7a473f4ce92529 && \
    git checkout 02cf17d91cabda163f7a0a605b7a473f4ce92529 && \
    sed -i "s|namizun_db = Redis()|namizun_db = Redis(unix_socket_path='$REDIS_SOCKET')|" namizun_core/database.py

CMD ["python3", "uploader.py"]
