#!/usr/bin/env python3
"""
Stage 1: Collect candidate PDF links using Google Custom Search API.

For each plan & doc_label, query once (or with an OR of both plan-id formats),
save all PDF candidates, and dump raw JSON (cache) for offline analysis.

Outputs: candidates.csv with rows:
  plan_id, plan_name, company, doc_label, query_used, candidate_links
"""

import os, csv, json, time, random, argparse, logging, hashlib
import requests

# ---------------------------
# Setup
# ---------------------------

LOG_FILE = "medicare/google_them/google_pdf_grabber.log"
logger = logging.getLogger("pdf_grabber")

DOC_TYPES = {
    "Summary_of_Benefits": "summary of benefits",
    "Evidence_of_Coverage": "evidence of coverage",
    "Drug_Formulary": "formulary drug list",
}

BASE_DIR = os.path.dirname(__file__)
ENV_PATH = os.path.join(BASE_DIR, "env.json")
CONFIG_PATH = os.path.join(BASE_DIR, "search_config.json")

with open(ENV_PATH, "r", encoding="utf-8") as f:
    env = json.load(f)
API_KEY = env["Custom Search Api"]["key"].strip()
CX_ID   = env["Programmable Search Engine"]["id"].strip()

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CFG = json.load(f)

SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

# ---------------------------
# Helpers
# ---------------------------

def normalize_plan_id(plan_id: str) -> str:
    parts = plan_id.replace(" ", "").split("-")
    if len(parts) != 3:
        raise ValueError(f"Unexpected plan_id format: {plan_id}")
    prefix, mid, suffix = parts
    return f"{prefix}{mid}{suffix.zfill(3)}"

def polite_sleep():
    time.sleep(random.uniform(CFG.get("sleep_seconds_min", 0.8), CFG.get("sleep_seconds_max", 1.8)))

def is_pdf_url(u: str) -> bool:
    return ".pdf" in (u or "").lower()

def hashed_name(query: str) -> str:
    return hashlib.sha1(query.encode("utf-8")).hexdigest()[:12]

def build_query(plan_id_raw: str, plan_id_norm: str, plan_name: str, doc_label: str) -> str:
    base_terms = []
    # Prefer including plan name to boost relevance
    if plan_name:
        base_terms.append(plan_name)

    # Plan ID(s)
    use_or = CFG.get("use_or_for_plan_ids", True)
    if use_or and plan_id_norm:
        base_terms.append(f"(\"{plan_id_raw}\" OR {plan_id_norm})")
    else:
        # Fall back to raw only; Stage 1 will try norm separately if needed
        base_terms.append(f"\"{plan_id_raw}\"")

    # Doc type hint (targeted) or broad?
    if doc_label in DOC_TYPES:
        base_terms.append(DOC_TYPES[doc_label])

    # Year hint
    if CFG.get("include_year_in_query", True):
        base_terms.append(str(CFG.get("target_year", "")))

    terms = " ".join(t for t in base_terms if t)
    return f"{terms} filetype:pdf".strip()

