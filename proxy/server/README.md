# V2RAY
## Requirements
  - docker
  - docker-compose
## For the First Time
  - copy v2ray.json.template to v2ray.json and add users there.
  - copy .env.template to .env and modify the varialbles in there.
  - run and add your domains for certbot.
    ``` sh
      docker-compose run  --rm -p "80:80" --entrypoint certbot certbot certonly --standalone --cert-name cert
  ```

## Run
  - run docker-compose up -d
