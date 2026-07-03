"""
test_auth_success.py — Preuve que le systeme d'authentification KORA
fonctionne de bout en bout avec les identifiants reels en production.
"""
import sys
import requests

BASE_URL = "http://213.156.135.139"
EMAIL = "mistermarcket@gmail.com"
PASSWORD = "BingoManiak1492#?"

_PASSED = 0
_FAILED = 0

def _check(name, ok, detail=""):
    global _PASSED, _FAILED
    if ok:
        _PASSED += 1
        print(f"  [OK] {name}")
    else:
        _FAILED += 1
        print(f"  [FAIL] {name} -- {detail}")

def main():
    print(f"\n=== test_auth_success -- {BASE_URL} ===\n")
    session = requests.Session()

    r_login = session.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    _check("POST /api/auth/login -> 200", r_login.status_code == 200, f"got {r_login.status_code}: {r_login.text}")
    _check("cookie kora_session pose", "kora_session" in session.cookies)

    r_me = session.get(f"{BASE_URL}/api/auth/me")
    _check("GET /api/auth/me -> 200 (session valide)", r_me.status_code == 200, f"got {r_me.status_code}")
    if r_me.status_code == 200:
        data = r_me.json()
        _check("authenticated=True", data.get("authenticated") is True, str(data))
        _check("role=editor", data.get("role") == "editor", str(data))

    print(f"\n{_PASSED} passes, {_FAILED} echoues\n")
    sys.exit(0 if _FAILED == 0 else 1)

if __name__ == "__main__":
    main()
