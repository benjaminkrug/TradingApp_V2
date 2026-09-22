# Nachrichtenstimmung als Verfeinerung der Übernacht-Auswahl — Pilot-Protokoll

**Status: vorregistriert.** Geschrieben und committet am 22.09.2026, **bevor** der GDELT-Client, die Stimmungsberechnung oder der Vergleichstest existieren. Git-Zeitstempel als Beleg.

## Woher die Hypothese kommt

Der Nutzer fragte, ob sich die bereits validierte Übernacht-Auswahlstrategie (`OVERNIGHT_SELECTION_PROTOCOL.md`, Top-20-Konfiguration besteht knapp alle Kriterien) verbessern lässt, indem zusätzlich nach **echten positiven Nachrichten** gefiltert wird, statt nur nach Volumen. Die zitierte Studie zu Übernacht-Renditen (arXiv, "Does Overnight News Explain Overnight Returns?") deutet genau darauf hin: Nachrichteninhalt sagt Übernacht-Renditen besser vorher als reines Aufmerksamkeits-/Volumenmaß.

## Was genau getestet wird

**Nicht** ein Ersatz der Volumen-Auswahl, sondern eine Verfeinerung: Von den täglich bereits ausgewählten Top-20-Aktien (nach Volumen) — schneidet die Hälfte mit relativ positiverer Nachrichtenstimmung besser ab als die Hälfte mit relativ negativerer?

## Datenquelle: GDELT Project (kostenlos)

Empirisch bestätigt am 22.09.2026, direkt gegen die echte API getestet (nicht nur aus Dokumentation übernommen):
- Historische Zeiträume sind abrufbar (nicht nur die letzten 3 Monate) — Juni–August 2022 erfolgreich abgerufen.
- Tagesgenaue "Tone"-Werte pro Abfrage bestätigt.
- Exakte Firmennamen-Phrasen (z. B. `"Apple Inc"`) funktionieren als Abfrage, was das Problem mehrdeutiger Namen (Apple die Frucht, Target die Zielscheibe) entschärft, aber nicht vollständig löst.
- **Realer Rate-Limit ist unvorhersehbarer als dokumentiert:** Die Fehlermeldung nennt "1 Anfrage pro 5 Sekunden", tatsächlich brauchte es in einem Test bis zu ~25 Sekunden zwischen Versuchen, in einem anderen ging es sofort. Der Abruf-Client muss das mit Wiederholung und wachsender Wartezeit abfangen, nicht mit einer festen Pause.
- Maximal 3 Monate Zeitspanne pro einzelner Abfrage — für 5,7 Jahre Historie pro Firma braucht es ~23 Abfragen.

## Datenqualitäts-Fund vor dem eigentlichen Test

Die Ticker→Firmenname-Zuordnung (`sp500_constituents.csv`, Community-Quelle) enthält mindestens einen klaren Fehler: Ticker "P" wird als "Everpure" (eine Wasserfilter-Marke) geführt, mit Branche "Technology Hardware" und Sitz "Santa Clara, California" — das passt nicht zusammen und wurde laut Datei erst am 21.09.2026 geändert, vermutlich eine fehlerhafte Ticker-Neuzuordnung in der Quelle. **"P" wird aus dem Pilot-Universum ausgeschlossen.** Die übrigen Namen der Pilot-Liste wurden stichprobenartig auf Plausibilität geprüft (Branche/Sitz passt zum bekannten Unternehmen).

## Pilot-Universum

**Die 24 am häufigsten von der Volumen-Auswahl (Top-20-Konfiguration) gezogenen Aktien**, ermittelt aus bereits vorhandenen Daten (kein neuer Abruf nötig): ECHO, NWS, APP, COO, STZ, PCG, TKO, STT, CRH, HPE, BF.B, FDX, JKHY, FERG, DLTR, FDS, CPAY, TPL, CIEN, IBKR, WDAY, KEYS, DELL, NVR.

