# -*- coding: utf-8 -*-
"""
rag_ab.py — A/B: mide si retrieval de rag-local + umbral mejora a micro-expert
frente al recall nativo. No toques servidores (8937 rag-local, 8940 llama-server).
"""
import sys
import json
import time
import urllib.request
import urllib.error

# Windows: forzar stdout utf-8 (un print con no-cp1252 rompio una corrida previa)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RAG = "http://127.0.0.1:8937"
LLM = "http://127.0.0.1:8942"
ORACLE = "ctt_oracle.json"
RESULTS = "rag_ab_bonsai_results.json"
THRESHOLD = 0.35
K = 3
MAX_TOKENS = 4096
TEMP = 0.7
TOP_P = 0.9
TIMEOUT = 900
RETRIES = 1

# Sondas de contaminacion extra
SONDAS = [
    {"id": "sonda_paris", "q": "What is the capital of France? Answer with one word.", "keyword": "paris"},
    {"id": "sonda_nacl", "q": "What is the chemical formula of table salt? Answer briefly.", "keyword": "nacl"},
]


def http_json(method, url, payload=None, timeout=TIMEOUT):
    """Req/resp JSON crudo. Devuelve (status, data). Lanza excepcion si red falla."""
    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode('utf-8', errors='replace')
        status = resp.status
    try:
        parsed = json.loads(body) if body else None
    except json.JSONDecodeError:
        parsed = body
    return status, parsed


def health(host, attempts=3, gap=10):
    last = None
    for i in range(attempts):
        try:
            st, data = http_json('GET', host + '/health', timeout=10)
            ok = (st == 200)
            last = f"GET {host}/health -> {st} {data}"
            if ok:
                return True, last
        except Exception as e:
            last = f"GET {host}/health -> EXC {type(e).__name__}: {e}"
        if i < attempts - 1:
            time.sleep(gap)
    return False, last


def collection_exists(name):
    try:
        st, data = http_json('GET', f"{RAG}/collections", timeout=15)
        if st == 200 and isinstance(data, list):
            return name in data
    except Exception:
        pass
    return False


def delete_collection(name):
    try:
        st, data = http_json('DELETE', f"{RAG}/collections/{name}", timeout=30)
        return st, data
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace')
    except Exception as e:
        return None, f"EXC {type(e).__name__}: {e}"


def build_doc(fact_id, fact):
    title = fact.split(':')[-1].strip() if ':' in fact else fact
    title = title[:60]
    md = (
        "---\n"
        f"type: fact\n"
        f"title: {title}\n"
        f"description: {fact}\n"
        "tags:\n"
        "  - aurora\n"
        "---\n"
        f"{fact}\n"
    )
    return {"id": fact_id, "md": md}


def seed_aurora(facts):
    # DELETE previo
    if collection_exists("aurora"):
        st, d = delete_collection("aurora")
        print(f"[seed] DELETE aurora -> {st} {d}")
        time.sleep(1)
    docs = []
    for i, fact in enumerate(facts, start=1):
        docs.append(build_doc(f"f{i}", fact))
    body = {"name": "aurora", "docs": docs}
    st, data = http_json('POST', f"{RAG}/collections", payload=body, timeout=60)
    print(f"[seed] POST /collections aurora ({len(docs)} docs) -> {st}")
    if st != 200:
        print(f"[seed] RESP: {data}")
    return st, data


def count_aurora():
    """Cuenta docs via query k alto (todos los hits)."""
    try:
        st, data = http_json('POST', f"{RAG}/collections/aurora/query",
                             payload={"text": "aurora project deploy database team", "k": 50}, timeout=30)
        if st == 200 and isinstance(data, list):
            ids = {h.get('id') for h in data if isinstance(h, dict)}
            return len(ids), data
    except Exception as e:
        print(f"[count] EXC {e}")
    return -1, None


def query_aurora(text):
    st, data = http_json('POST', f"{RAG}/collections/aurora/query",
                         payload={"text": text, "k": K}, timeout=30)
    if st != 200 or not isinstance(data, list):
        return []
    return data


def build_context(hits):
    keep = [h for h in hits if float(h.get('score', 0.0)) >= THRESHOLD]
    if not keep:
        return "", []
    lines = "\n".join(f"- {h.get('description', '')}" for h in keep)
    return f"Facts from memory:\n{lines}", keep


def llm_answer(question, context):
    if context:
        system = f"{context}\n\nYou are MicroExpert, a helpful AI assistant.\nIMPORTANT: Use the information above to answer the user."
    else:
        system = "You are MicroExpert, a helpful AI assistant.\nAnswer concisely and accurately."
    payload = {
        "model": "MiniCPM5-1B",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
        "temperature": TEMP,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
        "stream": False,
    }
    last_err = None
    for attempt in range(RETRIES + 1):
        try:
            t0 = time.time()
            st, data = http_json('POST', f"{LLM}/v1/chat/completions", payload=payload, timeout=TIMEOUT)
            wall = time.time() - t0
            if st == 200 and isinstance(data, dict):
                choices = data.get('choices', [])
                if choices:
                    msg = choices[0].get('message', {})
                    content = msg.get('content', '') or ''
                    return content.strip(), wall, None
            last_err = f"status={st} data={str(data)[:200]}"
        except Exception as e:
            last_err = f"EXC {type(e).__name__}: {e}"
        if attempt < RETRIES:
            time.sleep(2)
    return "", 0.0, last_err


