# CLAUDE.md — Projektgedächtnis / Handoff

**Zweck dieser Datei:** Du (Claude) liest diese Datei automatisch beim Start jeder neuen Session in diesem Repo. Sie fasst den kompletten Stand zusammen, damit eine neue Session (z. B. am PC des Nutzers, mit echtem Netzwerkzugriff) sofort weiterarbeiten kann, ohne den gesamten bisherigen Chatverlauf zu kennen. Zuletzt aktualisiert: 23.09.2026, nach dem News-Stimmungs-Pilot (`NEWS_SENTIMENT_PILOT_PROTOCOL.md`) — Ergebnis: **kein Beleg, dass GDELT-Stimmung die Übernacht-Auswahlstrategie verbessert** (Nullergebnis, p=0,065, falsche Richtung). Die Übernacht-Auswahlstrategie selbst (siehe `OVERNIGHT_SELECTION_PROTOCOL.md`) bleibt unverändert der beste bisherige Kandidat, mit wichtigen Einschränkungen (K8 ungelöst, K4 nur knapp).

**Für den Nutzer:** Wenn du eine neue Claude-Code-Session öffnest (z. B. an deinem PC), lädt sie diese Datei automatisch. Du kannst direkt "mach weiter" o. ä. sagen — Claude hat dann den vollen Kontext.

---

## 1. Was das hier ist

Ein AI-gestütztes Research-/Signal-/Paper-Trading-System für US-Aktien — **explizit kein Buy-and-Hold-Tool und kein vollautomatischer Trading-Bot.** Research- und Lerntool, keine Anlageberatung (siehe `DISCLAIMER.md`, wird in der Web-App als Banner angezeigt). Vollständige fachliche Spezifikation: `ROADMAP.md` (v2, ~20 Abschnitte, mit `[v2]`-Markern für alles, was gegenüber der ursprünglichen Nutzer-Roadmap verändert wurde, basierend auf Analyse + Transkript-Auswertung von DaviddTechs Trading-Methodik).

Alle 11 Phasen aus `ROADMAP.md` Abschnitt 19 sind implementiert (Details unten, Abschnitt 4). **270 Tests lokal grün** (Stand 21.09.2026). Seit 21.09.2026 gilt zusätzlich das vorregistrierte `VALIDATION_PROTOCOL.md` — der frühere 12-Punkte-Gate in `app/validation/gate.py` ist dadurch überholt (sein `walk_forward_stable`-Kriterium ließ eine wertlose Strategie in 50 % der Fälle bestehen).

---

## 2. Git-Stand

- **Branch:** `claude/ai-trading-app-roadmap-w0nrm2`
- **Letzter Commit:** `d9d56d4` (Fix: `backend-tests`-CI-Job schlug seit mehreren Commits fehl, `httpx`-Import in `test_providers.py` ungeschützt — behoben, CI wieder grün auf allen 4 Jobs)
- **Remote:** `https://github.com/benjaminkrug/TradingApp_V2`
- Lokaler Stand und `origin/claude/ai-trading-app-roadmap-w0nrm2` sind deckungsgleich (Stand 23.09.2026), CI grün (`frontend-build`, `backend-tests`, `backend-api-tests`, `probe-nautilus-trader` alle `success`).
- **Noch kein Pull Request erstellt** — der Branch liegt direkt auf GitHub, aber wurde nie in `main` gemerged. Das ist eine offene Entscheidung: PR erstellen? In `main` mergen? Bisher nicht gefragt/entschieden.

---

## 3. KRITISCH: Umgebungsunterschied Sandbox vs. PC

Die gesamte bisherige Entwicklung lief in einer Sandbox **ohne Netzwerkzugriff** auf:
- PyPI (`pypi.org`) — `pip install` funktioniert dort nicht
- npm-Registry (`registry.npmjs.org`) — `npm install` funktioniert dort nicht
- `api.alpaca.markets`, `api.polygon.io` — keine echten Marktdaten möglich

Alle drei geben `403 Forbidden` mit `x-deny-reason: host_not_allowed` (Organisationsrichtlinie der Sandbox, nicht temporär).

**Konsequenz für den bisherigen Code:** Vieles wurde geschrieben, aber nie lokal ausgeführt — nur über GitHub-Actions-CI verifiziert (dort ist Netzwerkzugriff vorhanden). Backend-Tests liefen immer nur mit reiner Standardbibliothek (kein `pip install` nötig). FastAPI-Tests und der komplette Frontend-Build liefen **ausschließlich in CI**, nie lokal in der Sandbox.

