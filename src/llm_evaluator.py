from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import random
import re
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

PROMPT_VERSION = "thesis-appendix-b-final"

N1_META_MARKER = "nije odvojeno; sadržano na početku bodyja"
METADATA_IN_BODY_TEXT = "nije posebno izdvojeno; sadržano je na početku teksta"

TONE_BASIS_TO_VALUE = {
    "strong_attack": -2,
    "critical_targeting": -1,
    "neutral_treatment": 0,
    "supportive_platform": 1,
    "strong_support": 2,
}

BALANCE_BASIS_TO_VALUE = {
    "single_perspective": 0,
    "unequal_perspectives": 1,
    "roughly_equal_perspectives": 2,
}

ALLOWED_FRAMINGS = {
    "konflikt",
    "odgovornost",
    "ekonomski",
    "moralni",
    "proceduralni",
    "nacionalni",
    "neutralan",
}

ALLOWED_LEANS = {
    "neutralan",
    "nejasno",
    "pro_vlast",
    "pro_opozicija",
    "pro_bosnjacka_opcija",
    "pro_srpska_opcija",
    "pro_hrvatska_opcija",
    "pro_gradjanska_opcija",
}

ALLOWED_ACTORS: set[str] = set()
ACTOR_ALIASES: dict[str, str] = {}
SYSTEM_PROMPT = ""
USER_PROMPT_TEMPLATE = ""
PROMPT_TEMPLATE_SHA256 = ""

SYSTEM_PROMPT_TEMPLATE = """Ti si stručan analitičar političkog diskursa u
bosanskohercegovačkim medijima.

Analizu radi ovim redom:
1. odredi dominantnog aktera
2. odredi kako članak tretira upravo tog aktera
3. odredi framing
4. prebroj stvarno zastupljene političke perspektive
5. odredi urednički political lean

Ključna pravila:
- Ton dominantnog aktera prema drugima NIJE ton članka prema njemu.
- Formalno pripisivanje izjave ne čini članak automatski neutralnim.
- Neutralno napisan članak nije automatski balansiran.
- Ishod sudske ili institucionalne odluke sam po sebi nije political lean.
- Ne izmišljaj činjenice ni političke veze izvan članka i navedene mape.
- Najprije odredi smjer tona, zatim njegov intenzitet. Ne biraj srednju
  vrijednost samo zato što djeluje sigurnije ili zato što je ekstrem rjeđi.
- Vrati isključivo JSON prema zadanoj shemi.

## Politička mapa za analizirani period
{POLITICKA_MAPA_ZA_ANALIZIRANI_PERIOD}
"""

