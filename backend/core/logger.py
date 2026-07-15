import logging
import json
import sys
from datetime import datetime

# Événements considérés comme des succès notables plutôt que de simples
# informations de routine — affichés en "OK" (vert) plutôt qu'"INFO" (bleu)
# dans le flux /system/logs, cohérent avec le code couleur déjà en place
# côté frontend (LEVEL_COLOR). Heuristique par suffixe, pas une liste figée
# à maintenir manuellement à chaque nouvel événement de succès.
_OK_SUFFIXES = ("_success", "_completed", "_done", "_published")

# Le frontend (app/system/logs/page.tsx) filtre sur des libellés COURTS
# ("WARN", pas "WARNING") — logging.warning() produit level="warning", que
# .upper() seul aurait donné "WARNING", ne correspondant à aucun bouton de
# filtre existant. Mapping explicite plutôt qu'une troncature fragile.
_LEVEL_DISPLAY = {"info": "INFO", "warning": "WARN", "error": "ERROR", "debug": "DEBUG"}


class StructuredLogger:
    """Structured JSON logger for KORA."""

    def __init__(self, name: str = "kora"):
        self._logger = logging.getLogger(name)
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.DEBUG)

    def _emit(self, level: str, event: str, **kwargs):
        record = {
            "ts": datetime.utcnow().isoformat(),
            "level": level,
            "event": event,
            **kwargs,
        }
        msg = json.dumps(record, ensure_ascii=False, default=str)
        getattr(self._logger, level)(msg)

        # Diffusion vers le flux global /stream/logs (audit 2026-07-15) —
        # best-effort total : une panne ici ne doit JAMAIS faire échouer un
        # appel de log applicatif, ni ralentir le chemin critique.
        try:
            from core.log_stream import broadcast
            display_level = "OK" if level == "info" and event.endswith(_OK_SUFFIXES) else _LEVEL_DISPLAY.get(level, level.upper())
            detail = {k: v for k, v in kwargs.items() if k not in ("ts", "level", "event")}
            broadcast({
                "ts": record["ts"],
                "level": display_level,
                "node": event,
                "message": (f"{event} — {json.dumps(detail, ensure_ascii=False, default=str)}" if detail else event),
            })
        except Exception:
            pass

    def info(self, event: str, **kwargs):
        self._emit("info", event, **kwargs)

    def warning(self, event: str, **kwargs):
        self._emit("warning", event, **kwargs)

    def error(self, event: str, **kwargs):
        self._emit("error", event, **kwargs)

    def debug(self, event: str, **kwargs):
        self._emit("debug", event, **kwargs)


logger = StructuredLogger()
