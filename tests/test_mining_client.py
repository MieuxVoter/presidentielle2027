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
