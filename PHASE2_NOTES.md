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
3. `fastapi`, `pandas`, `sqlalchemy` etc. in `backend/pyproject.toml` sind aus demselben Sandbox-Grund weiterhin nur deklariert, nicht einzeln verifiziert — aber da `pip` auf GitHub-Runnern nachweislich funktioniert (s. o.), ist das Risiko hier gering.
4. CI installiert im Hauptjob weiterhin nur `pytest` und führt die stdlib-Tests aus. Ein vollständiger Dependency-Install-Job kommt, sobald Punkt 2 ansteht und echter Code ihn braucht.
