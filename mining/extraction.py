"""Extraction E2/E3 et vérifications indépendantes de la mise en page.

Le modèle lit la notice ; ce module refuse tout ce qui ne peut pas être relié à
une page fournie. Il ne tente volontairement pas de reconstituer un tableau PDF
avec des expressions régulières : les huit instituts ne le mettent pas en page
de la même manière.
"""

import csv
import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from merge import _norm
from mining import steps
from mining.client import LLMError

METHOD_TOKENS = 2500
TABLE_TOKENS = 4000
FRENCH_MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}
SAMPLE_LABELS = {
    "exprime une intention de vote": "exprimé une intention de vote",
    "certains d'aller voter": "certains d'aller voter",
}


class ValidationError(ValueError):
    """La réponse du modèle n'est pas assez étayée pour devenir une donnée."""


def _silent(*_args):
    """Journal par défaut : les tests n'impriment rien, mine_poll.py passe print."""


def tail(text, limit=400):
    """La fin d'une réponse : là où le modèle conclut, ou là où il a été coupé."""
    text = (text or "").strip()
    return "…" + text[-limit:] if len(text) > limit else text


@dataclass(frozen=True)
class Methodology:
    institute: str
    commissioner: str
    start: str
    end: str
    sample: int
    registered: int | None
    population: str
    source_dates: str
    source_sample: str
    source_registered: str = ""


@dataclass(frozen=True)
class CandidateValue:
    name: str
    value: Decimal
    source: str

    def as_csv(self):
        """Le format des résultats : 16.0 devient 16, 0.5 reste 0.5."""
        return format(self.value.normalize(), "f")


@dataclass(frozen=True)
class ExtractedTable:
    page: int
    tour: str
    samples: tuple
    values: tuple


@dataclass
class Extraction:
    methodology: Methodology | None = None
    tables: list = field(default_factory=list)
    failures: list = field(default_factory=list)


def normalized_text(text):
    """Normalisation tolérante à pdfplumber, mais pas aux mots inventés."""
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("’", "'").replace("`", "'")
    return " ".join(text.split())


def citation_in_page(citation, page):
    """La citation est-elle vraiment dans la page, après espaces équivalents ?"""
    wanted = normalized_text(citation)
    return bool(wanted) and wanted in normalized_text(page.text)


def _numbers(text):
    """Nombres entiers ou décimaux du texte, espaces fines comprises."""
    return [token.replace(" ", "").replace("\u202f", "") for token in re.findall(r"(?<!\d)\d[\d\s\u202f]*(?!\d)", text)]


def source_has_number(source, number):
    return str(number) in _numbers(source)


def _source_has_value(source, value):
    """Accepte 1,5 / 1.5 et la convention documentée <1% -> 0.5."""
    compact = normalized_text(source).replace(" ", "")
    if value == Decimal("0.5") and re.search(r"<\s*1\s*%?", compact):
        return True
    found = re.findall(r"(?<![\d.])\d+(?:[,.]\d+)?", compact)
    try:
        return any(Decimal(item.replace(",", ".")) == value for item in found)
    except InvalidOperation:
        return False


def _parse_date(value, field):
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} doit être une date AAAA-MM-JJ") from exc


def _source_has_date(source, value):
    date = _parse_date(value, "date")
    compact = normalized_text(source).lower()
    if value in compact:
        return True
    for name, month in FRENCH_MONTHS.items():
        if month != date.month:
            continue
        pattern = rf"(?<!\d){date.day}(?:er)?(?:\s+(?:au|a|à|et|-)\s+\d+(?:er)?)?\s+{name}\s+{date.year}(?!\d)"
        if re.search(pattern, compact):
            return True
    return False