**Am PC sollte das alles anders sein** — echter Netzwerkzugriff heißt: `pip install`, `npm install`, und potenziell sogar eine echte Alpaca-Verbindung sind jetzt möglich. Das ist der Hauptgrund, warum diese Handoff-Datei existiert: Viele "nie verifiziert"-Punkte aus den PHASE-Notes lassen sich am PC zum ersten Mal wirklich testen.

**Bestätigt am 21.09.2026:** Am PC sind `fastapi`/`httpx` bereits installiert, alle Tests laufen lokal grün (statt 217+7 skipped), und Netzwerkzugriff auf `data.alpaca.markets` funktioniert wirklich (per `curl` verifiziert, inkl. Alpacas eigener CORS-Header).

**Korrigierter Punkt (ursprünglich falsch dokumentiert):** Kurzzeitig sah es so aus, als könnte Claude Codes Tool-Sandbox die echten Secret-Werte aus `.env` nicht lesen (leere Strings bei `Read`/`Bash`). **Das stimmt nicht** — die Datei war zu dem Zeitpunkt im Editor nur noch ungespeichert (ohne Inhalt auf der Festplatte), keine Sandbox-Sperre. Sobald gespeichert, kann Claude `.env`-Secrets ganz normal lesen und für echte API-Calls verwenden. **Wichtige Konsequenz für künftige Sessions:** Es gibt keine technische Bremse, die Claude daran hindert, mit echten Zugangsdaten aus `.env` echte (auch kostenpflichtige oder folgenreiche) API-Calls zu machen — das muss durch bewusstes Verhalten sichergestellt werden, nicht durch die Umgebung. Bei echten Broker-/API-Keys: vor einem tatsächlichen Call kurz überlegen, ob er wirklich gewollt ist, nicht einfach weil er technisch möglich ist. Details zur Korrektur: `PHASE3_NOTES.md`.

**Bereits gefundene Stolpersteine, die man am PC vermeiden sollte:**
- Demo-Skripte in `backend/scripts/` müssen mit `PYTHONPATH=.` aufgerufen werden, sonst `ModuleNotFoundError: No module named 'app'`:
  ```bash
  cd backend && PYTHONPATH=. python scripts/phase11_live_readiness_demo.py
  ```
  (`python scripts/x.py` legt `scripts/` auf den Pfad, nicht `backend/` — `python -m unittest discover` hat dieses Problem nicht, weil `-m` das Arbeitsverzeichnis verwendet.)
- **`python3` als Befehl funktioniert auf diesem Windows-PC nicht** (löst auf einen Microsoft-Store-Alias-Stub auf, der nichts tut) — `python` oder `py` verwenden.

---

## 4. Stand pro Phase (alle 11 abgeschlossen)

Jede Phase hat eine eigene `PHASE<N>_NOTES.md` im Repo-Root mit vollem Detail (was gebaut wurde, was getestet wurde, gefundene Bugs, offene Punkte). Diese Datei hier fasst nur zusammen — **bei Unsicherheit die jeweilige PHASE_NOTES.md lesen.**

| # | Phase | Kern-Ergebnis | Datei |
|---|---|---|---|
| 1 | Research/Scaffold | Roadmap v2, Projekt-Grundgerüst | — |
| 2 | Backtest-Engine-Fundament | `reference_engine.py` (Korrektheits-Referenz, next-bar-open-Fills), Point-in-Time-Guard (`SimulationCursor`) | `PHASE2_NOTES.md` |
| 3 | Data Layer | NYSE-Kalender, Survivorship-Bias-Fix (`PointInTimeUniverse`), Provider-Abstraktion (`FakeProvider` echt, **`AlpacaProvider` seit 21.09.2026 echt implementiert** — s. u., `PolygonProvider` nur dokumentierter Stub) | `PHASE3_NOTES.md` |
| 4 | Strategy Factory | 3 manuelle Strategien (VWAP Momentum, EMA Pullback, Opening Range Breakout) | `PHASE4_NOTES.md` |
| 5 | Validation Engine | OOS-Sperre, Walk-Forward, Monte Carlo, Leakage-Detection, 12-Punkte-Gate (`app/validation/gate.py`) | `PHASE5_NOTES.md` |
| 6 | Signal Engine | Scanner (statische ~30-Ticker-Liste, **unverifiziert, siehe unten**), Risk/Position-Sizing, kalibriertes Scoring, `build_signal()` | `PHASE6_NOTES.md` |
| 7 | AI Strategy Generator | 2 weitere Strategien (Mean Reversion, Relative Volume Momentum) — **beide fielen ehrlich durchs 12-Punkte-Gate** (synthetische Daten) | `PHASE7_NOTES.md` |
| 8 | Web-App | FastAPI-Backend (`app/api/`) + Vue-3-Frontend (`frontend/`), gegen synthetische Demo-Daten | `PHASE8_NOTES.md` |
| 9 | Paper Trading | `PaperTradingEngine`/`Portfolio` — Stop/Target-Durchsetzung, Handelsende-Flatten, Kaufkraft-Prüfung | `PHASE9_NOTES.md` |
| 10 | Forward Testing | `ForwardTestSession` — Infrastruktur für über echte Zeit verteilte Tests, kein echtes Ergebnis (siehe unten) | `PHASE10_NOTES.md` |
| 11 | Controlled Live Test | News/Earnings-Pre-Trade-Gate, `evaluate_live_readiness()`-Checkliste — **keine Order-Ausführungsfähigkeit** (bewusst) | `PHASE11_NOTES.md` |