USER_PROMPT_BASE = """# 1. DOMINANTNI AKTER

Odredi aktera o kojem članak najviše govori. To je tema članka, a ne
automatski osoba koja je dala izjavu. U pravilu vrati jednog aktera.
Dva aktera odvojena zarezom dozvoljena su samo kada su stvarno
ravnopravno zastupljena.

Koristi tačno nazive ispod, malim slovima bez dijakritike.

Pojedinci:
{LISTA_POJEDINACA}

Stranke:
{LISTA_POLITICKIH_STRANAKA}

Institucije/entiteti:
{LISTA_INSTITUCIJA_I_DRUGIH_POLITICKIH_CJELINA}

Normalizacija:
{PRAVILA_NORMALIZACIJE_OZNAKA}

Ako konkretna osoba nije na listi, koristi njenu stranku ili instituciju
samo kada je to stvarni predmet članka. Ne mijenjaj predmet samo radi liste.

Hijerarhija:
1. Ako je članak prvenstveno o instituciji -> institucija.
2. Ako je prvenstveno o političaru -> političar.
3. Ako je prvenstveno o političkoj stranci -> stranka.

# 2. TONE_BASIS -- TRETMAN DOMINANTNOG AKTERA

Ton određuj u DVA KORAKA:

A) SMJER
- negativan
- neutralan
- pozitivan

B) INTENZITET
- običan/umjeren
- izrazit/snažan

Najprije dovrši:
"Dominantni akter je ___; članak ga prikazuje negativno, neutralno ili
pozitivno; najjači urednički signal je ___."

Vrati jednu vrijednost:

- strong_attack
  Mapa: tone=-2.
  Izrazito negativan UREDNIČKI tretman dominantnog aktera. Koristi kada
  vrijedi najmanje jedan od ova dva uslova:
  A) postoji jedan odlučujući urednički signal u naslovu ili leadu, a
     ostatak teksta ga dosljedno pojačava; ILI
  B) postoje najmanje dva nezavisna snažna urednička signala.
  Snažni signali uključuju:
  - ismijavanje, demonizaciju ili diskreditirajuću formulaciju
  - nepripisanu tvrdnju o kriminalu, izdaji, nesposobnosti ili moralnoj
    neprihvatljivosti predstavljenu kao činjenicu
  - sistemsko građenje izrazito negativne slike kroz naslov, lead i body
  - propagandni ili mobilizirajući tretman protiv aktera

- critical_targeting
  Mapa: tone=-1.
  Akter je jasno negativno predstavljen, meta kritike, optužbe, osude,
  nepovoljne odluke ili pripisane odgovornosti, ali portal ne prelazi prag
  izrazito diskreditirajućeg ili propagandnog tretmana.

- neutral_treatment
  Mapa: tone=0.
  Akter je prikazan faktografski, proceduralno ili uravnoteženo, bez jasnog
  pozitivnog ili negativnog uredničkog tretmana.

- supportive_platform
  Mapa: tone=+1.
  Akter je predstavljen pretežno povoljno ili mu članak daje nekritičku
  platformu: njegova poruka dominira, nema stvarne provjere ili relevantnog
  odgovora, ali nema izrazito promotivnog/slavljeničkog tretmana.

- strong_support
  Mapa: tone=+2.
  Izrazito pozitivan, promotivan ili afirmativan UREDNIČKI tretman
  dominantnog aktera. Heroizacija je dovoljan, ali nije obavezan uslov.
  Koristi kada vrijedi najmanje jedan od ova dva uslova:
  A) postoji jedan odlučujući promotivni signal u naslovu ili leadu, a
     ostatak teksta ga dosljedno pojačava; ILI
  B) postoje najmanje dva nezavisna snažna pozitivna urednička signala.
  Snažni signali uključuju:
  - superlative, slavljenje, heroizaciju ili emotivnu pohvalu
  - uredničko predstavljanje aktera kao izuzetno uspješnog, presudnog,
    zaštitnika, pobjednika ili uzora
  - nekritičko ponavljanje uspjeha i zasluga kroz cijeli tekst
  - propagandni ili kampanjski tretman u korist aktera
  Članak ne mora aktera doslovno nazvati spasiteljem da bi bio +2. Dovoljno
  je da je ukupni urednički paket izrazito promotivan i znatno jači od
  obične nekritičke platforme.

GRANICE IZMEĐU KATEGORIJA:
- -1 naspram -2:
  Ako je teška kritika jasno pripisana izvoru i portal je prenosi uglavnom
  izvještajno, koristi critical_targeting.
  Ako portal optužbu usvaja, pojačava, ponavlja ili dodaje vlastiti
  diskreditirajući okvir, koristi strong_attack.
- +1 naspram +2:
  Ako portal samo nekritički prenosi stav ili daje povoljan prostor,
  koristi supportive_platform.
  Ako naslov, lead i izbor konteksta aktivno promovišu, slave ili
  izrazito uzdižu aktera, koristi strong_support.

OBAVEZNE KONTROLE:
- Ton dominantnog aktera prema drugima NIJE ton članka prema njemu.
- Negativne riječi koje akter izgovara o drugima ne znače negativan ton
  prema tom akteru.
- Naslov i lead imaju veliku uredničku težinu, ali ne broj isti signal
  dvaput samo zato što je ista tvrdnja ponovljena.
- Ne pokušavaj postići unaprijed zadanu raspodjelu kategorija. Koristi svih
  pet kategorija samo kada ih konkretni dokazi opravdavaju.
- Ako si prvobitno izabrao critical_targeting ili supportive_platform,
  obavezno provjeri da li postoji odlučujući signal ili najmanje dva
  nezavisna snažna signala za strong_attack ili strong_support.

PRIMJERI GRANICE:
A) Naslov: "Opozicija optužila ministra za kriminal"; tekst jasno pripisuje
   tvrdnju opoziciji i izvještava bez dodatnog diskreditiranja.
   dominantni akter=ministar -> critical_targeting (-1).
B) Naslov/lead portalovim glasom predstavlja ministra kao kriminalca, tekst
   ponavlja optužbu kao činjenicu i selektivno gradi sliku moralno
   neprihvatljivog aktera bez distance.
   dominantni akter=ministar -> strong_attack (-2).
C) Članak uglavnom prenosi govor političara, njegove argumente i jednu
   pozitivnu poruku bez provjere ili odgovora.
   dominantni akter=političar -> supportive_platform (+1).
D) Naslov i lead slave "historijski uspjeh", koriste superlative, a cijeli
   tekst selektivno niže zasluge aktera bez kritičkog konteksta.
   dominantni akter=političar -> strong_support (+2).

# 3. FRAMING

Vrati jednu vrijednost:
konflikt, odgovornost, ekonomski, moralni, proceduralni,
nacionalni ili neutralan.

- konflikt: sukob, prepucavanje, podjele
- odgovornost: ko je kriv ili odgovoran
- ekonomski: budžet, cijene, dug i materijalne posljedice
- moralni: etička osuda ili ispravno/pogrešno
- proceduralni: zakon, institucije, izbori, glasanje, imenovanja
- nacionalni: identitet, konstitutivnost, entitetska i kolektivna prava
- neutralan: nema izraženog okvira

Kod dileme koristi naslov i lead kao urednički signal.

# 4. BALANCE_BASIS -- PERSPEKTIVE, NE NEUTRALNOST

Vrati jednu vrijednost:

- single_perspective
  Samo jedna relevantna politička perspektiva; stranačko saopćenje; jedna
  izjava bez odgovora; ili suha proceduralna vijest bez suprotstavljenih
  perspektiva. Mapa: balance=0.

- unequal_perspectives
  Najmanje dvije relevantne suprotstavljene perspektive postoje, ali jedna
  dobija osjetno manje prostora, detalja ili slabiji tretman. Mapa: balance=1.

- roughly_equal_perspectives
  Najmanje dvije relevantne suprotstavljene perspektive dobijaju približno
  jednak prostor, detalje i tretman. Mapa: balance=2.

OBAVEZNE KONTROLE:
- Neutralan/faktografski tekst bez više perspektiva = single_perspective.
- Više izvora koji zastupaju isti stav i dalje su jedna perspektiva.
- Pozadinske činjenice nisu druga politička perspektiva.
- Jasno citirana ili prepričana suprotna politička pozicija računa se kao
  druga perspektiva čak i kada nije direktan odgovor na glavnu izjavu.
- Samo kratko spominjanje imena druge strane, bez njenog stava ili argumenta,
  nije druga perspektiva.
- unequal_perspectives koristi kada su dva suprotna stava stvarno prisutna,
  ali je jedan mnogo kraći, slabije objašnjen ili stavljen u podređen položaj.
- Za roughly_equal_perspectives moraš moći imenovati najmanje dvije
  suprotstavljene strane koje su stvarno dobile približno jednak tretman.

# 5. POLITICAL_LEAN

Political lean je urednički tretman cijelog članka, a ne samo pripadnost
izvora ili strana kojoj odgovara ishod događaja.

Vrijednosti:
neutralan, nejasno, pro_vlast, pro_opozicija, pro_bosnjacka_opcija,
pro_srpska_opcija, pro_hrvatska_opcija, pro_gradjanska_opcija.

Prvo provjeri postoji li UREDNIČKI SIGNAL:
1. naslov prihvata, pojačava ili vrijednosno oblikuje tvrdnju jedne strane
2. članak jednostrano amplificira političku/nacionalnu poruku bez odgovora
3. selekcija citata, prostora i konteksta sistemski favorizira jednu opciju
4. autor koristi zaštitnički, optužujući ili nacionalno mobilizirajući jezik

Odluka:
- Neutralan nije podrazumijevana vrijednost. Prvo pokušaj utvrditi postoji
  li uredničko favoriziranje. Tek ako ga zaista nema, koristi neutralan.
- Ne koristi nejasno samo zato što nisi potpuno siguran. Nejasno koristi
  samo kada postoje stvarno kontradiktorni urednički signali.
- Ako je signal jasan -> odgovarajuća pro_* vrijednost.

Važne kontrole:
- Formalno "X je rekao" nije samo po sebi neutralizacija. Jednostrano
  amplificiranje saopćenja može imati lean.
- Ali balance=0 samo po sebi nije dovoljan za lean; mora postojati
  politička ili nacionalna poruka koju urednički tretman amplificira.
- Suho prenošenje sudske/institucionalne odluke ostaje neutralno čak i kada
  odluka politički koristi ili šteti određenoj strani.
- Pozitivan/negativan tone prema pojedincu nije automatski political lean.

# IZLAZ

Vrati tačno sljedeća polja:
dominant_actor, tone_basis, framing, balance_basis, political_lean.

Vrati isključivo JSON prema zadanoj shemi.

# ČLANAK

PORTAL: {portal}
NASLOV: {title}
DATUM: {date}
KATEGORIJA / NADNASLOV: {category}
LEAD / UVOD: {lead}

TEKST:
{body}
"""

