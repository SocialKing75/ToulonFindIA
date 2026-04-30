"""
Interface acheteur SuperIA — Streamlit
"""
import streamlit as st
import requests
import json
from datetime import datetime

API_URL = "http://localhost:8000"

# Configure page
st.set_page_config(
    page_title="SuperIA",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .stMetric {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
    }
    .result-card {
        border: 2px solid #e0e0e0;
        border-radius: 0.5rem;
        padding: 1.5rem;
        margin: 1rem 0;
        background: white;
    }
    .score-badge-positive {
        color: #28a745;
        font-weight: bold;
        font-size: 1.2em;
    }
    .score-badge-neutral {
        color: #ffc107;
        font-weight: bold;
        font-size: 1.2em;
    }
    .score-badge-negative {
        color: #dc3545;
        font-weight: bold;
        font-size: 1.2em;
    }
    .info-pill {
        display: inline-block;
        background: #e3f2fd;
        padding: 0.5rem 1rem;
        border-radius: 1rem;
        margin: 0.5rem 0.5rem 0.5rem 0;
        font-size: 0.9rem;
    }
    .stButton > button {
        background: linear-gradient(135deg, #2563EB 0%, #1d4ed8 100%);
        color: white;
        border: none;
        border-radius: 0.5rem;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
    }
</style>
""", unsafe_allow_html=True)

st.title("SuperIA — Votre assistant IA pour l'achat immobilier à Toulon")
st.markdown("*Trouvez les meilleures opportunités immobilières grâce à l'analyse de données DVF et à l'IA*")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Sidebar: Buyer profile ---
with st.sidebar:
    st.header("📋 Mon profil d'acheteur")

    intention = st.selectbox(
        "Je cherche",
        ["rp", "rs", "investissement", "mixte"],
        format_func=lambda x: {
            "rp": "Résidence principale",
            "rs": "Résidence secondaire",
            "investissement": "Investissement locatif",
            "mixte": "Immeuble mixte",
        }[x],
    )

    budget = st.number_input(
        "Budget max (€)",
        min_value=50_000,
        max_value=2_000_000,
        value=300_000,
        step=10_000
    )

    surface_min = st.number_input(
        "Surface min (m²)",
        min_value=0,
        max_value=300,
        value=0
    )

    nb_pieces_min = st.number_input(
        "Nombre de pièces min",
        min_value=0,
        max_value=10,
        value=0
    )

    quartiers = st.multiselect(
        "Quartiers préférés (optionnel)",
        [
            "Mourillon", "Centre-Ville", "La Seyne", "Ouest",
            "Est", "Mayol", "Aiguillette", "Val-Dôme"
        ],
        help="Laisser vide pour rechercher dans tous les quartiers"
    )

    description = st.text_area(
        "Décrivez votre bien idéal",
        placeholder="Ex: T3 calme, proche mer, lumineux, parking...",
        height=80
    )

    st.divider()
    st.caption("Vos critères seront utilisés pour trouver les meilleures opportunités")

# --- Main content ---
tab_recherche, tab_chat, tab_marche = st.tabs(["Rechercher", "Chat", "Marché"])

# --- TAB 1: RECHERCHE ---
with tab_recherche:
    st.header("Trouver mes biens")
    st.write("Analysez les meilleures opportunités du marché toulonnais selon votre profil.")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("Cliquez sur **Trouver mes biens** pour lancer la recherche")
    with col2:
        search_button = st.button("Trouver mes biens", type="primary", key="search_btn")

    if search_button:
        if budget <= 0 or (surface_min == 0 and not description):
            st.warning("Veuillez définir un budget et (une surface OU une description)")
        else:
            with st.spinner("Recherche en cours... Cela peut prendre quelques secondes"):
                try:
                    payload = {
                        "intention": intention,
                        "budget_max": budget,
                        "surface_min": surface_min if surface_min > 0 else None,
                        "nb_pieces_min": nb_pieces_min if nb_pieces_min > 0 else None,
                        "quartiers": quartiers if quartiers else [],
                        "description_libre": description,
                    }

                    response = requests.post(
                        f"{API_URL}/rechercher",
                        json=payload,
                        timeout=30
                    )

                    if response.status_code == 200:
                        data = response.json()
                        resultats = data.get("resultats", [])

                        if not resultats:
                            st.info("Aucun bien trouvé correspondant à votre profil. Essayez d'élargir vos critères.")
                        else:
                            st.success(f"✅ {len(resultats)} bien(s) trouvé(s)")

                            for idx, resultat in enumerate(resultats, 1):
                                bien = resultat["bien"]
                                scoring = resultat["scoring"]
                                fiche_llm = resultat["fiche_llm"]

                                with st.container(border=True):
                                    # Header with score
                                    col1, col2, col3 = st.columns([2, 2, 1])

                                    with col1:
                                        st.markdown(f"### #{idx} — {bien['type']} • {bien['quartier']}")

                                    with col2:
                                        st.metric("Score opportunité", f"{scoring['score']}", f"{scoring['ecart_pct']:+.1f}%")

                                    with col3:
                                        st.markdown(f"<div style='text-align: center; font-size: 1.5em; margin-top: 0.5rem'>{scoring['label']}</div>", unsafe_allow_html=True)

                                    st.divider()

                                    # Property details
                                    col1, col2, col3, col4 = st.columns(4)
                                    with col1:
                                        st.metric("Prix", f"{bien['prix']:,.0f}€")
                                    with col2:
                                        st.metric("Surface", f"{bien['surface']:.0f}m²")
                                    with col3:
                                        st.metric("Prix/m²", f"{scoring['prix_m2']:.0f}€")
                                    with col4:
                                        st.metric("Source", bien['source'] or "N/A")

                                    st.divider()

                                    # LLM analysis in expander
                                    with st.expander("📋 Analyse détaillée du bien", expanded=(idx == 1)):
                                        st.markdown(fiche_llm)

                                    # Link to property
                                    if bien.get("url_source"):
                                        st.markdown(f"[🔗 Voir l'annonce]({bien['url_source']})")

                    else:
                        error_detail = response.json().get("detail", "Erreur inconnue")
                        st.error(f"❌ Erreur serveur : {error_detail}")

                except requests.exceptions.Timeout:
                    st.error("❌ Délai d'attente dépassé. Le serveur met trop de temps à répondre.")
                except requests.exceptions.ConnectionError:
                    st.error(f"❌ Impossible de se connecter au serveur API ({API_URL}). Vérifiez que le backend est lancé.")
                except Exception as e:
                    st.error(f"❌ Erreur : {str(e)}")

# --- TAB 2: CHAT ---
with tab_chat:
    st.header("Chat avec SuperIA")
    st.write("Posez vos questions sur le marché immobilier toulonnais. SuperIA analysera les données réelles pour vous répondre.")

    # Chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    question = st.chat_input("Votre question...", key="chat_input")

    if question:
        # Display user message
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        # Get response
        with st.spinner("SuperIA réfléchit..."):
            try:
                response = requests.post(
                    f"{API_URL}/chat",
                    json={"question": question},
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    reponse = data.get("reponse", "")
                    sources = data.get("sources", [])

                    # Display assistant response
                    with st.chat_message("assistant"):
                        st.markdown(reponse)

                        if sources:
                            st.divider()
                            st.caption("📚 Sources citées :")
                            for source in sources[:3]:
                                st.markdown(f"- [{source}]({source})")

                    # Store in session
                    st.session_state.messages.append({"role": "assistant", "content": reponse})

                else:
                    error_detail = response.json().get("detail", "Erreur inconnue")
                    st.error(f"❌ Erreur : {error_detail}")

            except requests.exceptions.ConnectionError:
                st.error(f"❌ Impossible de se connecter au serveur API ({API_URL})")
            except Exception as e:
                st.error(f"❌ Erreur : {str(e)}")

# --- TAB 3: MARCHÉ ---
with tab_marche:
    st.header("État du marché toulonnais")
    st.write("Consultez les médianes DVF par quartier pour comprendre l'évolution du marché.")

    marche_button = st.button("📊 Charger les médianes DVF par quartier", type="primary", key="marche_btn")

    if marche_button:
        with st.spinner("Récupération des données de marché..."):
            try:
                response = requests.get(
                    f"{API_URL}/marche/quartiers",
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    quartiers_data = data.get("quartiers", {})

                    if quartiers_data:
                        st.success(f"✅ Données chargées — {len(quartiers_data)} quartier(s)")

                        # Display as table
                        table_data = []
                        for quartier, info in quartiers_data.items():
                            table_data.append({
                                "Quartier": quartier,
                                "Médiane €/m²": f"{info.get('mediane_prix_m2', 0):.0f}",
                                "Ventes 2024": info.get("volume_ventes_2024", "-"),
                                "Évolution 1 an": f"{info.get('evolution_1an_pct', 0):+.1f}%",
                                "Min €/m²": f"{info.get('prix_min_m2', 0):.0f}",
                                "Max €/m²": f"{info.get('prix_max_m2', 0):.0f}",
                            })

                        st.dataframe(
                            table_data,
                            use_container_width=True,
                            hide_index=True
                        )

                        st.divider()

                        # Summary chart
                        st.subheader("💹 Médiane par quartier")
                        chart_data = {row["Quartier"]: int(row["Médiane €/m²"].replace(",", "")) for row in table_data}

                        st.bar_chart(chart_data)

                    else:
                        st.warning("⚠️ Aucune donnée de marché disponible")

                else:
                    st.error(f"❌ Erreur serveur : {response.json().get('detail', 'Erreur inconnue')}")

            except requests.exceptions.ConnectionError:
                st.error(f"❌ Impossible de se connecter au serveur API ({API_URL})")
            except Exception as e:
                st.error(f"❌ Erreur : {str(e)}")

# --- Footer ---
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("📍 Spécialisé sur Toulon")
with col3:
    st.caption(f"🔄 Données DVF 2024-2026")