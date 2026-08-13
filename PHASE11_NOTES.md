# Phase 11 — Controlled Live Test: Status & offene Punkte

Referenz: `ROADMAP.md` Abschnitt 14 und 19 ("Erst nach Klärung PDT/Kontogröße, sehr kleines Kapital").

## Wichtigste Einordnung vor allem anderen

**Diese Phase enthält keine Fähigkeit, echte Trades auszulösen oder eine echte Broker-Verbindung herzustellen — absichtlich.** Alles Bisherige (Phase 1–10) hat reale externe Abhängigkeiten (PyPI, Alpaca, npm-Registry) mit demselben Muster behandelt: echten Code schreiben, ehrlich dokumentieren, dass er in dieser Sandbox nicht verifizierbar ist, per CI oder durch den Nutzer selbst verifizieren lassen. Bei echtem Geld reicht dieses Muster nicht — "ungetesteter Code, der bei Gelegenheit gegen echtes Kapital läuft" ist etwas fundamental anderes als "ungetesteter Code, der bei Gelegenheit gegen eine Test-API läuft". Diese Phase liefert deshalb ausschließlich **Sicherheits- und Bereitschafts-Infrastruktur** — kein Order-Ausführungsclient gegen einen echten Broker. Die Entscheidung, tatsächlich Kapital einzusetzen, bleibt vollständig beim Nutzer, außerhalb dieser Sandbox, mit echten Zugangsdaten.

## Vorab geklärt: DECISIONS.md #6 — mit Einschränkung

Vor Beginn dieser Phase wurden dieselben drei Fragen gestellt wie zuvor bei #4/#5 (Kontostruktur, Kapitalhöhe, Reihenfolge News-Filter/Phase 11). Der Nutzer hat auf alle drei mit "keine Präferenz" geantwortet — anders als bei #4/#5/#7, wo jeweils aktiv eine Option gewählt wurde. Das wird in DECISIONS.md **ausdrücklich nicht als "festgelegt" geführt**, sondern als angewendeter Default (Cash-Konto, 750 USD, News-Filter zuerst) — dieselbe Empfehlung, die in den Fragen selbst stand, aber ohne individuelle Bestätigung übernommen. **Muss vor echtem Kapitaleinsatz erneut mit dem Nutzer bestätigt werden.**

