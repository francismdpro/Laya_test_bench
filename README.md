# Laya Test Bench

Banc de test pour [Laya](https://github.com/NandhaKishorM/laya), le moteur de décision Système 1 de Convai Innovations : un script en ligne de commande et une interface web pour expérimenter les trois primitives de questions typées (`choice`, `score`, `noul`) sur des états de natures très différentes (emails, tickets, JSON, code, bulletins…).

Laya répond à toutes les questions en **une seule passe non-autoregressive** avec des probabilités calibrées, dans plus de 100 langues. Les poids du modèle sont diffusés sous licence Apache 2.0.

<img width="1920" height="1040" alt="image" src="https://github.com/user-attachments/assets/5ea0271d-b04a-43f9-8a9e-43072dce0453" />


## Fonctionnalités

- `laya_run.py` : script CLI générique — lit n'importe quel fichier JSON `{state, questions}`, appelle Laya, mesure les temps et met en forme les réponses selon leur type.
- `app_laya.py` : interface web (Flask) pour éditer les fichiers d'entrée, exécuter des prédictions et visualiser les résultats (distributions en barres, routing, temps de réponse, tokens).
- 10 fichiers d'exemple couvrant des domaines variés (météo, IT, bourse, RH, modération, cuisine, sport, hôtellerie, revue de code, logistique).
- Validation systématique des fichiers d'entrée avec des messages d'erreur explicites (voir [Dépannage](#dépannage)).

## Installation

Python 3.10+ recommandé.

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows (bash : source .venv/bin/activate)
pip install -r requirements.txt
```

Au premier appel, les checkpoints `convaiinnovations/laya` sont téléchargés automatiquement (comptez quelques centaines de Mo).

## Démarrage rapide

### En ligne de commande

```bash
python laya_run.py 01_meteo.json               # exécute un fichier
python laya_run.py mon_fichier.json --debug   # + affichage du résultat brut
```

### Interface web

```bash
python app_laya.py
```

Puis ouvrir http://127.0.0.1:5000 dans le navigateur.

## Format des fichiers d'entrée

Chaque fichier JSON décrit un état et des questions typées :

```json
{
  "state": {
    "subject": "Facturation - facture en double",
    "body": "Bonjour, je constate que j'ai été facturé deux fois..."
  },
  "questions": {
    "queue": {
      "type": "choice",
      "instructions": "Dans quel service doit aller ce ticket ?",
      "criteria": {
        "billing": "Paiements, factures, remboursements.",
        "technical": "Bugs, erreurs techniques, indisponibilités."
      }
    },
    "refund_requested": {
      "type": "noul",
      "instructions": "Le client demande-t-il explicitement un remboursement ?"
    },
    "urgency": {
      "type": "score",
      "instructions": "Évaluer le niveau d'urgence de ce ticket.",
      "criteria": [
        "Pas urgent du tout.",
        "Peu urgent.",
        "Moyennement urgent.",
        "Urgent.",
        "Très urgent, à traiter immédiatement."
      ]
    }
  }
}
```

Règles par type de question :

| Type | `criteria` | Réponse |
|---|---|---|
| `choice` | dictionnaire `option → description` | option retenue + distribution sur toutes les options |
| `score` | **liste ordonnée** de descriptions de niveaux (2 à 10, index 0 = premier niveau) | niveau attendu (valeur continue) + distribution sur les niveaux |
| `noul` | absent | probabilité que la réponse soit oui |

## Interprétation des résultats

Le résultat de `predict` est structuré ainsi :

```python
result["answers"][qid]           # réponse d'une question
  ["choice" | "score" | "noul"]  # la réponse elle-même, sous la clé du type
  ["probabilities"]              # distribution complète
  ["answer_confidence"]          # probabilité de la réponse renvoyée (pour le gating)
  ["legend"]                     # score uniquement : indice de niveau -> description
result["routing"]                # checkpoint choisi et raison (ex. 'fr' -> multilingual)
result["usage"]                  # tokens d'entrée / sortie
```

Points d'attention :

- Pour `score`, les clés de `probabilities` et `legend` sont des **chaînes** (`"0"`, `"1"`, …), pas des entiers.
- `answer_confidence` est le nombre à seuiller pour décider d'agir ou non ; `confidence` est la confiance globale de la prédiction.
- Sur le checkpoint multilingue, un léger biais de position fait que les questions `score` sélectionnent rarement le premier niveau : validez sur vos propres données.

## Fichiers d'exemple

| Fichier | Domaine | Démonstration |
|---|---|---|
| `01_meteo.json` | Météo | classification d'alerte + gravité sur 5 niveaux |
| `02_informatique.json` | IT / DevOps | diagnostic parmi 5 causes, priorité d'intervention |
| `03_bourse.json` | Finance | sentiment boursier, ampleur de mouvement de cours |
| `04_recrutement.json` | RH | state structuré (CV JSON) |
| `05_moderation.json` | Modération | arbitrage de sanction |
| `06_cuisine.json` | Cuisine | difficulté technique d'une recette |
| `07_sport.json` | Sport | question `noul` à réponse négative attendue |
| `08_hotel.json` | Hôtellerie | 5 catégories de réclamation |
| `09_code_review.json` | Revue de code | state contenant du code source |
| `10_logistique.json` | Logistique | timeline d'événements à interpréter |

## Dépannage

**`ValueError: a score question takes 'criteria' as a list of level descriptions`**
Une question `score` doit fournir `criteria` en **liste** ordonnée de descriptions, pas un bloc `scale`/`labels`.

**`KeyError: 'queue'`**
Les réponses sont imbriquées : `result["answers"]["queue"]`, pas `result["queue"]`.

**Clés de type entier dans `probabilities` d'un score.**
Les clés sont des chaînes (`"0"`, `"1"`, …) : convertissez-les avec `int(k)` avant tri ou indexation.

## Structure du projet

```
.
├── laya_run.py        # CLI générique
├── app_laya.py        # interface web Flask
├── requirements.txt
├── README.md
└── *.json             # fichiers d'exemple (state + questions)
```

## Références

- [Laya sur GitHub](https://github.com/NandhaKishorM/laya) — code source de la bibliothèque
- [convaiinnovations/laya sur Hugging Face](https://huggingface.co/convaiinnovations/laya) — checkpoints
