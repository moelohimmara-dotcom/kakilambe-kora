#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# KORA Frontend — Script de déploiement Vercel
# Usage : ./deploy/deploy-vercel.sh [--prod] [--dry-run]
#
# Prérequis :
#   - Vercel CLI : npm i -g vercel
#   - Authentifié : vercel login
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
IFS=$'\n\t'

PROD=false
DRY_RUN=false
for arg in "$@"; do
  [[ "$arg" == "--prod"    ]] && PROD=true
  [[ "$arg" == "--dry-run" ]] && DRY_RUN=true
done

CYAN='\033[0;36m'; GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[FAIL]${NC}  $*" >&2; exit 1; }
dry()     { echo -e "${YELLOW}[DRY]${NC}   $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "${SCRIPT_DIR}/../frontend" && pwd)"

# ── 1. Pré-vérifications ───────────────────────────────────────────────────────
info "=== KORA Frontend — Déploiement Vercel ==="
$PROD && info "Mode : PRODUCTION" || info "Mode : Preview"
echo ""

command -v node >/dev/null 2>&1 || error "Node.js introuvable"
command -v npm  >/dev/null 2>&1 || error "npm introuvable"
[[ -d "$FRONTEND_DIR" ]] || error "Répertoire frontend introuvable"
[[ -f "$FRONTEND_DIR/package.json" ]] || error "package.json introuvable"

NODE_VER=$(node -v | cut -c2- | cut -d. -f1)
[[ $NODE_VER -ge 18 ]] || error "Node.js 18+ requis (actuel: $(node -v))"
success "Node.js $(node -v) OK"

# ── 2. Variables d'environnement ──────────────────────────────────────────────
info "Vérification des variables Vercel..."

REQUIRED_ENV_VARS=(
  "NEXT_PUBLIC_API_URL"
  "ADMIN_SECRET_KEY"
)

MISSING=()
for var in "${REQUIRED_ENV_VARS[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    MISSING+=("$var")
  fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  warn "Variables manquantes localement (doivent être dans Vercel Dashboard) :"
  for v in "${MISSING[@]}"; do echo "   • $v"; done
else
  success "Variables d'environnement présentes"
fi

# ── 3. Build local de validation ──────────────────────────────────────────────
info "Build TypeScript + Next.js (validation)..."

if $DRY_RUN; then
  dry "Build ignoré (--dry-run)"
else
  cd "$FRONTEND_DIR"
  npm ci --silent
  npm run build 2>&1 | tail -20
  success "Build Next.js réussi"
fi

# ── 4. Vérification .gitignore ────────────────────────────────────────────────
info "Vérification .gitignore (sécurité)..."

GITIGNORE="$FRONTEND_DIR/.gitignore"
if [[ -f "$GITIGNORE" ]]; then
  grep -q "\.env"       "$GITIGNORE" || warn ".env absent du .gitignore frontend !"
  grep -q "\.env.local" "$GITIGNORE" || warn ".env.local absent du .gitignore frontend !"
  grep -q "\.next"      "$GITIGNORE" || warn ".next absent du .gitignore frontend !"
  success ".gitignore OK"
else
  warn ".gitignore frontend introuvable"
fi

ROOT_GITIGNORE="${SCRIPT_DIR}/../.gitignore"
if [[ -f "$ROOT_GITIGNORE" ]]; then
  grep -q "\.env" "$ROOT_GITIGNORE" || warn ".env absent du .gitignore racine !"
fi

# ── 5. Vérification .env.example (pas de vraies clés) ────────────────────────
info "Vérification .env.example (pas de secrets)..."

ENV_EXAMPLE="$FRONTEND_DIR/.env.example"
if [[ -f "$ENV_EXAMPLE" ]]; then
  # Cherche des patterns ressemblant à des clés réelles (longueur > 20 après le =)
  SUSPICIOUS=$(grep -E '=.{20,}' "$ENV_EXAMPLE" | grep -v '^#' | grep -v 'your_' | grep -v 'xxx' | grep -v 'example' | grep -v 'http' || true)
  if [[ -n "$SUSPICIOUS" ]]; then
    warn "Vérifiez ces lignes dans .env.example (potentielles clés réelles) :"
    echo "$SUSPICIOUS" | while read -r line; do echo "   $line"; done
  else
    success ".env.example OK — aucune clé réelle détectée"
  fi
else
  warn ".env.example absent"
fi

# ── 6. Déploiement Vercel ─────────────────────────────────────────────────────
cd "$FRONTEND_DIR"

if $DRY_RUN; then
  dry "Déploiement ignoré (--dry-run)"
  dry "Commande réelle : vercel deploy$(${PROD} && echo ' --prod' || echo '')"
else
  command -v vercel >/dev/null 2>&1 || error "Vercel CLI non installé — npm i -g vercel"

  info "Déploiement sur Vercel..."
  if $PROD; then
    DEPLOY_URL=$(vercel deploy --prod --yes 2>&1 | tail -1)
  else
    DEPLOY_URL=$(vercel deploy --yes 2>&1 | tail -1)
  fi

  success "Déployé : $DEPLOY_URL"
fi

# ── 7. Health check ───────────────────────────────────────────────────────────
if ! $DRY_RUN && [[ -n "${DEPLOY_URL:-}" ]]; then
  info "Health check Vercel..."
  sleep 5
  HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${DEPLOY_URL}/api/admin/login" \
    -X POST -H "Content-Type: application/json" \
    -d '{"secret":"__probe__"}' || echo "000")

  # 401 = endpoint fonctionnel (mauvais secret attendu), 500+ = problème
  if [[ "$HTTP_STATUS" == "401" || "$HTTP_STATUS" == "200" ]]; then
    success "Endpoint /api/admin/login répond (HTTP $HTTP_STATUS)"
  else
    warn "Réponse inattendue : HTTP $HTTP_STATUS — vérifiez les logs Vercel"
  fi
fi

echo ""
success "=== Déploiement Frontend terminé ==="
$PROD && info "Production : https://kakilambe.com" || info "Preview URL affichée ci-dessus"
