# Phase 8 — Web-App: Status & offene Punkte

Referenz: `ROADMAP.md` Abschnitt 19 (Dashboard, Charts, Signals, Trade Detail View, Trade Journal).

## Was gebaut wurde

**Backend (`backend/app/api/`)** — FastAPI-Layer über die bereits verifizierte Backend-Logik (Scanner, Strategien, `build_signal`), kein neuer fachlicher Code:

- `GET /api/strategies` — alle 5 implementierten Strategien mit Beschreibung, `validated`-Flag und `gate_note`. Keine wird als `validated=True` geführt: Mean Reversion und Relative Volume Momentum sind laut `PHASE7_NOTES.md` durch das Gate gefallen, die drei Phase-4-Strategien wurden nie durchs Gate geschickt. Das hier fälschlich als "empfohlen" darzustellen würde genau der Regel aus `ROADMAP.md` Abschnitt 15 widersprechen.
- `GET /api/signals`, `GET /api/signals/{symbol}` — scannt `STATIC_UNIVERSE` (DECISIONS.md #1) gegen synthetische Demo-Bars und liefert das letzte BUY-Signal je Symbol über die echte `build_signal()`-Pipeline aus Phase 6 (Entry/Stop/Target/Risk:Reward/Shares/Rationale). Jede Antwort trägt `data_source: "synthetic_demo"`.
- `GET /api/signals/{symbol}/bars` — OHLCV-Reihe für den Chart in der Trade Detail View.
- `GET /api/dashboard` — Kennzahlen (Universumsgröße, Anzahl Strategien, Anzahl aktueller Signale). Portfolio-Metriken (Equity-Kurve, offene Positionen, realisierter PnL) fehlen bewusst — es gibt noch keine Paper-Trading-Engine (Phase 9), die sie liefern könnte.
- `GET /api/trades` — Trade Journal, liefert bewusst eine leere Liste mit Hinweistext statt erfundener Beispieltrades.

**Warum synthetisch statt echt:** Alpaca/Polygon sind weiterhin unverifizierte Stubs (Phase 3) — dieselbe Einschränkung wie in jeder vorherigen Phase. `app/api/demo_data.py` generiert deterministische (pro Symbol geseedete) synthetische 5-Minuten-Bars über den echten NYSE-Kalender, nach demselben Muster wie `scripts/phase7_synthetic_gate_run.py`. Jede API-Antwort, die davon abhängt, ist explizit mit `data_source: "synthetic_demo"` gekennzeichnet, damit weder das Frontend noch ein direkter API-Aufrufer das für echte Marktdaten halten kann.

**Frontend (`frontend/`)** — Vue 3 + TypeScript + Vite, wie in `DECISIONS.md` festgelegt:

- `DashboardView.vue` — Marktübersicht-Kacheln + Hinweistexte
- `SignalsView.vue` — Scan-Ergebnisse mit Strategie-Auswahl, Link zur Detailansicht
- `TradeDetailView.vue` — Entry/Stop/Target/Risk:Reward/Shares/Confidence/Rationale + Candlestick-Chart (`PriceChart.vue`, TradingView Lightweight Charts, wie in `DECISIONS.md` festgelegt)
- `JournalView.vue` — Trade Journal (aktuell immer leer, siehe oben)
- Ein permanenter Disclaimer-Banner in `App.vue` ("Research & paper-trading tool only... siehe DISCLAIMER.md") — das ist die erste Phase, in der überhaupt eine Oberfläche existiert, die ein Mensch sieht, also auch die erste Stelle, an der der Disclaimer tatsächlich sichtbar sein muss statt nur in einer Markdown-Datei zu stehen.

## Ehrlicher Stand der Verifikation

**Nichts hiervon konnte in dieser Sandbox lokal installiert oder ausgeführt werden**, aus demselben Grund wie in jeder vorherigen Phase, jetzt aber zum ersten Mal für zwei Ökosysteme gleichzeitig:

- PyPI ist weiterhin blockiert (`403 host_not_allowed`) — `fastapi`, `pydantic`, `httpx` konnten nicht installiert werden. `tests/test_api.py` ist deshalb mit `@unittest.skipUnless(...)` geschrieben: läuft lokal als "skipped", nicht als Fehler, und lässt die bestehenden 166 Tests (159 aus Phase 1-7 + 7 neue API-Tests, alle übersprungen) grün.
- Der npm-Registry (`registry.npmjs.org`) ist **ebenfalls** blockiert, mit demselben `403 host_not_allowed` — geprüft per `curl -sSI https://registry.npmjs.org/vue`. `npm install` war für Vue/Vite/TypeScript/Lightweight-Charts also grundsätzlich nicht möglich, nicht einmal um die Syntax zu prüfen.

**Wie stattdessen verifiziert wurde**, exakt das Muster aus Phase 2 (dort: `nautilus_trader` per CI-Probe-Job bestätigt):

1. Die reine Backend-Logik hinter der API (Signal-Erzeugung über alle 5 Strategien, `demo_data.py`s Bar-Generierung) wurde manuell gegen 3 Symbole durchlaufen lassen — lief fehlerfrei, alle erzeugten Signale erfüllen `stop < entry < target`. Das deckt die eigentliche Geschäftslogik ab, unabhängig von FastAPI selbst.
2. Zwei neue CI-Jobs in `.github/workflows/ci.yml`:
   - `backend-api-tests`: `pip install -e ".[dev]"` (jetzt inkl. `httpx`) + `pytest -q` — führt `tests/test_api.py`s 7 Tests auf einem Runner mit echtem PyPI-Zugriff tatsächlich aus, statt sie nur zu überspringen. Das ist der "vollständige Dependency-Install"-Job, den der CI-Kommentar seit Phase 2 als bewusst aufgeschoben dokumentiert hatte — jetzt gebraucht, jetzt eingebaut.
   - `frontend-build`: `npm install && npm run type-check && npm run build` — die einzige Möglichkeit, den Vue/TS-Code überhaupt auf Syntax- und Typfehler zu prüfen, da lokal kein `npm` an die Registry kam.
3. Beide Jobs sind reguläre (nicht `continue-on-error`) Jobs, weil hier — anders als bei `nautilus_trader` in Phase 2 — nicht offen ist, *ob* die Dependency installierbar ist, sondern nur, *ob der eigene Code korrekt ist*. Ein Fehlschlag hier ist ein echter, zu behebender Fehler, kein informativer Forschungs-Datenpunkt.

**CI-Ergebnis (Run 31673199292, Commit 99bf62e):** alle 4 Jobs grün, insbesondere `backend-api-tests` (7 API-Tests liefen echt, nicht übersprungen) und `frontend-build` (`npm install && npm run type-check && npm run build` erfolgreich) — beide neuen Jobs waren zuvor noch nie gelaufen und hätten jeden Syntax-/Typ-/Importfehler in `app/api/` oder `frontend/src/` aufgedeckt. Das ist die erste tatsächliche Bestätigung, dass sowohl der FastAPI- als auch der Vue/TS-Code korrekt ist — vorher nur durch manuelle Logikprüfung (Schritt 1 oben) und lokale Kompilierbarkeits-/Syntaxchecks abgedeckt.

## Was noch offen ist

1. **Kein echter Beweis, dass die Vue/TS-Syntax korrekt ist**, bis der `frontend-build`-CI-Job tatsächlich grün gelaufen ist — anders als beim Python-Code, der wenigstens mit dem stdlib-Interpreter direkt geprüft werden konnte, gibt es für TypeScript/Vue-SFC-Syntax in dieser Sandbox keine lokale Prüfmöglichkeit überhaupt, auch keine partielle.
2. **`app/api/` hat keinen Persistenzlayer.** Jede Anfrage berechnet Bars/Signale neu (deterministisch pro Symbol, aber ohne Caching) — für eine Demo-API mit ~30 Symbolen unproblematisch, aber kein Muster, das eins zu eins auf echte Marktdaten mit echtem Abfragevolumen übertragen werden sollte.
3. **Keine Authentifizierung/Autorisierung.** Für eine lokale Research-Oberfläche laut ROADMAP MVP-Scope bewusst nicht Teil dieser Phase; müsste vor jeder Nicht-lokalen Nutzung nachgerüstet werden.
4. **Trade Journal ist reine UI-Hülle ohne Daten** — wird erst mit Phase 9 (Paper Trading) sinnvoll befüllbar.
5. **`package-lock.json` wurde nicht committet**, da `npm install` nie lokal lief, um ihn zu erzeugen — der CI-Job nutzt deshalb `npm install` statt `npm ci`. Sobald der Job einmal erfolgreich lief, sollte der dabei erzeugte Lockfile-Inhalt aus dem CI-Log übernommen und committet werden, um reproduzierbare Builds zu bekommen (`npm ci`) statt bei jedem Lauf neu aufzulösen.
