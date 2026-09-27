# app_laya.py
# Interface web pour tester Laya : éditer les fichiers JSON d'entrée,
# lancer une prédiction et visualiser les résultats formatés.
#
# Installation : pip install flask laya
# Lancement    : python app_laya.py
# Ouverture    : http://127.0.0.1:5000
#
# Les fichiers JSON (state + questions) sont lus/écrits dans le dossier
# courant (ou LAYA_DATA_DIR si défini).

import json
import os
import threading
import time

from flask import Flask, jsonify, request

from laya import Router

DATA_DIR = os.environ.get("LAYA_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
VALID_TYPES = {"choice", "score", "noul"}

app = Flask(__name__)

_router = None
_predict_lock = threading.Lock()


def get_router():
    """Charge le Router une seule fois (télécharge les checkpoints au 1er appel)."""
    global _router
    if _router is None:
        _router = Router(preload=True)
    return _router


def safe_name(name):
    base = os.path.basename(name or "")
    if not base.endswith(".json") or base.startswith("."):
        raise ValueError("nom de fichier invalide (attendu : xxx.json)")
    return base


def validate_payload(data):
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
            if not isinstance(q.get("criteria"), list) or not q["criteria"]:
                raise ValueError(f"question {qid!r} : 'score' exige 'criteria' en liste de niveaux")
        elif qtype == "choice":
            if not isinstance(q.get("criteria"), dict) or not q["criteria"]:
                raise ValueError(f"question {qid!r} : 'choice' exige 'criteria' en dict option -> description")
    return state, questions


# ------------------------------------------------------------------ API
@app.get("/api/files")
def list_files():
    files = sorted(
        f for f in os.listdir(DATA_DIR)
        if f.endswith(".json") and os.path.isfile(os.path.join(DATA_DIR, f))
    )
    return jsonify({"files": files})


@app.get("/api/file/<name>")
def read_file(name):
    try:
        base = safe_name(name)
        with open(os.path.join(DATA_DIR, base), encoding="utf-8") as f:
            return jsonify({"name": base, "content": f.read()})
    except FileNotFoundError:
        return jsonify({"error": f"fichier introuvable : {name}"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/file/<name>")
def write_file(name):
    try:
        base = safe_name(name)
        content = (request.get_json(force=True) or {}).get("content", "")
        data = json.loads(content)          # refuse d'écrire du JSON invalide
        validate_payload(data)
        with open(os.path.join(DATA_DIR, base), "w", encoding="utf-8") as f:
            f.write(content)
        return jsonify({"ok": True})
    except json.JSONDecodeError as e:
        return jsonify({"error": f"JSON invalide : {e}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.delete("/api/file/<name>")
def delete_file(name):
    try:
        base = safe_name(name)
        os.remove(os.path.join(DATA_DIR, base))
        return jsonify({"ok": True})
    except (FileNotFoundError, ValueError):
        return jsonify({"error": "fichier introuvable ou nom invalide"}), 404


@app.post("/api/predict")
def predict():
    payload = request.get_json(force=True) or {}
    try:
        if payload.get("content"):
            data = json.loads(payload["content"])
        elif payload.get("name"):
            with open(os.path.join(DATA_DIR, safe_name(payload["name"])), encoding="utf-8") as f:
                data = json.load(f)
        else:
            return jsonify({"error": "fournir 'name' ou 'content'"}), 400

        state, questions = validate_payload(data)

        t0 = time.perf_counter()
        router = get_router()                       # chargement éventuel (non chronométré)
        loaded_ms = (time.perf_counter() - t0) * 1000

        with _predict_lock:
            t1 = time.perf_counter()
            result = router.predict(state, questions)
            elapsed_ms = (time.perf_counter() - t1) * 1000

        return jsonify({
            "ok": True,
            "elapsed_ms": elapsed_ms,
            "loaded_ms": loaded_ms,
            "n_questions": len(questions),
            "result": result,
        })
    except FileNotFoundError:
        return jsonify({"error": "fichier introuvable"}), 404
    except (json.JSONDecodeError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # erreur du modèle : renvoyée telle quelle à l'UI
        return jsonify({"error": f"{type(e).__name__} : {e}"}), 500


# ------------------------------------------------------------------ UI
@app.get("/")
def index():
    return PAGE


PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Laya Test Bench</title>
<style>
  :root {
    --bg: #0f1218; --panel: #171c26; --panel2: #1d2431; --border: #2a3345;
    --text: #dce3ee; --muted: #8b96a8; --accent: #4f9cf9; --ok: #3ecf8e;
    --warn: #f5b74f; --err: #ef6b73;
  }
  * { box-sizing: border-box; }
  body { margin:0; font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg);
         color: var(--text); height:100vh; display:flex; flex-direction:column; }
  header { display:flex; align-items:center; gap:14px; padding:10px 18px;
           background:var(--panel); border-bottom:1px solid var(--border); }
  header h1 { font-size:16px; margin:0; }
  header .dot { width:10px; height:10px; border-radius:50%; background:var(--muted); }
  header .dot.loaded { background: var(--ok); }
  main { flex:1; display:flex; min-height:0; }
  #sidebar { width:230px; background:var(--panel); border-right:1px solid var(--border);
             display:flex; flex-direction:column; }
  #sidebar h2 { font-size:11px; text-transform:uppercase; color:var(--muted);
                padding:12px 14px 6px; margin:0; letter-spacing:.08em; }
  #filelist { flex:1; overflow-y:auto; }
  .file { padding:8px 14px; cursor:pointer; font-size:13px; border-left:3px solid transparent; }
  .file:hover { background:var(--panel2); }
  .file.active { background:var(--panel2); border-left-color:var(--accent); color:#fff; }
  .file .del { float:right; color:var(--muted); visibility:hidden; cursor:pointer; }
  .file:hover .del { visibility:visible; }
  .file .del:hover { color:var(--err); }
  #sidebar .actions { padding:10px; border-top:1px solid var(--border); }
  button { background:var(--panel2); color:var(--text); border:1px solid var(--border);
           border-radius:6px; padding:7px 12px; cursor:pointer; font-size:13px; }
  button:hover { border-color:var(--accent); }
  button.primary { background:var(--accent); border-color:var(--accent); color:#08111f; font-weight:600; }
  button:disabled { opacity:.5; cursor:wait; }
  #editor-col { flex:1; display:flex; flex-direction:column; border-right:1px solid var(--border); min-width:0; }
  #editor-bar { display:flex; gap:8px; align-items:center; padding:8px 12px;
                background:var(--panel); border-bottom:1px solid var(--border); }
  #editor-bar .name { font-size:13px; color:var(--muted); margin-right:auto;
                      font-family:Consolas,monospace; }
  #editor { flex:1; width:100%; resize:none; border:0; padding:12px; background:var(--bg);
            color:#cfe3b8; font-family:Consolas,'Courier New',monospace; font-size:13px;
            line-height:1.5; outline:none; }
  #result-col { flex:1.2; overflow-y:auto; padding:16px; min-width:0; }
  .card { background:var(--panel); border:1px solid var(--border); border-radius:10px;
          padding:14px 16px; margin-bottom:14px; }
  .card h3 { margin:0 0 10px; font-size:14px; color:#fff; }
  .card h3 .type { color:var(--muted); font-weight:400; font-size:12px; }
  .meta { display:grid; grid-template-columns:auto 1fr; gap:3px 16px; font-size:13px; margin:0; }
  .meta dt { color:var(--muted); }
  .meta dd { margin:0; }
  .decision { font-size:15px; margin:8px 0; padding:8px 12px; border-radius:8px;
              background:var(--panel2); border:1px solid var(--border); }
  .decision b { color:var(--ok); }
  .bar-row { display:flex; align-items:center; gap:8px; font-size:12.5px; margin:4px 0; }
  .bar-label { width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .bar-track { flex:1; height:14px; background:var(--panel2); border-radius:4px; overflow:hidden; }
  .bar-fill { height:100%; background:var(--accent); border-radius:4px; }
  .bar-row.best .bar-fill { background:var(--ok); }
  .bar-row.best .bar-label { color:#fff; font-weight:600; }
  .bar-pct { width:60px; text-align:right; color:var(--muted); font-variant-numeric:tabular-nums; }
  .q-instr { color:var(--muted); font-size:12.5px; margin:2px 0 6px; }
  .badge { display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px;
           background:var(--panel2); color:var(--muted); margin-left:8px; }
  #status { margin-left:auto; font-size:12px; color:var(--muted); }
  #error { display:none; background:#3a171b; border:1px solid var(--err); color:var(--err);
           border-radius:8px; padding:10px 14px; margin-bottom:14px; font-size:13px;
           white-space:pre-wrap; }
  .empty { color:var(--muted); font-size:13px; padding:30px; text-align:center; }
</style>
</head>
<body>
<header>
  <h1>Laya Test Bench</h1>
  <span class="dot" id="model-dot"></span>
  <span id="model-name" style="font-size:12px;color:var(--muted)">modèle non chargé</span>
  <span id="status"></span>
</header>
<main>
  <div id="sidebar">
    <h2>Fichiers d'entrée</h2>
    <div id="filelist"></div>
    <div class="actions">
      <button onclick="newFile()" style="width:100%">+ Nouveau fichier</button>
    </div>
  </div>
  <div id="editor-col">
    <div id="editor-bar">
      <span class="name" id="current-name">&mdash;</span>
      <button onclick="formatJson()">Formater</button>
      <button onclick="saveFile()">Enregistrer</button>
      <button class="primary" onclick="run()" id="btn-run">Exécuter</button>
    </div>
    <textarea id="editor" spellcheck="false" placeholder="Sélectionnez ou créez un fichier JSON..."></textarea>
  </div>
  <div id="result-col">
    <div id="error"></div>
    <div id="results"><div class="empty">Les résultats appara&icirc;tront ici apr&egrave;s ex&eacute;cution.</div></div>
  </div>
</main>
<script>
let current = null;

const $ = id => document.getElementById(id);
const fmtPct = p => (p * 100).toFixed(1) + ' %';
const fmtMs = ms => ms < 1000 ? ms.toFixed(1) + ' ms' : (ms / 1000).toFixed(2) + ' s';

function setStatus(msg) { $('status').textContent = msg; }
function showError(msg) { const e = $('error'); e.textContent = msg; e.style.display = msg ? 'block' : 'none'; }

async function loadFiles() {
  const r = await fetch('/api/files').then(r => r.json());
  const list = $('filelist');
  list.innerHTML = '';
  (r.files || []).forEach(name => {
    const div = document.createElement('div');
    div.className = 'file' + (name === current ? ' active' : '');
    const span = document.createElement('span');
    span.textContent = name;
    span.onclick = () => openFile(name);
    const del = document.createElement('span');
    del.className = 'del';
    del.textContent = '\\u2715';
    del.onclick = () => deleteFile(name);
    div.appendChild(span);
    div.appendChild(del);
    list.appendChild(div);
  });
}

async function openFile(name) {
  const r = await fetch('/api/file/' + name).then(r => r.json());
  if (r.error) return showError(r.error);
  showError('');
  current = name;
  $('current-name').textContent = name;
  $('editor').value = r.content;
  loadFiles();
}

function newFile() {
  const name = prompt('Nom du nouveau fichier (ex. 11_sante.json) :');
  if (!name) return;
  if (!name.endsWith('.json')) return showError('le nom doit finir par .json');
  current = name;
  $('current-name').textContent = name + ' (non enregistré)';
  $('editor').value = JSON.stringify({
    state: { texte: "Décrivez ici l'état à analyser..." },
    questions: {
      ma_question: {
        type: "choice",
        instructions: "Votre question ici ?",
        criteria: { option_a: "Description A.", option_b: "Description B." }
      }
    }
  }, null, 2);
  loadFiles();
}

async function saveFile() {
  if (!current) return showError('aucun fichier sélectionné');
  let data;
  try { data = JSON.parse($('editor').value); }
  catch (e) { return showError('JSON invalide : ' + e.message); }
  const r = await fetch('/api/file/' + current, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: JSON.stringify(data, null, 2) })
  }).then(r => r.json());
  if (r.error) return showError(r.error);
  showError('');
  setStatus('enregistré : ' + current);
  loadFiles();
}

async function deleteFile(name) {
  if (!confirm('Supprimer ' + name + ' ?')) return;
  const r = await fetch('/api/file/' + name, { method: 'DELETE' }).then(r => r.json());
  if (r.error) return showError(r.error);
  if (current === name) { current = null; $('editor').value = ''; $('current-name').textContent = '—'; }
  loadFiles();
}

function formatJson() {
  try {
    $('editor').value = JSON.stringify(JSON.parse($('editor').value), null, 2);
    showError('');
  } catch (e) { showError('JSON invalide : ' + e.message); }
}

async function run() {
  let content;
  try { content = $('editor').value; JSON.parse(content); }
  catch (e) { return showError('JSON invalide : ' + e.message); }
  const btn = $('btn-run');
  btn.disabled = true;
  setStatus('prédiction en cours (chargement du modèle au 1er appel)...');
  showError('');
  try {
    const r = await fetch('/api/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: content })
    }).then(r => r.json());
    if (r.error) { showError(r.error); return; }
    render(r);
  } catch (e) {
    showError('erreur réseau : ' + e);
  } finally {
    btn.disabled = false;
    setStatus('');
  }
}

