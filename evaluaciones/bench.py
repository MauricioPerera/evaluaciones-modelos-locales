#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Harness de benchmark para minicpm5-fable5-thinking contra eval_set.json.
Calificacion determinista por maquina. No usa juicio de LLM para calificar.
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import subprocess
import tempfile

CWD = os.path.dirname(os.path.abspath(__file__))
EVAL_SET = os.path.join(CWD, "eval_set.json")
RESULTS_JSON = os.path.join(CWD, "bench_results.json")
REPORT_MD = os.path.join(CWD, "BENCHMARK-REPORT.md")
RUN_LOG = os.path.join(CWD, "tmp_bench_run.log")

THINK_TOKEN = "</think>"
REQUEST_TIMEOUT = 120
CODE_TIMEOUT = 10


def log(msg=""):
    line = str(msg)
    print(line, flush=True)
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def ollama_alive():
    for attempt in range(3):
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=10) as r:
                r.read()
            return True
        except Exception as e:
            log(f"[ollama ping intento {attempt+1}/3] error: {e!r}")
            if attempt < 2:
                time.sleep(10)
    return False


def split_thinking(text):
    """Devuelve (raw, graded). graded = despues del ultimo THINK_TOKEN, o todo."""
    if text is None:
        return "", ""
    idx = text.rfind(THINK_TOKEN)
    if idx == -1:
        return text, text
    graded = text[idx + len(THINK_TOKEN):]
    return text, graded


