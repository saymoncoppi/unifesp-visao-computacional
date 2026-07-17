#!/usr/bin/env bash
#
# run_server.sh — sobe o servidor web (FastAPI/ASGI via Gunicorn) do inspetor.
#
# O projeto Python vive em src/ (pyproject.toml, uv.lock, .venv, config/, app/).
# Este script faz as verificações básicas e delega para o uv:
#
#   uv sync
#   uv run gunicorn -c config/gunicorn.conf.py app.api:app
#
# Servidor sobe em http://0.0.0.0:8000 (acessível pela LAN).

set -euo pipefail

# Raiz do repositório = diretório deste script (funciona de qualquer cwd).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$ROOT/src"

# Cores (só se for terminal).
if [ -t 1 ]; then
  RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; BLUE=$'\033[0;34m'; NC=$'\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; BLUE=''; NC=''
fi
ok()   { printf '%s✓%s %s\n' "$GREEN" "$NC" "$1"; }
warn() { printf '%s!%s %s\n' "$YELLOW" "$NC" "$1"; }
die()  { printf '%s✗%s %s\n' "$RED" "$NC" "$1" >&2; exit 1; }
info() { printf '%s→%s %s\n' "$BLUE" "$NC" "$1"; }

# --- Banner (rosa pastel) ---------------------------------------------------
if [ -t 1 ]; then PINK=$'\033[38;5;218m'; else PINK=''; fi
banner() {
  printf '\n%s' "$PINK"
  cat <<'BANNER'
 _          _          _   ___                           _
| |    __ _| |__   ___| | |_ _|_ __  ___ _ __   ___  ___| |_ ___  _ __
| |   / _` | '_ \ / _ \ |  | || '_ \/ __| '_ \ / _ \/ __| __/ _ \| '__|
| |__| (_| | |_) |  __/ |  | || | | \__ \ |_) |  __/ (__| || (_) | |
|_____\__,_|_.__/ \___|_| |___|_| |_|___/ .__/ \___|\___|\__\___/|_|
                                        |_|
BANNER
  printf '%s\n\n' "$NC"
}
banner

# O uv precisa rodar de dentro de src/ (é onde está o pyproject.toml/uv.lock),
# e o próprio gunicorn.conf.py faz chdir para src/ ao carregar.
[ -d "$SRC" ] || die "Diretório src/ não encontrado em $ROOT"

# --- 1. .venv (raiz ou src) -------------------------------------------------
if [ -d "$ROOT/.venv" ]; then
  ok ".venv encontrado na raiz do repositório"
elif [ -d "$SRC/.venv" ]; then
  ok ".venv encontrado em src/"
else
  warn ".venv não encontrado (nem na raiz, nem em src/) — 'uv sync' vai criar"
fi

# --- 2. .env (raiz ou src) --------------------------------------------------
if [ -f "$ROOT/.env" ]; then
  ok ".env encontrado na raiz do repositório"
elif [ -f "$SRC/.env" ]; then
  ok ".env encontrado em src/"
else
  warn ".env não encontrado — o app usa fallback baseado em regras sem GOOGLE_API_KEY"
  warn "  (copie um dos .env.example e ajuste, se quiser habilitar o Gemini)"
fi

# --- 3. uv instalado --------------------------------------------------------
if command -v uv >/dev/null 2>&1; then
  ok "uv instalado ($(uv --version))"
else
  die "uv não está instalado. Instale com: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# --- 4. uv sync -------------------------------------------------------------
info "Rodando 'uv sync' em src/ ..."
( cd "$SRC" && uv sync )
ok "Dependências sincronizadas"

# --- 5. TLS/HTTPS (sempre) --------------------------------------------------
# A funcionalidade Scan usa a câmera (getUserMedia), que o navegador só libera
# em "contexto seguro": localhost OU https. Para testar a câmera pelo celular na
# LAN é preciso HTTPS, então o servidor sempre sobe com TLS: geramos um
# certificado self-signed (válido para localhost + IP da LAN) e o
# gunicorn.conf.py o usa via SSL_CERTFILE/SSL_KEYFILE.
command -v openssl >/dev/null 2>&1 || die "openssl não está instalado (necessário para o HTTPS)."
CERT_DIR="$SRC/config/certs"
CERT="$CERT_DIR/dev-cert.pem"
KEY="$CERT_DIR/dev-key.pem"
mkdir -p "$CERT_DIR"

# IP da LAN (primeiro endereço não-loopback), para incluir no SAN do certificado.
LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -n "$LAN_IP" ] || LAN_IP="127.0.0.1"

if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
  info "Gerando certificado self-signed (localhost, 127.0.0.1, $LAN_IP) ..."
  openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
    -keyout "$KEY" -out "$CERT" \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:$LAN_IP" \
    >/dev/null 2>&1 || die "Falha ao gerar o certificado com openssl."
  ok "Certificado gerado em config/certs/ (self-signed)"
else
  ok "Certificado existente reutilizado (config/certs/dev-cert.pem)"
fi

export SSL_CERTFILE="$CERT"
export SSL_KEYFILE="$KEY"
warn "Certificado self-signed: o navegador vai avisar 'não confiável'."
warn "  Aceite o aviso uma vez (no PC e no celular) para liberar a câmera."
info "Acesse no celular:  https://$LAN_IP:8000"

# --- 6. subir o servidor ----------------------------------------------------
info "Subindo Gunicorn em https://0.0.0.0:8000 (Ctrl+C para parar) ..."
cd "$SRC"
exec uv run gunicorn -c config/gunicorn.conf.py app.api:app
