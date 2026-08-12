# Phase 2 — Backtest-Engine-Fundament: Status & offene Punkte

Referenz: `ROADMAP.md` Abschnitt 9 und 19. Dieses Dokument hält fest, was in Phase 2 tatsächlich fertiggestellt und *in dieser Sandbox ausgeführt und verifiziert* wurde, und was aus einer konkreten Umgebungseinschränkung heraus noch offen ist — nicht verschwiegen, sondern bewusst als nächster Schritt markiert.

## Umgebungs-Einschränkung (wichtig)

Diese Ausführungsumgebung hat **keinen Netzwerkzugriff auf PyPI** (`pypi.org` / `files.pythonhosted.org` liefern `403 host_not_allowed` — Organisationsrichtlinie, kein temporärer Fehler, siehe Diagnose unten). Damit war `pip install` für jedes externe Paket (inkl. `pandas`, `pytest`, `nautilus_trader`) hier nicht möglich.

```
$ curl -sSI https://pypi.org/simple/requests/
HTTP/2 403
x-deny-reason: host_not_allowed
```

Konsequenz für Phase 2: Ich habe den Teil, der sich ohne externe Abhängigkeiten bauen und **wirklich ausführen** lässt, fertiggestellt und getestet. Den Teil, der eine echte Paketinstallation braucht (Nautilus-Trader-Integration), habe ich bewusst *nicht* vorgetäuscht fertiggestellt, sondern als offenen Punkt unten markiert. GitHub Actions (Datei `.github/workflows/ci.yml`) läuft auf gehosteten Runnern mit vollem Internetzugang — dort ist die Installation real möglich und sollte beim nächsten Push/PR verifiziert werden.

## Was fertig ist und lokal verifiziert wurde

- `backend/app/data/point_in_time.py` — `PointInTimeSeries` + `SimulationCursor`: strukturelle Durchsetzung von "keine Zukunftsdaten" (ROADMAP Abschnitt 7). Eine Strategie bekommt nie die volle Datenreihe, sondern nur einen Cursor, der ausschließlich vorwärts läuft und `history` nur bis zum aktuellen Balken zurückgibt.
- `backend/app/backtest/reference_engine.py` — eine bewusst simple, **nicht produktive** Backtest-Schleife, die als Korrektheits-Referenz dient: Ihr Ergebnis für konstruierte Szenarien lässt sich von Hand nachrechnen.
- `backend/tests/` — 9 Tests, reine Standardbibliothek (`unittest`, keine Installation nötig), lokal ausgeführt:

  ```
  $ python3 -m unittest discover -s tests -v
  ...
  Ran 9 tests in 0.001s
  OK
  ```

  Darunter zwei Tests mit von Hand berechnetem Ergebnis (z. B. Kauf bei Close 102, Verkauf bei Close 103, Fee 0.01/Seite → erwarteter PnL 0.98, exakt geprüft) — das ist der in Abschnitt 9 geforderte "bekannte Testfall", nur eben gegen die Referenz-Engine statt gegen Nautilus Trader.

## Update 12.08.2026: Framework-Entscheidung verifiziert

Ein nicht-blockierender Probe-Job (`probe-nautilus-trader` in `.github/workflows/ci.yml`) wurde auf einem echten GitHub-Actions-Runner (ubuntu-latest, Python 3.12) ausgeführt — dort besteht, anders als in dieser Sandbox, voller PyPI-Zugriff:

```
Successfully installed ... nautilus_trader-1.231.0 ...
nautilus_trader 1.231.0
```

