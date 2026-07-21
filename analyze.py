"""Análisis del dump NDJSON: categorización + detectar 'free' que en realidad
son delisted/no comprables. Uso: python analyze.py dump_us.ndjson"""
import sys, collections
try:
    import orjson as J
    loads = J.loads
except Exception:
    import json; loads = json.loads

PERMANENT_END = "9998-12-30"
NOW = "2026-07-21"

def offers(p):
    """availabilities comprables (Actions∋Purchase), no-trial, no-hidden."""
    out = []
    for dsa in p.get("DisplaySkuAvailabilities", []) or []:
        sku = dsa.get("Sku", {}) or {}
        skp = sku.get("Properties", {}) or {}
        if (sku.get("SkuType") or "").lower() == "trial": continue
        if skp.get("IsSubscriptionHidden"): continue
        for av in dsa.get("Availabilities", []) or []:
            acts = av.get("Actions") or []
            pr = (av.get("OrderManagementData", {}) or {}).get("Price", {}) or {}
            cond = av.get("Conditions", {}) or {}
            out.append({
                "actions": acts,
                "purchase": "Purchase" in acts,
                "list": pr.get("ListPrice"),
                "cur": pr.get("CurrencyCode"),
                "end": cond.get("EndDate") or "",
                "start": cond.get("StartDate") or "",
            })
    return out

def main(path):
    ptype = collections.Counter()
    actions_all = collections.Counter()
    n = 0
    free_examples = []      # marcados free por nuestra logica actual
    no_purchase = 0
    ended_past = 0          # tienen availabilities pero todas con EndDate pasado
    for line in open(path, "rb"):
        if not line.strip(): continue
        p = loads(line); n += 1
        ptype[p.get("ProductType")] += 1
        ofs = offers(p)
        for o in ofs:
            for a in o["actions"]: actions_all[a] += 1
        purch = [o for o in ofs if o["purchase"]]
        for o in purch:
            for a in o["actions"]: pass
        # logica ACTUAL de is_free: hay comprables y TODAS son 0
        paid = [o for o in purch if (o["list"] or 0) > 0]
        title = (p.get("LocalizedProperties",[{}])[0].get("ProductTitle") or "")[:34]
        if purch and not paid:
            # marcado FREE hoy. ¿Es sospechoso? (todas las ventanas vencidas)
            all_ended = all(o["end"] and not o["end"].startswith(PERMANENT_END)
                            and o["end"][:10] < NOW for o in purch)
            free_examples.append((title, p.get("ProductType"),
                                  [o["actions"] for o in purch][:2],
                                  [o["end"][:10] for o in purch][:2], all_ended))
        if not purch:
            no_purchase += 1

    print(f"=== {n} productos ===")
    print("ProductType:", dict(ptype.most_common()))
    print("Actions vistas:", dict(actions_all.most_common(12)))
    print(f"sin Purchase (no comprables): {no_purchase}")
    print(f"marcados FREE por la logica actual: {len(free_examples)}")
    susp = [e for e in free_examples if e[4]]
    print(f"  de esos, SOSPECHOSOS (todas las ventanas vencidas = delisted?): {len(susp)}")
    print("--- muestra FREE (title | type | actions | endDates | ventana-vencida) ---")
    for e in free_examples[:20]:
        print(f"  {e[0]:34s} | {e[1]:6s} | {e[2]} | {e[3]} | vencida={e[4]}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dump_us.ndjson")
