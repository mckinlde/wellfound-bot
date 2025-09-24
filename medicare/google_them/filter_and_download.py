#!/usr/bin/env python3
"""
Stage 2: Filter candidate links and download chosen PDFs.

Reads:
  - candidates.csv (from Stage 1)
  - domain_whitelist.json (runtime-editable)

Writes:
  - plan_pdfs.csv with chosen link per (plan, doc_label)
  - PDFs to outdir/
"""

import os, csv, json, argparse, logging, requests
from urllib.parse import urlparse

LOG_FILE = "medicare/google_them/filter_and_download.log"
logger = logging.getLogger("filter_and_download")

BASE_DIR = os.path.dirname(__file__)
WHITELIST_PATH = os.path.join(BASE_DIR, "domain_whitelist.json")

def normalize_plan_id(plan_id: str) -> str:
    parts = plan_id.replace(" ", "").split("-")
    if len(parts) != 3:
        return ""  # don't hard-fail in Stage 2
    prefix, mid, suffix = parts
    return f"{prefix}{mid}{suffix.zfill(3)}"

def load_whitelist(path: str):
    if not os.path.exists(path):
        logger.warning(f"[WARN] domain_whitelist.json not found at {path}; proceeding without restrictions")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def host_matches(url: str, allowed_hosts: list[str]) -> bool:
    if not allowed_hosts:
        return True  # no restriction for this company
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(allowed in host for allowed in allowed_hosts)

def score_candidate(url: str, plan_id_raw: str, plan_id_norm: str, allowed_hosts: list[str]) -> int:
    """Simple transparent scoring for picking a link (before PDF validation)."""
    score = 0
    # 1) Domain preference
    if host_matches(url, allowed_hosts):
        score += 5
    # 2) Plan ID hints in URL
    u = url.lower()
    if plan_id_raw.lower() in u:
        score += 3
    if plan_id_norm and plan_id_norm.lower() in u:
        score += 2
    # 3) Year hint in URL (light preference; real validation happens later)
    #    Not required to avoid false negatives.
    # if "2025" in u: score += 1
    return score

def download_pdf(session, url, dest_path):
    if not url:
        return False
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if os.path.exists(dest_path):
        logger.info(f"[SKIP] {dest_path} already exists")
        return True
    try:
        r = session.get(url, stream=True, timeout=45)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        logger.info(f"[DOWNLOAD] {url} → {dest_path}")
        return True
    except Exception as e:
        logger.error(f"[ERROR] Download failed {url}: {e}")
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="candidates.csv from Stage 1")
    ap.add_argument("--outdir", required=True, help="Directory to save PDFs")
    ap.add_argument("--output", required=True, help="plan_pdfs.csv")
    ap.add_argument("--whitelist", default=WHITELIST_PATH, help="Path to domain_whitelist.json")
    ap.add_argument("--download-topk", type=int, default=1, help="Download top-K candidates per (plan, doc_label)")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"), logging.StreamHandler()]
    )
    logger.setLevel(logging.INFO)

    whitelist = load_whitelist(args.whitelist)
    os.makedirs(args.outdir, exist_ok=True)

    out_exists = os.path.exists(args.output)
    out_fh = open(args.output, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(out_fh, fieldnames=[
        "plan_id","plan_name","company","doc_label","chosen_link","pdf_filepath","all_candidates"
    ])
    if not out_exists:
        writer.writeheader()

    session = requests.Session()

    with open(args.input, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        plan_id   = row["plan_id"]
        plan_name = row["plan_name"]
        company   = row["company"]
        doc_label = row["doc_label"]
        candidates = json.loads(row["candidate_links"] or "[]")

        plan_id_norm = normalize_plan_id(plan_id)
        allowed_hosts = whitelist.get(company, [])

        # Score & sort candidates
        ranked = sorted(
            candidates,
            key=lambda u: score_candidate(u, plan_id, plan_id_norm, allowed_hosts),
            reverse=True
        )

        chosen = ranked[:args.download_topk]  # usually 1; can keep 2 for validator to choose later
        saved_paths = []

        for i, url in enumerate(chosen, start=1):
            pdf_path = os.path.join(args.outdir, f"{plan_id}_{doc_label}_{i}.pdf" if args.download_topk > 1 else f"{plan_id}_{doc_label}.pdf")
            if download_pdf(session, url, pdf_path):
                saved_paths.append(pdf_path)

        writer.writerow({
            "plan_id": plan_id,
            "plan_name": plan_name,
            "company": company,
            "doc_label": doc_label,
            "chosen_link": chosen[0] if chosen else "",
            "pdf_filepath": ";".join(saved_paths),
            "all_candidates": json.dumps(candidates)
        })
        out_fh.flush()

    out_fh.close()

if __name__ == "__main__":
    main()
