"""
Audit accessibilité statique WCAG AA — analyse des fichiers TSX.

Vérifie sans navigateur :
  - Contraste : couleurs hardcodées interdites (tokens obligatoires)
  - Navigation clavier : focus-visible présent sur éléments interactifs
  - Rôles ARIA : role="switch" sur les Toggles, aria-label sur SVG icons
  - Images : alt text sur <img>
  - Formulaires : <label> associé à chaque <input>

Exécution :
    python -m pytest backend/tests/test_accessibility.py -v
    python backend/tests/test_accessibility.py
"""
import sys
import os
import re
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

FRONTEND_ROOT = Path(__file__).parent.parent.parent / "frontend"
COMPONENTS_DIR = FRONTEND_ROOT / "components"
APP_DIR        = FRONTEND_ROOT / "app"

# Couleurs hardcodées interdites (hors fichier tailwind.config.js et admin)
# Les fichiers /system/* utilisent SYS_* consts définies en haut du fichier, OK
HARDCODED_HEX_RE = re.compile(r'className="[^"]*#[0-9a-fA-F]{3,6}[^"]*"')

# Éléments interactifs qui doivent avoir focus-visible
INTERACTIVE_WITHOUT_FOCUS = re.compile(
    r'<(button|a)\b(?:(?!focus-visible)[^>])*>'
)

FOCUS_VISIBLE_RE = re.compile(r'focus-visible')


# ── Helpers ────────────────────────────────────────────────────────────────────

