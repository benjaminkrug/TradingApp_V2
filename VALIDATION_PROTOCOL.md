# Validierungsprotokoll — vorab festgelegt

**Status: vorregistriert.** Dieses Dokument wurde am 21.09.2026 geschrieben und committet, **bevor** die darin beschriebenen Tests implementiert oder ausgeführt wurden. Der Git-Zeitstempel ist der Beleg dafür. Jede spätere Änderung an den Kriterien wird unten im Änderungsprotokoll festgehalten, mit Datum und Begründung — insbesondere, ob sie vor oder nach Kenntnis von Ergebnissen erfolgte.

**Warum überhaupt Vorregistrierung:** Wenn man Kriterien erst festlegt, nachdem man Ergebnisse gesehen hat, findet man immer eine Begründung dafür, warum ausgerechnet das eigene Ergebnis zählt. Genau daran kranken die veröffentlichten Opening-Range-Breakout-Studien (keine sauber getrennte Validierungsperiode nach Fixierung aller Regeln), während die Falsifikationsstudie von Mesfin (2026) durch Vorregistrierung glaubwürdig ist — sie hat Positivkontrollen mit t = 3,11 und t = 4,30, kann echten Edge also nachweislich erkennen und lehnt nicht einfach alles ab.

**Anlass:** Die erste Validierung gegen echte Marktdaten (`REAL_DATA_VALIDATION_NOTES.md`) hat gezeigt, dass der bisherige Prüfaufbau nicht aussagekräftig war — er testete eine Strategievariante, die so nie gehandelt würde, mit einem Kriterium, das eine wertlose Strategie in 50 % der Fälle bestehen lässt. Dieses Protokoll ersetzt ihn.

---

## Bestehenskriterien

