from typing import TypedDict, List, Optional, Annotated
from pydantic import BaseModel, Field
import operator


class ArticleKORA(BaseModel):
    """Article structuré produit par le nœud writer."""
    titre: str
    chapeau: str
    corps: str
    meta_description: str = Field(..., max_length=160)
    mots_cles: List[str] = Field(default_factory=list)
    categorie_wp_id: int = 1
    source_url: str
    source_nom: str
    image_prompt: str
    llm_provider_used: str = ""
    llm_model_used: str = ""


class KoraState(TypedDict):
    """État global du graphe LangGraph KORA."""
    # Contexte du cycle
    mode: str                               # "auto" | "semi"
    cycle_id: str

    # Données collectées
    raw_sources: List[dict]                 # Articles bruts (Tavily + Firecrawl)
    selected_articles: List[dict]           # Articles sélectionnés pour rédaction

    # Article en cours de traitement
    current_article: Optional[dict]
    generated_article: Optional[dict]       # dict sérialisable d'ArticleKORA
    image_url: Optional[str]
    wp_media_id: Optional[int]
    wp_post_id: Optional[int]

    # Compteurs & logs
    published_count: int
    errors: List[str]

    # Contrôle HITL
    hitl_approved: bool

    # Index de progression (pour boucle article par article)
    article_index: int