def grade(text, keyword):
    if not text:
        return False
    return keyword.lower() in text.lower()


def main():
    # 0. Health checks (abort tras 3 intentos espaciados 10s)
    print("=== HEALTH ===")
    ok_rag, ev_rag = health(RAG)
    ok_llm, ev_llm = health(LLM)
    print(f"rag-local: {ok_rag} | {ev_rag}")
    print(f"llama-server: {ok_llm} | {ev_llm}")
    if not (ok_rag and ok_llm):
        # Documentar y abortar
        report = {
            "blocked": True,
            "reason": "health check failed",
            "rag_health": ev_rag,
            "llm_health": ev_llm,
        }
        with open(RESULTS, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        # Reporte de bloqueo
        with open("RAG-AB-BONSAI-REPORT-RAW.md", 'w', encoding='utf-8') as f:
            f.write("# RAG-AB-REPORT — BLOQUEADO\n\n")
            f.write(f"rag-local: `{ev_rag}`\n\n")
            f.write(f"llama-server: `{ev_llm}`\n\n")
        print("BLOQUEADO — health check fallo tras 3 intentos espaciados 10s")
        sys.exit(2)

    # 1. Cargar oraculo
    with open(ORACLE, 'r', encoding='utf-8') as f:
        oracle = json.load(f)
    facts = oracle["facts_proyecto_ficticio"]
    preguntas = oracle["preguntas"]
    controles = oracle["control"]

    # 2. Sembrado
    print("=== SEED ===")
    st, data = seed_aurora(facts)
    time.sleep(2)
    count, count_data = count_aurora()
    print(f"[seed] count aurora == {count} (esperado 10)")
    count_evidence = json.dumps(count_data, ensure_ascii=False)[:600] if count_data else "n/a"
    assert count == 10, f"count != 10 (got {count})"

    # 3. Evaluacion
    print("=== EVAL ===")
    all_items = []
    # aurora
    for p in preguntas:
        all_items.append({**p, "kind": "aurora"})
    # control
    for c in controles:
        all_items.append({**c, "kind": "control"})
    # sondas
    for s in SONDAS:
        all_items.append({**s, "kind": "sonda"})

    resultados = []
    for it in all_items:
        qid = it["id"]
        q = it["q"]
        kw = it["keyword"]
        kind = it["kind"]
        t0 = time.time()
        hits = query_aurora(q)
        scores_topk = [round(float(h.get('score', 0.0)), 4) for h in hits]
        context, kept = build_context(hits)
        facts_iny = len(kept)
        ans, wall_llm, err = llm_answer(q, context)
        wall_total = round(time.time() - t0, 3)
        passed = grade(ans, kw)
        print(f"[eval] {qid} ({kind}) pass={passed} iny={facts_iny} scores={scores_topk} wall={wall_total}s")
        resultados.append({
            "id": qid,
            "kind": kind,
            "question": q,
            "keyword": kw,
            "pass": bool(passed),
            "respuesta": ans,
            "scores_topk": scores_topk,
            "facts_inyectados": facts_iny,
            "wall_seconds": wall_total,
            "error": err,
        })

    # 4. Agregados
    aurora = [r for r in resultados if r["kind"] == "aurora"]
    control = [r for r in resultados if r["kind"] == "control"]
    sondas = [r for r in resultados if r["kind"] == "sonda"]
    aurora_pass = sum(1 for r in aurora if r["pass"])
    control_pass = sum(1 for r in control if r["pass"])
    sondas_pass = sum(1 for r in sondas if r["pass"])
    iny_no_aurora = sum(r["facts_inyectados"] for r in resultados if r["kind"] != "aurora")

    agregados = {
        "aurora_pass": aurora_pass,
        "aurora_total": len(aurora),
        "control_pass": control_pass,
        "control_total": len(control),
        "sondas_pass": sondas_pass,
        "sondas_total": len(sondas),
        "inyecciones_en_no_aurora": iny_no_aurora,
        "threshold": THRESHOLD,
        "k": K,
        "count_aurora": count,
        "count_evidence": count_evidence,
    }
    out = {"agregados": agregados, "resultados": resultados}
    with open(RESULTS, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("=== RESUMEN ===")
    print(f"aurora: {aurora_pass}/{len(aurora)}")
    print(f"control: {control_pass}/{len(control)}")
    print(f"sondas: {sondas_pass}/{len(sondas)}")
    print(f"inyecciones en no-aurora: {iny_no_aurora}")
    print(f"count aurora: {count}")
    sys.exit(0)


if __name__ == "__main__":
    main()