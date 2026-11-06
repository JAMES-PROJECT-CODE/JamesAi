"""Conservative, explainable spam heuristics. Deletion is opt-in per group."""
import re
from collections import defaultdict, deque
import time

_recent = defaultdict(lambda: deque(maxlen=8))
URL_RE = re.compile(r"https?://\S+", re.I)
SUSPICIOUS_TERMS = ("free crypto", "double your money", "claim your prize", "seed phrase")

def inspect_message(chat_id: int, user_id: int, text: str) -> tuple[bool, str]:
    """Return (is_likely_spam, reason); intentionally favors low false positives."""
    now = time.time()
    bucket = _recent[(chat_id, user_id)]
    while bucket and now - bucket[0][0] > 45:
        bucket.popleft()
    bucket.append((now, text[:500]))

    lowered = text.lower()
    if any(term in lowered for term in SUSPICIOUS_TERMS):
        return True, "message contains a common scam phrase"
    if len(URL_RE.findall(text)) >= 4:
        return True, "message contains several links"
    if len(bucket) >= 5 and len({item[1] for item in bucket}) <= 2:
        return True, "repeated messages in a short period"
    return False, ""
