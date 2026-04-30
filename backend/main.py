from contextlib import asynccontextmanager
from pathlib import Path
import json
import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import BaseModel
from anthropic import Anthropic
from .ingestion import sync
from .rag import search_similar
from .scoring import score_opportunite, fiche_decision
from . import alert

scheduler = AsyncIOScheduler()

# Load DVF data and prompts
def load_dvf_data():
    dvf_path = Path(__file__).parent.parent / "data" / "dvf_quartiers.json"
    if dvf_path.exists():
        return json.loads(dvf_path.read_text())
    return {"quartiers": {}}

def load_prompt(filename):
    prompt_path = Path(__file__).parent.parent / "prompts" / filename
    if prompt_path.exists():
        return prompt_path.read_text()
    return ""

DVF_DATA = load_dvf_data()
SYSTEM_PROMPT = load_prompt("system.txt")
FICHE_DECISION_TEMPLATE = load_prompt("fiche_decision.txt")

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sync quotidienne automatique à 7h00
    scheduler.add_job(sync, "cron", hour=7, minute=0)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="NidBuyer API", version="0.1.0", lifespan=lifespan)


# --- Modèles ---

class ProfilAcheteur(BaseModel):
    intention: str          # "rp" | "rs" | "investissement" | "mixte"
    budget_max: float
    surface_min: float | None = None
    quartiers: list[str] = []
    nb_pieces_min: int | None = None
    description_libre: str = ""

class AlerteProfil(BaseModel):
    email: str
    profil: ProfilAcheteur


# --- Endpoints produit ---

@app.get("/biens")
def liste_biens(budget_max: float | None = None, surface_min: float | None = None, quartier: str | None = None):
    """Liste filtrée des biens disponibles."""
    # TODO : requêter la base de données / ChromaDB
    raise HTTPException(status_code=501, detail="Non implémenté")


@app.get("/biens/{bien_id}")
def detail_bien(bien_id: str):
    """Détail d'un bien + fiche décision LLM."""
    # TODO : récupérer le bien et appeler fiche_decision()
    raise HTTPException(status_code=501, detail="Non implémenté")


@app.post("/rechercher")
def rechercher(profil: ProfilAcheteur):
    """Profil acheteur → top 5 biens avec scores et fiches décision."""
    try:
        # Construct search query
        query_parts = [profil.description_libre] if profil.description_libre else []
        if profil.surface_min:
            query_parts.append(f"au moins {profil.surface_min}m²")
        if profil.nb_pieces_min:
            query_parts.append(f"{profil.nb_pieces_min} pièces")
        query = " ".join(query_parts) or f"bien {profil.intention}"

        # Search similar properties
        filtre = {"quartier": profil.quartiers[0]} if profil.quartiers else None
        biens_similaires = search_similar(query, n_results=5, filtre_meta=filtre)

        if not biens_similaires:
            raise HTTPException(status_code=404, detail="Aucun bien trouvé correspondant à votre profil")

        # Score each property
        resultats = []
        for bien in biens_similaires:
            quartier = bien.get("quartier", "")
            dvf_quartier = DVF_DATA["quartiers"].get(quartier, {})
            mediane = dvf_quartier.get("mediane_prix_m2", bien.get("prix_m2", 3000))

            # Score the opportunity
            scoring = score_opportunite(bien, mediane, profil.intention)

            # Generate decision sheet
            fiche_text = fiche_decision(bien, dvf_quartier)

            # Get LLM analysis
            profil_desc = f"Type: {profil.intention} | Budget: {profil.budget_max}€ | Surface min: {profil.surface_min}m²"
            prompt_content = FICHE_DECISION_TEMPLATE.format(
                fiche_structuree=fiche_text,
                description_annonce=bien.get("description", ""),
                profil=profil_desc,
            )

            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt_content}],
            )
            fiche_llm = response.content[0].text

            resultats.append({
                "bien": {
                    "type": bien.get("type"),
                    "surface": bien.get("surface"),
                    "prix": bien.get("prix"),
                    "quartier": bien.get("quartier"),
                    "url_source": bien.get("url_source"),
                    "source": bien.get("source"),
                },
                "scoring": scoring,
                "fiche_llm": fiche_llm,
            })

        return {"resultats": resultats, "count": len(resultats)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
def chat(question: str, profil: ProfilAcheteur | None = None):
    """Question libre → réponse LLM argumentée."""
    try:
        # Get RAG context
        biens_context = search_similar(question, n_results=3)

        # Build context text
        contexte = ""
        sources = []
        if biens_context:
            contexte = "Biens pertinents du marché :\n"
            for bien in biens_context:
                contexte += f"- {bien.get('type')} {bien.get('surface')}m² à {bien.get('prix')}€ ({bien.get('quartier')})\n"
                if bien.get("url_source"):
                    sources.append(bien["url_source"])

        # Call Claude with RAG context
        prompt_content = f"""{contexte}

Question de l'acheteur : {question}

Réponds de manière factuelle et concise, en t'appuyant sur les données du marché toulonnais."""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt_content}],
        )

        return {
            "reponse": response.content[0].text,
            "sources": list(set(sources)),  # Remove duplicates
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/alerte")
def creer_alerte(alerte: AlerteProfil):
    """Sauvegarder un profil pour recevoir des alertes sur nouveaux biens."""
    try:
        alert.sauvegarder_profil(alerte.email, alerte.profil.dict())
        return {"status": "alerte créée", "email": alerte.email}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/marche/quartiers")
def marche_quartiers():
    """Médiane DVF 2024-2026 par quartier de Toulon."""
    return DVF_DATA


# --- Endpoint admin ---

@app.post("/admin/sync")
def admin_sync(background_tasks: BackgroundTasks, dry_run: bool = False):
    """
    Déclenche manuellement une synchronisation des annonces.
    Tourne en arrière-plan pour ne pas bloquer la réponse.

    Args:
        dry_run: si True, scrape sans indexer (pour tester)
    """
    background_tasks.add_task(sync, dry_run=dry_run)
    return {"status": "sync lancée en arrière-plan", "dry_run": dry_run}


@app.get("/admin/status")
def admin_status():
    """Statut de la base : nombre d'annonces indexées, dernière sync."""
    from pathlib import Path
    from .rag import get_collection
    try:
        n = get_collection().count()
    except Exception:
        n = 0
    last_sync = Path("data/.last_sync")
    return {
        "annonces_indexees": n,
        "derniere_sync": last_sync.read_text() if last_sync.exists() else "jamais",
    }
