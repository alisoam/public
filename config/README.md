# Requirements
- python
  ``` sh
  $ pip install -r requirements.txt
  ```

- i3
  ``` sh
  # apt-get install i3
  # apt-get install i3-wm dunst i3lock i3status suckless-tools
  # apt-get install compton hsetroot rxvt-unicode xsel rofi fonts-noto fonts-mplus xsettingsd lxappearance scrot viewnior pm-utils
  ```

- kitty
  ``` sh
  # apt install kitty
  ```

- sbox.py deps: `bubblewrap`, `socat` and `python3` (>= 3.8, stdlib only).
  The default allowlisted mode runs a built-in SOCKS5 + HTTP-CONNECT proxy
  (asyncio) on the host — no third-party proxy needed. Destinations are
  allowlisted before any DNS lookup, and hostnames resolving to private,
  loopback or link-local addresses are rejected. `--net` mode (shared host
  network, no allowlist) needs bwrap only
  ``` sh
  # apt install bubblewrap socat python3
  ```

# RUN
``` sh
$ chmod +x ./sync.sh
$ ./sync.sh check
```
