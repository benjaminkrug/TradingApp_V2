# Übernacht-Auswahlstrategie — vorab festgelegtes Protokoll

**Status: vorregistriert.** Geschrieben und committet am 21.09.2026, **bevor** Auswahllogik, Datenanbindung oder Backtest existieren. Der Git-Zeitstempel ist der Beleg.

## Woher die Hypothese kommt

Zwei unabhängig belegte Effekte, in dieser Session recherchiert:

1. **Übernacht-Rendite ist ein bekannter Effekt** — in unserem eigenen kleinen Test (AAPL/MSFT/NVDA, ~137 Handelstage) der stärkste bisher gemessene Wert (Tagesblock-Bootstrap t = +1,33, nicht signifikant, aber uneinheitlich zwischen Symbolen — siehe Chat-Verlauf).
2. **Der Auslöser dieser Rendite ist in der Literatur benannt** (Berkman/Koch/Tuttle/Zhang 2012; Aboody/Even-Tov/Lehavy/Trueman 2018): Aktien mit ungewöhnlich hoher Aufmerksamkeit/Volumen an Tag N werden am Morgen von Tag N+1 von Privatanlegern hochgekauft — daher die hohe Übernacht-Rendite. Im Tagesverlauf gleicht sich das tendenziell wieder aus (Stimmungs-Reversal, kein fundamentales Signal — Aktien mit hoher Übernacht-Rendite underperformen laut denselben Studien **langfristig**).

**Explizit festgehalten, damit das nicht überverkauft wird:** Diese Kombination — Auswahl nach Tagesvolumen, Handel als Übernacht-Position — ist **unsere eigene Synthese**, keine in genau dieser Form in einer Studie getestete Strategie. Beide Bausteine sind einzeln belegt, die Kombination nicht.

## Warum mit kostenlosen Daten, nicht mit Databento

Anders als die intraday-basierte "Stocks in Play"-Variante (`SELECTION_LAYER_PROTOCOL.md`) braucht diese Version **nur Tagesdaten** — sowohl für die Auswahl (Tagesvolumen relativ zum Durchschnitt) als auch für den Trade selbst (Schlusskurs → nächste Eröffnung). Tagesdaten für ein breites Universum liefert Alpaca kostenlos. Die 199-USD/Monat-Frage für Databentos Security Master stellt sich für diesen ersten Test nicht.

## Universum

**S&P-500-Mitgliederliste, Stand 21.09.2026**, aus einer öffentlichen Quelle bezogen. **Bewusst mit Survivorship Bias behaftet** (heutige Liste rückwirkend angewendet, keine Punkt-in-Zeit-Historie — dieselbe K8-Einschränkung wie in `SELECTION_LAYER_PROTOCOL.md`, hier ebenfalls ungelöst). Jedes Ergebnis gilt bis zur Lösung von K8 als vorläufig.

**Eignungsfilter:** Kurs > 5 USD. Kein zusätzlicher Liquiditätsfilter — S&P-500-Mitgliedschaft impliziert bereits ausreichende Liquidität.

**Wichtiger Unterschied zur "Stocks in Play"-Studie, offen benannt:** Die Studie wählt die Top 20 aus ~7.000 eignungsfähigen Aktien (~0,3 %). Wir wählen aus 500 S&P-Mitgliedern (Top 20 = 4 %, Top 5 = 1 %) — strukturell weniger selektiv. Deshalb werden **zwei** Konfigurationen getestet, nicht nachträglich die günstigere ausgewählt: **Top 20** und **Top 5**, beide vorab hier festgelegt.

## Auswahlmechanik

Für jeden Handelstag N, mit Daten, die an Tag N tatsächlich schon bekannt sind:
- Relatives Volumen = Tagesvolumen an Tag N ÷ Durchschnittsvolumen der vorangegangenen 20 Handelstage (Standard-Konvention für Tagesdaten — bewusst nicht die 14 Tage aus der Intraday-Studie übernommen, da dort ein anderer, minütlicher Kontext gemeint war).
- Rangliste nach relativem Volumen, Top 20 bzw. Top 5 gehandelt.

## Trade

**Einstieg:** Schlusskurs von Tag N. **Ausstieg:** Eröffnungskurs von Tag N+1. Kein Intraday-Timing — bewusst, weil K7 im vorherigen Gate-Lauf gezeigt hat, dass Einstiegs-Timing auf unseren Daten keine Information trägt (p-Median 0,799). Kein Stop-Loss: Ein Stop kann außerhalb der Handelszeiten nicht ausgeführt werden, ein "Übernacht-Stop" wäre eine Illusion von Risikokontrolle.

**Positionsgröße/Risiko in diesem ersten Test: bewusst ausgeklammert.** Diese Runde beantwortet ausschließlich die statistische Frage "zeigt Auswahl+Übernacht-Halten einen Effekt in Prozent-Rendite" — wie schon beim allerersten Drei-Symbole-Test vor Einführung der Paper-Engine. `trade_return_bp` ist skaleninvariant (in `SELECTION_LAYER_PROTOCOL.md` gegengeprüft), reale Positionsgrößen/Kapitalallokation sind eine separate, spätere Frage, falls diese Strategie überhaupt so weit kommt.

## Kriterien

**K3 (Kosten):** Netto-Rendite bei 2 bp Friktion, plus Break-even-Ausweis — unverändert aus `VALIDATION_PROTOCOL.md`.