def actor_key(value: Any) -> str:
    text = str(value or "").strip().casefold()
    text = text.replace("đ", "d")
    text = "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    text = text.replace("&", " i ")
    text = re.sub(r"[.\-_/]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def load_configuration(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Konfiguracija mora biti JSON objekt.")
    required = {"political_map", "individuals", "parties", "institutions", "normalization"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Nedostaju konfiguracijska polja: {sorted(missing)}")
    for key in ("individuals", "parties", "institutions"):
        if not isinstance(data[key], list) or not all(isinstance(x, str) for x in data[key]):
            raise ValueError(f"Polje {key!r} mora biti lista stringova.")
    if not isinstance(data["political_map"], str):
        raise ValueError("Polje 'political_map' mora biti string.")
    if not isinstance(data["normalization"], dict):
        raise ValueError("Polje 'normalization' mora biti objekt.")
    return data

def apply_configuration(data: dict[str, Any]) -> None:
    global ALLOWED_ACTORS
    global ACTOR_ALIASES
    global SYSTEM_PROMPT
    global USER_PROMPT_TEMPLATE
    global PROMPT_TEMPLATE_SHA256

    individuals = [actor_key(x) for x in data["individuals"]]
    parties = [actor_key(x) for x in data["parties"]]
    institutions = [actor_key(x) for x in data["institutions"]]
    aliases = {
        actor_key(alias): actor_key(canonical)
        for alias, canonical in data["normalization"].items()
    }

    ALLOWED_ACTORS = set(individuals + parties + institutions)
    ACTOR_ALIASES = aliases

    normalization_text = "; ".join(
        f"{actor_key(alias)}→{actor_key(canonical)}"
        for alias, canonical in data["normalization"].items()
    )

    SYSTEM_PROMPT = SYSTEM_PROMPT_TEMPLATE.replace(
        "{POLITICKA_MAPA_ZA_ANALIZIRANI_PERIOD}",
        data["political_map"].strip(),
    )

    USER_PROMPT_TEMPLATE = USER_PROMPT_BASE
    USER_PROMPT_TEMPLATE = USER_PROMPT_TEMPLATE.replace(
        "{LISTA_POJEDINACA}",
        ", ".join(individuals),
    )
    USER_PROMPT_TEMPLATE = USER_PROMPT_TEMPLATE.replace(
        "{LISTA_POLITICKIH_STRANAKA}",
        ", ".join(parties),
    )
    USER_PROMPT_TEMPLATE = USER_PROMPT_TEMPLATE.replace(
        "{LISTA_INSTITUCIJA_I_DRUGIH_POLITICKIH_CJELINA}",
        ", ".join(institutions),
    )
    USER_PROMPT_TEMPLATE = USER_PROMPT_TEMPLATE.replace(
        "{PRAVILA_NORMALIZACIJE_OZNAKA}",
        normalization_text,
    )

    PROMPT_TEMPLATE_SHA256 = hashlib.sha256(
        (SYSTEM_PROMPT + "\n\n" + USER_PROMPT_TEMPLATE).encode("utf-8")
    ).hexdigest()

ANNOTATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "dominant_actor": {"type": "string"},
        "tone_basis": {
            "type": "string",
            "enum": sorted(TONE_BASIS_TO_VALUE),
        },
        "framing": {
            "type": "string",
            "enum": sorted(ALLOWED_FRAMINGS),
        },
        "balance_basis": {
            "type": "string",
            "enum": sorted(BALANCE_BASIS_TO_VALUE),
        },
        "political_lean": {
            "type": "string",
            "enum": sorted(ALLOWED_LEANS),
        },
    },
    "required": [
        "dominant_actor",
        "tone_basis",
        "framing",
        "balance_basis",
        "political_lean",
    ],
}


GEMINI_ANNOTATION_SCHEMA = json.loads(json.dumps(ANNOTATION_SCHEMA))
GEMINI_ANNOTATION_SCHEMA.pop("additionalProperties", None)


@dataclass
class ProviderResult:
    text: str
    response_id: str = ""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class LLMProvider:
    name = "base"

    def prepare_attempt(self, attempt: int) -> None:
        pass

    def preflight(self, model: str) -> None:
        pass

    def call(self, system: str, user: str, model: str) -> ProviderResult:
        raise NotImplementedError


def is_transient_error(exc: Exception) -> bool:
    message = str(exc).casefold()
    tokens = (
        "rate limit",
        "timeout",
        "timed out",
        "connection",
        "temporarily",
        "server error",
        "service unavailable",
        "internal error",
        "429",
        "500",
        "502",
        "503",
        "504",
    )
    return any(token in message for token in tokens)