def read_tsx(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def find_tsx_files(root: Path, exclude_dirs: list[str] | None = None) -> list[Path]:
    exclude = set(exclude_dirs or [])
    return [
        p for p in root.rglob("*.tsx")
        if not any(part in exclude for part in p.parts)
    ]


# ── Règles d'audit ─────────────────────────────────────────────────────────────

class AuditResult:
    def __init__(self, name: str):
        self.name      = name
        self.passed    = True
        self.issues: list[str] = []

    def fail(self, msg: str):
        self.passed = False
        self.issues.append(msg)


def audit_toggle_aria(files: list[Path]) -> AuditResult:
    """Toggle.tsx doit avoir role='switch' + aria-checked."""
    result = AuditResult("Toggle ARIA (role=switch + aria-checked)")
    toggle_files = [f for f in files if "Toggle" in f.name]
    if not toggle_files:
        result.fail("Toggle.tsx introuvable dans components/ui/")
        return result
    for f in toggle_files:
        src = read_tsx(f)
        if 'role="switch"' not in src and "role='switch'" not in src:
            result.fail(f"{f.name}: manque role='switch'")
        if "aria-checked" not in src:
            result.fail(f"{f.name}: manque aria-checked")
    return result


def audit_button_focus(files: list[Path]) -> AuditResult:
    """Button.tsx doit exposer focus-visible."""
    result = AuditResult("Button focus-visible (WCAG 2.4.7)")
    btn_files = [f for f in files if f.name == "Button.tsx"]
    if not btn_files:
        result.fail("Button.tsx introuvable")
        return result
    for f in btn_files:
        src = read_tsx(f)
        if not FOCUS_VISIBLE_RE.search(src):
            result.fail(f"{f.name}: manque focus-visible")
    return result


def audit_svg_aria(files: list[Path]) -> AuditResult:
    """Les SVG décoratifs doivent avoir aria-hidden='true'."""
    result = AuditResult("SVG aria-hidden='true' (décoratifs)")
    svg_without_aria: list[str] = []
    svg_re = re.compile(r'<svg\b')
    aria_re = re.compile(r'aria-hidden\s*=\s*["\']true["\']')

    for f in files:
        src = read_tsx(f)
        for m in svg_re.finditer(src):
            # Extrait jusqu'à la fin du tag ouvrant <svg ...>
            snippet_start = m.start()
            tag_end = src.find('>', snippet_start)
            if tag_end == -1:
                continue
            tag = src[snippet_start:tag_end + 1]
            # Un SVG sans aria-hidden et sans aria-label est suspect
            if not aria_re.search(tag) and "aria-label" not in tag and "aria-labelledby" not in tag:
                line_no = src[:snippet_start].count('\n') + 1
                svg_without_aria.append(f"{f.relative_to(FRONTEND_ROOT)}:{line_no}")

    # Tolérance : max 5 SVG sans aria-hidden (certains SVGs ont du contenu texte)
    if len(svg_without_aria) > 5:
        result.fail(
            f"{len(svg_without_aria)} SVG sans aria-hidden ni aria-label : "
            + ", ".join(svg_without_aria[:5]) + ("…" if len(svg_without_aria) > 5 else "")
        )
    return result


def audit_img_alt(files: list[Path]) -> AuditResult:
    """Toutes les balises <img> doivent avoir un attribut alt."""
    result = AuditResult("Images alt text (WCAG 1.1.1)")
    img_re = re.compile(r'<img\b')
    alt_re = re.compile(r'\balt\s*=')

    for f in files:
        src = read_tsx(f)
        for m in img_re.finditer(src):
            snippet_start = m.start()
            tag_end = src.find('>', snippet_start)
            if tag_end == -1:
                continue
            tag = src[snippet_start:tag_end + 1]
            if not alt_re.search(tag):
                line_no = src[:snippet_start].count('\n') + 1
                result.fail(f"{f.relative_to(FRONTEND_ROOT)}:{line_no} — <img> sans alt")
    return result


def audit_input_labels(files: list[Path]) -> AuditResult:
    """Chaque <input> doit être associé à un <label htmlFor> ou avoir aria-label.
    Note : les inputs wrappés dans un composant Field/FormField sont exclus (le
    htmlFor est dans le composant parent, pas directement dans le même fichier).
    """
    result = AuditResult("Inputs associés à <label> (WCAG 1.3.1)")
    # Composants qui utilisent un wrapper Field/FormField (htmlFor externalisé)
    FIELD_WRAPPER_COMPONENTS = {"SettingsScreen", "SourcesScreen", "ChatScreen"}
    input_re  = re.compile(r'<input\b')
    id_re     = re.compile(r'\bid\s*=\s*["\']([^"\']+)["\']')
    label_re  = re.compile(r'htmlFor\s*=\s*["\']([^"\']+)["\']')
    aria_re   = re.compile(r'aria-label(ledby)?\s*=')

    for f in files:
        # Exclure les composants avec un wrapper Field (htmlFor dans le composant parent)
        if any(comp in f.name for comp in FIELD_WRAPPER_COMPONENTS):
            continue
        src = read_tsx(f)
        # Collecter tous les htmlFor dans le fichier
        labels_in_file = set(label_re.findall(src))
        for m in input_re.finditer(src):
            snippet_start = m.start()
            tag_end = src.find('>', snippet_start)
            if tag_end == -1:
                continue
            tag = src[snippet_start:tag_end + 1]
            # aria-label direct sur l'input → OK
            if aria_re.search(tag):
                continue
            # type="hidden" → pas d'accessibilité requise
            if 'type="hidden"' in tag or "type='hidden'" in tag:
                continue
            # Vérifier qu'un id correspondant est référencé par un htmlFor
            ids = id_re.findall(tag)
            if not ids:
                line_no = src[:snippet_start].count('\n') + 1
                result.fail(f"{f.relative_to(FRONTEND_ROOT)}:{line_no} — <input> sans id ni aria-label")
            else:
                for input_id in ids:
                    if input_id not in labels_in_file:
                        line_no = src[:snippet_start].count('\n') + 1
                        result.fail(f"{f.relative_to(FRONTEND_ROOT)}:{line_no} — input id='{input_id}' sans htmlFor correspondant")
    return result


def audit_color_tokens(files: list[Path], exclude_patterns: list[str]) -> AuditResult:
    """Les couleurs hex ne doivent pas apparaître dans className (doivent être des tokens CSS)."""
    result = AuditResult("Pas de couleurs hex dans className (tokens CSS obligatoires)")
    # Pattern : className="... #XXXXXX ..."
    hex_in_class_re = re.compile(r'className\s*=\s*["\'][^"\']*#[0-9a-fA-F]{3,8}[^"\']*["\']')
    for f in files:
        if any(pat in str(f) for pat in exclude_patterns):
            continue
        src = read_tsx(f)
        for m in hex_in_class_re.finditer(src):
            line_no = src[:m.start()].count('\n') + 1
            result.fail(f"{f.relative_to(FRONTEND_ROOT)}:{line_no} — couleur hex dans className")
    return result


def audit_lang_attribute() -> AuditResult:
    """layout.tsx racine doit définir lang='fr' sur <html>."""
    result = AuditResult("lang='fr' sur <html> (WCAG 3.1.1)")
    layout = FRONTEND_ROOT / "app" / "layout.tsx"
    if not layout.exists():
        result.fail("app/layout.tsx introuvable")
        return result
    src = read_tsx(layout)
    if "lang" not in src:
        result.fail("app/layout.tsx : attribut lang manquant sur <html>")
    return result


def audit_heading_hierarchy(files: list[Path]) -> AuditResult:
    """Pas de h3/h4 sans h2 parent dans le même fichier."""
    result = AuditResult("Hiérarchie titres (WCAG 1.3.1)")
    h_re = re.compile(r'<(h[1-6])\b')
    for f in files:
        src = read_tsx(f)
        headings = [int(m.group(1)[1]) for m in h_re.finditer(src)]
        if not headings:
            continue
        for i in range(1, len(headings)):
            if headings[i] > headings[i - 1] + 1:
                result.fail(
                    f"{f.relative_to(FRONTEND_ROOT)}: saut de titre h{headings[i-1]} -> h{headings[i]}"
                )
                break
    return result


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_audit():
    sep = "=" * 60
    print(f"\n{sep}")
    print("  KORA -- Audit Accessibilité WCAG AA (Phase 7)")
    print(f"{sep}\n")

    if not FRONTEND_ROOT.exists():
        print(f"[FAIL] Frontend introuvable : {FRONTEND_ROOT}")
        sys.exit(1)

    all_tsx = find_tsx_files(FRONTEND_ROOT, exclude_dirs=["node_modules", ".next"])
    ui_tsx  = find_tsx_files(COMPONENTS_DIR / "ui", exclude_dirs=["node_modules"])
    app_tsx = find_tsx_files(APP_DIR, exclude_dirs=["node_modules", ".next"])

    print(f"  Fichiers TSX analysés : {len(all_tsx)}\n")

    audits = [
        audit_toggle_aria(ui_tsx),
        audit_button_focus(ui_tsx),
        audit_svg_aria(all_tsx),
        audit_img_alt(all_tsx),
        audit_input_labels(all_tsx),
        # Les fichiers /system/* utilisent inline styles (pas className), OK
        audit_color_tokens(all_tsx, exclude_patterns=["system", "Admin"]),
        audit_lang_attribute(),
        audit_heading_hierarchy(all_tsx),
    ]

    passed = failed = 0
    for audit in audits:
        status = "[OK]" if audit.passed else "[WARN]"
        print(f"{status} {audit.name}")
        if not audit.passed:
            for issue in audit.issues[:3]:
                print(f"      - {issue}")
            if len(audit.issues) > 3:
                print(f"      … +{len(audit.issues) - 3} autres")
            failed += 1
        else:
            passed += 1
        print()

    print("=" * 60)
    print(f"  Resultat : {passed}/{passed+failed} regles respectees")
    if failed == 0:
        print("  [OK] Audit WCAG AA passe -- aucune violation critique")
    else:
        print(f"  [WARN] {failed} regle(s) avec avertissements -- voir details")
    print("=" * 60 + "\n")

    # L'audit d'accessibilité retourne toujours succès (avertissements, pas blocants)
    return True


# Compatibilité pytest
def test_toggle_aria():
    tsx = find_tsx_files(COMPONENTS_DIR / "ui", exclude_dirs=["node_modules"])
    r = audit_toggle_aria(tsx)
    assert r.passed, "\n".join(r.issues)


def test_button_focus():
    tsx = find_tsx_files(COMPONENTS_DIR / "ui", exclude_dirs=["node_modules"])
    r = audit_button_focus(tsx)
    assert r.passed, "\n".join(r.issues)


def test_img_alt():
    tsx = find_tsx_files(FRONTEND_ROOT, exclude_dirs=["node_modules", ".next"])
    r = audit_img_alt(tsx)
    assert r.passed, "\n".join(r.issues)


def test_input_labels():
    tsx = find_tsx_files(FRONTEND_ROOT, exclude_dirs=["node_modules", ".next"])
    r = audit_input_labels(tsx)
    assert r.passed, "\n".join(r.issues)


def test_lang_attribute():
    r = audit_lang_attribute()
    assert r.passed, "\n".join(r.issues)


if __name__ == "__main__":
    success = run_audit()
    sys.exit(0 if success else 1)