Ein Strategiekandidat gilt nur dann als forward-test-reif, wenn **alle sieben** Kriterien gleichzeitig erfüllt sind (`DECISIONS.md` #8: streng). Teilerfüllung ist kein Bestehen, wird aber vollständig gespeichert (siehe "Ergebnisspeicher").

### K1 — Kein Look-Ahead, keine Datenlecks
`detect_leakage` meldet null Abweichungen zwischen vollem und abgeschnittenem Lauf. Unverändert gegenüber dem bisherigen Gate; dieser Test war nie das Problem.

### K2 — Bewertet werden die echten Handelsregeln
Die Bewertung erfolgt über die Ausführungslogik, die auch real gehandelt würde (`app/paper/`: ATR-Stop, Gewinnziel, Positionsgröße aus Kontorisiko), **nicht** über `reference_engine.py`.

`reference_engine.py` läuft als Gegenprobe weiter mit. Sie bleibt das, wofür sie gebaut wurde: ein von Hand nachrechenbares Korrektheits-Orakel. Weichen beide Engines unerklärlich stark voneinander ab, gilt das als Bug-Verdacht und muss aufgeklärt werden, bevor ein Ergebnis zählt.

**Ausführungsparameter werden einmal fixiert** (ATR-Periode, ATR-Vielfaches, Chance-Risiko-Verhältnis, Risiko-Prozent) und danach nicht pro Strategie nachjustiert. Jede spätere Justierung zählt als zusätzlicher Test im Sinne von K7.

### K3 — Positiver Nettoertrag nach Handelskosten
Erwartungswert pro Trade > 0 bei **2 Basispunkten Round-Trip-Friktion** als Referenzannahme (Größenordnung aus der Replikationsliteratur für liquide Instrumente; Spread allein liegt bei Large Caps darunter, der Rest deckt Marktimpact und die für Ausbruchseinstiege typische adverse Selektion ab).

Zusätzlich **immer auszuweisen: die Break-even-Friktion** — der Wert, ab dem der Edge verschwindet (`DECISIONS.md` #9). Ein Kandidat, dessen Break-even unter ~4 bp liegt, gilt auch bei bestandenem K3 als fragil und ist im Bericht als solcher zu kennzeichnen.

### K4 — Statistische Signifikanz
t ≥ 2,0 auf den **Netto**-Erträgen pro Trade im Out-of-Sample-Zeitraum.

Berechnung über **Block-Bootstrap mit ganzen Handelstagen als Blöcke**, nicht über den einfachen t-Test. Grund: Trades sind nicht unabhängig — sie häufen sich zeitlich, und an einem guten Tag gewinnen mehrere Symbole gemeinsam. Der naive t-Test behandelt jeden Trade als frische Münze und **überschätzt die Signifikanz dadurch systematisch**.

K4 ist ein Mindestfilter, kein Beweis. Das eigentliche Urteil fällt K7.

### K5 — Ausreichende Stichprobe
Mindestens **30 Trades pro OOS-Fold** und mindestens **200 Trades insgesamt**. Die 30 sind eine Untergrenze aus der Literatur, kein Gütesiegel — bei den dicken Verteilungsrändern von Trade-Erträgen sind sie eigentlich knapp. Deshalb zusätzlich die Gesamtzahl.

### K6 — Richtungskonsistenz über Marktphasen
Positiver Nettoertrag in **jedem einzelnen** von mindestens **drei** OOS-Zeiträumen, die **unterschiedliche Marktphasen** abdecken (nicht nur drei aufeinanderfolgende Quartale desselben Aufwärtstrends).

Bewusste Asymmetrie: Dieses Kriterium kann auch echte Strategien aussortieren — selbst gute Fonds haben Verlustjahre. Das wird in Kauf genommen, weil das aktuelle Problem Fehlalarme sind, nicht verpasste Chancen.

**Auf den heutigen Datenbestand ist K6 nicht anwendbar:** Das bisherige Testfenster (05.03.–21.09.2026) enthält genau eine Marktphase, alle drei getesteten Aktien stiegen um 22–28 %. K6 erzwingt damit automatisch die Beschaffung längerer Historie.

### K7 — Permutationstest gegen Zufall und Mehrfachtestung
p < 0,05 gegen folgende Nullhypothese: **Einstiegszeitpunkte werden innerhalb derselben Handelstage zufällig neu gezogen**, bei gleicher Anzahl Trades und gleicher Verteilung der Haltedauern. Mindestens 10.000 Permutationen.

Die Frage lautet damit exakt: *Ist unser Timing besser als blindes Handeln mit gleicher Marktpräsenz?*

Diese Konstruktion löst zugleich das Beta-Problem, das durch die Öffnung der Haltedauer (`DECISIONS.md` #2, geändert 21.09.2026) entsteht: Zufällige Einstiege in einem steigenden Markt vereinnahmen dieselbe Marktdrift wie die echte Strategie. Was übrig bleibt, ist Timing-Können — nicht Marktexposure.

---

## Immer zu berichten (keine Bestehenskriterien)

Diese Zahlen entscheiden nichts, müssen aber in jedem Bericht stehen, weil ihr Fehlen in der Vergangenheit zu Fehlschlüssen geführt hat:

- **Break-even-Friktion** (siehe K3)
- **Vergleich gegen Buy-and-Hold** desselben Symbols im selben Zeitraum, absolut und risikoadjustiert
- **Zeit im Markt** (Anteil der Zeit mit offener Position) — ohne diesen Wert ist ein Renditevergleich irreführend
- **Anteil über Nacht gehaltener Positionen** und maximale Haltedauer
- **Verteilung der maximalen Drawdowns** aus dem Monte-Carlo-Bootstrap (ohne PASS/FAIL, solange keine Risikotoleranz-Entscheidung getroffen ist)
- **Aufteilung des Ertrags** in Intraday- und Übernacht-Anteil

---

## Ergebnisspeicher

Jeder Lauf schreibt **vollständige Kennzahlen** in einen append-only Ergebnisspeicher — nicht nur PASS/FAIL (`DECISIONS.md` #8). Festgehalten werden mindestens: Strategie und Parameter, Symbol, Datenfenster, Datenquelle und Feed, alle Kriterienwerte, Zeitstempel, Git-Commit.

Zweck: Wenn das strenge Gate alles aussortiert — was zu erwarten ist — bleiben die Zahlen erhalten, sodass Beinahe-Treffer später gezielt wieder aufgegriffen werden können, statt die Suche bei null zu beginnen.

---

## Protokoll der Mehrfachtestung

K7 kann nur dann korrekt bewerten, wenn bekannt ist, wie oft gesucht wurde. Die wahre Zahl ausprobierter Konfigurationen ist immer größer als die Zahl der Läufe, weil auch implizite Entscheidungen zählen (Bar-Größe, Länge der Opening Range, Auswahl der Symbole, Länge des Datenfensters).

Deshalb: **Jede getestete Konfiguration wird hier oder im Ergebnisspeicher protokolliert**, auch verworfene. Bekannter Stand vor Inkrafttreten dieses Protokolls: 3 Strategien × 3 Symbole = 9 Kombinationen (`REAL_DATA_VALIDATION_NOTES.md`), zuzüglich nicht exakt bezifferbarer impliziter Wahlen. Bei der Bewertung wird deshalb konservativer gerechnet, als die reine Laufzahl nahelegt.

---

## Was dieses Protokoll ausdrücklich NICHT leistet

- Es macht keine Aussage über Survivorship Bias in der Symbolauswahl — das bleibt manuell zu prüfen.
- Es ersetzt keinen Forward-Test. Ein bestandener Gate-Lauf ist die *Voraussetzung* für einen Forward-Test, nicht sein Ersatz.
- Es garantiert keine Profitabilität. Es senkt nur die Wahrscheinlichkeit, Zufall für Können zu halten.
- Die Datenqualität bleibt eine eigene Baustelle: Der kostenlose Alpaca-Feed liefert nur IEX-Volumen (wenige Prozent des Gesamtmarkts). Volumenbasierte Signale sind darauf nur eingeschränkt beurteilbar.

---

## Änderungsprotokoll

| Datum | Änderung | Vor/nach Kenntnis von Ergebnissen? |
|---|---|---|
| 21.09.2026 | Erstfassung, vor Implementierung und Ausführung | vorher |
