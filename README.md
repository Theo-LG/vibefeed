# Veille IA

Agrégateur de veille IA personnel. Ingère des articles depuis une liste de blogs et flux RSS, les résume automatiquement via un LLM local (Ollama) ou une API, et les présente dans une interface web minimaliste avec filtre par source, séparation par jour, et digest hebdomadaire.

![dark mode](https://img.shields.io/badge/dark%20%2F%20light-mode-818cf8) ![backend](https://img.shields.io/badge/backend-ollama%20%7C%20anthropic%20%7C%20openai-orange)

## Ce que ça fait

- Récupère les derniers articles depuis des flux RSS et des pages scrapées (BS4)
- Résume chaque article en 2–3 bullets + tags + score de pertinence (1–5) via LLM
- Stocke tout dans SQLite
- Affiche un feed web avec filtres, dark/light mode et séparateurs de jour
- Génère un digest hebdomadaire "Week in AI" en français

## Lancer le projet

### 1. Prérequis

- Python 3.11+
- [Ollama](https://ollama.ai) installé et le modèle souhaité téléchargé (ou une clé API Anthropic/OpenAI)

```bash
ollama pull gemma4:e4b   # modèle par défaut
```

### 2. Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configuration

Copie `config/llm.yaml.example` en `config/llm.yaml` et adapte selon ton backend :

```yaml
backend: ollama   # ollama | anthropic | openai

ollama:
  model: gemma4:e4b
  context_window: 8192

anthropic:
  model: claude-haiku-4-5-20251001
  # api_key: sk-ant-...  (ou via ANTHROPIC_API_KEY)
```

Les sources à surveiller sont listées dans `url_list.md`.

### 4. Ingestion

```bash
python -m vibefeed.ingest
```

Récupère les nouveaux articles depuis toutes les sources, les résume et les stocke dans `vibefeed.db`. Les articles déjà présents sont ignorés.

### 5. Interface web

```bash
uvicorn vibefeed.app:app
```

Ouvre [http://localhost:8000](http://localhost:8000).

En mode développement (hot reload) :

```bash
uvicorn vibefeed.app:app --reload
```

## Structure

```
config/          Configuration LLM et tags
prompts/         Prompts summary.md et digest.md
templates/       Templates Jinja2 (index, weekly)
url_list.md      Liste des sources à surveiller
vibefeed/
  ingest.py      Pipeline d'ingestion
  app.py         Serveur FastAPI
  llm.py         Abstraction LLM (ollama / anthropic / openai)
  sources/       Fetchers par source (rss, jina, anthropic)
vibefeed.db      Base SQLite (générée à la première ingestion)
```

## Ajouter une source

Ajouter l'URL dans `url_list.md`. Si la source a un flux RSS, l'ajouter dans `vibefeed/sources/rss.py`. Sinon le scraper BS4 générique prend le relais — ou créer un scraper dédié dans `vibefeed/sources/`.

## Disclaimer

Ce projet est publié à titre éducatif et pour usage personnel uniquement. L'auteur n'est pas responsable de l'usage qui en est fait par des tiers. Il appartient à chaque utilisateur de s'assurer que son usage respecte les conditions d'utilisation des sites ciblés et la législation applicable dans son pays.