def institutions_from_polls(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return sorted({row["nom_institut"].strip() for row in csv.DictReader(handle) if row["nom_institut"].strip()})


def populations_from_polls(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return sorted({row["population"].strip() for row in csv.DictReader(handle) if row["population"].strip()})


def candidate_names(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return [row["complete_name"].strip() for row in csv.DictReader(handle) if row["complete_name"].strip()]


def _key_values(answer):
    """Dernière occurrence de `CLE: valeur`, pour tolérer une courte réflexion."""
    values = {}
    for raw in (answer or "").splitlines():
        match = re.match(r"^\s*([A-Z_]+)\s*:\s*(.*?)\s*$", raw)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def _canonical(value, choices, field):
    lookup = {_norm(choice): choice for choice in choices}
    canonical = lookup.get(_norm(value))
    if not canonical:
        raise ValidationError(f"{field} n'est pas dans le jeu fermé")
    return canonical


def parse_methodology(answer, pages, institutes, populations, notice_date=None):
    """Lit E2 puis applique ses citations, dates et bornes numériques."""
    data = _key_values(answer)
    required = (
        "INSTITUT",
        "COMMANDITAIRE",
        "DEBUT",
        "FIN",
        "ECHANTILLON",
        "INSCRITS",
        "POPULATION",
        "SOURCE_DATES",
        "SOURCE_ECHANTILLON",
        "SOURCE_INSCRITS",
    )
    missing = [key for key in required if key not in data]
    if missing:
        raise ValidationError("champs E2 absents : " + ", ".join(missing))

    institute = _canonical(data["INSTITUT"], institutes, "INSTITUT")
    population = _canonical(data["POPULATION"], populations, "POPULATION")
    start, end = _parse_date(data["DEBUT"], "DEBUT"), _parse_date(data["FIN"], "FIN")
    if end < start:
        raise ValidationError("FIN est antérieure à DEBUT")
    if (end - start).days > 31:
        raise ValidationError("la période de terrain dépasse 31 jours")
    if notice_date and end > notice_date:
        raise ValidationError("FIN est postérieure à la date de la notice")
    try:
        sample = int(data["ECHANTILLON"])
        registered = int(data["INSCRITS"]) if data["INSCRITS"] else None
    except ValueError as exc:
        raise ValidationError("ECHANTILLON et INSCRITS doivent être des entiers sans espace") from exc
    if sample <= 0 or (registered is not None and not 0 < registered <= sample):
        raise ValidationError("les effectifs E2 ne sont pas cohérents")

    page_text = "\n".join(page.text for page in pages)
    page_proxy = type("MethodologyPages", (), {"text": page_text})()
    for field in ("SOURCE_DATES", "SOURCE_ECHANTILLON"):
        if not citation_in_page(data[field], page_proxy):
            raise ValidationError(f"{field} est introuvable dans les pages de méthodologie")
    if data["SOURCE_INSCRITS"] and not citation_in_page(data["SOURCE_INSCRITS"], page_proxy):
        raise ValidationError("SOURCE_INSCRITS est introuvable dans les pages de méthodologie")
    if not _source_has_date(data["SOURCE_DATES"], data["DEBUT"]) or not _source_has_date(
        data["SOURCE_DATES"], data["FIN"]
    ):
        raise ValidationError("SOURCE_DATES ne justifie pas DEBUT et FIN")
    if not source_has_number(data["SOURCE_ECHANTILLON"], sample):
        raise ValidationError("SOURCE_ECHANTILLON ne justifie pas ECHANTILLON")
    registered_source = data["SOURCE_INSCRITS"] or data["SOURCE_ECHANTILLON"]
    if registered is not None and not source_has_number(registered_source, registered):
        raise ValidationError("la source ne justifie pas INSCRITS")
    return Methodology(
        institute=institute,
        commissioner=data["COMMANDITAIRE"],
        start=data["DEBUT"],
        end=data["FIN"],
        sample=sample,
        registered=registered,
        population=population,
        source_dates=data["SOURCE_DATES"],
        source_sample=data["SOURCE_ECHANTILLON"],
        source_registered=data["SOURCE_INSCRITS"],
    )


def _parse_samples(value):
    if not value.strip():
        return ()
    parsed = []
    for item in value.split("|"):
        match = re.match(r"^\s*(.*?)\s*=\s*([\d\s\u202f]+)\s*$", item)
        if not match:
            raise ValidationError("EFFECTIFS doit contenir « libellé = nombre »")
        label = SAMPLE_LABELS.get(_norm(match.group(1)))
        if not label:
            raise ValidationError(f"libellé d'effectif inconnu : {match.group(1).strip()}")
        count = int(match.group(2).replace(" ", "").replace("\u202f", ""))
        if count <= 0:
            raise ValidationError("un effectif doit être positif")
        parsed.append((label, count))
    labels = [label for label, _ in parsed]
    if len(labels) != len(set(labels)):
        raise ValidationError("un effectif est présent deux fois")
    return tuple(parsed)


def _canonical_tour(value):
    key = _norm(value).replace(" ", "")
    if key in {"1ertour", "premiertour"}:
        return "1er Tour"
    if key in {"2ndtour", "secondtour", "2emtour", "deuxiemetour"}:
        return "2nd Tour"
    raise ValidationError("TOUR doit être « 1er Tour » ou « 2nd Tour »")


def _decimal(value):
    try:
        parsed = Decimal(value.strip().replace(",", "."))
    except InvalidOperation as exc:
        raise ValidationError(f"valeur non numérique : {value}") from exc
    if not Decimal("0") <= parsed <= Decimal("100"):
        raise ValidationError("une intention doit être comprise entre 0 et 100")
    return parsed


def _parse_table(lines, page, known):
    fields, values = {}, []
    for line in lines:
        field = re.match(r"^\s*(TOUR|EFFECTIFS)\s*:\s*(.*?)\s*$", line, re.IGNORECASE)
        if field:
            fields[field.group(1).upper()] = field.group(2)
            continue
        pieces = [piece.strip() for piece in line.split("|", 2)]
        if len(pieces) != 3 or not all(pieces):
            raise ValidationError("ligne de tableau attendue : candidat | valeur | ligne source")
        name, number, source = pieces
        canonical = {_norm(candidate): candidate for candidate in known}.get(_norm(name), name)
        value = _decimal(number)
        if not citation_in_page(source, page):
            raise ValidationError(f"citation introuvable pour {name}")
        if _norm(name) not in _norm(source):
            raise ValidationError(f"la citation ne contient pas le candidat {name}")
        if not _source_has_value(source, value):
            raise ValidationError(f"la citation ne contient pas la valeur {number} de {name}")
        values.append(CandidateValue(canonical, value, source))
    if "TOUR" not in fields:
        raise ValidationError("TOUR absent du tableau")
    tour = _canonical_tour(fields["TOUR"])
    samples = _parse_samples(fields.get("EFFECTIFS", ""))
    if len(values) < 2:
        raise ValidationError("un tableau doit avoir au moins deux candidats")
    names = [_norm(item.name) for item in values]
    if len(names) != len(set(names)):
        raise ValidationError("un candidat est présent deux fois")
    total = sum((item.value for item in values), Decimal("0"))
    if abs(total - Decimal("100")) > Decimal("1.5"):
        raise ValidationError(f"la somme des intentions vaut {total}, pas 100 ± 1.5")
    if tour == "2nd Tour" and len(values) != 2:
        raise ValidationError("un second tour doit contenir exactement deux candidats")
    for _label, count in samples:
        if not source_has_number(page.text, count):
            raise ValidationError(f"l'effectif {count} est absent de la page")
    return ExtractedTable(page.number, tour, samples, tuple(values))


def parse_tables(answer, page, known_candidates):
    """Valide chaque bloc E3 ; un bloc mauvais n'annule pas une autre page."""
    blocks, current, failures = [], None, []
    no_table = False
    for raw in (answer or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.upper() == "AUCUN TABLEAU":
            no_table = True
            continue
        if line.upper() == "TABLEAU":
            if current is not None:
                failures.append("TABLEAU imbriqué")
            current = []
            continue
        if line.upper() == "FIN":
            if current is None:
                failures.append("FIN sans TABLEAU")
            else:
                blocks.append(current)
                current = None
            continue
        if current is not None:
            current.append(raw)
    if current is not None:
        failures.append("TABLEAU sans FIN")
    if no_table and blocks:
        failures.append("AUCUN TABLEAU et TABLEAU sont contradictoires")
    tables = []
    for index, block in enumerate(blocks, 1):
        try:
            tables.append(_parse_table(block, page, known_candidates))
        except ValidationError as exc:
            failures.append(f"page {page.number}, tableau {index} : {exc}")
    if not blocks and not no_table:
        failures.append(f"page {page.number} : aucun bloc TABLEAU exploitable")
    return tables, failures


def _render_pages(pages):
    return "\n".join(f"--- page {page.number} ---\n{page.text}" for page in pages)


def _ask_methodology(client, pages, institutes, populations, notice_date, log=_silent):
    prompt = steps.load_prompt("e2_methodologie").safe_substitute(
        pages=_render_pages(pages),
        instituts="\n".join(f"- {name}" for name in institutes),
        populations="\n".join(f"- {name}" for name in populations),
    )
    last = None
    for attempt in range(2):
        answer = client.ask(steps.system_prompt(), prompt, max_tokens=METHOD_TOKENS)
        try:
            return parse_methodology(answer.text, pages, institutes, populations, notice_date)
        except ValidationError as exc:
            last = exc
            cut = " (réponse tronquée)" if getattr(answer, "truncated", False) else ""
            log(f"   ✗ E2 essai {attempt + 1} rejeté{cut} : {exc}\n   fin de la réponse : {tail(answer.text)}")
            prompt += "\nRappel : réponds uniquement avec toutes les lignes imposées et des citations présentes dans ces pages."
    raise ValidationError(f"E2 rejetée après relance : {last}")


def extract(client, pages, triage, candidates_path, polls_path, notice_date=None, log=_silent):
    """Exécute E2 puis E3 sur les seules pages proposées par le triage.

    La page méthodologique est repliée vers les trois premières pages si E1 ne
    l'a pas donnée : les versions historiques du prompt E1 ne la demandaient pas.
    """
    selected = {page.number: page for page in pages}
    method_numbers = triage.methodo_pages or [page.number for page in pages[:3]]
    method_pages = [selected[number] for number in method_numbers if number in selected]
    result = Extraction()
    origin = "citées par E1" if triage.methodo_pages else "repli sur les 3 premières"
    log(f"🔎 E2 méthodologie : pages {[page.number for page in method_pages]} ({origin})")
    if not method_pages:
        result.failures.append("aucune page de méthodologie disponible")
        return result
    try:
        result.methodology = _ask_methodology(
            client,
            method_pages,
            institutions_from_polls(polls_path),
            populations_from_polls(polls_path),
            notice_date,
            log,
        )
    except ValidationError as exc:
        result.failures.append(str(exc))
        return result
    except LLMError as exc:
        # Budget épuisé ou fournisseurs muets : l'appelant doit pouvoir publier
        # la raison sous l'issue au lieu de faire échouer le job.
        result.failures.append(f"appel E2 impossible ({exc})")
        return result

    method = result.methodology
    log(
        f"✅ E2 : {method.institute} · {method.commissioner} · {method.start} → {method.end} · "
        f"échantillon {method.sample} · inscrits {method.registered or '-'}"
    )

    known = candidate_names(candidates_path)
    seen_sets = set()
    for number in triage.pages_with_intentions:
        page = selected.get(number)
        if not page:
            result.failures.append(f"page de tableau {number} absente")
            continue
        log(f"🔎 E3 page {number}")
        prompt = steps.load_prompt("e3_tableaux").safe_substitute(
            candidats="\n".join(f"- {name}" for name in known), number=page.number, page=page.text
        )
        try:
            answer = client.ask(steps.system_prompt(), prompt, max_tokens=TABLE_TOKENS)
        except LLMError as exc:  # BudgetExceeded compris ; un bug de code doit rester visible
            result.failures.append(f"page {number} : appel E3 impossible ({exc})")
            continue
        tables, failures = parse_tables(answer.text, page, known)
        # Une page annoncée par E1 devrait normalement donner un tableau. Une
        # réponse hors contrat reçoit donc une chance supplémentaire, sans jamais
        # transformer l'essai invalide en donnée utilisable.
        if not tables and failures:
            try:
                retry = client.ask(
                    steps.system_prompt(),
                    prompt + "\nRappel : utilise exactement des blocs TABLEAU…FIN et des citations de cette page.",
                    max_tokens=TABLE_TOKENS,
                )
                retry_tables, retry_failures = parse_tables(retry.text, page, known)
                if retry_tables:
                    tables, failures = retry_tables, retry_failures
                else:
                    failures.extend(retry_failures)
            except LLMError as exc:
                failures.append(f"page {number} : relance E3 impossible ({exc})")
        summary = ", ".join(f"{table.tour} ({len(table.values)} candidats)" for table in tables) or "aucun"
        log(f"   page {number} : tableau(x) valide(s) : {summary}")
        for failure in failures:
            log(f"   ✗ {failure}")
        if not tables:
            cut = " (réponse tronquée)" if getattr(answer, "truncated", False) else ""
            log(f"   fin de la réponse{cut} : {tail(answer.text)}")
        result.failures.extend(failures)
        for table in tables:
            key = frozenset(_norm(item.name) for item in table.values)
            if key in seen_sets:
                result.failures.append(f"page {number} : jeu de candidats déjà extrait, tableau écarté")
                continue
            seen_sets.add(key)
            result.tables.append(table)
    return result