**K4 (Signifikanz):** Tagesblock-Bootstrap (`cluster_bootstrap`, bereits verifiziert) — passt hier besonders gut, weil an einem Tag mehrere Aktien gleichzeitig ausgewählt werden und genau diese Häufung der Grund ist, warum der naive Test nicht funktioniert.

**K5 (Stichprobe):** ≥ 200 Trades insgesamt, ≥ 30 pro Drittel des Zeitraums (wie bisher).

**K6 (Marktphasen):** Backtest-Zeitraum bewusst so gewählt, dass er mehrere echte Marktphasen abdeckt (s. u.) — das war beim Drei-Symbole-Test unmöglich (nur ein ~6,5-Monats-Fenster), hier zum ersten Mal wirklich prüfbar.

**K-neu — Auswahltest (ersetzt K7 für diese Strategie):** K7 aus `VALIDATION_PROTOCOL.md` (Einstiegszeitpunkt-Permutation) passt hier nicht — es gibt kein Intraday-Timing zu testen. Stattdessen: **Zufällige Aktienauswahl statt Volumen-Rangliste**, gleicher Tag, gleiche Anzahl Aktien, gleiche Trade-Form (Schluss→nächste Eröffnung). Tausende Male wiederholt. Die Frage lautet exakt: *Ist die Auswahl nach Volumen besser als eine zufällige Auswahl aus derselben eignungsfähigen Menge, am selben Tag?* Das isoliert den Auswahleffekt vom allgemeinen Markt-Beta über Nacht (jede Zufallsauswahl trägt dieselbe Marktbewegung).

**Warum das nicht dieselbe Funktion ist wie zuvor:** Der vorherige Permutationstest (`permutation_test_entry_timing`) hat Einstiege in Bar-Anzahl verschoben — bei einem Übernacht-Trade wäre das strukturell fehlerhaft (Bar-Abstand zwischen Schlusskurs und nächster Eröffnung ist "1 Bar" in unseren Tagesdaten, unabhängig von der tatsächlich vergangenen Zeit). Das ist bereits einmal falsch angewendet und danach verworfen worden (siehe Chat-Verlauf, Diagnose-Skript). Für diesen Test wird eine **neue, eigene Funktion** gebaut und mit einem Fall mit bekannter Antwort gegengeprüft, bevor sie auf echte Daten trifft.

## Backtest-Zeitraum

**01.01.2021 – heute (~5,7 Jahre).** Bewusst lang genug gewählt, um mehrere Marktphasen zu enthalten (2022 Bärenmarkt, 2023–2025 Erholung/Rally) — im Gegensatz zum vorherigen ~6,5-Monats-Fenster, das nur eine einzige Phase abdeckte und K6 damit gar nicht prüfbar machte.

## Was dieses Protokoll ausdrücklich nicht löst

- Survivorship Bias (K8) bleibt ungelöst, jedes Ergebnis ist vorläufig.
- Es ist eine eigene Hypothese, keine Literatur-Replikation — ein Bestehen bestätigt nicht die zitierten Studien, nur unsere eigene Kombination.
- Positionsgröße/Kapitalallokation für echtes (Paper-)Trading ist nicht Teil dieses ersten Tests.

## Änderungsprotokoll

| Datum | Änderung | Vor/nach Kenntnis von Ergebnissen? |
|---|---|---|
| 21.09.2026 | Erstfassung, vor jeder Implementierung, Datenanbindung oder jedem Testlauf | vorher |
| 21.09.2026 | `AlpacaProvider` lieferte unbereinigte Kurse (`adjustment="raw"`), Aktiensplits (NVDA, GOOGL, AMZN, CMG u. a., 64 Fälle über 503 Symbole) erschienen als künstliche ~90-%-Übernacht-Verluste. Behoben: `adjustment="split"`, Daten komplett neu geladen. | **Nach Kenntnis eines fehlerhaften Ergebnisses** (der erste Lauf sah vielversprechend aus, war aber kontaminiert) — **vor** Kenntnis irgendeines Ergebnisses auf bereinigten Daten. Die Korrektur selbst ist eine Datenqualitäts-Reparatur, keine nachträgliche Anpassung der Kriterien. |
| 22.09.2026 | Zwei zusätzliche Datenfilter in `overnight_selection.py`: (a) Bars mit Volumen 0 (Phantom-Kerzen, gefunden bei TPL — 3 Fälle mit exakt gleichem Platzhalterkurs) werden nirgends verwendet; (b) Übernacht-Bewegungen über 30 % werden ausgeschlossen (`MAX_PLAUSIBLE_OVERNIGHT_BP`), da sie vermutlich nicht von Alpacas Split-Bereinigung erfasste Unternehmensaktionen sind (Honeywell/DuPont-Abspaltungen 2025/26, mit echtem hohem Volumen, keine Datenfehler). | **Vor** jedem Lauf auf den bereinigten Daten — gefunden durch systematisches Scannen auf verbleibende Ausreißer, nicht durch ein bereits gesehenes Endergebnis. Bewusster Kompromiss, offen benannt: Der 30-%-Filter würde auch einen echten, extrem seltenen Nachrichtenschock ausschließen — ohne echte Unternehmensaktions-Daten (K8) lässt sich das nicht sauber trennen. |