def strip_json_fence(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        match = re.match(
            r"^```(?:json)?\s*(.*?)\s*```$",
            cleaned,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if match:
            cleaned = match.group(1).strip()
    return cleaned


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self) -> None:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Nije pronađen OPENAI_API_KEY.")
        self.client = OpenAI(api_key=api_key)

    def _create(
        self,
        model: str,
        messages: list[dict[str, str]],
        structured: bool,
        include_temperature: bool,
    ):
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        if structured:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "media_bias_annotation",
                    "strict": True,
                    "schema": ANNOTATION_SCHEMA,
                },
            }
        else:
            kwargs["response_format"] = {"type": "json_object"}

        if include_temperature:
            kwargs["temperature"] = 0.0

        return self.client.chat.completions.create(**kwargs)

    def call(self, system: str, user: str, model: str) -> ProviderResult:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        last_error: Optional[Exception] = None
        for structured, include_temperature in (
            (True, True),
            (True, False),
            (False, True),
            (False, False),
        ):
            try:
                response = self._create(
                    model=model,
                    messages=messages,
                    structured=structured,
                    include_temperature=include_temperature,
                )
                usage = getattr(response, "usage", None)
                return ProviderResult(
                    text=response.choices[0].message.content or "",
                    response_id=getattr(response, "id", "") or "",
                    prompt_tokens=getattr(usage, "prompt_tokens", None),
                    completion_tokens=getattr(usage, "completion_tokens", None),
                    total_tokens=getattr(usage, "total_tokens", None),
                )
            except Exception as exc:
                last_error = exc
                if is_transient_error(exc):
                    raise

        assert last_error is not None
        raise last_error


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, max_tokens: int = 768) -> None:
        import anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Nije pronađen ANTHROPIC_API_KEY.")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.max_tokens = max_tokens

    def call(self, system: str, user: str, model: str) -> ProviderResult:


        last_error: Optional[Exception] = None
        variants = (
            {"thinking": {"type": "disabled"}, "temperature": 0.0},
            {"thinking": {"type": "disabled"}},
            {"temperature": 0.0},
            {},
        )

        for optional_kwargs in variants:
            try:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=self.max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                    **optional_kwargs,
                )

                text_blocks = [
                    block.text
                    for block in response.content
                    if getattr(block, "type", None) == "text"
                    and getattr(block, "text", None)
                ]
                if not text_blocks:
                    raise ValueError("Claude odgovor ne sadrži tekstualni blok.")

                usage = getattr(response, "usage", None)
                input_tokens = getattr(usage, "input_tokens", None)
                output_tokens = getattr(usage, "output_tokens", None)
                total_tokens = (
                    input_tokens + output_tokens
                    if isinstance(input_tokens, int) and isinstance(output_tokens, int)
                    else None
                )

                return ProviderResult(
                    text=strip_json_fence("\n".join(text_blocks)),
                    response_id=getattr(response, "id", "") or "",
                    prompt_tokens=input_tokens,
                    completion_tokens=output_tokens,
                    total_tokens=total_tokens,
                )
            except Exception as exc:
                last_error = exc
                if is_transient_error(exc):
                    raise

        assert last_error is not None
        raise last_error


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self,
        thinking_level: str = "low",
        max_output_tokens: int = 2048,
    ) -> None:
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError(
                "Gemini provider zahtijeva paket google-genai."
            ) from exc

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("Nije pronađen GEMINI_API_KEY ili GOOGLE_API_KEY.")

        self.client = genai.Client(api_key=api_key)
        self.thinking_level = thinking_level
        self.max_output_tokens = max_output_tokens

    def _config(self, include_temperature: bool, include_thinking: bool):
        from google.genai import types

        config_kwargs: dict[str, Any] = {
            "system_instruction": None,                    
            "response_mime_type": "application/json",
            "response_schema": GEMINI_ANNOTATION_SCHEMA,
            "max_output_tokens": self.max_output_tokens,
        }

        if include_temperature:
            config_kwargs["temperature"] = 0.0

        if include_thinking and self.thinking_level != "none":
            level_map = {
                "minimal": types.ThinkingLevel.MINIMAL,
                "low": types.ThinkingLevel.LOW,
                "medium": types.ThinkingLevel.MEDIUM,
                "high": types.ThinkingLevel.HIGH,
            }
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_level=level_map[self.thinking_level]
            )

        return config_kwargs

    def call(self, system: str, user: str, model: str) -> ProviderResult:
        from google.genai import types

        last_error: Optional[Exception] = None
        include_thinking_first = self.thinking_level != "none"
        variants = (
            (True, include_thinking_first),
            (False, include_thinking_first),
            (True, False),
            (False, False),
        )

        seen: set[tuple[bool, bool]] = set()
        for include_temperature, include_thinking in variants:
            key = (include_temperature, include_thinking)
            if key in seen:
                continue
            seen.add(key)

            try:
                config_kwargs = self._config(
                    include_temperature=include_temperature,
                    include_thinking=include_thinking,
                )
                config_kwargs["system_instruction"] = system
                config = types.GenerateContentConfig(**config_kwargs)

                response = self.client.models.generate_content(
                    model=model,
                    contents=user,
                    config=config,
                )

                text = strip_json_fence(getattr(response, "text", None) or "")
                if not text:
                    raise ValueError("Gemini odgovor ne sadrži JSON tekst.")

                usage = getattr(response, "usage_metadata", None)
                prompt_tokens = getattr(usage, "prompt_token_count", None)
                completion_tokens = getattr(usage, "candidates_token_count", None)
                thoughts_tokens = getattr(usage, "thoughts_token_count", None)
                total_tokens = getattr(usage, "total_token_count", None)

                if (
                    isinstance(completion_tokens, int)
                    and isinstance(thoughts_tokens, int)
                ):
                    completion_tokens += thoughts_tokens

                response_id = (
                    getattr(response, "response_id", None)
                    or getattr(response, "id", None)
                    or ""
                )

                return ProviderResult(
                    text=text,
                    response_id=str(response_id),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
            except Exception as exc:
                last_error = exc
                if is_transient_error(exc):
                    raise

        assert last_error is not None
        raise last_error


class XAIProvider(OpenAIProvider):

    name = "xai"

    def __init__(
        self,
        reasoning_effort: str = "auto",
        cache_id: str = "",
    ) -> None:
        from openai import OpenAI

        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            raise RuntimeError("Nije pronađen XAI_API_KEY.")

        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
            timeout=3600.0,
        )
        self.reasoning_effort = reasoning_effort
        self.cache_id = cache_id

    def _effective_reasoning_effort(self, model: str) -> Optional[str]:
        if self.reasoning_effort != "auto":
            return None if self.reasoning_effort == "default" else self.reasoning_effort

        key = model.casefold()
        if key.startswith("grok-4.5"):

            return "medium"


        return None

    def _create(
        self,
        model: str,
        messages: list[dict[str, str]],
        structured: bool,
        include_temperature: bool,
    ):
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        if self.cache_id:
            kwargs["extra_headers"] = {"x-grok-conv-id": self.cache_id}

        if structured:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "media_bias_annotation",
                    "strict": True,
                    "schema": ANNOTATION_SCHEMA,
                },
            }
        else:
            kwargs["response_format"] = {"type": "json_object"}

        effort = self._effective_reasoning_effort(model)
        if effort is not None:
            kwargs["extra_body"] = {"reasoning_effort": effort}


        if include_temperature and effort in {None, "none"}:
            kwargs["temperature"] = 0.0

        return self.client.chat.completions.create(**kwargs)


