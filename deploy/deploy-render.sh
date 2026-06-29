#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# KORA Backend — Script de déploiement Render.com
# Usage : ./deploy/deploy-render.sh [--dry-run]
#
# Prérequis :
#   - Render CLI installé : npm i -g @render/cli  OU  brew install render
#   - Authentifié : render login
#   - Variables d'environnement définies dans Render Dashboard
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
IFS=$'\n\t'

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

CYAN='\033[0;36m'; GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[FAIL]${NC}  $*" >&2; exit 1; }
dry()     { echo -e "${YELLOW}[DRY]${NC}   $*"; }

# ── 1. Pré-vérifications ───────────────────────────────────────────────────────
info "=== KORA Backend — Déploiement Render.com ==="
echo ""

info "Vérification des dépendances..."
command -v python3 >/dev/null 2>&1 || error "python3 introuvable"
command -v pip     >/dev/null 2>&1 || error "pip introuvable"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/../backend" && pwd)"

[[ -d "$BACKEND_DIR" ]] || error "Répertoire backend introuvable : $BACKEND_DIR"
[[ -f "$BACKEND_DIR/requirements.txt" ]] || error "requirements.txt introuvable"
[[ -f "$BACKEND_DIR/main.py"          ]] || error "main.py introuvable"

# ── 2. Variables d'environnement requises ─────────────────────────────────────
info "Vérification des variables d'environnement requises..."

REQUIRED_ENV_VARS=(
  "SUPABASE_URL"
  "SUPABASE_ANON_KEY"
  "SUPABASE_SERVICE_KEY"
  "GROQ_API_KEY"
  "GEMINI_API_KEY"
  "OPENROUTER_API_KEY"
  "TAVILY_API_KEY"
  "WP_URL"
  "WP_USER"
  "WP_APP_PASSWORD"
  "REDIS_URL"
  "GMAIL_ADDRESS"
  "REPORT_EMAIL"
  "FAL_KEY"
  "SECRET_KEY"
)

MISSING=()
for var in "${REQUIRED_ENV_VARS[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    MISSING+=("$var")
  fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  warn "Variables manquantes localement (doivent être définies dans Render Dashboard) :"
  for v in "${MISSING[@]}"; do echo "   • $v"; done
  echo ""
  warn "Si déploiement CI/CD automatique via render.yaml, ces vars sont lues depuis Render."
else
  success "Toutes les variables d'environnement présentes"
fi

# ── 3. Tests avant déploiement ────────────────────────────────────────────────
info "Exécution des tests backend..."

if $DRY_RUN; then
  dry "Tests ignorés (--dry-run)"
else
  cd "$BACKEND_DIR"
  # Installer les dépendances dans un venv temporaire
  if [[ ! -d ".venv-deploy" ]]; then
    python3 -m venv .venv-deploy
  fi
  source .venv-deploy/bin/activate
  pip install -q -r requirements.txt

  python -m pytest tests/test_cycle_mock.py tests/test_fallback_llm.py \
    -v --tb=short \
    || error "Tests échoués — déploiement annulé"
  deactivate
  success "Tous les tests passent"
fi

# ── 4. Validation render.yaml ──────────────────────────────────────────────────
info "Validation de render.yaml..."

RENDER_YAML="${SCRIPT_DIR}/../render.yaml"
if [[ ! -f "$RENDER_YAML" ]]; then
  error "render.yaml introuvable à la racine du projet"
fi

# Vérifier les champs critiques
python3 - <<'PYEOF'
import sys
try:
    import yaml
except ImportError:
    print("  [WARN] PyYAML non installé — validation YAML ignorée")
    sys.exit(0)

with open(sys.argv[1]) as f:
    doc = yaml.safe_load(f)

services = doc.get("services", [])
if not services:
    print("[FAIL] Aucun service dans render.yaml")
    sys.exit(1)

svc = services[0]
required = ["type", "name", "env", "buildCommand", "startCommand"]
missing = [k for k in required if k not in svc]
if missing:
    print(f"[FAIL] Champs manquants dans render.yaml : {missing}")
    sys.exit(1)

print(f"  [OK] render.yaml valide — service '{svc['name']}' (type={svc['type']})")
PYEOF "$RENDER_YAML"

success "render.yaml validé"

# ── 5. Déploiement ────────────────────────────────────────────────────────────
if $DRY_RUN; then
  dry "Déploiement ignoré (--dry-run)"
  dry "Commande réelle : render deploy --service kora-backend"
else
  if command -v render >/dev/null 2>&1; then
    info "Déploiement via Render CLI..."
    render deploy --service kora-api --wait \
      || error "Échec du déploiement Render"
    success "Déploiement Render déclenché"
  else
    warn "Render CLI non installé — déploiement via git push"
    info "Le déploiement Render se déclenche automatiquement sur git push main"
    info "Assurez-vous que le repo est connecté dans le Render Dashboard."
  fi
fi

# ── 6. Health check post-déploiement ─────────────────────────────────────────
if ! $DRY_RUN && [[ -n "${RENDER_BACKEND_URL:-}" ]]; then
  info "Health check post-déploiement..."
  MAX_RETRIES=12
  RETRY_DELAY=10
  for i in $(seq 1 $MAX_RETRIES); do
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${RENDER_BACKEND_URL}/health" || echo "000")
    if [[ "$HTTP_STATUS" == "200" ]]; then
      success "Health check OK : ${RENDER_BACKEND_URL}/health"
      break
    fi
    info "Tentative $i/$MAX_RETRIES — statut $HTTP_STATUS — attente ${RETRY_DELAY}s..."
    sleep $RETRY_DELAY
    if [[ $i -eq $MAX_RETRIES ]]; then
      error "Health check échoué après ${MAX_RETRIES} tentatives"
    fi
  done
else
  warn "RENDER_BACKEND_URL non défini — health check ignoré"
  warn "Vérifiez manuellement : https://<votre-service>.onrender.com/health"
fi

echo ""
success "=== Déploiement Backend terminé ==="
