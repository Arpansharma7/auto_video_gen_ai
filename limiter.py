import time
import threading
from datetime import date

MODELS = {
    "gemini-3.1-flash-lite":         {"rpm": 15, "tpm": 250_000, "rpd": 500},
    "gemini-3.1-flash-lite-preview": {"rpm": 15, "tpm": 250_000, "rpd": 500},
    "gemini-flash-lite-latest":      {"rpm": 15, "tpm": 250_000, "rpd": 500},
    "gemma-4-31b":                   {"rpm": 30, "tpm": 16_000,  "rpd": 14_400},
}

class ModelState:
    def __init__(self, limits):
        self.limits = limits
        self.call_times = []
        self.token_times = []
        self.day = date.today()
        self.day_count = 0

    def reset_if_new_day(self):
        if date.today() != self.day:
            self.day = date.today()
            self.day_count = 0

    def available(self, est_tokens):
        self.reset_if_new_day()
        now = time.time()
        self.call_times = [t for t in self.call_times if now - t < 60]
        self.token_times = [(t, tok) for t, tok in self.token_times if now - t < 60]
        used_tokens = sum(tok for _, tok in self.token_times)
        if self.day_count >= self.limits["rpd"]:
            return False
        if len(self.call_times) >= self.limits["rpm"]:
            return False
        if used_tokens + est_tokens > self.limits["tpm"]:
            return False
        return True

    def record(self, est_tokens):
        now = time.time()
        self.call_times.append(now)
        self.token_times.append((now, est_tokens))
        self.day_count += 1


class MultiModelLimiter:
    def __init__(self, models=MODELS):
        self.lock = threading.Lock()
        self.states = {name: ModelState(limits) for name, limits in models.items()}

    def get_model(self, est_tokens=1000):
        with self.lock:
            for name, state in self.states.items():
                if state.available(est_tokens):
                    state.record(est_tokens)
                    return name
            return None


limiter = MultiModelLimiter()

def rate_limited(est_tokens=1000):
    def deco(fn):
        def wrapper(*args, **kwargs):
            model = limiter.get_model(est_tokens)
            if model is None:
                raise RuntimeError("All Gemini models exhausted for now — fall back to Ollama")
            kwargs["model"] = model
            return fn(*args, **kwargs)
        return wrapper
    return deco