# laya_run.py
# Usage : python laya_run.py [fichier_input.json] [--debug]
#
# Le fichier JSON d'entree contient :
#   {
#     "state":    { ...n'importe quel dictionnaire decrivant l'etat... },
#     "questions": {
#       "<id>": {
#         "type": "choice" | "score" | "noul",
#         "instructions": "...",
#         "criteria": ...   # dict option->description pour "choice",
#                           # LISTE de descriptions de niveaux pour "score",
#                           # absent pour "noul"
#       }, ...
#     }
#   }
#
# Le script est generique : il lit ce fichier, appelle Laya une seule fois,
# mesure les temps, puis met en forme chaque reponse selon le type declare
# dans le JSON (choice / score / noul).

import json
import sys
import time

from laya import Router

DEFAULT_INPUT = "questions.json"
VALID_TYPES = {"choice", "score", "noul"}


# ---------------------------------------------------------------- utilitaires
def bar(pct, width=24):
    """Barre ASCII proportionnelle a un pourcentage (0.0 - 1.0)."""
    filled = round(pct * width)
    return "#" * filled + "." * (width - filled)


def fmt_pct(p, digits=1):
    return f"{p * 100:.{digits}f} %".rjust(7)


def fmt_ms(ms):
    return f"{ms:.1f} ms" if ms < 1000 else f"{ms / 1000:.2f} s"


# ---------------------------------------------------------------- chargement
def load_input(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    state = data.get("state")
    questions = data.get("questions")
    if not isinstance(state, dict) or not state:
        raise ValueError("le JSON doit contenir une clé 'state' (dictionnaire non vide)")
    if not isinstance(questions, dict) or not questions:
        raise ValueError("le JSON doit contenir une clé 'questions' (dictionnaire non vide)")

    for qid, q in questions.items():
        qtype = q.get("type")
        if qtype not in VALID_TYPES:
            raise ValueError(f"question {qid!r} : 'type' doit être parmi {sorted(VALID_TYPES)}")
        if not q.get("instructions"):
            raise ValueError(f"question {qid!r} : 'instructions' est requis")
        if qtype == "score":
            crit = q.get("criteria")
            if not isinstance(crit, list) or not crit:
                raise ValueError(
                    f"question {qid!r} : une question 'score' prend 'criteria' comme une "
                    f"LISTE de descriptions de niveaux, index 0 en premier"
                )
        elif qtype == "choice":
            crit = q.get("criteria")
            if not isinstance(crit, dict) or not crit:
                raise ValueError(
                    f"question {qid!r} : une question 'choice' prend 'criteria' comme un "
                    f"dictionnaire option -> description"
                )
    return data, state, questions


# ---------------------------------------------------------------- formatage
def print_header(title):
    print()
    print("=" * 62)
    print(f" {title}")
    print("=" * 62)


def print_question(qid, qtype, instructions):
    print()
    print(f"[{qid}]  ({qtype})")
    print(f"  Q : {instructions}")


def print_choice(question, answer):
    print_question(answer["qid"], "choice", question["instructions"])
    decision = answer["choice"]
    conf = answer["answer_confidence"]
    print(f"  --> Décision : {decision}   (confiance : {fmt_pct(conf)})")
    print()
    probs = answer["probabilities"]
    for option in sorted(probs, key=probs.get, reverse=True):
        p = probs[option]
        mark = " <-- " if option == decision else "     "
        print(f"      {option:<14} {bar(p)} {fmt_pct(p)}{mark}")


def print_noul(question, answer):
    print_question(answer["qid"], "noul", question["instructions"])
    p_yes = answer["noul"]
    verdict = "OUI" if p_yes >= 0.5 else "NON"
    print(f"  --> Décision : {verdict}   (P(oui) : {fmt_pct(p_yes)})")
    print()
    print(f"      {'oui':<14} {bar(p_yes)} {fmt_pct(p_yes)}")
    print(f"      {'non':<14} {bar(1 - p_yes)} {fmt_pct(1 - p_yes)}")


def print_score(question, answer):
    print_question(answer["qid"], "score", question["instructions"])
    expected = answer["score"]
    probs = answer["probabilities"]            # clés str : '0', '1', ...
    legend = answer["legend"]
    best = max(probs, key=probs.get)
    print(f"  --> Niveau attendu : {expected:.2f} / {len(probs) - 1}")
    print(f"  --> Niveau le plus probable : {best} ({legend[best]})")
    print()
    for k in sorted(probs, key=int):
        p = probs[k]
        mark = " <-- " if k == best else "     "
        print(f"  {k}. {legend[k]:<34} {bar(p)} {fmt_pct(p)}{mark}")


FORMATTERS = {"choice": print_choice, "noul": print_noul, "score": print_score}


# ---------------------------------------------------------------- principal
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    debug = "--debug" in sys.argv
    path = args[0] if args else DEFAULT_INPUT

    data, state, questions = load_input(path)

    t0 = time.perf_counter()
    router = Router(preload=True)
    init_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    result = router.predict(state, questions)
    predict_ms = (time.perf_counter() - t1) * 1000
    per_question_ms = predict_ms / len(questions)

    if debug:
        print("Résultat brut Laya :")
        print(result)

    print_header("RESULTAT LAYA")
    print(f"  Fichier d'entrée  : {path}")
    print(f"  Modèle           : {result.get('model')}")
    print(f"  Questions         : {len(questions)}")
    print(f"  Temps de réponse  : {fmt_ms(predict_ms)} "
          f"({fmt_ms(per_question_ms)} / question)")

    answers = result["answers"]
    for qid, question in questions.items():
        answer = answers[qid]
        answer["qid"] = qid
        qtype = answer["type"]
        formatters = FORMATTERS.get(qtype)
        if formatters is None:
            print(f"\n[{qid}]  ({qtype}) : type inconnu, réponse brute : {answer}")
        else:
            formatters(question, answer)

    routing = result.get("routing", {})
    usage = result.get("usage", {})
    print_header("ROUTING, USAGE & TEMPS")
    if routing:
        print(f"  Modèle routé      : {routing.get('model')}")
        print(f"  Repo              : {routing.get('repo')}")
        print(f"  Raison            : {routing.get('reason')}")
    if usage:
        print(f"  Tokens d'entrée   : {usage.get('input_tokens')}")
        print(f"  Tokens de sortie  : {usage.get('output_tokens')}")
    print(f"  Init router       : {fmt_ms(init_ms)}")
    print(f"  Prédiction        : {fmt_ms(predict_ms)} "
          f"(1 passe pour {len(questions)} questions)")
    print()
    print("=" * 62)


if __name__ == "__main__":
    main()