class OpenRouterProvider(OpenAIProvider):

    name = "openrouter"

    def __init__(self, max_tokens: int = 8192) -> None:
        from openai import OpenAI

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("Nije pronađen OPENROUTER_API_KEY.")

        self.client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/gichbe/media-bias-analysis-thesis",
                "X-Title": "BiH Media Bias Thesis",
            },
        )
        self.max_tokens = max_tokens

    def _create(
        self,
        model: str,
        messages: list[dict[str, str]],
        structured: bool,
        include_temperature: bool,
    ):
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "extra_body": {
                "reasoning": {
                    "enabled": True,
                    "exclude": True,
                },
                "provider": {
                    "require_parameters": True,
                },
            },
        }

        if structured:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "media_bias_annotation",
                    "strict": True,
                    "schema": ANNOTATION_SCHEMA,
                },
            }
        else:
            kwargs["response_format"] = {"type": "json_object"}

        if include_temperature:
            kwargs["temperature"] = 0.0

        return self.client.chat.completions.create(**kwargs)


class OllamaProvider(LLMProvider):

    name = "ollama"

    def __init__(
        self,
        host: str,
        num_ctx: int,
        num_predict: int,
        timeout: float,
        keep_alive: str,
        seed: int,
        think: bool,
    ) -> None:
        normalized_host = host.strip().rstrip("/")
        if not re.match(r"^https?://", normalized_host, flags=re.IGNORECASE):
            normalized_host = f"http://{normalized_host}"

        self.host = normalized_host
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.timeout = timeout
        self.keep_alive = keep_alive
        self.seed = seed
        self.think = think
        self.attempt = 1

    def prepare_attempt(self, attempt: int) -> None:
        self.attempt = max(1, attempt)

    def _request_json(
        self,
        method: str,
        path: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{self.host}{path}",
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            try:
                details_obj = json.loads(details)
                details = str(details_obj.get("error", details))
            except json.JSONDecodeError:
                pass
            raise RuntimeError(f"Ollama HTTP {exc.code}: {details[:500]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Nije moguće povezati se na Ollamu ({self.host}): {exc.reason}"
            ) from exc
        except TimeoutError as exc:
            raise RuntimeError(
                f"Ollama poziv je istekao nakon {self.timeout:.0f} sekundi."
            ) from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Ollama nije vratila validan JSON odgovor: {raw[:500]!r}"
            ) from exc

        if not isinstance(parsed, dict):
            raise RuntimeError("Ollama odgovor nije JSON objekt.")
        if parsed.get("error"):
            raise RuntimeError(f"Ollama greška: {parsed['error']}")
        return parsed

    def preflight(self, model: str) -> None:
        version = self._request_json("GET", "/api/version")
        tags = self._request_json("GET", "/api/tags")
        installed = {
            str(item.get("name", "")).strip()
            for item in tags.get("models", [])
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        }

        acceptable = {model}
        if ":" not in model:
            acceptable.add(f"{model}:latest")

        if not installed.intersection(acceptable):
            sample = ", ".join(sorted(installed)[:8]) or "nijedan"
            raise RuntimeError(
                f"Ollama model {model!r} nije instaliran. Instalirani: {sample}"
            )

        logger.info(
            "Ollama %s | model=%s | num_ctx=%d | num_predict=%d | think=%s",
            str(version.get("version", "nepoznata")),
            model,
            self.num_ctx,
            self.num_predict,
            self.think,
        )

    @staticmethod
    def _clean_content(text: str) -> str:
        cleaned = (text or "").strip()
        cleaned = re.sub(
            r"^\s*<think>.*?</think>\s*",
            "",
            cleaned,
            flags=re.DOTALL | re.IGNORECASE,
        )
        return strip_json_fence(cleaned)

    def call(self, system: str, user: str, model: str) -> ProviderResult:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "think": self.think,
            "format": ANNOTATION_SCHEMA,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": 0.0,
                "seed": self.seed + self.attempt - 1,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
        }

        response = self._request_json("POST", "/api/chat", payload)
        message = response.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Ollama odgovor nema polje message.")

        content = self._clean_content(str(message.get("content", "")))
        if not content:
            raise RuntimeError("Ollama je vratila prazan odgovor.")

        prompt_tokens = response.get("prompt_eval_count")
        completion_tokens = response.get("eval_count")
        total_tokens = None
        if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
            total_tokens = prompt_tokens + completion_tokens

        created_at = str(response.get("created_at", "")).strip()
        response_id = f"ollama:{model}:{created_at}" if created_at else ""

        return ProviderResult(
            text=content,
            response_id=response_id,
            prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
            completion_tokens=(
                completion_tokens if isinstance(completion_tokens, int) else None
            ),
            total_tokens=total_tokens,
        )


def clean_field(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "null"}:
        return default
    return text


