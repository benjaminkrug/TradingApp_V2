# Nachrichten-Volumen als Verfeinerung der Übernacht-Auswahl — Pilot-Protokoll

**Status: vorregistriert.** Geschrieben und committet am 23.09.2026, **bevor** der Abruf-Code für den Volumen-Modus, die relative Berechnung oder der Vergleichstest existieren. Git-Zeitstempel als Beleg. Einzige Ausnahme, wie beim Stimmungs-Pilot: ein reiner API-Mechanik-Test (1 Firma, 10 Tage, siehe Änderungsprotokoll) — trägt keine Information über die eigentliche Hypothese, nur "funktioniert der Modus technisch".

## Woher die Hypothese kommt

Der Nutzer schlug vor, statt (oder zusätzlich zu) Handelsvolumen zu prüfen, ob **Nachrichten-Volumen** (wie viele Artikel an einem Tag über eine Firma erscheinen) ein nützliches Auswahlsignal ist — die Idee war ursprünglich, den ganzen Markt danach zu scannen. Als ersten, kostengünstigen Schritt wird das hier auf dem bereits bestehenden 24-Firmen-Pilot getestet (siehe `NEWS_SENTIMENT_PILOT_PROTOCOL.md` für die identische Vorgehensweise bei Stimmung statt Volumen).

**Wichtiger Unterschied zum Stimmungs-Pilot, der die Erwartung dämpfen sollte:** Nachrichten-Volumen und Handelsvolumen haben vermutlich eine gemeinsame Ursache (ein echtes Ereignis treibt beides gleichzeitig hoch). Die hier schon per Handelsvolumen vorselektierten Top-20-Aktien haben deshalb wahrscheinlich *ohnehin* schon überdurchschnittliches Nachrichten-Volumen — der Test misst also den **zusätzlichen** Erklärungswert von Nachrichten-Volumen *über das bereits vorhandene Handelsvolumen-Signal hinaus*, nicht Nachrichten-Volumen als eigenständiges Signal auf dem gesamten Markt. Das ist ein schwerer zu bestehender, konservativerer Test als ein direkter Test auf dem ganzen Markt — genau deshalb aber auch aussagekräftiger, wenn er tatsächlich etwas findet.

## Was genau getestet wird

Von den täglich bereits ausgewählten Top-20-Aktien (nach Handelsvolumen) — schneidet die Hälfte mit relativ höherem Nachrichten-Volumen besser ab als die Hälfte mit relativ niedrigerem? Exakt dieselbe Test-Struktur wie beim Stimmungs-Pilot, nur mit einer anderen GDELT-Datenreihe.

## Datenquelle: GDELT `timelinevol`-Modus

Technisch gegen die echte API geprüft (23.09.2026, vor jeder inhaltlichen Berechnung):
```
mode=timelinevol, query="Apple Inc", 01.–10.06.2026
→ {"timeline": [{"series": "Volume Intensity", "data": [{"date": "20260601T000000Z", "value": 0.01}, ...]}]}
```
- **Identisches JSON-Format wie `timelinetone`** (nur anderer `series`-Name) — der bestehende `_parse_timeline`-Parser funktioniert unverändert, da er generisch nach `date`/`value`-Paaren sucht, nicht nach dem `series`-Namen filtert.
- `value` ist die **normierte Volumen-Intensität**: der Anteil aller an dem Tag von GDELT erfassten Artikel weltweit, der die Firma erwähnt (z. B. 0,01 = 1 %) — nicht die rohe Artikelanzahl. Das ist tageweise bereits vergleichbar (kein Nachrichten-Gesamtvolumen-Trend über die Zeit verzerrt das Ergebnis), also die richtige Wahl gegenüber `timelinevolraw`.
- Gleicher Rate-Limit wie beim Tone-Modus (unvorhersehbar, "1 Anfrage/5s" in der Fehlermeldung, real oft mehr) — bereits bestätigt bei diesem Test (erster Versuch abgelehnt, zweiter nach Backoff erfolgreich).
- Gleiche 90-Tage-Obergrenze pro Abfrage, gleiche Chunking-Logik.

