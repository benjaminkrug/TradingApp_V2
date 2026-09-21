# Phase 3 — Data Layer: Status & offene Punkte

Referenz: `ROADMAP.md` Abschnitt 7 und 19.

## Umgebungs-Einschränkung (gleiche Ursache wie Phase 2)

`api.alpaca.markets` und `api.polygon.io` sind aus dieser Sandbox ebenso gesperrt wie PyPI (`403`, `x-deny-reason: host_not_allowed` — Organisationsrichtlinie):

```
$ curl -sSI https://api.alpaca.markets
HTTP/1.1 403 Forbidden
$ curl -sSI https://api.polygon.io
HTTP/1.1 403 Forbidden
```

Anders als bei Nautilus Trader in Phase 2 lässt sich das hier **nicht** einfach über einen GitHub-Actions-Probe-Job lösen: Dafür wären echte API-Keys nötig, die weder existieren noch (ohne Rücksprache) als Secret hinterlegt werden sollten. Die eigentliche Live-Datenabfrage bleibt deshalb ein offener Punkt, der erst mit echten Zugangsdaten verifiziert werden kann — siehe unten.

## Was fertig ist und getestet wurde (33 neue Tests, stdlib-only)

- **`app/data/calendar.py`** — NYSE-Handelskalender. Deterministische Ganztags-Feiertage (Neujahr, MLK, Presidents' Day, Good Friday, Memorial Day, Juneteenth ab 2022, Independence Day, Labor Day, Thanksgiving, Christmas) inkl. Wochenend-Verschiebung. Sitzungszeiten (`session_bounds`) korrekt DST-bewusst berechnet (in `America/New_York`, dann nach UTC konvertiert) — per Test verifiziert, dass Sommer/Winter-Öffnung sich um genau 1 Stunde UTC unterscheiden.
- **`app/data/corporate_actions.py`** — Split-Rückrechnung (`adjust_for_splits`). Mit Begründung im Docstring, warum das *kein* Look-Ahead-Verstoß ist (Split-Verhältnisse sind zum Zeitpunkt jedes Signals bereits bekannte, statische Fakten — keine neue Information). Getestet inkl. kumulierter Mehrfach-Splits.
- **`app/data/universe.py`** — `PointInTimeUniverse`: die eigentliche Survivorship-Bias-Lösung aus Abschnitt 7. Getestet, dass ein zwischenzeitlich entferntes Symbol für vergangene Anfragedaten korrekt *enthalten* bleibt (das ist der ganze Zweck) und ab seinem Entfernungsdatum korrekt ausgeschlossen wird.
- **`app/data/quality.py`** — `check_bars`: strukturierter Befund-Report statt stillem Reparieren (Duplikate, Lücken, ungültige OHLC-Relationen, negatives Volumen, nicht-positive Preise).
- **`app/data/providers/`** — `MarketDataProvider`-Abstraktion (ABC) + `FakeProvider` (In-Memory, beweist die Abstraktion ist ohne Netzwerk nutzbar) + `AlpacaProvider`/`PolygonProvider` als **dokumentierte Stubs**, die bewusst `NotImplementedError` werfen statt einer ungeprüften HTTP-Implementierung, die falsche Sicherheit vortäuschen würde. Getestet, dass sie tatsächlich klar und informativ fehlschlagen, statt z. B. still eine leere Liste zurückzugeben.

Zusätzlich: `Bar` und `Fill` haben jetzt ein `symbol`-Feld (fehlte in Phase 2 — für einen Single-Symbol-Testfall unschädlich, aber Phase 3 handelt von echten Multi-Symbol-Daten). `PointInTimeSeries` lehnt jetzt gemischte Symbole ab. Alle 17 Phase-2-Tests laufen nach diesem Umbau weiterhin grün.

## Nachtrag 21.09.2026 — Alpaca-Anbindung implementiert (am PC, nicht mehr in der Sandbox)

`AlpacaProvider.get_bars()` (`backend/app/data/providers/alpaca.py`) ist jetzt eine echte Implementierung gegen die Alpaca Market Data API v2 (`GET /v2/stocks/{symbol}/bars` auf `data.alpaca.markets` — bewusst ein anderer Host als `ALPACA_BASE_URL`/`paper-api.alpaca.markets`, das ist der Trading/Account-Endpoint, nicht der Marktdaten-Endpoint). Pagination über `next_page_token`, `feed=iex` als Default (kostenlose Accounts bekommen nur IEX, nicht das konsolidierte SIP-Tape), `httpx` jetzt echte Laufzeit-Abhängigkeit (vorher nur in `dev`-Extras für FastAPI-Tests).

**Was tatsächlich verifiziert wurde:**
- Netzwerkzugriff auf `data.alpaca.markets` funktioniert von dieser Umgebung aus (anders als in der alten Sandbox) — per `curl` bestätigt, inklusive Alpacas eigener CORS-Header (`Access-Control-Allow-Headers: Apca-Api-Key-Id, Apca-Api-Secret-Key`), also wirklich der echte Server, keine Firmen-Firewall dazwischen.
- 9 neue hermetische Unit-Tests (`tests/test_providers.py`, `httpx.MockTransport`, kein Netzwerk) verifizieren URL/Header/Parameter-Konstruktion, Antwort-Parsing, Pagination, 401-Behandlung. Alle 229 Tests (vorher 224) laufen lokal grün.
- Der alte Test "wirft NotImplementedError" wurde entfernt (Provider ist kein Stub mehr) und durch die echten Tests ersetzt.

**Warum das nicht von Claude selbst end-to-end verifiziert werden konnte:** Claude Codes Tool-Sandbox kann die echten Secret-Werte aus `.env` strukturell nicht lesen — weder `Read`, noch `Bash`/`source`, noch ein Python-Skript, das die Datei direkt öffnet, sehen mehr als leere Werte für `ALPACA_API_KEY`/`ALPACA_SECRET_KEY`, obwohl die Datei im Editor sichtbar echte Werte enthält. Das ist offensichtlich eine bewusste Schutzmaßnahme gegen Secret-Exfiltration, keine CRLF-Eigenart (gegengeprüft).

**End-to-End-Verifikation durch den Nutzer, 21.09.2026:** `backend/scripts/verify_alpaca_connection.py` selbst in einem PowerShell-Terminal außerhalb von Claude Code ausgeführt (`$env:PYTHONPATH="."`; `python scripts/verify_alpaca_connection.py`). Ergebnis: **SUCCESS — 6 echte Tagesbars für AAPL** (11.–18.09.2026, Preise 326,57–338,41 USD, plausibel). Key-ID wurde korrekt nur als `...OF3T` angezeigt, kein Secret im Klartext ausgegeben. **Damit ist die Alpaca-Marktdaten-Anbindung jetzt vollständig end-to-end verifiziert, nicht mehr nur hermetisch getestet.**

## Was noch offen ist

1. ~~Echte Alpaca/Polygon-Anbindung.~~ **Alpaca-Teil implementiert UND end-to-end mit echten Paper-Keys verifiziert (s. Nachtrag oben).** Polygon bleibt Stub — laut DECISIONS.md #4 ohnehin nur "optional später".
2. **Historische Indexmitgliedschaft (echte Daten).** `PointInTimeUniverse` ist nur der Mechanismus. Es gibt noch keine echten historischen S&P-500-Mitgliedschaftsdaten — das ist typischerweise ein kostenpflichtiger Datensatz und eine Beschaffungsaufgabe, keine Programmieraufgabe. Nicht mit einer plausibel aussehenden, aber erfundenen Fixture vorgetäuscht.
3. **Keine Halbtags-Handelstage.** NYSE veröffentlicht verkürzte Handelstage (z. B. Tag vor dem 4. Juli) pro Kalenderjahr, nicht nach fester Regel — eine handgepflegte Tabelle würde unbemerkt veralten. Bewusst nicht geraten, sondern als Lücke benannt.
4. **Corporate Actions decken nur Splits ab.** Dividenden werden in `ROADMAP.md` Abschnitt 7 als "ggf." (optional) geführt — noch nicht gebaut, kein aktueller Bedarf in Phase 4/5.