**Begründung für diese Auswahl statt Zufallsstichprobe:** Häufig ausgewählte Aktien liefern mehr Datenpunkte pro Firma für den Vergleichstest — mehr statistische Kraft pro investierter API-Anfrage. Bewusster Kompromiss, offen benannt: Diese Aktien sind nicht repräsentativ fürs ganze Universum, sie sind einfach die, die am öftesten hohes Volumen hatten. Ein Effekt, der nur bei diesen 24 Aktien gefunden wird, ist nicht automatisch auf alle 503 übertragbar.

## Zeitraum des Piloten

**Die letzten 2 Jahre (23.09.2024–22.09.2026), nicht die vollen 5,7 Jahre.** Bewusste Abkürzung für einen ersten, schnellen Test: ~8 statt ~23 Drei-Monats-Abfragen pro Firma, bei 24 Firmen ~192 statt ~552 Anfragen. **Konsequenz, offen benannt:** Dieser Zeitraum enthält nicht den Bärenmarkt von 2022 — K6 (Konsistenz über Marktphasen) ist mit diesem verkürzten Fenster nicht sinnvoll prüfbar, nur K3/K4 und der eigentliche Stimmungs-Vergleich. Bei einem vielversprechenden Ergebnis wird der Zeitraum auf die vollen 5,7 Jahre ausgeweitet, nicht vorher.

## Methodik (spiegelt die bereits verifizierte Volumen-Logik)

1. **Relative Stimmung statt absoluter Schwelle:** Tageswert des "Tone" einer Firma geteilt durch/verglichen mit ihrem eigenen gleitenden Durchschnitt der vorangegangenen 20 Handelstage — exakt dasselbe Muster wie `relative_volume_by_day`, nur mit Ton statt Volumen. Kein absoluter "Ton > 0"-Schnitt, weil Presseberichterstattung im Schnitt oft leicht negativ eingefärbt ist (Nachrichtenwert), nicht neutral bei 0.
2. **Niemals Blick in die Zukunft:** Der gleitende Durchschnitt nutzt ausschließlich Werte vor dem jeweiligen Tag — geprüft wie beim Volumen-Fall.
3. **Test:** Von den Tagen mit Top-20-Auswahl: obere Hälfte nach relativem Ton vs. untere Hälfte (Median-Trennung an diesem Tag). Sind die Übernacht-Renditen der oberen Hälfte statistisch besser? Verwendet den bereits gebauten und verifizierten Tagesblock-Bootstrap (`cluster_bootstrap`) — kein neuer Statistik-Code, nur neue Eingabedaten.
4. **Kosten/Netto:** Wie immer nach 2 bp Friktion, Break-even-Punkt ausgewiesen.

## Was dieses Protokoll ausdrücklich nicht leistet

- Kein Ersatz für K8 (Survivorship Bias) — gilt hier genauso wie in `OVERNIGHT_SELECTION_PROTOCOL.md`.
- Ist eine **zusätzliche** Mehrfachtestung obendrauf — zählt als weitere Konfiguration in der Gesamtrechnung über alle Sitzungen.
- Kein Beweis, selbst bei Bestehen — GDELTs Namens-basierte Texterkennung ist unpräziser als eine echte Ticker-Sentiment-API (siehe Kostenvergleich in der vorherigen Recherche). Ein positives Ergebnis wäre ein Grund, in eine sauberere (kostenpflichtige) Quelle zu investieren — nicht der Beweis selbst.
- Nur 24 von 503 Aktien getestet — kein Anspruch auf Verallgemeinerung ohne weitere Ausweitung.

## Änderungsprotokoll

| Datum | Änderung | Vor/nach Kenntnis von Ergebnissen? |
|---|---|---|
| 22.09.2026 | Erstfassung, nach dem 1-2-Firmen-Test der API-Mechanik (Rate-Limit, Datumsbereich, Namensformat — technische Machbarkeitsprüfung, keine inhaltlichen Ergebnisse), vor jeder Stimmungsberechnung oder jedem Vergleichstest | Vorher, bezogen auf das eigentliche Ergebnis. Die API-Mechanik-Tests lieferten keine Information über die Kernfrage (positive vs. negative Stimmung → bessere Rendite). |
