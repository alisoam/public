# V2RAY
## Requirements
  - docker
  - docker-compose
  - A reverse proxy on external network 'reverse-proxy'. (Can be copied from ../server/compose.yaml nginx)
## For the First Time
  - copy v2ray.json.template to v2ray.json, select appropriate outbound protocole for proxy and add users there.
  - copy .env.template to .env and modify the varialbles in there.

## Run
  - run docker-compose up -d