def normalize_ws(value: Any) -> str:
    return re.sub(r"\s+", " ", clean_field(value)).strip()


def remove_first_exact_title_line(body: str, title: str) -> str:
    target = normalize_ws(title).casefold()
    if not target:
        return body

    output: list[str] = []
    nonempty_seen = 0
    removed = False

    for line in body.splitlines():
        if line.strip() and not removed:
            nonempty_seen += 1
            if nonempty_seen <= 5 and normalize_ws(line).casefold() == target:
                removed = True
                continue
        output.append(line)

    return "\n".join(output).strip()


def strip_category_from_lead(lead: str, category: str) -> str:
    match = re.match(r"^\[([^\]]+)\]\s*", lead)
    if (
        match
        and category
        and normalize_ws(match.group(1)).casefold()
        == normalize_ws(category).casefold()
    ):
        return lead[match.end():].strip()
    return lead


def lead_is_body_prefix(lead: str, body: str) -> bool:
    normalized_lead = normalize_ws(lead)
    normalized_body = normalize_ws(body)
    return bool(
        normalized_lead
        and normalized_body
        and normalized_body.casefold().startswith(normalized_lead.casefold())
    )


def prepare_prompt_fields(
    article: dict[str, Any],
    max_body_chars: int,
) -> dict[str, str]:
    portal = clean_field(article.get("portal"), "nepoznat")
    title = clean_field(article.get("title"), "bez naslova")
    date = clean_field(
        article.get("date_published", article.get("date")),
        "nepoznat",
    )
    category = clean_field(article.get("category"), "nije navedena")
    lead = clean_field(article.get("lead"), "nije naveden")
    body = clean_field(article.get("body"))

    body = remove_first_exact_title_line(body, title)
    lead = strip_category_from_lead(lead, category)

    if (
        category.casefold() == N1_META_MARKER.casefold()
        or lead.casefold() == N1_META_MARKER.casefold()
    ):
        category = METADATA_IN_BODY_TEXT
        lead = METADATA_IN_BODY_TEXT
    elif lead_is_body_prefix(lead, body):
        lead = METADATA_IN_BODY_TEXT

    if max_body_chars > 0 and len(body) > max_body_chars:
        head_chars = int(max_body_chars * 0.7)
        tail_chars = max_body_chars - head_chars
        body = (
            body[:head_chars].rstrip()
            + "\n\n[...skraćen srednji dio članka...]\n\n"
            + body[-tail_chars:].lstrip()
        )

    return {
        "portal": portal,
        "title": title,
        "date": date,
        "category": category,
        "lead": lead,
        "body": body,
    }


def build_user_prompt(article: dict[str, Any], max_body_chars: int) -> str:
    return USER_PROMPT_TEMPLATE.format(
        **prepare_prompt_fields(article, max_body_chars)
    )


def normalize_actor(value: Any) -> str:
    raw = normalize_ws(value)
    if not raw:
        return ""

    parts = [part.strip() for part in raw.split(",") if part.strip()]
    normalized_parts: list[str] = []

    for part in parts:
        key = actor_key(part)
        normalized_parts.append(ACTOR_ALIASES.get(key, key))

    return ",".join(normalized_parts)


def validate_annotation(annotation: Any) -> dict[str, Any]:
    if not isinstance(annotation, dict):
        raise ValueError("Izlaz nije JSON objekt.")

    required = {
        "dominant_actor",
        "tone_basis",
        "framing",
        "balance_basis",
        "political_lean",
    }

    missing = required - annotation.keys()
    extra = annotation.keys() - required
    if missing:
        raise ValueError(f"Nedostaju polja: {sorted(missing)}")
    if extra:
        raise ValueError(f"Nedozvoljena polja: {sorted(extra)}")

    tone_basis = annotation["tone_basis"]
    framing = annotation["framing"]
    balance_basis = annotation["balance_basis"]
    political_lean = annotation["political_lean"]

    if tone_basis not in TONE_BASIS_TO_VALUE:
        raise ValueError(f"Nevalidan tone_basis: {tone_basis!r}")
    if framing not in ALLOWED_FRAMINGS:
        raise ValueError(f"Nevalidan framing: {framing!r}")
    if balance_basis not in BALANCE_BASIS_TO_VALUE:
        raise ValueError(f"Nevalidan balance_basis: {balance_basis!r}")
    if political_lean not in ALLOWED_LEANS:
        raise ValueError(f"Nevalidan political_lean: {political_lean!r}")

    actor = normalize_actor(annotation["dominant_actor"])
    actor_parts = actor.split(",") if actor else []

    if len(actor_parts) not in {1, 2}:
        raise ValueError(f"Nevalidan broj dominantnih aktera: {actor!r}")
    if len(set(actor_parts)) != len(actor_parts):
        raise ValueError(f"Dupliciran dominantni akter: {actor!r}")

    invalid_actors = [part for part in actor_parts if part not in ALLOWED_ACTORS]
    if invalid_actors:
        raise ValueError(f"Nedozvoljen dominantni akter: {invalid_actors}")

    return {
        "dominant_actor": actor,
        "tone": TONE_BASIS_TO_VALUE[tone_basis],
        "tone_basis": tone_basis,
        "framing": framing,
        "balance": BALANCE_BASIS_TO_VALUE[balance_basis],
        "balance_basis": balance_basis,
        "political_lean": political_lean,
    }