## Pilot-Universum und Zeitraum

**Identisch zum Stimmungs-Pilot:** dieselben 24 Symbole (ECHO, NWS, APP, COO, STZ, PCG, TKO, STT, CRH, HPE, BF.B, FDX, JKHY, FERG, DLTR, FDS, CPAY, TPL, CIEN, IBKR, WDAY, KEYS, DELL, NVR), dieselben letzten 2 Jahre, dieselbe bereits gecachte Kurs- und Handelsvolumen-Auswahl (`data_cache/daily_bars_split_adjusted/`) — kein neuer Kursabruf nötig, nur ein neuer GDELT-Abruf im `timelinevol`-Modus.

## Methodik

1. **Relatives Nachrichten-Volumen statt absoluter Schwelle:** Tageswert der "Volume Intensity" einer Firma minus dem gleitenden Durchschnitt der vorangegangenen 20 Kalendertage — exakt dieselbe, bereits gebaute und getestete Funktion (`relative_tone_by_day` in `app/validation/news_sentiment.py`) wird unverändert wiederverwendet, nur mit Nachrichten-Volumen- statt Tone-Werten als Eingabe. Kein neuer Code für diesen Schritt — die Funktion ist bewusst generisch (Name bleibt trotzdem "tone", um den bereits committeten und getesteten Code nicht ohne Not umzubenennen; ein Kommentar an der Aufrufstelle macht die Wiederverwendung explizit).
2. **Niemals Blick in die Zukunft:** wie immer, geprüft wie beim Tone-Fall.
3. **Test:** Von den Tagen mit Top-20-Auswahl: obere Hälfte nach relativem Nachrichten-Volumen vs. untere Hälfte (Median-Trennung an diesem Tag). Tagesblock-Bootstrap (`cluster_bootstrap`), 2 bp Friktion, wie immer.

## Was dieses Protokoll ausdrücklich nicht leistet

- Kein Ersatz für K8 (Survivorship Bias) — gilt wie immer.
- **Zusätzliche Mehrfachtestung obendrauf.** Zählt als zwei weitere Konfigurationen (obere/untere Hälfte) zur Gesamtrechnung dieser Session — nach dem Stimmungs-Pilot (31 Konfigurationen) wären das 33. Ein p-Wert muss entsprechend strenger gelesen werden.
- **Kein Test von Nachrichten-Volumen als eigenständigem Auswahlsignal auf dem ganzen Markt** — das war die ursprüngliche Nutzer-Idee, aber bewusst noch nicht Teil dieses ersten, günstigen Piloten (siehe "Wichtiger Unterschied" oben). Bei einem positiven Ergebnis hier wäre eine Ausweitung auf mehr Symbole der nächste Schritt, nicht automatisch der ganze Markt (mehrere tausend Ticker wären bei GDELTs Rate-Limit ein Abruf von vermutlich vielen Stunden bis Tagen).
- Nur 24 von 503 Aktien — wie beim Stimmungs-Pilot keine Verallgemeinerung ohne Ausweitung.

## Änderungsprotokoll

| Datum | Änderung | Vor/nach Kenntnis von Ergebnissen? |
|---|---|---|
| 23.09.2026 | Erstfassung, nach dem 1-Firma-Test der `timelinevol`-API-Mechanik (Antwortformat, Rate-Limit-Verhalten — technische Machbarkeitsprüfung, keine inhaltlichen Ergebnisse), vor jeder Berechnung von relativem Nachrichten-Volumen oder jedem Vergleichstest | Vorher, bezogen auf das eigentliche Ergebnis. Der Mechanik-Test lieferte keine Information über die Kernfrage (hohes vs. niedriges Nachrichten-Volumen → bessere Rendite). |
