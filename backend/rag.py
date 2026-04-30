"""
Indexation et recherche sémantique sur les annonces immobilières.
Utilise ChromaDB comme base vectorielle.
"""
import chromadb
from chromadb.utils import embedding_functions


# TODO : choisir le modèle d'embedding (all-MiniLM-L6-v2, text-embedding-3-small, etc.)
# Justifier votre choix dans le README (vitesse vs qualité, coût, langue)
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

_client = chromadb.PersistentClient(path="./chroma_db")
_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)


def get_collection():
    return _client.get_or_create_collection(
        name="annonces_toulon",
        embedding_function=_ef,
    )


def indexer_annonces(annonces: list[dict]) -> None:
    """
    Indexe une liste d'annonces dans ChromaDB.

    Chaque annonce doit contenir au minimum :
    id, type, surface, quartier, prix, description
    """
    collection = get_collection()
    ids = [str(a["id_source"]) for a in annonces]
    documents = [
        f"{a['type']} {a.get('surface', '')}m² {a['quartier']} {a.get('description', '')}"
        for a in annonces
    ]
    metadatas = [
        {
            "surface": float(a.get("surface", 0)),
            "prix": float(a.get("prix", 0)),
            "quartier": a.get("quartier", ""),
            "type": a.get("type", ""),
            "url_source": a.get("url_source", ""),
            "source": a.get("source", ""),
        }
        for a in annonces
    ]
    collection.add(ids=ids, documents=documents, metadatas=metadatas)


def search_similar(query: str, n_results: int = 5, filtre_meta: dict | None = None) -> list[dict]:
    """
    Recherche sémantique : retourne les n_results biens les plus proches de la requête.

    Args:
        query: description en langage naturel du bien recherché
        n_results: nombre de résultats à retourner
        filtre_meta: filtres optionnels sur les métadonnées (ex: {"quartier": "Mourillon"})

    Returns:
        Liste de dicts avec les métadonnées des biens
    """
    collection = get_collection()
    kwargs = {"query_texts": [query], "n_results": n_results}
    if filtre_meta:
        kwargs["where"] = filtre_meta
    results = collection.query(**kwargs)

    biens = []
    if results["metadatas"] and results["metadatas"][0]:
        for meta, distance in zip(results["metadatas"][0], results["distances"][0]):
            biens.append({**meta, "distance": float(distance)})
    return biens