def parse_and_validate(raw: str) -> dict[str, Any]:
    cleaned = strip_json_fence(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse greška: {exc}") from exc
    return validate_annotation(parsed)


def ollama_profile(
    model: str,
    num_ctx_override: Optional[int],
    num_predict_override: Optional[int],
    think_override: Optional[bool],
) -> tuple[int, int, bool]:
    key = model.casefold()

    if "qwen" in key:
        num_ctx, num_predict, think = 12288, 1024, False
    elif "gemma" in key:
        num_ctx, num_predict, think = 8192, 768, False
    else:
        num_ctx, num_predict, think = 8192, 1024, False

    if num_ctx_override is not None:
        num_ctx = num_ctx_override
    if num_predict_override is not None:
        num_predict = num_predict_override
    if think_override is not None:
        think = think_override

    return num_ctx, num_predict, think


def choose_provider(args: argparse.Namespace) -> LLMProvider:
    explicit = args.provider
    model_key = args.model.casefold()

    if explicit == "auto":
        if model_key.startswith("claude"):
            explicit = "anthropic"
        elif model_key.startswith("gemini"):
            explicit = "gemini"
        elif model_key.startswith("grok"):
            explicit = "xai"
        elif "kimi" in model_key or model_key.startswith("moonshot"):
            explicit = "openrouter"
        elif model_key.startswith(("qwen", "gemma")):
            explicit = "ollama"
        else:
            explicit = "openai"

    if explicit == "openai":
        return OpenAIProvider()
    if explicit == "anthropic":
        return AnthropicProvider(max_tokens=args.anthropic_max_tokens)
    if explicit == "gemini":
        return GeminiProvider(
            thinking_level=args.gemini_thinking_level,
            max_output_tokens=args.gemini_max_output_tokens,
        )
    if explicit == "xai":
        return XAIProvider(
            reasoning_effort=args.xai_reasoning_effort,
            cache_id=args.xai_cache_id,
        )
    if explicit == "openrouter":
        return OpenRouterProvider(max_tokens=args.openrouter_max_tokens)
    if explicit == "ollama":
        num_ctx, num_predict, think = ollama_profile(
            args.model,
            args.ollama_num_ctx,
            args.ollama_num_predict,
            args.ollama_think,
        )
        return OllamaProvider(
            host=args.ollama_host,
            num_ctx=num_ctx,
            num_predict=num_predict,
            timeout=args.ollama_timeout,
            keep_alive=args.ollama_keep_alive,
            seed=args.seed,
            think=think,
        )

    raise ValueError(f"Nepoznat provider: {explicit}")


def load_articles(path: Path) -> list[dict[str, Any]]:
    if path.suffix.casefold() == ".json":
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list):
            raise ValueError("JSON input mora biti lista članaka.")
        return data

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def stratified_sample(
    articles: list[dict[str, Any]],
    per_portal: int,
    seed: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for article in articles:
        portal = clean_field(article.get("portal"), "nepoznat").casefold()
        grouped.setdefault(portal, []).append(article)

    rng = random.Random(seed)
    selected: list[dict[str, Any]] = []
    for portal in sorted(grouped):
        group = grouped[portal]
        if len(group) < per_portal:
            raise ValueError(
                f"Portal {portal!r} ima samo {len(group)} članaka, "
                f"a traženo je {per_portal}."
            )
        selected.extend(rng.sample(group, per_portal))

    rng.shuffle(selected)
    return selected


OUTPUT_FIELDS = [
    "article_id",
    "portal",
    "url",
    "title",
    "date_published",
    "category",
    "lead",
    "annotator_id",
    "provider",
    "model",
    "model_label",
    "prompt_version",
    "prompt_template_sha256",
    "tone",
    "tone_basis",
    "framing",
    "balance",
    "balance_basis",
    "political_lean",
    "dominant_actor",
    "confidence",
    "notes",
    "response_id",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "attempts",
]


def existing_ids(output_path: Path) -> set[str]:
    if not output_path.exists() or output_path.stat().st_size == 0:
        return set()

    with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            clean_field(row.get("article_id"))
            for row in reader
            if clean_field(row.get("article_id"))
        }


def append_csv_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0

    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in OUTPUT_FIELDS})
        handle.flush()
        os.fsync(handle.fileno())


