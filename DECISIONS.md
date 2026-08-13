# Verbindliche Entscheidungen

Festgehalten aus `ROADMAP.md`, Abschnitt 3, als Grundlage für die Implementierung. Änderungen an diesen Punkten sind möglich, aber müssen hier aktualisiert und begründet werden — Code und Dokumentation orientieren sich an diesem Stand.

**Hinweis zum Stand "vorläufig":** #4 und #5 waren ursprünglich Empfehlungen aus der ersten Analyse, nie einzeln vom Nutzer bestätigt — nur der Gesamtplan wurde freigegeben. Bei einer kritischen Nachprüfung am 12.08.2026 wurde das als zu weitgehend markiert: eine Datenanbieter-Wahl (reale Kontoanbindung) und ein Risikoparameter (reales Geld im späteren Live-Betrieb) sind Entscheidungen, die explizit vom Nutzer bestätigt werden sollten, nicht durch stillschweigende Übernahme einer Empfehlung. Code und weitere Phasen bauen bis auf Weiteres trotzdem auf diesen Werten auf — "vorläufig" heißt: gilt als Arbeitsstand, aber offen für Korrektur ohne dass das als Bruch mit einer früheren Zusage zu werten wäre.

**Update 13.08.2026:** #4 und #5 wurden vor Beginn von Phase 9 (Paper Trading) explizit einzeln mit dem Nutzer bestätigt, da Phase 9 zum ersten Mal tatsächlich auf diesen Werten operiert (vorher nur synthetische Demo-Daten in Phase 8). Beide gelten jetzt als **festgelegt**, nicht mehr vorläufig.

Bei der kritischen Nachprüfung von Phase 5/6 (12.08.2026) fiel derselbe Fehler noch einmal auf, diesmal bei #1: Die *Form* der Entscheidung ("~30 liquide Large-Caps, kein Live-Scanner") war bestätigt, aber die konkrete Ticker-Liste in `backend/app/signals/scanner.py` habe ich selbst zusammengestellt, ohne sie dem Nutzer vorzulegen. Dort im Code als "nicht geprüfte Beispielliste" dokumentiert, hier zur Konsistenz ebenfalls als vorläufig nachgetragen.

**Update 13.08.2026 (#6):** Vor Beginn von Phase 11 (Controlled Live Test) wurden dieselben drei Fragen einzeln gestellt wie zuvor bei #4/#5 — Kontostruktur, Kapitalhöhe, Reihenfolge News-Filter/Phase 11. Der Nutzer hat auf alle drei mit "keine Präferenz" geantwortet, anders als bei #4/#5/#7, wo jeweils eine konkrete Option aktiv gewählt wurde. Das ist **kein** "festgelegt" im selben Sinn: Es sind die in den Fragen selbst als Empfehlung markierten Defaults, angewendet, weil der Nutzer die Auswahl bewusst nicht treffen wollte — nicht individuell bestätigte Werte. Muss vor tatsächlichem Kapitaleinsatz erneut mit dem Nutzer bestätigt werden (siehe `PHASE11_NOTES.md`).

| # | Frage | Entscheidung | Stand |
|---|---|---|---|
| 1 | Aktienuniversum | Statische Liste ~30 liquide US-Large-Caps für MVP, kein Live-Scanner in v1 | festgelegt (Form) / **vorläufig** (konkrete Liste) |
| 2 | Haltedauer | 30 Min – wenige Stunden, Exit spätestens Handelsende (Intraday) | festgelegt |
| 3 | Long/Short | Long only für MVP | festgelegt |
| 4 | Datenanbieter | Alpaca (Start), Polygon.io optional später ergänzend | festgelegt (13.08.2026) |
| 5 | Risiko pro Trade | 0,25 % des (simulierten) Kontos, fester Wert im Code | festgelegt (13.08.2026) |
| 6 | PDT-Regel / Kontogröße (reales Live-Konto) | Default (keine Nutzerpräferenz): Cash-Konto (PDT-Regel gilt nicht für Cash-Konten), 750 USD | **Default, nicht individuell bestätigt** — vor echtem Kapitaleinsatz erneut mit dem Nutzer klären |
| 7 | Paper-Trading-Startkapital (simuliert, ≠ #6) | 50.000 USD | festgelegt (13.08.2026) |

## Weitere technische Festlegungen (ROADMAP.md Abschnitt 17)

- Backend: Python + FastAPI
- Backtesting-Framework: Nautilus Trader 1.231.0, **Installierbarkeit auf GitHub Actions (ubuntu-latest/Python 3.12) verifiziert am 12.08.2026** — siehe `PHASE2_NOTES.md`. Noch nicht als harte Abhängigkeit eingebunden, da noch kein Code darauf aufbaut (folgt Phase 3/4).
- Datenbank: PostgreSQL + TimescaleDB-Extension für Zeitreihen
- Cache/Queue: Redis, Celery
- Frontend: Vue 3 + TypeScript
- Charts: TradingView Lightweight Charts
- Deployment: Docker

## Nicht-Ziele des MVP

Keine automatischen Echtgeldorders, kein Deep Learning, kein dynamischer Scanner, kein Short-Selling, kein Crypto/Forex/Optionen/HFT, keine vollautomatische Kapitalsteuerung durch die KI (siehe `ROADMAP.md` Abschnitt 8).
