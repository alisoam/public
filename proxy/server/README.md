# V2RAY Server

## Requirements
  - docker
  - docker-compose
  - A reverse proxy on external network 'reverse-proxy'. (Can be copied from ../server/compose.yaml nginx)

## For the First Time
  - copy v2ray.json.bridge.template or v2ray.json.terminate.template to v2ray.json, select appropriate outbound protocole for proxy and add users there.

## Run
  - run docker-compose up -d