function barRow(label, p, isBest) {
  return '<div class="bar-row' + (isBest ? ' best' : '') + '">' +
    '<span class="bar-label">' + label + '</span>' +
    '<div class="bar-track"><div class="bar-fill" style="width:' +
    Math.max(p * 100, 0.5) + '%"></div></div>' +
    '<span class="bar-pct">' + fmtPct(p) + '</span></div>';
}

function render(res) {
  const result = res.result, elapsed = res.elapsed_ms, nq = res.n_questions;
  const answers = result.answers || {};
  let questions = {};
  try { questions = JSON.parse($('editor').value).questions || {}; } catch (e) {}

  let html = '<div class="card"><h3>Résumé' +
    '<span class="badge">' + (result.model || '?') + '</span>' +
    '<span class="badge">' + nq + ' question(s)</span>' +
    '<span class="badge">' + fmtMs(elapsed) + '</span></h3>' +
    '<dl class="meta">' +
    '<dt>Temps de réponse</dt><dd>' + fmtMs(elapsed) + ' (' + fmtMs(elapsed / nq) + ' / question)</dd>' +
    '<dt>Tokens</dt><dd>' + ((result.usage || {}).input_tokens ?? '—') + ' entrée / ' +
    ((result.usage || {}).output_tokens ?? '—') + ' sortie</dd>' +
    '<dt>Modèle routé</dt><dd>' + ((result.routing || {}).repo || '—') + '</dd>' +
    '<dt>Raison</dt><dd>' + ((result.routing || {}).reason || '—') + '</dd></dl></div>';

  for (const [qid, ans] of Object.entries(answers)) {
    const instr = (questions[qid] || {}).instructions || '';
    html += '<div class="card"><h3>' + qid +
      ' <span class="type">(' + ans.type + ')</span></h3>' +
      '<div class="q-instr">' + instr + '</div>';
    if (ans.type === 'choice') {
      const probs = ans.probabilities || {};
      html += '<div class="decision">Décision : <b>' + ans.choice + '</b> — confiance ' +
        fmtPct(ans.answer_confidence ?? 0) + '</div>';
      Object.entries(probs).sort((a, b) => b[1] - a[1])
        .forEach(([opt, p]) => { html += barRow(opt, p, opt === ans.choice); });
    } else if (ans.type === 'noul') {
      const pYes = ans.noul ?? 0;
      html += '<div class="decision">Décision : <b>' + (pYes >= 0.5 ? 'OUI' : 'NON') +
        '</b> — P(oui) = ' + fmtPct(pYes) + '</div>';
      html += barRow('oui', pYes, pYes >= 0.5);
      html += barRow('non', 1 - pYes, pYes < 0.5);
    } else if (ans.type === 'score') {
      const probs = ans.probabilities || {};
      const legend = ans.legend || {};
      const keys = Object.keys(probs);
      const best = keys.reduce((a, b) => probs[a] >= probs[b] ? a : b);
      html += '<div class="decision">Niveau attendu : <b>' + (+ans.score).toFixed(2) +
        '</b> / ' + (keys.length - 1) +
        ' &nbsp;|&nbsp; Niveau le plus probable : <b>' + best + '</b> (' + (legend[best] || '?') +
        ') &nbsp;|&nbsp; confiance ' + fmtPct(ans.answer_confidence ?? 0) + '</div>';
      keys.sort((a, b) => (+a) - (+b)).forEach(k => {
        html += barRow(k + '. ' + (legend[k] || ''), probs[k], k === best);
      });
    }
    html += '</div>';
  }
  $('results').innerHTML = html;

  $('model-dot').classList.add('loaded');
  $('model-name').textContent = 'modèle : ' + (result.model || 'laya');
}

loadFiles();
</script>
</body>
</html>"""


if __name__ == "__main__":
    print(f"Dossier de données : {DATA_DIR}")
    print("Interface : http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
