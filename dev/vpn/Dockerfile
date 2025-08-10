FROM python:3.12-alpine

# WireGuard, firewall, routing, resolvconf (wg-quick uses DNS=)
RUN apk add --no-cache wireguard-tools iptables ip6tables iproute2 openresolv curl bash

COPY run.py /run.py
ENTRYPOINT ["python3", "/run.py"]
