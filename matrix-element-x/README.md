# Deploying Element Server Suite (ESS) on Debian
*K3s + Traefik + cert-manager (Let’s Encrypt), no external reverse proxy*

This guide walks you through a clean, repeatable deployment of **ESS Community** on a fresh Debian server using **K3s** (single-node Kubernetes), **Traefik** (ingress), and **cert-manager** (automatic TLS).
It uses the following generic hostnames—swap `yourdomain.tld` for your real domain:

* **Server name (Matrix homeserver)**: `yourdomain.tld`
* **Synapse**: `matrix.yourdomain.tld`
* **Matrix Authentication Service (MAS)**: `account.yourdomain.tld`
* **Element Web**: `chat.yourdomain.tld`
* **Matrix RTC**: `mrtc.yourdomain.tld`

---

## 1) Prerequisites

**Server**

* Fresh Debian (sudo user).
* Public IPv4/IPv6 reachable on the Internet.

**DNS (A/AAAA)**
Point these records to your server’s public IP:

```
yourdomain.tld
matrix.yourdomain.tld
account.yourdomain.tld
chat.yourdomain.tld
mrtc.yourdomain.tld
```

**Open ports**

* 80/TCP and 443/TCP (web + ACME challenges)
* 30881/TCP and 30882/UDP (Matrix RTC SFU)

**Let’s Encrypt email**

* A valid email for ACME notifications & rate limits (you’ll set this in the script).

---

## 2) One-shot installer (copy/paste)

> Edit the variables at the top, then run on your Debian server.

```bash
#!/usr/bin/env bash
set -euo pipefail

### ── EDIT ME ────────────────────────────────────────────────────────────────
SERVER_NAME="yourdomain.tld"
ACME_EMAIL="admin@yourdomain.tld"   # email for Let's Encrypt notifications

# Subdomains (keep defaults or change)
MATRIX_HOST="matrix.${SERVER_NAME}"
ACCOUNT_HOST="account.${SERVER_NAME}"
CHAT_HOST="chat.${SERVER_NAME}"
MRTC_HOST="mrtc.${SERVER_NAME}"
### ──────────────────────────────────────────────────────────────────────────

export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -y
sudo apt-get install -y curl ca-certificates jq

# Optional: open firewall if UFW is enabled
if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow 80/tcp || true
  sudo ufw allow 443/tcp || true
  sudo ufw allow 30881/tcp || true
  sudo ufw allow 30882/udp || true
fi

# K3s (Traefik on 80/443; includes kubectl)
if ! systemctl is-active --quiet k3s; then
  curl -sfL https://get.k3s.io | sh -
fi

# Kubeconfig for this user
mkdir -p "${HOME}/.kube"
export KUBECONFIG="${HOME}/.kube/config"
sudo k3s kubectl config view --raw > "$KUBECONFIG"
chmod 600 "$KUBECONFIG"
chown "$(id -u)":"$(id -g)" "$KUBECONFIG"

# Helm
if ! command -v helm >/dev/null 2>&1; then
  curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

# cert-manager (with CRDs)
helm repo add jetstack https://charts.jetstack.io --force-update
helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --version v1.17.0 \
  --set crds.enabled=true

# Let’s Encrypt ClusterIssuer (HTTP-01 via Traefik)
cat <<YAML | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    # For testing, you can switch to the staging endpoint:
    # server: https://acme-staging-v02.api.letsencrypt.org/directory
    server: https://acme-v02.api.letsencrypt.org/directory
    email: ${ACME_EMAIL}
    privateKeySecretRef:
      name: letsencrypt-prod-private-key
    solvers:
      - http01:
          ingress:
            class: traefik
YAML

# Namespace + configuration
kubectl create namespace ess --dry-run=client -o yaml | kubectl apply -f -
CONF_DIR="${HOME}/ess-config-values"
mkdir -p "$CONF_DIR"

# Hostnames (read by the chart)
cat > "${CONF_DIR}/hostnames.yaml" <<YAML
serverName: ${SERVER_NAME}

synapse:
  ingress:
    host: ${MATRIX_HOST}

matrixAuthenticationService:
  ingress:
    host: ${ACCOUNT_HOST}

matrixRTC:
  ingress:
    host: ${MRTC_HOST}

elementWeb:
  ingress:
    host: ${CHAT_HOST}
YAML

# Chart fragment for Let's Encrypt
curl -fsSL \
  https://raw.githubusercontent.com/element-hq/ess-helm/main/charts/matrix-stack/ci/fragments/quick-setup-letsencrypt.yaml \
  -o "${CONF_DIR}/tls.yaml"

# Install ESS (uses bundled Postgres by default)
helm upgrade --install --namespace ess ess \
  oci://ghcr.io/element-hq/ess-helm/matrix-stack \
  -f "${CONF_DIR}/hostnames.yaml" \
  -f "${CONF_DIR}/tls.yaml" \
  --wait

echo
echo "✓ ESS is installed."
echo "  Element Web:   https://${CHAT_HOST}"
echo "  MAS (account): https://${ACCOUNT_HOST}"
echo "  Synapse:       https://${MATRIX_HOST}"
echo "  Matrix RTC:    TCP 30881 / UDP 30882"
echo
echo "Next: create your first admin user:"
echo "  kubectl exec -n ess -it deploy/ess-matrix-authentication-service -- \\"
echo "    mas-cli manage register-user --admin"
echo
echo "Check certificates with:"
echo "  kubectl -n ess get certificate"
```

**Run it:**

```bash
bash install_ess.sh
```

---

## 3) Deploy-time verification

1. **Certificates are ready**

   ```bash
   kubectl -n ess get certificate
   ```

   Expect `READY=True` for the Element Web, MAS, Synapse, RTC, and well-known certificates.

2. **Create an admin user**

   ```bash
   kubectl exec -n ess -it deploy/ess-matrix-authentication-service -- \
     mas-cli manage register-user --admin
   ```

3. **Open the services**

   * Element Web: `https://chat.yourdomain.tld`
   * Login via MAS using the admin user you just created.
   * Homeserver base URL: `https://matrix.yourdomain.tld`

That’s it — your ESS deployment is live with automatic TLS and ready for users.

4. **Add user authentication using SMTP (optional)**
```bash
cat > ~/ess-config-values/mas-registration.yaml <<'YAML'
matrixAuthenticationService:
  additional:
    user-config.yaml:
      # Inline plaintext config injected into MAS
      config: |
        email:
          from: '"Your Lab" <your.email@yourdomain.tld>'
          reply_to: '"Your Lab" <your.email@yourdomain.tld>'
          transport: smtp
          mode: starttls
          hostname: "smtp.yourdomain.tld"
          port: 587
          username: "your.email@yourdomain.tld"
          password: "your_app_password"   # <- your app password, no spaces
        account:
          password_registration_enabled: true
          password_recovery_enabled: true
          login_with_email_allowed: true
        policy:
          data:
            emails:
              # Allow only addresses from your domain
              allowed_addresses:
                suffixes: ["@yourdomain.tld"]
YAML
```
