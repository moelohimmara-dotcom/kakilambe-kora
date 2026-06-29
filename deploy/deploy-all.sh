#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# KORA — Déploiement complet (Backend Render + Frontend Vercel)
# Usage : ./deploy/deploy-all.sh [--prod] [--dry-run]
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CYAN='\033[0;36m'; GREEN='\033[0;32m'; BOLD='\033[1m'; NC='\033[0m'

echo -e "\n${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║    KORA — Déploiement Production complet          ║${NC}"
echo -e "${BOLD}${CYAN}║    GuinéePress Intelligence · kakilambe.com        ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${NC}\n"

ARGS=("$@")

echo -e "${CYAN}[1/2]${NC} Backend → Render.com"
bash "${SCRIPT_DIR}/deploy-render.sh" "${ARGS[@]}" || exit 1

echo ""
echo -e "${CYAN}[2/2]${NC} Frontend → Vercel"
bash "${SCRIPT_DIR}/deploy-vercel.sh" "${ARGS[@]}" || exit 1

echo ""
echo -e "${GREEN}${BOLD}✓ Déploiement complet terminé${NC}"
echo -e "  Backend  : https://<service>.onrender.com"
echo -e "  Frontend : https://kakilambe.com"
