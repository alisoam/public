#!/usr/bin/python3

import base64
import json

client_id = input("client-id: ")
domain = input("domain: ")
path = input("path: ")

j = json.dumps({
    "v": "2", "ps": domain, "add": domain, "port": "443", "id": client_id, "aid": "0", "net": "ws", "type": "none",
    "host": domain, "path": path, "tls": "tls"
})

print("vmess://" + base64.b64encode(j.encode('ascii')).decode('ascii'))
