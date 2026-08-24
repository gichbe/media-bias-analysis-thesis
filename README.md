# media-bias-analysis-thesis

Kod, pseudonimizovani anotacijski podaci i dodatni materijali za završni rad o automatizovanoj analizi političke pristrasnosti medija primjenom velikih jezičkih modela u Bosni i Hercegovini.

## Sadržaj repozitorija

```text
analysis/          Skripte za statističku analizu i generisanje figura
data/annotations/  Pseudonimizovane ljudske i LLM anotacije
docs/              Anotacijski priručnik
src/               LLM evaluator
```

Glavni evaluacijski skup sadrži 458 članaka koje su nezavisno anotirala tri ljudska anotatora kroz pet dimenzija:

- dominantni politički akter
- ton
- okvir izvještavanja
- balansiranost
- politička usmjerenost

Isti skup evaluiran je pomoću 17 velikih jezičkih modela.

## Javni podaci

Direktorij `data/annotations/` sadrži anotacijske rezultate potrebne za ponovno računanje glavnih statističkih analiza.

Radi zaštite izvornog korpusa:

- tekstovi, naslovi i URL-ovi članaka nisu objavljeni
- stvarni nazivi medijskih izvora nisu objavljeni
- identiteti anotatora nisu objavljeni
- dominantni akteri su pseudonimizovani
- identifikatori članaka su nasumično preslikani

Isto pseudonimizacijsko preslikavanje koristi se kroz sve ljudske i modelske anotacije, čime se zadržavaju relacije potrebne za računanje slaganja i evaluacijskih metrika.

Detalji su navedeni u `data/annotations/README.md`.

## Instalacija

Preporučena verzija je Python 3.11 ili novija.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Pokretanje analize

Glavna analiza:

```bash
python3 analysis/main_analysis.py
```

Analiza tona uz uslov slaganja o dominantnom akteru:

```bash
python3 analysis/targeted_actor_analysis.py
```

Dodatne statističke analize:

```bash
python3 analysis/additional_statistics.py
```

Sve trenutno dostupne analize mogu se pokrenuti i preko:

```bash
python3 analysis/run_all.py
```

Rezultati se generišu u direktoriju `results/`, a figure u `figures/`.

## Anotacijski protokol

Kompletan anotacijski priručnik nalazi se u:

```text
docs/codebook.md
```

Priručnik definiše svih pet anotacijskih dimenzija, njihove kategorije i pravila odlučivanja.

## LLM evaluator

`src/llm_evaluator.py` sadrži implementaciju evaluacijskog pipelinea korištenog za anotiranje članaka pomoću različitih LLM providera.

Ulazni korpus nije javno distribuiran kroz ovaj repozitorij.

## Reproducibilnost

Objavljeni pseudonimizovani anotacijski podaci omogućavaju ponovno računanje glavnih mjera slaganja i poređenja ljudi i modela bez objavljivanja izvornog sadržaja članaka.

Zbog pseudonimizacije identifikatora redoslijed jedinica analize može se razlikovati od internog radnog skupa. Zbog toga se bootstrap intervali pouzdanosti mogu minimalno razlikovati pri ponovnom izvođenju, dok determinističke point-estimate metrike ostaju nepromijenjene.
