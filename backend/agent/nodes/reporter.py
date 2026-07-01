"""
NŒUD 6 — send_report
Agrège les statistiques Supabase du cycle.
Envoie le rapport formaté via Gmail API.
"""
from agent.state import KoraState
from core.logger import logger
from db.connection import get_db
from sqlalchemy import text


_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background:#faf9f5; color:#141413; }}
  .container {{ max-width:600px; margin:0 auto; padding:32px 24px; }}
  .logo {{ font-size:24px; font-weight:800; margin-bottom:24px; }}
  .logo .slash {{ color:#d97757; }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin:20px 0; }}
  .kpi {{ background:white; border:1px solid #e8e6dc; border-radius:12px; padding:16px; text-align:center; }}
  .kpi-val {{ font-size:28px; font-weight:700; color:#d97757; }}
  .kpi-label {{ font-size:12px; color:#6b6963; margin-top:4px; }}
  .section {{ margin:24px 0; }}
  .section h2 {{ font-size:14px; font-weight:600; text-transform:uppercase; letter-spacing:1px; color:#6b6963; border-bottom:1px solid #e8e6dc; padding-bottom:8px; }}
  .article-row {{ padding:10px 0; border-bottom:1px solid #f3f2ee; }}
  .article-titre {{ font-size:14px; font-weight:500; }}
  .article-meta {{ font-size:12px; color:#6b6963; margin-top:4px; }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:20px; font-size:11px; font-weight:600; }}
  .badge-published {{ background:rgba(120,140,93,0.12); color:#788c5d; }}
  .badge-error {{ background:rgba(192,57,43,0.10); color:#c0392b; }}
  .footer {{ margin-top:32px; padding-top:16px; border-top:1px solid #e8e6dc; font-size:11px; color:#b0aea5; }}
</style></head>
<body>
<div class="container">
  <div class="logo"><span class="slash">/</span>KORA — Rapport du cycle</div>

  <div class="kpi-grid">
    <div class="kpi">
      <div class="kpi-val">{published}</div>
      <div class="kpi-label">Articles publiés</div>
    </div>
    <div class="kpi">
      <div class="kpi-val">{selected}</div>
      <div class="kpi-label">Sélectionnés</div>
    </div>
    <div class="kpi">
      <div class="kpi-val">{errors}</div>
      <div class="kpi-label">Erreurs</div>
    </div>
  </div>

  <div class="section">
    <h2>Articles publiés</h2>
    {articles_html}
  </div>

  {errors_section}

  <div class="footer">
    Cycle ID : {cycle_id} · Mode : {mode} · GuinéePress Intelligence / kakilambe.com
  </div>
</div>
</body>
</html>
"""


async def _update_cycle_db(cycle_id: str, published_count: int, selected_count: int):
    """Met à jour le cycle en base. Extracté pour faciliter les mocks."""
    try:
        async with get_db() as db:
            await db.execute(
                text("""
                UPDATE cycles
                SET status='COMPLETED', completed_at=now(),
                    articles_published=:pub, articles_selected=:sel
                WHERE id=:cid
                """),
                {"pub": published_count, "sel": selected_count, "cid": cycle_id},
            )
    except Exception as e:
        logger.warning("reporter_cycle_update_failed", error=str(e))


async def run(state: KoraState) -> KoraState:
    logger.info("node_reporter_start", cycle_id=state["cycle_id"])

    published_count = state.get("published_count", 0)
    selected_count = len(state.get("selected_articles", []))
    errors = state.get("errors", [])

    # Récupère les articles publiés de ce cycle depuis Supabase
    articles_rows = []
    try:
        async with get_db() as db:
            result = await db.execute(
                text("""
                SELECT titre, wp_url, source_nom, status
                FROM articles
                WHERE cycle_id = :cid AND status IN ('PUBLISHED','FAILED')
                ORDER BY created_at
                """),
                {"cid": state["cycle_id"]},
            )
            articles_rows = [dict(r) for r in result.mappings().all()]
    except Exception as e:
        logger.warning("reporter_db_query_failed", error=str(e))

    # Construit le HTML des articles
    articles_html = ""
    for a in articles_rows:
        badge = "badge-published" if a["status"] == "PUBLISHED" else "badge-error"
        label = "Publié" if a["status"] == "PUBLISHED" else "Échoué"
        link = f'<a href="{a["wp_url"]}" style="color:#d97757">{a["titre"]}</a>' if a.get("wp_url") else a["titre"]
        articles_html += f"""
        <div class="article-row">
          <div class="article-titre">{link}</div>
          <div class="article-meta">
            Source : {a.get("source_nom","?")} &nbsp;
            <span class="badge {badge}">{label}</span>
          </div>
        </div>
        """
    if not articles_html:
        articles_html = "<p style='color:#b0aea5'>Aucun article ce cycle.</p>"

    # Section erreurs
    errors_section = ""
    if errors:
        err_items = "".join(f"<li style='font-size:12px;color:#c0392b'>{e}</li>" for e in errors)
        errors_section = f"<div class='section'><h2>Erreurs</h2><ul>{err_items}</ul></div>"

    html = _REPORT_TEMPLATE.format(
        published=published_count,
        selected=selected_count,
        errors=len(errors),
        articles_html=articles_html,
        errors_section=errors_section,
        cycle_id=state["cycle_id"][:8],
        mode=state.get("mode", "semi"),
    )

    # Envoi Gmail
    try:
        from integrations.gmail_client import gmail_client
        import datetime
        today = datetime.date.today().strftime("%d/%m/%Y")
        await gmail_client.send_report(
            subject=f"/KORA — Rapport du {today} · {published_count} article(s) publié(s)",
            body_html=html,
        )
        logger.info("node_reporter_done", cycle_id=state["cycle_id"], published=published_count)
    except Exception as e:
        logger.error("reporter_gmail_failed", error=str(e))
        state["errors"].append(f"Reporter Gmail: {e}")

    await _update_cycle_db(state["cycle_id"], published_count, selected_count)

    return state
