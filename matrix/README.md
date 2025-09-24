## Proxy & Firewall Configuration

For secure deployments, use a DMZ directly on the server if possible, or manually configure firewall rules and port forwarding for each service.

**Setup Checklist:**
- Replace all example domains with your actual domain name.
- Generate strong, random passwords for all services.
- Use a valid SSL certificate (e.g., from [Let's Encrypt](https://letsencrypt.org/)).

### Initial Synapse Setup

Generate the initial Synapse configuration with randomized keys:

```sh
docker compose run --rm synapse-generate
```

This creates a config file for Synapse. Your custom configuration will be merged and override the generated settings.

---

## Nginx Proxy Configuration (using Nginx Proxy Manager)

### Proxy Table

| Subdomain                | Service & Port      | Notes                |
|--------------------------|---------------------|----------------------|
| `element.example.tld`    | `element:80` (HTTP) | Enable WebSockets    |
| `matrix.example.tld`     | `synapse:8008` (HTTP) | Enable WebSockets |

---

### Example Nginx Location Blocks

#### `element.example.tld` → `element:80`

```nginx
location / {
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;

    # WebSocket support
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    client_max_body_size 50M; # Sync with Synapse max_upload_size
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
    send_timeout 600s;

    # Optional: reduce buffering for uploads
    proxy_buffering off;
    proxy_request_buffering off;
}
```

#### `matrix.example.tld` → `synapse:8008`

```nginx
location / {
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;

    # WebSocket support
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
    send_timeout 600s;

    proxy_buffering off;
    proxy_request_buffering off;

    client_max_body_size 50M; # Sync with Synapse max_upload_size
}
```

#### Well-Known Matrix Endpoints

```nginx
location /.well-known/matrix/server {
    default_type application/json;
    return 200 '{"m.server":"matrix.example.tld:443"}';
}

location /.well-known/matrix/client {
    default_type application/json;
    add_header Access-Control-Allow-Origin *;
    return 200 '{"m.homeserver":{"base_url":"https://matrix.example.tld"}}';
}
```

---

## Testing Tools

- [Matrix Federation Tester](https://federationtester.matrix.org/)

