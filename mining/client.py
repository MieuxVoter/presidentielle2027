"""Client LLM minimal, compatible OpenAI, avec cascade de fournisseurs.

Un seul format de requête (`POST {base_url}/chat/completions`) suffit pour
OpenRouter, Mistral et Gemini : changer de fournisseur ne demande que trois
variables d'environnement.

La cascade sert aux quotas gratuits : dès qu'un fournisseur refuse (429, panne,
réponse illisible), on passe au suivant. OpenRouter fait en plus sa propre
bascule entre modèles gratuits via le paramètre `models`.

Stdlib uniquement.
"""

import json
import os
import time
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TIMEOUT = 90
RETRY_STATUSES = {408, 409, 429, 500, 502, 503, 504}

# Les catalogues gratuits changent souvent — les identifiants ci-dessous ont été
# relevés le 2026-09-13 et se périment. Ils sont surchargeables par variable
# d'environnement, et docs/LLM_MINING.md explique comment lister ceux du jour.
DEFAULTS = (
    ("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "OPENROUTER_MODELS"),
    ("mistral", "https://api.mistral.ai/v1", "MISTRAL_API_KEY", "MISTRAL_MODELS"),
    ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY", "GEMINI_MODELS"),
)
FALLBACK_MODELS = {
    # Trois modèles généralistes de fournisseurs différents : la cascade ne sert
    # à rien si les trois partagent le même quota. Les modèles spécialisés
    # (code, finance, santé, sûreté) sont volontairement écartés.
    "openrouter": (
        "google/gemma-4-31b-it:free,"
        "nvidia/nemotron-3-ultra-550b-a55b:free,"
        "nvidia/nemotron-3-super-120b-a12b:free," 
        "thinkingmachines/inkling:free"
    ),
    "mistral": "mistral-small-latest",
    "gemini": "gemini-2.0-flash",
}


class LLMError(RuntimeError):
    """Aucun fournisseur n'a pu répondre."""


class BudgetExceeded(LLMError):
    """Plafond d'appels ou de tokens atteint : on s'arrête au lieu de brûler un quota."""


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key: str
    models: tuple


@dataclass
class Answer:
    text: str
    provider: str
    model: str
    truncated: bool = False


@dataclass
class Client:
    """Interroge les fournisseurs dans l'ordre jusqu'à obtenir une réponse."""

    providers: tuple
    max_calls: int = 40
    max_tokens: int = 200_000
    calls: int = 0
    tokens: int = 0
    log: list = field(default_factory=list)

    def ask(self, system, prompt, *, max_tokens=32):
        """Une question, une réponse texte. Lève LLMError si personne ne répond."""
        if self.calls >= self.max_calls:
            raise BudgetExceeded(f"plafond de {self.max_calls} appels atteint")
        if self.tokens >= self.max_tokens:
            raise BudgetExceeded(f"plafond de {self.max_tokens} tokens atteint")

        errors = []
        for provider in self.providers:
            try:
                answer = self._call(provider, system, prompt, max_tokens)
            except LLMError as exc:
                errors.append(f"{provider.name}: {exc}")
                continue
            self.log.append({"provider": provider.name, "model": answer.model, "prompt": prompt, "answer": answer.text})
            return answer
        raise LLMError("aucun fournisseur n'a répondu — " + " | ".join(errors))

    def _call(self, provider, system, prompt, max_tokens):
        payload = {
            "model": provider.models[0],
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": max_tokens,
        }
        # Bascule interne d'OpenRouter entre plusieurs modèles gratuits.
        if provider.name == "openrouter" and len(provider.models) > 1:
            payload["models"] = list(provider.models)

        last = "aucune tentative"
        for attempt in range(2):
            try:
                body = self._post(provider, payload)
            except _Retryable as exc:
                last = str(exc)
                time.sleep(2 * (attempt + 1))
                continue
            except LLMError as exc:
                raise exc
            self.calls += 1
            self.tokens += (body.get("usage") or {}).get("total_tokens", 0)
            choices = body.get("choices") or []
            choice = choices[0] if choices else {}
            text = (choice.get("message") or {}).get("content") or ""
            # "length" : la sortie a été coupée par max_tokens. C'est une réponse
            # incomplète, pas un refus du format, et rejouer au même budget donnerait
            # la même coupure : on la rend telle quelle, à l'étape de décider.
            truncated = choice.get("finish_reason") == "length"
            if not text.strip() and not truncated:
                last = "réponse vide"
                continue
            return Answer(text.strip(), provider.name, body.get("model") or provider.models[0], truncated)
        raise LLMError(last)

    def _post(self, provider, payload):
        request = Request(
            f"{provider.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {provider.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "presidentielle2027-llm-mining",
            },
        )
        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in RETRY_STATUSES:
                raise _Retryable(f"HTTP {exc.code}") from exc
            raise LLMError(f"HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise _Retryable(str(exc)) from exc
        except json.JSONDecodeError as exc:
            raise LLMError(f"réponse illisible: {exc}") from exc


class _Retryable(LLMError):
    """Échec transitoire : on réessaie le même fournisseur avant de basculer."""


def providers_from_env(env=None):
    """Les fournisseurs dont la clé est présente, dans l'ordre de DEFAULTS.

    L'ordre peut être imposé par LLM_PROVIDERS (noms séparés par des virgules).
    """
    env = os.environ if env is None else env
    wanted = [n.strip() for n in (env.get("LLM_PROVIDERS") or "").split(",") if n.strip()]
    found = {}
    for name, base_url, key_env, models_env in DEFAULTS:
        key = (env.get(key_env) or "").strip()
        if not key:
            continue
        models = tuple(m.strip() for m in (env.get(models_env) or FALLBACK_MODELS[name]).split(",") if m.strip())
        found[name] = Provider(name, env.get(f"{name.upper()}_BASE_URL", base_url), key, models)
    order = wanted or [name for name, *_ in DEFAULTS]
    return tuple(found[name] for name in order if name in found)