Run: [31590849328](https://github.com/benjaminkrug/TradingApp_V2/actions/runs/31590849328), Job `probe-nautilus-trader`, `conclusion: success`. Damit ist Punkt 1 unten erledigt — nicht angenommen, sondern auf echter Infrastruktur nachgewiesen.

`nautilus_trader` ist trotzdem bewusst noch **nicht** als harte Abhängigkeit in `backend/pyproject.toml` eingetragen: Es gibt aktuell keinen Code, der es tatsächlich importiert (das kommt erst mit der echten Backtest-Integration, vermutlich Phase 3/4). Es jetzt schon als Pflicht-Dependency zu führen, würde jeden CI-Lauf unnötig verlangsamen, ohne dass etwas davon abhängt — das wird nachgeholt, sobald echter Code darauf aufbaut.

## Was noch offen ist

1. ~~Framework-Entscheidung verifizieren~~ ✅ erledigt, siehe oben.
2. **Cross-Validation.** Sobald echter Nautilus-Trader-Code existiert (Phase 3/4): dieselben Szenarien aus `test_reference_engine.py` dagegen laufen lassen und prüfen, ob das Ergebnis exakt (im Toleranzbereich) übereinstimmt. Erst danach gilt die Engine als vertrauenswürdig für Live-/Paper-Trading-Entscheidungen.
3. `fastapi`, `pandas`, `sqlalchemy` etc. in `backend/pyproject.toml` sind aus demselben Sandbox-Grund weiterhin nur deklariert, nicht einzeln verifiziert. **Korrektur:** Der Probe-Job hat nur die *isolierte* Installierbarkeit von `nautilus_trader` gezeigt, nicht die gemeinsame Auflösbarkeit mit den übrigen deklarierten Abhängigkeiten — "Risiko gering" war hier zu pauschal formuliert. Konkreter Datenpunkt aus dem Pip-Log: `nautilus_trader` verlangt `pandas>=2.3.3,<4.0.0`; `pyproject.toml` war auf `pandas>=2.2` gesetzt, jetzt auf `>=2.3.3` angehoben, um das konsistent zu halten. Ein echter kombinierter Install-Test folgt erst mit Punkt 2.
4. CI installiert im Hauptjob weiterhin nur `pytest` und führt die stdlib-Tests aus. Ein vollständiger Dependency-Install-Job kommt, sobald Punkt 2 ansteht und echter Code ihn braucht.
5. Der `probe-nautilus-trader`-Job läuft mit `continue-on-error: true` — das war bewusst so gewählt, damit ein Fehlschlag keine PRs blockiert, hat aber die Kehrseite, dass niemand automatisch benachrichtigt wird, falls die Installierbarkeit später (neue Python-Version, Paket zurückgezogen o. Ä.) bricht. Sobald echter Code auf `nautilus_trader` aufbaut, muss das ein echtes, überwachtes Gate werden, kein optionaler Job.

## Update 12.08.2026 (2): Kritische Nachprüfung von Phase 2 — Fund und Fix

Bei genauer Nachprüfung (auf Wunsch des Nutzers) wurde ein substanzieller Fehler in `reference_engine.py` gefunden: Trades wurden zum Schlusskurs **derselben Bar** ausgeführt, deren Daten das Signal erzeugt haben (Zero-Latency-Annahme). Das ist **kein Look-Ahead-Fehler** — der Point-in-Time-Guard war korrekt, keine Zukunftsdaten flossen in die Entscheidung ein — aber genau die Art Ausführungs-Unrealismus, vor der `ROADMAP.md` (basierend auf den Transkript-Analysen) ausdrücklich warnt, und im Widerspruch zur dort dokumentierten Praxis "nur die Eröffnung der folgenden Kerze handeln".

**Fix:** Die Engine führt Trades jetzt zur Eröffnung der **nächsten** Bar nach dem Signal aus (Pending-Order-Modell). Ein Signal auf der letzten Bar der Serie verfällt absichtlich unausgeführt (kein nächster Balken vorhanden) — jetzt explizit getestet statt nur implizit passiert.

Weitere bei der Nachprüfung gefundene und behobene Punkte:

- `LookAheadError` war irreführend benannt — die Exception feuert nur bei "Cursor noch nicht gestartet", nie bei einem tatsächlichen Look-Ahead-Versuch (den es strukturell gar nicht geben kann, da die API keine entsprechende Methode besitzt). Umbenannt zu `CursorNotStartedError`, Modul-Docstring erklärt jetzt explizit, *wodurch* Look-Ahead tatsächlich verhindert wird (Abwesenheit von API-Oberfläche, nicht diese Exception) — und dass das nur gilt, solange niemand direkt auf `cursor._bars` zugreift (Python erzwingt keine echte Kapselung).
- `Bar(order=True)` war ungenutzt (kein Aufrufer sortiert je ohne expliziten `key=`) und ein latentes Risiko: bei identischen Zeitstempeln hätte ein versehentliches `sorted(bars)` ohne `key` nach Preisfeldern sortiert, was keinen Sinn ergibt. Entfernt.
- `StopIteration` wurde manuell aus einer gewöhnlichen Methode geworfen — funktioniert nur, weil aktuell immer explizit abgefangen. `SimulationCursor` implementiert jetzt das reguläre Iterator-Protokoll (`__iter__`/`__next__`), `advance()` bleibt als lesbarer Alias.
- Naive (zeitzonenlose) `datetime`-Werte wurden akzeptiert — `Bar` ist ein grundlegender Datentyp für alles Weitere; das jetzt früh zu erzwingen ist billig, ein Nachrüsten später wäre es nicht. `Bar` lehnt naive Zeitstempel jetzt ab.
- Fehlende Testabdeckung ergänzt: mehrere aufeinanderfolgende Round-Trips, ignoriertes zweites BUY-Signal während offener Position (kein Pyramiding), Signal auf der letzten Bar (verfällt absichtlich).
- **Nicht behoben, bewusst offen gelassen:** Die Bedeutung von `Fill.fee` ist noch unsauber (wird auf beiden Fills gespeichert, aber nur beim Verkauf tatsächlich verdoppelt abgezogen; kein Test prüft das Feld selbst). Gehört zur realistischen Ausführungsmodellierung in Phase 9, nicht in den Scope von Phase 2 gezogen, um keinen Scope-Creep zu erzeugen.

Alle 16 Tests (7 neu hinzugekommen) laufen lokal grün: `python3 -m unittest discover -s tests -v` → `OK`.