**Test-Stand (aktualisiert 23.09.2026, am PC verifiziert):** 305 Tests, alle grün. Zuwachs gegenüber den 285 vom 22.09.: GDELT-Client (`app/data/providers/gdelt.py`) inkl. Retry-Fix für reine Verbindungsfehler, relative Stimmungsberechnung (`app/validation/news_sentiment.py`). Die alten "217 laufen, 7 übersprungen"-Zahlen galten nur für die alte Sandbox ohne `pip install`.

---

## 5. DECISIONS.md — verbindliche Entscheidungen (Kurzfassung)

Volltext mit Begründung: `DECISIONS.md`. **Wichtig:** Die Datei unterscheidet strikt zwischen **festgelegt** (Nutzer hat aktiv eine Option gewählt) und **Default/vorläufig** (Empfehlung übernommen, nie individuell bestätigt). Dieses Muster bitte in künftigen Sessions beibehalten — nicht stillschweigend von "Default" zu "bestätigt" hochstufen.

| # | Frage | Stand | Wert |
|---|---|---|---|
| 1 | Aktienuniversum | Form festgelegt, **konkrete Ticker-Liste vorläufig** | ~30 US-Large-Caps, Liste in `backend/app/signals/scanner.py` — nie vom Nutzer geprüft |
| 2 | Haltedauer | festgelegt | 30 Min – wenige Stunden, Exit spätestens Handelsende (Intraday) |
| 3 | Long/Short | festgelegt | Long only |
| 4 | Datenanbieter | festgelegt (13.08.2026) | Alpaca (Start), Polygon.io optional später |
| 5 | Risiko pro Trade | festgelegt (13.08.2026) | 0,25 % des Kontos, fest im Code |
| 6 | PDT-Regel/Kontogröße (echtes Live-Konto) | **Default, NICHT individuell bestätigt** | Cash-Konto, 750 USD — **muss vor echtem Kapitaleinsatz erneut mit Nutzer geklärt werden** |
| 7 | Paper-Trading-Startkapital (simuliert, ≠ #6) | festgelegt (13.08.2026) | 50.000 USD |

Weitere technische Festlegungen: Backend Python+FastAPI, Backtesting-Framework Nautilus Trader 1.231.0 (installierbar verifiziert, **nie tatsächlich integriert**), DB PostgreSQL+TimescaleDB (**nie aufgesetzt, nichts im Code nutzt es bisher**), Cache/Queue Redis/Celery (**ebenfalls nie aufgesetzt/genutzt**), Frontend Vue3+TS, Charts TradingView Lightweight Charts, Deployment Docker (**kein Dockerfile existiert bisher**).

---

## 6. Repo-Struktur

```
backend/
  app/
    api/              FastAPI-Routen (Dashboard, Signals, Strategies, Trades) — gegen synthetische Demo-Daten
    backtest/         reference_engine.py — Korrektheits-Referenz, next-bar-open-Fills, NICHT die Produktions-Engine
    data/
      calendar.py      NYSE-Handelskalender, DST-bewusst
      corporate_actions.py  Split-Rückrechnung
      point_in_time.py Bar, SimulationCursor (Backtest), StreamingCursor (Paper/Live)
      universe.py      Survivorship-bias-sicheres Punkt-in-Zeit-Universum
      quality.py       Data-Quality-Checks
      providers/       MarketDataProvider-Abstraktion; FakeProvider + AlpacaProvider (beide echt), PolygonProvider (STUB, NotImplementedError)
    features/indicators.py  SMA, EMA, ATR, Session-VWAP, Opening Range, Relative Volume, Distance-in-ATR
    strategies/        5 Strategien: vwap_momentum, ema_pullback, opening_range_breakout, mean_reversion, relative_volume_momentum
    validation/        metrics.py, oos.py, walk_forward.py, monte_carlo.py, leakage.py, gate.py (12-Punkte-Checkliste)
    signals/           risk.py (Position-Sizing, DailyLossGuard), scoring.py (kalibriert), signal.py (build_signal), scanner.py, news_filter.py (Phase 11)
    paper/             engine.py (PaperTradingEngine), portfolio.py (Portfolio, Kaufkraft-Prüfung)
    forward_test/      session.py (ForwardTestSession, über echte Zeit verteilte Tests)
    live_readiness/    readiness.py (Go/No-Go-Checkliste, KEINE Order-Ausführung)
  tests/               1 Testdatei pro Modul, reine unittest-Standardbibliothek, Hand-Verifikations-Disziplin (siehe Abschnitt 8)
  scripts/             Demo-/Reproduktionsskripte (phase7/9/10/11) + verify_alpaca_connection.py (Nutzer muss selbst ausführen, s. Abschnitt 3), IMMER mit PYTHONPATH=. aufrufen
  pyproject.toml       Dependencies; httpx jetzt echte Laufzeit-Abhängigkeit (AlpacaProvider)

frontend/              Vue 3 + TypeScript + Vite, NIE lokal mit npm installiert (nur CI-verifiziert)
  src/api/client.ts     Fetch-Wrapper gegen backend/app/api/
  src/views/            DashboardView, SignalsView, TradeDetailView, JournalView
  src/components/PriceChart.vue   TradingView Lightweight Charts

.github/workflows/ci.yml   4 Jobs: backend-tests, backend-api-tests, frontend-build, probe-nautilus-trader
ROADMAP.md              Volle fachliche Spezifikation (Pflichtlektüre bei Unsicherheit)
DECISIONS.md            Siehe Abschnitt 5
DISCLAIMER.md           Research-/Paper-Trading-Disclaimer, im Frontend sichtbar
PHASE2_NOTES.md … PHASE11_NOTES.md   Ein Dokument pro Phase, volles Detail
VALIDATION_PROTOCOL.md          Vorregistriertes Prüfprotokoll (K1-K7) für Intraday-Strategien. Git-Zeitstempel als Beleg. Pflichtlektüre vor jeder Änderung an der Validierung.
REAL_DATA_VALIDATION_NOTES.md   Alle Intraday-Gate-Läufe (21.09.2026) — 0 von 27 Konfigurationen bestehen; K7 zeigt fehlende Timing-Information
SELECTION_LAYER_PROTOCOL.md     Vorregistriertes Protokoll für die (noch nicht getestete) intraday "Stocks in Play"-Auswahlschicht — braucht Databento/Security-Master, siehe dort für die Kostenfrage
OVERNIGHT_SELECTION_PROTOCOL.md Vorregistriertes + Ergebnis-Nachtrag für die Übernacht-Auswahlstrategie (22.09.2026) — Top-20-Konfiguration besteht erstmals alle Kriterien, aber K4 nur knapp (t=2,00) und K8 (Survivorship Bias) ungelöst
NEWS_SENTIMENT_PILOT_PROTOCOL.md Vorregistriertes + Ergebnis-Nachtrag für den GDELT-Stimmungs-Pilot (23.09.2026) — 24-Symbol-Universum, 2 Jahre, **kein Beleg**, dass Stimmung die Übernacht-Auswahl verbessert (falsche Richtung, p=0,065)
transkript/              4 YouTube-Transkripte (DaviddTech-Methodik), Basis für ROADMAP v2
```

---

## 7. Befehle

**Wichtig am PC (Windows, bestätigt 21.09.2026): `python3` funktioniert nicht** — löst auf den Microsoft-Store-Alias-Stub auf und tut nichts Sinnvolles. `python` oder `py` verwenden (beide funktionieren, `py --version` → 3.11.9). Alle Befehle unten sind entsprechend mit `python` statt `python3` angepasst.

```bash
# Backend-Tests (am PC mit installierten Dependencies, 229 Tests grün)
cd backend && PYTHONPATH=. python -m unittest discover -s tests -v

# Backend mit vollen Dependencies (am PC bereits vorhanden)
cd backend && pip install -e ".[dev]"

# Backend-API lokal starten
cd backend && uvicorn app.api.main:app --reload   # http://localhost:8000

# Frontend (bisher NIE lokal installiert/verifiziert)
cd frontend && npm install
cd frontend && npm run dev      # http://localhost:5173
cd frontend && npm run type-check
cd frontend && npm run build

# Alpaca-Verbindung mit echten Keys verifizieren (NUR außerhalb von Claude Code ausführen, s. Abschnitt 3)
cd backend && PYTHONPATH=. python scripts/verify_alpaca_connection.py

# Demo-/Reproduktionsskripte (IMMER mit PYTHONPATH=.)
cd backend && PYTHONPATH=. python scripts/phase7_synthetic_gate_run.py
cd backend && PYTHONPATH=. python scripts/phase9_paper_trading_demo.py
cd backend && PYTHONPATH=. python scripts/phase10_forward_test_demo.py
cd backend && PYTHONPATH=. python scripts/phase11_live_readiness_demo.py
```

---

## 8. Etablierte Arbeitsweise — bitte in neuen Sessions beibehalten

Diese Konventionen haben sich über alle 11 Phasen bewährt und sollten fortgesetzt werden:

1. **Radikale Ehrlichkeit statt erfundener Ergebnisse.** Nie einen Test/eine Verifikation vortäuschen, die nicht wirklich lief. Wenn etwas nicht prüfbar ist (z. B. wegen Netzwerksperre), das explizit sagen — nicht so tun, als wäre es geprüft. Siehe `NOT_AUTOMATED`-Markierungen in `gate.py`, `news_filter.py`, `readiness.py`.
2. **Hand-Verifikations-Disziplin bei Tests.** Erwarteten Wert von Hand ausrechnen, dann erst `assert`en — nicht raten und dann den Test ans Ergebnis anpassen. Das hat wiederholt echte Bugs im eigenen Code gefunden (z. B. Gebühren-Berechnung in Phase 9, Kaufkraft-Prüfung in Phase 9, PYTHONPATH-Bug in Phase 9).
3. **"Schreib echten Code, dokumentiere die Einschränkung, verifiziere per CI"** — Muster für alles, was in der Sandbox nicht direkt testbar war (z. B. `nautilus_trader`-Installierbarkeit in Phase 2 per CI-Probe-Job bestätigt). Am PC ist das jetzt oft nicht mehr nötig, da echter Netzwerkzugriff besteht — aber wo etwas *echtes Geld oder echte Broker-Credentials* betrifft, bleibt Vorsicht angebracht (siehe Punkt 5).
4. **Ein `PHASE<N>_NOTES.md` pro Phase**, aktualisiert auch nach kritischen Nachprüfungen (nicht nur beim ersten Schreiben). Format: Was wurde gebaut, was getestet, gefundene Bugs mit Ursache, was ist offen. Dieses Muster für neue Phasen/größere Arbeiten fortführen.
5. **DECISIONS.md**: `festgelegt` nur wenn der Nutzer eine Option **aktiv gewählt** hat — nicht bei "keine Präferenz" oder stillschweigender Zustimmung zum Gesamtplan. Bei "keine Präferenz" wird die Empfehlung als **Default** übernommen und explizit so markiert, nicht als Entscheidung verkauft.
6. **Commit + Push nach jeder Phase, CI-Ergebnis abwarten und im PHASE_NOTES.md nachtragen.** Commit-Messages sind ausführlich (Was, Warum, gefundene Bugs) — Vorbilder in `git log`.
7. **Bei hartem Geld/Risiko (Phase 11) bewusst NICHT so weit gebaut wie technisch möglich gewesen wäre** — kein Order-Ausführungsclient gegen einen echten Broker, obwohl das Muster ("Stub schreiben, später verifizieren") auch hier anwendbar gewesen wäre. Diese Grenze bewusst gezogen, siehe `PHASE11_NOTES.md`. Bei zukünftigen Erweiterungen in diese Richtung: erst fragen, nicht bauen.
8. **Bei echten Geschäftsentscheidungen (nicht Implementierungsdetails) explizit fragen**, nicht selbst festlegen — siehe wie #4/#5/#6/#7 in DECISIONS.md gehandhabt wurden.

---

## 9. Bekannte offene Punkte (über alle Phasen konsolidiert)

- ~~`AlpacaProvider`/`PolygonProvider` sind reine Stubs~~ **`AlpacaProvider` seit 21.09.2026 echt implementiert UND end-to-end mit echten Paper-Keys verifiziert** (Nutzer hat `backend/scripts/verify_alpaca_connection.py` selbst ausgeführt: SUCCESS, 6 echte AAPL-Tagesbars zurückbekommen). `PolygonProvider` bleibt reiner Stub (laut DECISIONS.md #4 ohnehin nur optional/später).
- **Konkrete Ticker-Liste in `scanner.py`** nie vom Nutzer geprüft (nur die allgemeine Form "~30 Large-Caps" wurde bestätigt).
- **News-Relevanz-Prüfung existiert nicht**, nicht mal als Stub (`app/signals/news_filter.py`'s `check_relevant_news()` — bewusst, siehe `PHASE11_NOTES.md`, da "relevant" eine Einschätzungsfrage ist, die der Code nicht beurteilen kann).
- **Kein echter Forward-Test-Datensatz** — `ForwardTestSession` ist nur gegen synthetische Daten demonstriert.
- **DECISIONS.md #6 ist nur ein Default**, keine bestätigte Entscheidung.
- **Kein Order-Ausführungsclient** — bewusste Grenze (siehe oben).
- **Nautilus Trader nie integriert** — nur Installierbarkeit verifiziert (Phase 2). `reference_engine.py` bleibt eine handgeschriebene Korrektheits-Referenz, nicht die Produktions-Engine.
- **PostgreSQL/TimescaleDB/Redis/Celery/Docker** — alle in DECISIONS.md als Tech-Stack festgelegt, aber nichts davon wurde bisher aufgesetzt oder vom Code genutzt. Alles läuft bisher In-Memory/synthetisch.
- **Kein Persistenzlayer** — `Portfolio`/`ForwardTestSession`-Zustand lebt nur im Prozessspeicher, nichts überlebt einen Neustart.
- **Trade Journal (Phase 8 API)** liefert bewusst eine leere Liste — nie an echte Paper-Trading-Ergebnisse angebunden.
- ~~`package-lock.json` fehlt~~ **Behoben 21.09.2026** — erster lokaler `npm install` hat ihn erzeugt, committet, CI nutzt jetzt `npm ci` statt `npm install`.
- **Web-App (Dashboard/Signals/Trades-API) nutzt weiterhin synthetische Demo-Daten**, nicht die jetzt echte `AlpacaProvider`-Anbindung — `/api/dashboard` meldet das ehrlich selbst (`"data_source":"synthetic_demo"`). Umstellung auf echte Daten ist noch offen (Teil von Phase C, siehe Abschnitt 10).
- **Kein Pull Request erstellt**, Branch liegt direkt auf GitHub ohne Merge nach `main`.
- **Keine der 3 Phase-4-Intraday-Strategien besteht das vollständige Gate — 0 von 27 Konfigurationen** (3 Strategien × 3 Symbole × 3 Stop-Horizonte, s. `REAL_DATA_VALIDATION_NOTES.md`). Entscheidend ist das *Warum*: Der Permutationstest (K7) ergibt einen p-Median von 0,799 — zufälliges Einstiegs-Timing schlägt unsere Strategien typischerweise in ~80 % der Ziehungen. Das Timing trägt keine Information. **Mehr Daten für diese Strategien zu kaufen wäre daher voraussichtlich verschwendet.**
- **22.09.2026: Übernacht-Auswahlstrategie (Top 20 nach Tagesvolumen, Halten Schluss→nächste Eröffnung) besteht als erste überhaupt alle Kriterien** — s. `OVERNIGHT_SELECTION_PROTOCOL.md`. Zwei wichtige Einschränkungen: K4 (Signifikanz) ist nur knapp (t=2,00 bei Schwelle 2,0, über 7 Bootstrap-Seeds stabil bei 1,99–2,05, aber unter einer konservativen Mehrfachtest-Korrektur über alle 29 in dieser Session geprüften Konfigurationen nicht mehr robust). K8 (Survivorship Bias) bleibt ungelöst — heutige S&P-500-Liste rückwirkend auf 2021 angewendet, fehlende Titel (delisted/übernommen) nicht berücksichtigt. Der Auswahltest selbst (Volumen schlägt Zufallsauswahl, p=0,0001) ist dagegen robust signifikant.
- **Neu, 23.09.2026: News-Stimmungs-Pilot (GDELT) liefert KEIN verwertbares Signal** — s. `NEWS_SENTIMENT_PILOT_PROTOCOL.md`. Getestet: Verbessert eine zusätzliche Filterung der Übernacht-Auswahl nach relativer GDELT-Nachrichtenstimmung das Ergebnis? 24-Symbol-Pilot, 2 Jahre, 24/24 Symbole vollständig geladen. Ergebnis: Aktien mit *negativerer* Stimmung schnitten besser ab als die mit positiverer (Gegenteil der Hypothese), aber nicht signifikant (t=1,76, p=0,065 — knapp über 0,05, und weit über der bei 31 Konfigurationen insgesamt nötigen Bonferroni-Schwelle von ~0,0016). Nebenbei ein echter Bug gefunden und behoben: `_get_with_backoff` in `app/data/providers/gdelt.py` fing nur HTTP-429-Fehler ab, keine reinen Verbindungs-Timeouts — ein einzelner Netzwerk-Hänger brach den ganzen Mehr-Symbol-Abruf ab (mehrfach bei DELL/NVR beobachtet, jetzt mit Regressionstests behoben). **Konsequenz: Stimmungsfilterung mit GDELT wird nicht weiterverfolgt** — die reine Volumen-Auswahl bleibt der bessere Ausgangspunkt. **Nächster sinnvoller Schritt bleibt: K8 lösen (Databento Security Master, 199 USD/Monat — siehe `SELECTION_LAYER_PROTOCOL.md` für die Kostendiskussion) oder weitere Robustheitsprüfung der Übernacht-Auswahl, bevor an Forward-Test/echtes Kapital überhaupt zu denken ist.**
- **Zwei echte Datenfehler bei `AlpacaProvider` gefunden und behoben (21./22.09.2026):** (1) `adjustment="raw"` ließ Aktiensplits als künstliche ~90-%-Kurseinbrüche erscheinen (NVDA, GOOGL, AMZN u. a.) — jetzt konfigurierbar, `"split"` für mehrjährige Backtests verwenden. (2) Vereinzelte Phantom-Tagesbars mit Volumen 0 und identischem Platzhalterkurs (gefunden bei TPL) — werden jetzt in `overnight_selection.py` gefiltert. Beide Fixes gelten bisher nur für die Übernacht-Auswahlstrategie, **nicht rückwirkend auf andere Skripte angewendet** — bei künftigen mehrjährigen/breiten Backtests daran denken.
- **Monte-Carlo-Drawdown-Schwelle ist eine offene Geschäftsentscheidung** (wie DECISIONS.md #5/#6) — bisher bewusst nicht gesetzt, Punkt bleibt `NOT_AUTOMATED`.

---

## 10. Nächste Schritte (Reihenfolge wie zuletzt mit dem Nutzer besprochen)

### Phase A — Vorbereitung (Nutzer)
1. Alpaca-Paper-Trading-Account eröffnen (kostenlos), **Paper-Keys** generieren (nicht Live-Keys).
2. Sicherstellen, dass die aktuelle Umgebung (PC) echten Internetzugang hat — sollte am PC automatisch der Fall sein.

### Phase B — Code lauffähig machen
3. ✅ `pip install -e ".[dev]"` — am PC bereits vorhanden, 229/229 Tests laufen grün.
4. ✅ **`AlpacaProvider.get_bars()` implementiert und end-to-end verifiziert** (21.09.2026) — echte Anbindung an `data.alpaca.markets`, hermetisch getestet UND vom Nutzer selbst mit echten Paper-Keys erfolgreich gegen echte AAPL-Kursdaten gelaufen (`backend/scripts/verify_alpaca_connection.py`, Ergebnis: 6 Tagesbars).
5. ✅ `.env` mit echten Paper-Keys befüllt (`.env` ist in `.gitignore`, wird nie committet).
6. ✅ **Backend + Frontend lokal gestartet und verifiziert** (21.09.2026): `uvicorn app.api.main:app` auf Port 8000 (`/docs`, `/api/health`, `/api/dashboard` antworten), `npm run dev` auf Port 5173 (Type-Check fehlerfrei, im Browser vom Nutzer bestätigt: lädt fehlerfrei). CORS zwischen den beiden funktioniert (Backend erlaubt exakt `http://localhost:5173` — beim Start auf `127.0.0.1` statt `localhost` binden würde CORS brechen, das ist beim ersten Versuch passiert und wurde korrigiert). Nebenbei erster `npm install` überhaupt → `package-lock.json` erzeugt, committet, CI auf `npm ci` umgestellt.
7. **Alternativ/zusätzlich:** Falls Alpaca-Keys als GitHub-Actions-Secrets hinterlegt werden, einen Verbindungs-Probe-Job in `.github/workflows/ci.yml` bauen — exakt das Muster, mit dem `nautilus_trader` in Phase 2 verifiziert wurde (`probe-nautilus-trader`-Job als Vorlage). Noch nicht gemacht, nicht dringend, da Alpaca-Anbindung bereits lokal verifiziert ist.
**Damit ist Phase B fachlich abgeschlossen.**

### Phase B.5 — Echte-Daten-Validierung (eingeschoben 21.09.2026, VOR Forward-Test)

Grund: Keine Strategie hatte je das 12-Punkte-Gate auf echten Daten durchlaufen, nur auf synthetischen Zufallsdaten (Phase 5/6/7). Ein Forward-Test bestätigt laut Roadmap ein bereits bestandenes OOS-Ergebnis — es gab noch keins auf echten Daten zu bestätigen. Details, Tabelle, Einschränkungen: `REAL_DATA_VALIDATION_NOTES.md`.

8. ✅ **Gate-Läufe mit echten Alpaca-Daten, 3 Symbole** (`backend/scripts/real_data_gate_run.py`, AAPL/MSFT/NVDA, 05.03.–21.09.2026): **keine Strategie besteht konsistent** — VWAP Momentum 0/3, EMA Pullback 1/3 (nur AAPL, war Stichproben-Zufall), Opening Range Breakout 2/3 (AAPL, NVDA — fällt auf MSFT durch). Monte-Carlo-Schwelle bewusst offen gelassen (Geschäftsentscheidung, s. u.).
9. **Offen:** Weitere Symbole UND andere (nicht überlappende) Zeiträume gegen Opening Range Breakout testen (`PYTHONPATH=. python scripts/real_data_gate_run.py SYMBOL`) — 2/3 auf einem einzigen ~6,5-Monats-Fenster ist zu wenig, um sie als Forward-Test-Kandidat zu bezeichnen. VWAP Momentum und EMA Pullback nicht weiter priorisieren, solange sie mehrheitlich durchfallen.
10. **Geschäftsentscheidung offen:** Monte-Carlo-Drawdown-Schwelle (wie viel maximaler Drawdown ist akzeptabel?) — bisher nicht mit dem Nutzer geklärt, kein DECISIONS.md-Eintrag.

### Phase C — Echter Forward-Test (Wochen bis Monate)
11. Falls Opening Range Breakout nach weiteren Tests (Schritt 9) mehrheitlich besteht: für den Forward-Test auswählen. Falls nicht — zurück zu Schritt 9 mit mehr Symbolen/Zeiträumen, oder ehrlich akzeptieren, dass noch keine der 3 Phase-4-Strategien forward-test-reif ist.
12. Täglichen Job (Cron o. ä.) einrichten: `AlpacaProvider.get_bars()` für den letzten Handelstag holen → `ForwardTestSession.ingest()` füttern.
13. Regelmäßig `session.status()` prüfen, bis `ready_for_review=True` (ROADMAP-Kriterium: ≥20 Trades **oder** ~3 Monate).
14. `compare_to_oos()` (in `app/forward_test/session.py`) gegen die dokumentierten OOS-Ergebnisse der jeweiligen Strategie laufen lassen.

### Phase D — Vor echtem Kapitaleinsatz
15. **DECISIONS.md #6 final mit dem Nutzer bestätigen** (aktuell nur Default: Cash-Konto, 750 USD).
16. `evaluate_live_readiness()` (in `app/live_readiness/readiness.py`) laufen lassen — muss `passed=True` zeigen. `broker_connectivity_verified` und `human_sign_off` bleiben *immer* `NOT_AUTOMATED`, das ist Absicht.
17. Broker-Konnektivität mit einer echten Test-Order in Alpacas Paper-Umgebung selbst verifizieren.
18. **Bewusste, separate Entscheidung mit dem Nutzer:** ob/wie echtes Kapital eingesetzt wird. Braucht eine eigene, explizite Order-Ausführungs-Architektur, die absichtlich noch nicht existiert — nicht ungefragt bauen.

---

## 11. Ton/Stil-Hinweise für künftige Sessions

- Der Nutzer kommuniziert auf Deutsch, erwartet knappe, direkte Antworten ohne unnötige Präambel.
- Der Nutzer hat wiederholt "sehr genau" kritische Nachprüfungen eingefordert und erwartet, dass dabei echte Bugs gefunden werden (nicht nur Dokumentation nachgetragen wird) — dieses Anspruchsniveau beibehalten.
- Bei Unklarheit über eine Geschäftsentscheidung (nicht Implementierungsdetail): fragen, nicht raten oder stillschweigend entscheiden.
- Committen und pushen ist etablierte Praxis nach jeder abgeschlossenen Einheit Arbeit, CI-Ergebnis danach prüfen und dokumentieren.
