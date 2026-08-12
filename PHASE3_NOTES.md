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

## Was noch offen ist

1. **Echte Alpaca/Polygon-Anbindung.** Kann in dieser Sandbox nicht verifiziert werden (Netzwerksperre + keine Keys). Nächster Schritt: entweder du testest `AlpacaProvider`/`PolygonProvider` lokal mit echten Keys, oder wir hinterlegen sie als GitHub-Actions-Secrets für einen künftigen Probe-Job (nach demselben Muster wie der Nautilus-Trader-Check in Phase 2) — dafür wäre vorher zu klären, ob du das möchtest, da damit reale Zugangsdaten ins Spiel kommen.
2. **Historische Indexmitgliedschaft (echte Daten).** `PointInTimeUniverse` ist nur der Mechanismus. Es gibt noch keine echten historischen S&P-500-Mitgliedschaftsdaten — das ist typischerweise ein kostenpflichtiger Datensatz und eine Beschaffungsaufgabe, keine Programmieraufgabe. Nicht mit einer plausibel aussehenden, aber erfundenen Fixture vorgetäuscht.
3. **Keine Halbtags-Handelstage.** NYSE veröffentlicht verkürzte Handelstage (z. B. Tag vor dem 4. Juli) pro Kalenderjahr, nicht nach fester Regel — eine handgepflegte Tabelle würde unbemerkt veralten. Bewusst nicht geraten, sondern als Lücke benannt.
4. **Corporate Actions decken nur Splits ab.** Dividenden werden in `ROADMAP.md` Abschnitt 7 als "ggf." (optional) geführt — noch nicht gebaut, kein aktueller Bedarf in Phase 4/5.