def run_search(query, page_index, session=None, debug_dir=None, plan_id=None, label=None):
    """Use on-disk cache first. Otherwise call API, save JSON, and return items list."""
    session = session or requests.Session()
    params = {"key": API_KEY, "cx": CX_ID, "q": query, "num": 10, "start": page_index}
    qhash = hashed_name(query)
    fname = f"{plan_id}_{label}_p{(page_index-1)//10+1}_{qhash}.json" if plan_id and label else f"p{(page_index-1)//10+1}_{qhash}.json"

    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)
        fpath = os.path.join(debug_dir, fname)
        # Cache hit
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            items = data.get("items", [])
            logger.debug(f"[CACHE] {fname} → {len(items)} items")
            return items

    # Call API with backoff on 429
    attempts = CFG.get("retry_attempts", 5)
    for attempt in range(attempts):
        r = session.get(SEARCH_URL, params=params, timeout=30)
        if r.status_code == 429:
            retry = int(r.headers.get("Retry-After", 0)) or (2 ** attempt)
            logger.warning(f"[429] rate-limited; sleeping {retry}s (attempt {attempt+1}/{attempts})")
            time.sleep(retry)
            continue
        r.raise_for_status()
        data = r.json()
        items = data.get("items", [])

        if debug_dir:
            with open(fpath, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            logger.debug(f"[DEBUG] Saved raw JSON → {fpath} ({len(items)} items)")

        return items

    raise requests.HTTPError("Exceeded retries after repeated 429s")

def collect_candidates_for_label(plan_id, plan_name, doc_label, pages, debug_dir, session, plan_id_norm):
    """Collect all PDF URLs for a given label with early stopping based on min_candidates_to_stop."""
    min_stop = CFG.get("min_candidates_to_stop", {}).get(doc_label, 1)
    candidates, seen = [], set()

    query = build_query(plan_id, plan_id_norm, plan_name, doc_label)
    logger.debug(f"[QUERY] {plan_id} {doc_label} → {query}")

    for page in range(pages):
        start_index = page * 10 + 1
        items = run_search(query, start_index, session=session, debug_dir=debug_dir, plan_id=plan_id, label=doc_label)
        for item in items:
            url = item.get("link", "")
            if is_pdf_url(url) and url not in seen:
                seen.add(url)
                candidates.append(url)
        logger.debug(f"[DEBUG] {plan_id} {doc_label} page {page+1}: {len(items)} items, {len(candidates)} pdfs so far")
        polite_sleep()
        if len(candidates) >= min_stop:
            break

    logger.info(f"[API SEARCH] {plan_id} {doc_label} → {len(candidates)} candidates")
    return query, candidates

# ---------------------------
# Main
# ---------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True, help="Output candidates CSV")
    ap.add_argument("--pages", type=int, default=None, help="Override max pages per query")
    ap.add_argument("--debug", action="store_true", help="Save/load raw JSON in outdir/debug_json")
    ap.add_argument("--outdir", required=True, help="Base directory for debug JSON (and future outputs)")
    args = ap.parse_args()

    # Logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"), logging.StreamHandler()]
    )
    logger.setLevel(log_level)

    max_pages = args.pages or CFG.get("max_pages_per_query", 3)
    debug_dir = os.path.join(args.outdir, "debug_json") if args.debug else None

    with open(args.input, newline="", encoding="utf-8") as f:
        plans = list(csv.DictReader(f))

    out_exists = os.path.exists(args.output)
    out_fh = open(args.output, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(out_fh, fieldnames=[
        "plan_id","plan_name","company","doc_label","query_used","candidate_links"
    ])
    if not out_exists:
        writer.writeheader()

    session = requests.Session()

    # Process plans; prioritize SoB/EoC, optionally skip Formulary if both found
    for idx, plan in enumerate(plans, start=1):
        plan_id = (plan.get("plan_id") or "").strip()
        plan_name = (plan.get("plan_name") or "").strip()
        company  = (plan.get("company")  or "").strip()

        try:
            plan_id_norm = normalize_plan_id(plan_id)
        except Exception as e:
            logger.warning(f"[WARN] normalize_plan_id failed for {plan_id}: {e}")
            plan_id_norm = ""

        logger.info(f"[INFO] ({idx}/{len(plans)}) Collecting for {plan_id} {plan_name}")

        found_labels = set()
        for doc_label in ["Summary_of_Benefits", "Evidence_of_Coverage", "Drug_Formulary"]:
            # Optional: skip formulary if we already have SoB & EoC candidates
            if (doc_label == "Drug_Formulary"
                and CFG.get("skip_formulary_when_sob_eoc_found", True)
                and {"Summary_of_Benefits","Evidence_of_Coverage"}.issubset(found_labels)):
                logger.info(f"[SKIP] {plan_id} Formulary search skipped (SoB & EoC already have candidates)")
                continue

            query_used, candidates = collect_candidates_for_label(
                plan_id, plan_name, doc_label, max_pages, debug_dir, session, plan_id_norm
            )
            if candidates:
                found_labels.add(doc_label)

            writer.writerow({
                "plan_id": plan_id,
                "plan_name": plan_name,
                "company": company,
                "doc_label": doc_label,
                "query_used": query_used,
                "candidate_links": json.dumps(candidates)
            })
            out_fh.flush()

    out_fh.close()

if __name__ == "__main__":
    main()
