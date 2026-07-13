#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# KORA — Déploiement Backend (Render)
# Usage : ./deploy/deploy-all.sh [--prod] [--dry-run]
#
# Le frontend n'est plus déployé sur Vercel — l'étape correspondante a été
# retirée. TODO : ajouter ici la nouvelle étape de déploiement frontend une
# fois l'hébergement de remplacement choisi.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CYAN='\033[0;36m'; GREEN='\033[0;32m'; BOLD='\033[1m'; NC='\033[0m'

echo -e "\n${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║    KORA — Déploiement Backend                     ║${NC}"
echo -e "${BOLD}${CYAN}║    GuinéePress Intelligence · kakilambe.com        ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${NC}\n"

ARGS=("$@")

echo -e "${CYAN}[1/1]${NC} Backend → Render.com"
bash "${SCRIPT_DIR}/deploy-render.sh" "${ARGS[@]}" || exit 1

echo ""
echo -e "${GREEN}${BOLD}✓ Déploiement Backend terminé${NC}"
echo -e "  Backend  : https://<service>.onrender.com"
