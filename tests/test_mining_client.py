"""Sélection des fournisseurs et plafonds. Aucun appel réseau."""

import pytest

from mining import client as llm


def test_aucun_fournisseur_sans_cle():
    assert llm.providers_from_env({}) == ()


def test_un_fournisseur_par_cle_presente():
    providers = llm.providers_from_env({"MISTRAL_API_KEY": "k"})
    assert [p.name for p in providers] == ["mistral"]
    assert providers[0].api_key == "k"


def test_ordre_par_defaut_openrouter_en_tete():
    env = {"GEMINI_API_KEY": "g", "OPENROUTER_API_KEY": "o", "MISTRAL_API_KEY": "m"}
    assert [p.name for p in llm.providers_from_env(env)] == ["openrouter", "mistral", "gemini"]


def test_ordre_impose_par_llm_providers():
    env = {"OPENROUTER_API_KEY": "o", "MISTRAL_API_KEY": "m", "LLM_PROVIDERS": "mistral,openrouter"}
    assert [p.name for p in llm.providers_from_env(env)] == ["mistral", "openrouter"]


def test_llm_providers_ignore_un_fournisseur_sans_cle():
    env = {"MISTRAL_API_KEY": "m", "LLM_PROVIDERS": "openrouter,mistral"}
    assert [p.name for p in llm.providers_from_env(env)] == ["mistral"]


def test_liste_de_modeles_surchargeable():
    env = {"OPENROUTER_API_KEY": "o", "OPENROUTER_MODELS": "a:free, b:free"}
    assert llm.providers_from_env(env)[0].models == ("a:free", "b:free")


def test_modeles_par_defaut_non_vides():
    providers = llm.providers_from_env({"OPENROUTER_API_KEY": "o"})
    assert providers[0].models and all(providers[0].models)


def test_base_url_surchargeable():
    env = {"MISTRAL_API_KEY": "m", "MISTRAL_BASE_URL": "https://exemple.test/v1"}
    assert llm.providers_from_env(env)[0].base_url == "https://exemple.test/v1"


def test_plafond_d_appels_leve_budget_exceeded():
    conversation = llm.Client(providers=(), max_calls=0)
    with pytest.raises(llm.BudgetExceeded):
        conversation.ask("sys", "question")


def test_plafond_de_tokens_leve_budget_exceeded():
    conversation = llm.Client(providers=(), max_tokens=0)
    with pytest.raises(llm.BudgetExceeded):
        conversation.ask("sys", "question")


def test_sans_fournisseur_on_leve_llm_error():
    conversation = llm.Client(providers=())
    with pytest.raises(llm.LLMError):
        conversation.ask("sys", "question")


def _corps(contenu, finish_reason="stop"):
    return {
        "model": "m",
        "usage": {"total_tokens": 10},
        "choices": [{"message": {"content": contenu}, "finish_reason": finish_reason}],
    }


def _client_factice(monkeypatch, post):
    conversation = llm.Client(providers=(llm.Provider("fake", "https://x.test", "k", ("m",)),))
    monkeypatch.setattr(conversation, "_post", post)
    return conversation


def test_finish_reason_length_marque_la_reponse_tronquee(monkeypatch):
    conversation = _client_factice(monkeypatch, lambda provider, payload: _corps("Page 33…", "length"))
    answer = conversation.ask("sys", "q")
    assert answer.truncated is True
    assert answer.text == "Page 33…"


def test_reponse_complete_non_tronquee(monkeypatch):
    conversation = _client_factice(monkeypatch, lambda provider, payload: _corps("OUI\nPAGES: 3"))
    assert conversation.ask("sys", "q").truncated is False


def test_reponse_tronquee_vide_rendue_sans_rejouer(monkeypatch):
    # Rejouer au même budget redonnerait la même coupure : c'est à l'étape de décider.
    appels = []

    def post(provider, payload):
        appels.append(payload)
        return _corps("", "length")

    answer = _client_factice(monkeypatch, post).ask("sys", "q")
    assert answer.truncated is True
    assert len(appels) == 1


