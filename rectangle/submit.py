import requests

BASE = "https://challenge.rectanglehq.com"

APP_KEY = "FDE-CHALLENGE-01"
IDEMPOTENCY_KEY = "9a4ded66eefada956217eab16adaa9724bd2c7d358b31276a5fdbdaff0de8f546e11398b953b2498150949aa51a718b2cd951e1bd33be70e06c563646f026772"

# Load your fixed Go source
with open(r"decoded_challenge.go", "r", encoding="utf-8") as f:
    fixed_go_code = f.read()

print(fixed_go_code)
input("Enter to send")
solution = {
    "name": "Douglas McKinley",
    "email": "mail@cadocary.com",
    "code": fixed_go_code,
    "answer": "A,B,D,F",
}

headers = {
    "Content-Type": "application/json",
    "X-Application-Key": APP_KEY,
    "X-Idempotency-Key": IDEMPOTENCY_KEY,
}

resp = requests.post(BASE, json=solution, headers=headers, timeout=30)
print("FINAL SUBMIT:", resp.status_code)
print(resp.text)
