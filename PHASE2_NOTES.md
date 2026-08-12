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

## Was noch offen ist (nicht vergessen, sondern blockiert durch die Sandbox)

1. **Framework-Entscheidung verifizieren.** `ROADMAP.md` schlägt Nautilus Trader vor (identischer Codepfad für Backtest/Live/Paper, event-driven, damit strukturell look-ahead-sicher). Das basiert auf meinem Trainingsstand; ob die aktuelle Version, Python-3.11/3.12-Kompatibilität und Installierbarkeit auf der Zielplattform tatsächlich stimmen, konnte ich hier **nicht** live prüfen. `nautilus_trader` ist deshalb bewusst *nicht* in `backend/pyproject.toml` als Abhängigkeit eingetragen (nur als auskommentierter Kandidat), damit CI nicht an einer ungeprüften Annahme scheitert.
2. **Cross-Validation.** Sobald Nautilus Trader (oder die Alternative) installierbar ist: dieselben Szenarien aus `test_reference_engine.py` dagegen laufen lassen und prüfen, ob das Ergebnis exakt (im Toleranzbereich) übereinstimmt. Erst danach gilt die Engine als vertrauenswürdig für Phase 3+.
3. **`pip install -e backend/.[dev]` einmal in einer Umgebung mit Internetzugang ausführen** (lokal bei dir oder via CI) — auch `fastapi`, `pandas` etc. sind aus demselben Grund bisher nur deklariert, nicht verifiziert.
4. CI (`.github/workflows/ci.yml`) installiert aktuell nur `pytest` und führt die stdlib-Tests aus. Ein zweiter Job mit vollständiger Dependency-Installation kommt dazu, sobald Punkt 1–3 geklärt sind.

## Empfehlung

Diesen offenen Teil entweder (a) du führst `pip install -e backend/.[dev]` einmal lokal aus und meldest das Ergebnis zurück, oder (b) ich öffne einen PR und lasse GitHub Actions es dort verifizieren (volles Internet auf den Runnern). Push auf den Branch reicht, um CI auszulösen — ein PR ist dafür nicht zwingend nötig.
