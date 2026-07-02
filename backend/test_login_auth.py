"""
test_login_auth.py — Preuve que le login KORA fonctionne de bout en bout
sur le VPS (POST /api/auth/login -> cookie de session -> GET /api/auth/me).

Contexte du bug corrigé : le cookie de session portait l'attribut Secure,
que les navigateurs (RFC 6265) refusent silencieusement sur une connexion
HTTP non chiffrée — exactement la situation du VPS tant qu'il n'a pas de
domaine/certificat. La librairie `requests` n'applique pas cette règle de
sécurité comme un vrai navigateur (elle stocke le cookie même sans HTTPS),
donc ce script valide le contrat de l'API (login -> session valide -> rôle),
pas le comportement navigateur en lui-même — c'est ce dernier qui a été
vérifié manuellement via les en-têtes HTTP bruts (curl -i) avant le fix.

Exécution : python test_login_auth.py [base_url]
"""
import sys
import requests

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://213.156.135.139"
EMAIL = "mistermarcket@gmail.com"
PASSWORD = "BingoManiak1492#?"

_PASSED = 0
_FAILED = 0


def _check(name: str, ok: bool, detail: str = ""):
    global _PASSED, _FAILED
    if ok:
        _PASSED += 1
        print(f"  [OK] {name}")
    else:
        _FAILED += 1
        print(f"  [FAIL] {name} — {detail}")


def main():
    print(f"\n=== test_login_auth — {BASE_URL} ===\n")
    session = requests.Session()

    # 1. Mauvais mot de passe -> 401
    r_bad = session.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": "wrong"})
    _check("login avec mauvais mot de passe -> 401", r_bad.status_code == 401, f"got {r_bad.status_code}")

    # 2. Bon identifiants -> 200 + cookie de session posé
    r_login = session.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    _check("login avec bons identifiants -> 200", r_login.status_code == 200, f"got {r_login.status_code}: {r_login.text}")
    _check("cookie kora_session présent après login", "kora_session" in session.cookies)

    # 3. Session valide -> /me confirme authenticated=True
    r_me = session.get(f"{BASE_URL}/api/auth/me")
    _check("GET /api/auth/me -> 200 après login", r_me.status_code == 200, f"got {r_me.status_code}: {r_me.text}")
    if r_me.status_code == 200:
        data = r_me.json()
        _check("session authentifiée (authenticated=True)", data.get("authenticated") is True, str(data))
        _check("rôle correctement identifié (editor, pas admin)", data.get("role") == "editor", str(data))

    # 4. Login admin -> cookie admin + rôle admin
    r_admin = session.post(f"{BASE_URL}/api/auth/admin", json={"secret": PASSWORD})
    _check("login admin -> 200", r_admin.status_code == 200, f"got {r_admin.status_code}: {r_admin.text}")
    r_me2 = session.get(f"{BASE_URL}/api/auth/me")
    if r_me2.status_code == 200:
        _check("rôle mis à jour en admin après login admin", r_me2.json().get("role") == "admin", str(r_me2.json()))

    # 5. Logout -> session invalidée
    session.delete(f"{BASE_URL}/api/auth/login")
    r_me3 = session.get(f"{BASE_URL}/api/auth/me")
    _check("GET /api/auth/me -> 401 après logout", r_me3.status_code == 401, f"got {r_me3.status_code}")

    # 6. Preuve navigateur : le cookie Secure n'est plus forcé sur HTTP
    r_raw = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    set_cookie = r_raw.headers.get("set-cookie", "")
    is_https = BASE_URL.startswith("https://")
    secure_present = "Secure" in set_cookie
    _check(
        f"attribut Secure du cookie cohérent avec le schéma ({'https' if is_https else 'http'})",
        secure_present == is_https,
        f"Set-Cookie: {set_cookie}",
    )

    print(f"\n{_PASSED} passés, {_FAILED} échoués\n")
    if _FAILED:
        sys.exit(1)


if __name__ == "__main__":
    main()
