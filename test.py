# test_laya.py
from laya import Router

# 1) Créer le router et précharger les modèles
router = Router(preload=True)

# 2) "state" = l'état sur lequel Laya va prendre des décisions (email, ticket, JSON…)
state = {
    "subject": "Facturation - facture en double",
    "body": (
        "Bonjour,\n\n"
        "Je constate que j'ai été facturé deux fois pour la même commande. "
        "Merci de me rembourser la facture en trop aujourd'hui.\n\n"
        "Cordialement,\n"
        "Jean Dupont"
    ),
}

# 3) "questions" = prompts typés (choice, score, noul)
# Pour "score" : criteria est une LISTE ordonnée de descriptions de niveaux,
# l'indice 0 étant le premier niveau.
questions = {
    "queue": {
        "type": "choice",
        "instructions": "Dans quel service doit aller ce ticket ?",
        "criteria": {
            "billing": "Paiements, factures, remboursements.",
            "technical": "Bugs, erreurs techniques, indisponibilités.",
            "other": "Tout le reste.",
        },
    },
    "refund_requested": {
        "type": "noul",
        "instructions": "Le client demande-t-il explicitement un remboursement ?",
    },
    "urgency": {
        "type": "score",
        "instructions": "Évaluer le niveau d'urgence de ce ticket.",
        "criteria": [
            "Pas urgent du tout.",
            "Peu urgent.",
            "Moyennement urgent.",
            "Urgent.",
            "Très urgent, à traiter immédiatement.",
        ],
    },
}

# 4) Appel au modèle : une passe non-autoregressive qui renvoie toutes les réponses typées
result = router.predict(state, questions)


# 5) Mise en forme de la sortie
def bar(pct, width=24):
    """Barre de progression ASCII proportionnelle à un pourcentage (0-1)."""
    filled = round(pct * width)
    return "#" * filled + "." * (width - filled)


def fmt_pct(p, digits=1):
    return f"{p * 100:.{digits}f} %".rjust(7)


def print_header(title):
    print()
    print("=" * 62)
    print(f" {title}")
    print("=" * 62)


def print_question(qid, qtype, instructions):
    print()
    print(f"[{qid}]  ({qtype})")
    print(f"  Q : {instructions}")


def print_choice(qid, question, answer):
    print_question(qid, "choice", question["instructions"])
    decision = answer["choice"]
    conf = answer["answer_confidence"]
    print(f"  --> Décision : {decision}   (confiance : {fmt_pct(conf)})")
    print()
    probs = answer["probabilities"]
    for option in sorted(probs, key=probs.get, reverse=True):
        p = probs[option]
        mark = " <-- " if option == decision else "     "
        print(f"      {option:<14} {bar(p)} {fmt_pct(p)}{mark}")


def print_noul(qid, question, answer):
    print_question(qid, "noul", question["instructions"])
    p_yes = answer["noul"]
    verdict = "OUI" if p_yes >= 0.5 else "NON"
    print(f"  --> Décision : {verdict}   (P(oui) : {fmt_pct(p_yes)})")
    print()
    print(f"      {'oui':<14} {bar(p_yes)} {fmt_pct(p_yes)}")
    print(f"      {'non':<14} {bar(1 - p_yes)} {fmt_pct(1 - p_yes)}")


def print_score(qid, question, answer):
    print_question(qid, "score", question["instructions"])
    expected = answer["score"]
    probs = answer["probabilities"]            # clés str : '0', '1', ...
    legend = answer["legend"]
    best = max(probs, key=probs.get)
    n_levels = len(probs)
    print(f"  --> Niveau attendu : {expected:.2f} / {n_levels - 1}")
    print(f"  --> Niveau le plus probable : {best} ({legend[best]})")
    print()
    for k in sorted(probs, key=int):
        p = probs[k]
        mark = " <-- " if k == best else "     "
        print(f"  {k}. {legend[k]:<34} {bar(p)} {fmt_pct(p)}{mark}")


def print_routing_and_usage(result):
    routing = result.get("routing", {})
    usage = result.get("usage", {})
    print_header("ROUTING & USAGE")
    if routing:
        print(f"  Modèle routé      : {routing.get('model')}")
        print(f"  Repo              : {routing.get('repo')}")
        print(f"  Raison            : {routing.get('reason')}")
    if usage:
        print(f"  Tokens d'entrée   : {usage.get('input_tokens')}")
        print(f"  Tokens de sortie  : {usage.get('output_tokens')}")


def main():
    answers = result["answers"]

    print_header("RESULTAT LAYA")
    print(f"  Modèle            : {result.get('model')}")
    print(f"  Sujet analysé     : {state['subject']}")
    print(f"  Questions         : {len(questions)}")

    for qid, question in questions.items():
        answer = answers[qid]
        qtype = answer["type"]
        if qtype == "choice":
            print_choice(qid, question, answer)
        elif qtype == "noul":
            print_noul(qid, question, answer)
        elif qtype == "score":
            print_score(qid, question, answer)

    print_routing_and_usage(result)
    print()
    print("=" * 62)


main()