def call_ollama(model, prompt, options):
    """Devuelve (data_dict_or_None, error_str_or_None). 1 reintento."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": options,
    }).encode("utf-8")

    last_err = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
                body = r.read().decode("utf-8", errors="replace")
            wall = time.time() - t0
            data = json.loads(body)
            return data, wall, None
        except Exception as e:
            last_err = repr(e)
            log(f"  [request error intento {attempt+1}/2] {last_err}")
            if attempt == 0:
                time.sleep(2)
    return None, None, last_err


# ---------- Calificadores ----------

def grade_math(answer, expected_number):
    # ultimo numero: enteros y decimales, ignorar comas de miles
    pattern = r'[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-+]?\d+\.\d+|[-+]?\d+'
    matches = re.findall(pattern, answer)
    if not matches:
        return False, None, "sin numero"
    last = matches[-1].replace(",", "")
    try:
        val = float(last)
    except ValueError:
        return False, None, f"no parseable: {last!r}"
    ok = abs(val - float(expected_number)) <= 1e-6
    return ok, val, None


def extract_code(answer):
    # primer bloque python dentro de fences ```...```
    fence = re.search(r'```(?:python)?\s*\n?(.*?)```', answer, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1)
    return answer


def grade_coding(answer, tests):
    code = extract_code(answer)
    program = code + "\n\n" + "\n".join(tests) + "\n"
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8", dir=CWD
        ) as tf:
            tmp_path = tf.name
            # prefijo tmp_ requerido
            tf.write(program)
        # renombrar para cumplir prefijo tmp_
        final_path = os.path.join(CWD, "tmp_code_exec.py")
        os.replace(tmp_path, final_path)
        try:
            proc = subprocess.run(
                [sys.executable, final_path],
                timeout=CODE_TIMEOUT,
                capture_output=True,
                text=True,
            )
            ok = proc.returncode == 0
            return ok, None, (proc.stderr or proc.stdout or "")[:500]
        finally:
            try:
                os.remove(final_path)
            except OSError:
                pass
    except subprocess.TimeoutExpired:
        return False, None, "timeout 10s"
    except Exception as e:
        return False, None, f"exec error: {e!r}"


def grade_instruction(answer, check, expected):
    if check == "one_word_equals":
        s = answer.strip()
        # quitar puntuacion final
        s = re.sub(r'[.,;:!?]+$', '', s).strip()
        words = s.split()
        is_one_word = len(words) == 1
        ok = is_one_word and s.lower() == str(expected).lower()
        return ok, None, None
    elif check == "json_equals":
        s = answer.strip()
        i = s.find("{")
        j = s.rfind("}")
        if i != -1 and j != -1 and j > i:
            s = s[i:j + 1]
        try:
            parsed = json.loads(s)
        except Exception as e:
            return False, None, f"json invalido: {e!r}"
        ok = parsed == expected
        return ok, None, None
    elif check == "n_nonempty_lines":
        lines = [ln for ln in answer.splitlines() if ln.strip() != ""]
        bad = False
        for ln in lines:
            st = ln.strip()
            if re.match(r'\d+\.', st) or st.startswith("-") or st.startswith("*"):
                bad = True
                break
        ok = (len(lines) == int(expected)) and not bad
        return ok, None, ("lista-marker" if bad else None)
    elif check == "exact_stripped":
        ok = answer.strip() == str(expected)
        return ok, None, None
    elif check == "digits_sequence":
        digits = "".join(re.findall(r'\d', answer))
        ok = digits == str(expected)
        return ok, None, None
    else:
        return False, None, f"check desconocido: {check}"


def grade_knowledge(answer, expected_letter):
    # primera letra A-D standalone (no parte de palabra), con () o . permitidos
    m = re.search(r'(?<![A-Za-z])\(?([A-Da-d])\)?\.?(?![A-Za-z])', answer)
    if not m:
        return False, None, "sin letra A-D"
    letter = m.group(1).upper()
    ok = letter == str(expected_letter).upper()
    return ok, letter, None


# ---------- Metricas ----------

def perf_metrics(data, wall):
    if not data:
        return None, None, None, None
    eval_count = data.get("eval_count", 0) or 0
    eval_duration = data.get("eval_duration", 0) or 0  # nanosegundos
    prompt_eval_count = data.get("prompt_eval_count", None)
    tps = None
    if eval_duration and eval_duration > 0:
        tps = eval_count / (eval_duration / 1e9)
    return eval_count, eval_duration, prompt_eval_count, tps


# ---------- Reporte ----------

def write_report(results, agg, global_agg, avg_tps, tok_s_list):
    lines = []
    lines.append("# BENCHMARK-REPORT — minicpm5-fable5-thinking\n")
    lines.append(f"Fecha de corrida: generada por `bench.py`. Oráculo: `eval_set.json` (congelado).\n")
    lines.append("Modelo: `minicpm5-fable5-thinking` (1B, GGUF Q8_0, razonamiento que termina en `</think>`).\n")
    lines.append("Calificación determinista por máquina, sin juicio de LLM. Temperature=0.\n")

    lines.append("\n## 1. Resultados por categoría\n")
    lines.append("| Categoría | Aciertos | Total | Porcentaje |")
    lines.append("|---|---|---|---|")
    for cat in ["math", "coding", "instruction_following", "knowledge"]:
        a = agg[cat]
        lines.append(f"| {cat} | {a['aciertos']} | {a['total']} | {a['porcentaje']}% |")
    lines.append(f"| **GLOBAL** | **{global_agg['aciertos']}** | **{global_agg['total']}** | **{global_agg['porcentaje']}%** |")

    lines.append("\n## 2. Resultados por ítem\n")
    lines.append("| ID | Categoría | Resultado | Respuesta corta |")
    lines.append("|---|---|---|---|")
    for r in results:
        corta = r["respuesta_calificada"].replace("|", "\\|").replace("\n", " ")
        corta = (corta[:60] + "…") if len(corta) > 60 else corta
        lines.append(f"| {r['id']} | {r['category']} | {r['status']} | {corta} |")

    # velocidad
    valid = [t for t in tok_s_list if t is not None]
    if valid:
        media = sum(valid) / len(valid)
        srt = sorted(valid)
        n = len(srt)
        mediana = srt[n // 2] if n % 2 == 1 else (srt[n // 2 - 1] + srt[n // 2]) / 2
        vmin, vmax = min(valid), max(valid)
    else:
        media = mediana = vmin = vmax = 0.0

    lines.append("\n## 3. Métricas de velocidad (tokens/s de generación)\n")
    lines.append(f"- Tokens/s — media: **{media:.2f}** | mediana: **{mediana:.2f}**")
    lines.append(f"- Mínimo: {vmin:.2f} tok/s | Máximo: {vmax:.2f} tok/s")
    lines.append(f"- Promedio tok/s (agregado global): **{avg_tps:.2f}**")
    lines.append(f"- Ítems con métrica válida: {len(valid)} / {len(tok_s_list)}")

    # fallos
    fallos = [r for r in results if r["status"] in ("fail", "error")]
    lines.append("\n## 4. Fallos\n")
    if not fallos:
        lines.append("Sin fallos.")
    else:
        for r in fallos:
            lines.append(f"\n### {r['id']} ({r['category']}) — {r['status']}")
            lines.append(f"- Esperado: `{json.dumps(r['expected'], ensure_ascii=False)}`")
            if r.get("detail"):
                lines.append(f"- Detalle: {r['detail']}")
            lines.append(f"- Respuesta calificada (textual, truncada 300):")
            txt = r["respuesta_calificada"]
            lines.append("```")
            lines.append(txt)
            lines.append("```")

    # trade-offs
    lines.append("\n## 5. Decisiones de interpretación (trade-offs)\n")
    lines.append("- **math**: se extrae el último número de la respuesta con regex "
                 "`[-+]?\\d{1,3}(?:,\\d{3})+... | [-+]?\\d+\\.\\d+ | [-+]?\\d+`; "
                 "las comas se tratan como separadores de miles (se eliminan) y el punto como decimal. "
                 "Comparación numérica con tolerancia 1e-6.")
    lines.append("- **coding**: se toma el primer bloque dentro de fences ``` (con o sin etiqueta `python`); "
                 "si no hay fences se usa el texto entero. El código se ejecuta en un subproceso "
                 "`python` separado con timeout 10s junto con los asserts; pass = exit 0. "
                 "Nunca se ejecuta código en el proceso principal.")
    lines.append("- **knowledge**: primera letra A–D que aparezca *standalone* (no adyacente a otras letras), "
                 "mayúscula o minúscula, admitiendo paréntesis o punto alrededor. "
                 "Esto evita falsos positivos de letras dentro de palabras (p.ej. la 'a' de 'Mars').")
    lines.append("- **instruction_following / one_word_equals**: se quita puntuación final (.,;:!?) y se exige "
                 "una sola palabra (sin espacios internos).")
    lines.append("- **instruction_following / n_nonempty_lines**: se rechazan líneas que inicien con "
                 "`dígito+.` , `-` o `*` (marcadores de lista).")
    lines.append("- **instruction_following / json_equals**: se recorta al primer `{` y último `}` antes de parsear.")
    lines.append("- **tokens/s**: `eval_count / (eval_duration/1e9)` (Ollama reporta `eval_duration` en ns). "
                 "Promedio global calculado sobre ítems con métrica válida (excluye errores de request).")

    # salida de ejecucion
    lines.append("\n## 6. Salida de ejecución\n")
    lines.append("Últimas ~20 líneas reales de stdout de la corrida:\n")
    lines.append("```")
    try:
        with open(RUN_LOG, "r", encoding="utf-8") as f:
            all_lines = f.read().splitlines()
        tail = all_lines[-20:]
        lines.extend(tail)
    except Exception as e:
        lines.append(f"(no se pudo leer log: {e!r})")
    lines.append("```")

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------- Main ----------

def main():
    # reset log
    try:
        os.remove(RUN_LOG)
    except OSError:
        pass

    if not os.path.exists(EVAL_SET):
        print("BLOQUEADO: eval_set.json no existe en el cwd.")
        sys.exit(2)

    if not ollama_alive():
        print("BLOQUEADO: Ollama no responde en localhost:11434 tras 3 intentos.")
        sys.exit(2)

    with open(EVAL_SET, "r", encoding="utf-8") as f:
        eval_set = json.load(f)

    config = eval_set["config"]
    model = config["model"]
    options = config.get("options", {})

    log(f"=== BENCH START === modelo={model} timeout_req={REQUEST_TIMEOUT}s")

    categories = ["math", "coding", "instruction_following", "knowledge"]
    results = []

    for cat in categories:
        items = eval_set.get(cat, [])
        log(f"\n--- {cat} ({len(items)} items) ---")
        for item in items:
            iid = item["id"]
            prompt = item["prompt"]
            log(f"[{iid}] llamando Ollama...")
            data, wall, err = call_ollama(model, prompt, options)

            if data is None:
                log(f"[{iid}] ERROR request: {err}")
                results.append({
                    "id": iid, "category": cat, "status": "error",
                    "expected": item.get("expected", item.get("expected_number",
                                item.get("expected_letter", item.get("tests")))),
                    "respuesta_calificada": "",
                    "raw_response": "",
                    "tokens_por_segundo": None,
                    "wall_seconds": None,
                    "detail": err,
                })
                continue

            raw = data.get("response", "") or ""
            _, graded = split_thinking(raw)
            eval_count, eval_duration, prompt_eval_count, tps = perf_metrics(data, wall)

            # calificar
            detail = None
            if cat == "math":
                ok, _val, detail = grade_math(graded, item["expected_number"])
                expected_out = item["expected_number"]
            elif cat == "coding":
                ok, detail, extra = grade_coding(graded, item["tests"])
                if extra and not ok:
                    detail = (detail or "") + f" | stderr: {extra}"
                expected_out = item["tests"]
            elif cat == "instruction_following":
                ok, _v, detail = grade_instruction(graded, item["check"], item["expected"])
                expected_out = item["expected"]
            elif cat == "knowledge":
                ok, _v, detail = grade_knowledge(graded, item["expected_letter"])
                expected_out = item["expected_letter"]
            else:
                ok = False
                expected_out = None

            status = "pass" if ok else "fail"
            log(f"[{iid}] {status} | tok/s={tps if tps is not None else 'NA'} | wall={wall:.2f}s | eval_count={eval_count}")

            results.append({
                "id": iid,
                "category": cat,
                "status": status,
                "expected": expected_out,
                "respuesta_calificada": graded[:300],
                "raw_response": raw,
                "tokens_por_segundo": round(tps, 4) if tps is not None else None,
                "wall_seconds": round(wall, 4),
                "prompt_eval_count": prompt_eval_count,
                "eval_count": eval_count,
                "eval_duration_ns": eval_duration,
                "detail": detail,
            })

    # agregados
    agg = {}
    tok_s_list = []
    for cat in categories:
        cat_items = [r for r in results if r["category"] == cat]
        aciertos = sum(1 for r in cat_items if r["status"] == "pass")
        total = len(cat_items)
        pct = round(100 * aciertos / total, 2) if total else 0.0
        agg[cat] = {"aciertos": aciertos, "total": total, "porcentaje": pct}
        tok_s_list.extend(r["tokens_por_segundo"] for r in cat_items)

    g_aciertos = sum(1 for r in results if r["status"] == "pass")
    g_total = len(results)
    g_pct = round(100 * g_aciertos / g_total, 2) if g_total else 0.0
    valid_tps = [t for t in tok_s_list if t is not None]
    avg_tps = round(sum(valid_tps) / len(valid_tps), 4) if valid_tps else 0.0
    global_agg = {"aciertos": g_aciertos, "total": g_total, "porcentaje": g_pct}

    bench_results = {
        "config": {"model": model, "options": options},
        "items": results,
        "agregados_por_categoria": agg,
        "global": global_agg,
        "promedio_tokens_por_segundo": avg_tps,
    }
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(bench_results, f, ensure_ascii=False, indent=2)

    write_report(results, agg, global_agg, avg_tps, tok_s_list)

    log("\n=== RESUMEN ===")
    for cat in categories:
        a = agg[cat]
        log(f"{cat}: {a['aciertos']}/{a['total']} = {a['porcentaje']}%")
    log(f"GLOBAL: {g_aciertos}/{g_total} = {g_pct}%")
    log(f"Promedio tok/s: {avg_tps}")
    log(f"Escrito: {RESULTS_JSON} y {REPORT_MD}")
    log("=== BENCH END ===")


if __name__ == "__main__":
    main()