Warum Cash-Konto: Da alle Strategien intraday sind (Position wird spätestens am selben Handelstag geschlossen, DECISIONS.md #2), zählt praktisch jeder Trade als "Day Trade". Ein Margin-Konto würde unter der PDT-Regel (FINRA, US-Regulierung) nach 4 Day-Trades innerhalb von 5 Handelstagen für 90 Tage gesperrt, sofern das Konto nicht mindestens 25.000 USD hält. Cash-Konten unterliegen der PDT-Regel überhaupt nicht (sie ist eine Margin-spezifische Regel) — Kompromiss dafür: T+1/T+2-Abwicklung, verkaufte Mittel sind nicht sofort wieder verfügbar. Für Long-only (DECISIONS.md #3) kein zusätzlicher Nachteil, da kein Leerverkauf benötigt wird.

## Was gebaut wurde

**`app/signals/news_filter.py`** — der in PHASE10_NOTES.md als offener Punkt benannte News/Earnings-Filter (ROADMAP Abschnitt 14: "Vor jedem Trade: Prüfung auf Earnings, relevante News, ungewöhnliche Volatilität"). Drei Prüfungen mit bewusst unterschiedlicher Ehrlichkeit über den eigenen Reifegrad:

1. **Earnings-Blackout** — echte Prüfung, echtes Interface (`EarningsCalendarProvider`), aber nur ein dokumentierter, unverifizierter Stub für echte Daten (keine Earnings-Kalender-API in dieser Sandbox erreichbar, dieselbe Einschränkung wie Alpaca/Polygon). `FakeEarningsCalendarProvider` für Tests, nach demselben Muster wie `FakeProvider`.
2. **Ungewöhnliche Volatilität** — eine **echte, tatsächlich funktionierende** Prüfung, keine Attrappe: vergleicht kurzfristige ATR gegen eine längerfristige Baseline-ATR (`app/features/indicators.py`s bereits verifiziertes `atr()`), braucht keine externe Datenquelle.
3. **Relevante News** — **nicht gebaut, nicht einmal als Stub.** "Relevant" ist eine Einschätzungsfrage (Sentiment, Materialität, Quellenglaubwürdigkeit), die dieser Code aktuell überhaupt nicht beurteilen kann, nicht nur eine, die er mangels Daten nicht verifizieren kann. Eine erfundene Schnittstelle ohne echten Inhalt dahinter würde mehr Reife vortäuschen, als tatsächlich existiert — ehrlicher als `NOT_AUTOMATED` geführt, im selben Stil wie `app/validation/gate.py`.

Optional in `PaperTradingEngine`/`run_paper_trading`/`ForwardTestSession` verdrahtet (`earnings_provider=None` per Default — überspringt das Gate vollständig, alle 200 bestehenden Phase-9/10-Tests bleiben dadurch unverändert grün).

**`app/live_readiness/readiness.py`** — Go/No-Go-Checkliste, kein Ausführungscode. `evaluate_live_readiness()` prüft: Forward-Test-Bereitschaft (Phase 10), PDT-sicheres Konto, konfigurierter Kill-Switch (`DailyLossGuard`), verdrahteter News-Filter — alle vier automatisierbar und PASS/FAIL. Zwei weitere Punkte sind **grundsätzlich nicht automatisierbar** und werden auch nicht als solche vorgetäuscht: Broker-Konnektivität (kann aus dieser Sandbox nicht geprüft werden, Alpaca ist netzwerkseitig blockiert) und die menschliche Freigabe selbst ("kein Code kann die explizite Autorisierung des Nutzers ersetzen, echtes Kapital zu riskieren").

`LiveTestConstraints.max_position_pct_of_capital` — ein zweiter, von der risikobasierten Positionsgrößenberechnung unabhängiger Deckel. Grund: Phase 9 fand, dass reine Risiko-%-Bemessung bei engem Stop eine Position verlangen kann, die weit mehr kostet als das gesamte Konto (PHASE9_NOTES.md). `Portfolio`s Kaufkraft-Prüfung (Phase 9) fängt das bereits ab, aber bei einem sehr kleinen Live-Konto (750 USD) ist ein expliziter, unabhängiger Deckel eine zusätzliche Sicherheitsschicht, die nicht allein von einer einzelnen Berechnung abhängt.

**`scripts/phase11_live_readiness_demo.py`** — führt einen Forward-Test (wie Phase 10, jetzt mit News-Filter verdrahtet) auf synthetischen Daten durch und lässt das Ergebnis durch `evaluate_live_readiness()` laufen. Druckt einen expliziten Hinweis, dass `passed=True` sich nur auf automatisierbare Punkte auf synthetischen Daten bezieht — keine Freigabe für echtes Kapital.

## Was ausdrücklich NICHT gebaut wurde — und warum das eine Grenze ist, keine Lücke

- **Kein Order-Ausführungsclient gegen Alpaca (oder einen anderen Broker).** `AlpacaProvider` (Phase 3) deckt nur Marktdaten ab, nicht Order-Ausführung — und bleibt ein unverifizierter Stub. Ein Ausführungsclient hätte in dieser Sandbox ohnehin nicht getestet werden können (Netzwerksperre), aber selbst wenn er es könnte: reale Order-Ausführung ist eine Fähigkeit, die nie ohne unmittelbare, bewusste menschliche Aufsicht im Moment der Ausführung existieren sollte. Das hier zu bauen "weil es dem bisherigen Muster folgt" wäre falsch angewandte Konsistenz.
- **Kein automatischer Übergang von Paper zu Live.** `evaluate_live_readiness()` erzeugt einen Bericht, keine Aktion. Ein `passed=True` verändert keinen Zustand und triggert nichts.

## Was noch offen ist

1. **DECISIONS.md #6 ist ein Default, keine individuell bestätigte Entscheidung** (siehe oben) — vor echtem Kapitaleinsatz erneut zu klären.
2. **Relevante-News-Prüfung existiert nicht.** Würde eine Sentiment-/Materialitäts-Einschätzung brauchen, die weit über eine Datenquellen-Anbindung hinausgeht — eigenständiges, größeres Vorhaben.
3. **Broker-Konnektivität nie verifiziert.** Muss der Nutzer selbst mit echten Alpaca-Zugangsdaten außerhalb dieser Sandbox tun.
4. **Kein echter Forward-Test-Datensatz existiert** (siehe PHASE10_NOTES.md) — `evaluate_live_readiness()`s `forward_test_confirmed`-Prüfung ist bisher nur gegen synthetische Daten demonstriert, nie gegen einen echten, über echte Zeit gelaufenen Test.
5. **Kein Order-Ausführungsclient** (siehe oben) — bewusste Grenze, kein technisches Versäumnis.
6. **`max_position_pct_of_capital` (25 %) ist ein weiterer unbestätigter Default**, nicht Teil von DECISIONS.md #1–#7, da er erst in dieser Phase als Sicherheitsmechanismus eingeführt wurde.

224 Tests laufen grün (24 neue: 13 `news_filter`, 3 `PaperTradingEngine`-Pretrade-Gate-Integration, 8 `live_readiness`), 7 weiterhin übersprungen (FastAPI, siehe PHASE8_NOTES.md).