def append_failure(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        handle.flush()


def evaluate_article(
    provider: LLMProvider,
    model: str,
    article: dict[str, Any],
    max_body_chars: int,
    max_attempts: int,
    backoff_base: float,
) -> tuple[Optional[dict[str, Any]], Optional[ProviderResult], int, str]:
    base_user_prompt = build_user_prompt(article, max_body_chars)
    validation_hint = ""
    last_error = ""

    for attempt in range(1, max_attempts + 1):
        prompt = base_user_prompt
        if validation_hint:
            prompt += (
                "\n\nVAŽNO: Prethodni izlaz nije prošao validaciju: "
                f"{validation_hint}. Vrati potpuno novi validan JSON prema "
                "istoj zadanoj shemi."
            )

        try:
            provider.prepare_attempt(attempt)
            provider_result = provider.call(SYSTEM_PROMPT, prompt, model)
            annotation = parse_and_validate(provider_result.text)
            return annotation, provider_result, attempt, ""
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Pokušaj %d/%d nije uspio za %s: %s",
                attempt,
                max_attempts,
                clean_field(article.get("article_id")),
                last_error,
            )
            validation_hint = str(exc)[:350]

            if attempt < max_attempts:
                sleep_seconds = backoff_base * (2 ** (attempt - 1))
                sleep_seconds += random.uniform(0, min(1.0, backoff_base))
                time.sleep(sleep_seconds)

    return None, None, max_attempts, last_error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LLM annotation evaluator.")

    parser.add_argument("--input", required=True, help="Ulazni CSV ili JSON")
    parser.add_argument("--config", required=True, help="Konfiguracijski JSON")
    parser.add_argument("--model", required=True, help="Tačan provider/model ID")
    parser.add_argument("--model-label", default="", help="Naziv za CSV prikaz")
    parser.add_argument("--output", required=True, help="Izlazni CSV")
    parser.add_argument(
        "--provider",
        choices=[
            "auto",
            "openai",
            "anthropic",
            "gemini",
            "xai",
            "openrouter",
            "ollama",
        ],
        default="auto",
    )


    parser.add_argument("--anthropic-max-tokens", type=int, default=768)
    parser.add_argument(
        "--gemini-thinking-level",
        choices=["none", "minimal", "low", "medium", "high"],
        default="low",
    )
    parser.add_argument("--gemini-max-output-tokens", type=int, default=2048)
    parser.add_argument(
        "--xai-reasoning-effort",
        choices=["auto", "default", "none", "low", "medium", "high"],
        default="auto",
        help=(
            "auto: grok-4.5 uses medium, while other Grok model IDs use "
            "their provider-default reasoning configuration"
        ),
    )
    parser.add_argument(
        "--xai-cache-id",
        default="",
        help="Optional x-grok-conv-id header; empty disables it",
    )
    parser.add_argument("--openrouter-max-tokens", type=int, default=8192)

    parser.add_argument(
        "--ollama-host",
        default=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
    )
    parser.add_argument("--ollama-num-ctx", type=int, default=None)
    parser.add_argument("--ollama-num-predict", type=int, default=None)
    parser.add_argument("--ollama-timeout", type=float, default=900.0)
    parser.add_argument("--ollama-keep-alive", default="30m")
    think_group = parser.add_mutually_exclusive_group()
    think_group.add_argument(
        "--ollama-think",
        dest="ollama_think",
        action="store_true",
        help="Override thesis profile and enable local thinking mode",
    )
    think_group.add_argument(
        "--no-ollama-think",
        dest="ollama_think",
        action="store_false",
        help="Explicitly disable local thinking mode",
    )
    parser.set_defaults(ollama_think=None)
    parser.add_argument(
        "--skip-provider-preflight",
        action="store_true",
        help="Skip Ollama version/model availability check",
    )


    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sample-per-portal", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-body-chars", type=int, default=20000)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--backoff-base", type=float, default=2.0)
    parser.add_argument("--retry-delay", type=float, default=0.5)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Obriši postojeći output umjesto resume režima",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ne poziva model; provjeri input i ispiši prompt statistiku",
    )
    parser.add_argument(
        "--print-prompt",
        action="store_true",
        help="Ispiši sistemski i korisnički prompt za prvi članak i izađi",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    apply_configuration(load_configuration(Path(args.config)))

    input_path = Path(args.input)
    output_path = Path(args.output)
    failures_path = output_path.with_suffix(output_path.suffix + ".failures.jsonl")

    articles = load_articles(input_path)

    if args.sample_per_portal:
        articles = stratified_sample(
            articles,
            per_portal=args.sample_per_portal,
            seed=args.seed,
        )
    if args.limit is not None:
        articles = articles[: args.limit]

    if not articles:
        raise RuntimeError("Nema članaka za obradu.")

    if args.print_prompt:
        print("===== SYSTEM PROMPT =====")
        print(SYSTEM_PROMPT)
        print("\n===== USER PROMPT (PRVI ČLANAK) =====")
        print(build_user_prompt(articles[0], args.max_body_chars))
        print(f"\nPROMPT_TEMPLATE_SHA256={PROMPT_TEMPLATE_SHA256}")
        return

    if args.dry_run:
        prompt_lengths = [
            len(SYSTEM_PROMPT) + len(build_user_prompt(article, args.max_body_chars))
            for article in articles
        ]
        print(f"Članaka: {len(articles)}")
        print(f"Prompt template SHA256: {PROMPT_TEMPLATE_SHA256}")
        print(f"Ukupno prompt znakova: {sum(prompt_lengths):,}")
        print(
            "Gruba procjena input tokena: "
            f"{round(sum(prompt_lengths) / 4.5):,}–"
            f"{round(sum(prompt_lengths) / 3.5):,}"
        )
        return

    if args.overwrite:
        output_path.unlink(missing_ok=True)
        failures_path.unlink(missing_ok=True)

    completed = existing_ids(output_path)
    pending = [
        article
        for article in articles
        if clean_field(article.get("article_id")) not in completed
    ]

    logger.info(
        "Ukupno odabrano: %d | već završeno: %d | preostalo: %d",
        len(articles),
        len(articles) - len(pending),
        len(pending),
    )

    provider = choose_provider(args)
    if not args.skip_provider_preflight:
        provider.preflight(args.model)

    model_label = args.model_label.strip() or args.model
    successes = 0
    failures = 0

    for article in tqdm(pending, desc=f"LLM eval ({model_label})"):
        annotation, provider_result, attempts, error = evaluate_article(
            provider=provider,
            model=args.model,
            article=article,
            max_body_chars=args.max_body_chars,
            max_attempts=args.max_attempts,
            backoff_base=args.backoff_base,
        )

        if annotation is None or provider_result is None:
            failures += 1
            append_failure(
                failures_path,
                {
                    "article_id": article.get("article_id"),
                    "portal": article.get("portal"),
                    "url": article.get("url"),
                    "provider": provider.name,
                    "model": args.model,
                    "model_label": model_label,
                    "prompt_version": PROMPT_VERSION,
                    "prompt_template_sha256": PROMPT_TEMPLATE_SHA256,
                    "attempts": attempts,
                    "error": error,
                    "timestamp": datetime.now().isoformat(),
                },
            )
            continue

        output_row = {
            "article_id": article.get("article_id"),
            "portal": article.get("portal"),
            "url": article.get("url"),
            "title": article.get("title"),
            "date_published": article.get("date_published", article.get("date")),
            "category": article.get("category"),
            "lead": article.get("lead"),
            "annotator_id": f"LLM_{model_label}",
            "provider": provider.name,
            "model": args.model,
            "model_label": model_label,
            "prompt_version": PROMPT_VERSION,
            "prompt_template_sha256": PROMPT_TEMPLATE_SHA256,
            "tone": annotation["tone"],
            "tone_basis": annotation["tone_basis"],
            "framing": annotation["framing"],
            "balance": annotation["balance"],
            "balance_basis": annotation["balance_basis"],
            "political_lean": annotation["political_lean"],
            "dominant_actor": annotation["dominant_actor"],
            "confidence": "",
            "notes": "",
            "response_id": provider_result.response_id,
            "prompt_tokens": provider_result.prompt_tokens,
            "completion_tokens": provider_result.completion_tokens,
            "total_tokens": provider_result.total_tokens,
            "attempts": attempts,
        }

        append_csv_row(output_path, output_row)
        successes += 1
        time.sleep(args.retry_delay)

    logger.info(
        "Gotovo. Novi uspjesi: %d | neuspjesi: %d | output: %s",
        successes,
        failures,
        output_path,
    )
    if failures:
        logger.warning("Detalji neuspjeha: %s", failures_path)


if __name__ == "__main__":
    main()
