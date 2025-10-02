import hashlib
import requests
import sys

BASE = "https://challenge.rectanglehq.com"
RESET_URL = BASE + "/reset"

APP_KEY = "FDE-CHALLENGE-01"
NAME = "Douglas McKinley"
EMAIL = "mail@cadocary.com"

headers = {
    "Content-Type": "application/json",
    "X-Application-Key": APP_KEY,
}
payload = {"name": NAME, "email": EMAIL}

# ---- STEP 0: reset clean state ----
reset_resp = requests.post(RESET_URL, json=payload, headers=headers, timeout=30)
print("RESET:", reset_resp.status_code, reset_resp.text)

# ---- STEP 1: initial POST (to get request-id + algo) ----
resp = requests.post(BASE, json=payload, headers=headers, timeout=30)
print("STEP 1:", resp.status_code, resp.text)

xrid = resp.headers.get("X-Request-Id")
algo = resp.headers.get("X-Hash-Alg-For-Idempotency")
if not xrid or not algo:
    sys.exit("Missing X-Request-Id or algorithm header!")

to_hash = f"{EMAIL}:{xrid}"
print("String to hash:", repr(to_hash))
print("Algorithm:", algo)

algo = algo.lower()
if algo.startswith("blake2b"):
    bits = int(algo.replace("blake2b", ""))
    digest = hashlib.blake2b(to_hash.encode(), digest_size=bits // 8).hexdigest()
elif algo.startswith("blake2s"):
    bits = int(algo.replace("blake2s", ""))
    digest = hashlib.blake2s(to_hash.encode(), digest_size=bits // 8).hexdigest()
else:
    digest = hashlib.new(algo, to_hash.encode()).hexdigest()

print("X-Idempotency-Key:", digest)

# ---- STEP 2: follow-up with idempotency key ----
follow_headers = {
    "Content-Type": "application/json",
    "X-Application-Key": APP_KEY,
    "X-Idempotency-Key": digest,
}
final_resp = requests.post(BASE, json=payload, headers=follow_headers, timeout=30)
print("STEP 2:", final_resp.status_code, final_resp.text)