def test_openrouter_recoit_au_plus_trois_modeles(monkeypatch):
    # Au-delà, OpenRouter refuse toute la requête : HTTP 400, « 'models' array
    # must have 3 items or fewer ». Constaté sous l'issue #194.
    modeles = ("a:free", "b:free", "c:free", "d:free", "e:free")
    conversation = llm.Client(providers=(llm.Provider("openrouter", "https://x.test", "k", modeles),))
    envoyes = []

    def post(provider, payload):
        envoyes.append(payload)
        return _corps("OUI\nPAGES: 3")

    monkeypatch.setattr(conversation, "_post", post)
    conversation.ask("sys", "q")
    assert envoyes[0]["models"] == ["a:free", "b:free", "c:free"]
    assert envoyes[0]["model"] == "a:free"


def test_contenu_vide_avec_raisonnement_vaut_troncature(monkeypatch):
    # Cas réel, E3 sur l'issue #194 : le raisonnement épuise max_tokens, le contenu
    # revient vide avec finish_reason « stop ». Ce n'est pas une « réponse vide » à
    # rejouer au même budget, mais un manque de place à signaler.
    appels = []

    def post(provider, payload):
        appels.append(payload)
        return {
            "model": "m",
            "usage": {"total_tokens": 4000},
            "choices": [{"message": {"content": "", "reasoning": "Line11: ..."}, "finish_reason": "stop"}],
        }

    answer = _client_factice(monkeypatch, post).ask("sys", "q")
    assert answer.truncated is True and answer.text == ""
    assert len(appels) == 1


def test_contenu_vide_sans_raisonnement_reste_une_reponse_vide(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    appels = []

    def post(provider, payload):
        appels.append(payload)
        return _corps("")

    conversation = _client_factice(monkeypatch, post)
    # Le diagnostic doit dire quel modèle a rendu le vide, pour les logs du job.
    with pytest.raises(llm.LLMError, match=r"réponse vide \(modèle m, finish_reason stop, sans raisonnement\)"):
        conversation.ask("sys", "q")
    assert len(appels) == llm.ATTEMPTS


def test_reponse_vide_retentee_avec_un_autre_modele_de_tete(monkeypatch):
    # Cas réel, issue #194 : réponses vides intermittentes d'OpenRouter.
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    modeles = ("a:free", "b:free", "c:free")
    conversation = llm.Client(providers=(llm.Provider("openrouter", "https://x.test", "k", modeles),))
    envoyes = []

    def post(provider, payload):
        envoyes.append(payload)
        return _corps("" if len(envoyes) == 1 else "OUI\nPAGES: 3")

    monkeypatch.setattr(conversation, "_post", post)
    assert conversation.ask("sys", "q").text == "OUI\nPAGES: 3"
    assert [p["model"] for p in envoyes] == ["a:free", "b:free"]
    assert envoyes[1]["models"] == ["b:free", "c:free", "a:free"]


def _http_429(headers):
    from urllib.error import HTTPError

    def fake_urlopen(request, timeout=None):
        fake_urlopen.calls += 1
        raise HTTPError(request.full_url, 429, "Too Many Requests", headers, None)

    fake_urlopen.calls = 0
    return fake_urlopen


def test_quota_journalier_epuise_n_est_pas_retente(monkeypatch):
    # Cas réel, issue #194 : « free-models-per-day », 50 requêtes par jour.
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    fake = _http_429({"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1789430400000"})
    monkeypatch.setattr(llm, "urlopen", fake)
    conversation = llm.Client(providers=(llm.Provider("openrouter", "https://x.test", "k", ("m",)),))
    # Tous les fournisseurs à court de quota : QuotaExhausted, pour arrêter les pages suivantes.
    with pytest.raises(llm.QuotaExhausted, match=r"quota épuisé chez openrouter \(remise à zéro 00:00 UTC\)"):
        conversation.ask("sys", "q")
    assert fake.calls == 1


def test_un_429_passager_reste_retente(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    fake = _http_429({"X-RateLimit-Remaining": "3"})
    monkeypatch.setattr(llm, "urlopen", fake)
    conversation = llm.Client(providers=(llm.Provider("openrouter", "https://x.test", "k", ("m",)),))
    with pytest.raises(llm.LLMError, match="HTTP 429"):
        conversation.ask("sys", "q")
    assert fake.calls == llm.ATTEMPTS
