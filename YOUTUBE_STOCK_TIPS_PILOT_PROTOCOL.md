# YouTube-Aktienempfehlungen als Signal — Erkundungs-Pilot-Protokoll

**Status: vorregistriert.** Geschrieben und committet am 24.09.2026, **bevor** ein einziges Video gelesen, ein Transkript abgerufen oder eine Rendite nachgeschlagen wurde. Git-Zeitstempel als Beleg.

## Woher die Hypothese kommt

Nutzer-Idee (diese Session): Statt Nachrichtenartikel (GDELT, bereits getestet — kein Signal, siehe `NEWS_SENTIMENT_PILOT_PROTOCOL.md` und `NEWS_VOLUME_PILOT_PROTOCOL.md`) als Aufmerksamkeits-/Auswahlsignal zu nutzen, YouTube-Videos beobachten, die konkrete Aktien zum Kauf empfehlen, und prüfen, ob diese Empfehlung eine kurzfristige (1–x Tage) Kursbewegung vorhersagt. Ursprüngliche Vision des Nutzers: ~100 Kanäle systematisch und laufend überwachen. **Dieses Protokoll deckt bewusst nur einen sehr kleinen, günstigen ersten Erkundungs-Test ab**, nicht die volle Vision — siehe "Was dieses Protokoll ausdrücklich nicht leistet".

## Warum ein Erkundungs-Pilot, kein vollständiger Test

Drei echte Kostenblöcke, die vor einer 100-Kanal-Version geklärt werden müssten:
1. **Kanal-Historie systematisch abrufen** braucht die YouTube Data API (kostenloses Kontingent, aber ein Google-Cloud-API-Key, den nur der Nutzer selbst anlegen kann — `YOUTUBE_API_KEY` existiert noch nicht in `.env`).
2. **Automatisierte Extraktion** ("welche Aktie, welche Empfehlung, welcher Zeithorizont" aus einem Transkript) braucht ein LLM pro Video. `ANTHROPIC_API_KEY` existiert in `.env`, ist aber **leer** — echte, wenn auch pro Video vermutlich kleine, Kosten, sobald befüllt.
3. **100 Kanäle × Jahre an Videos** ist ein Vielfaches des Aufwands der bereits gescheiterten GDELT-Piloten.

**Deshalb hier:** Ein sehr kleiner (angestrebt 10–20 Videos), manuell kuratierter Test ohne API-Kosten — Transkripte werden mit der kostenlosen `youtube-transcript-api`-Bibliothek abgerufen, die Extraktion (Ticker/Empfehlung/Datum) mache **ich selbst beim Lesen des Transkripts**, nicht per automatisiertem LLM-API-Call. Erst wenn dieser Erkundungstest überhaupt einen Hinweis auf ein Signal zeigt, ist eine größere, kostenpflichtige Version gerechtfertigt — dasselbe "billig zuerst"-Muster wie bei GDELT.

## Kanalauswahl

Per Websuche (24.09.2026) ermittelt, keine Kanäle vom Nutzer vorgegeben — **das ist eine Einschränkung, offen benannt**: Diese Auswahl ist meine Recherche, nicht die Vorlieben des Nutzers, und deckt nicht "100 Kanäle" ab. Bewusst eine Mischung aus zwei Kategorien, damit der Pilot nicht nur einen Kanal-Typ testet:

**Momentum/Day-Trading-Calls** (kurzfristig, oft konkrete "Kauf jetzt"-Aussagen — passt am besten zur 1–2-Tage-Haltedauer):
- Ricky Gutierrez
- Timothy Sykes

**Value-/Fundamental-Picks** (längere These, aber oft mit konkretem Ticker und Kaufzeitpunkt):
- Jeremy Lefebvre
- Sven Carlin (Value Investing with Sven Carlin)
- Learn to Invest (Jimmy)
- Jason Fieber (Dividends and Income)

Quellen: [Benzinga – 5 Best Stock Trading YouTube Channels](https://www.benzinga.com/money/best-stock-trading-youtube-channels), Suchergebnisse zu Stock-Alert-/Momentum-Kanälen (Ricky Gutierrez, Timothy Sykes).

## Auswahlregel für Videos (vorab festgelegt, um Rosinenpickerei zu vermeiden)

Ein Video wird nur aufgenommen, wenn es **explizit eine einzelne, konkrete Aktie zum Kauf empfiehlt** (nicht: allgemeine Marktkommentare, Watchlists mit vielen Tickern ohne klare Einzelempfehlung, reine Bildungsinhalte ohne Kaufaussage). Erfasst werden pro Video: Ticker, Veröffentlichungsdatum (von YouTube, nicht vom Nutzer geschätzt), die wörtliche Kaufaussage/Begründung, ein genannter Zeithorizont/Kursziel falls vorhanden. Videos werden **in der Reihenfolge gesucht/gelesen, in der sie gefunden werden** (z. B. neueste zuerst pro Kanal) — nicht erst mehrere lesen und dann nur die passenden ins Protokoll aufnehmen.

## Methodik

1. **Punkt-in-Zeit-Disziplin:** Einstieg = erster Handelstag NACH dem Veröffentlichungsdatum des Videos (das Video existierte am Veröffentlichungstag selbst ggf. erst nach Handelsschluss — konservativ immer der nächste Tag als frühestmöglicher Handelszeitpunkt).
2. **Haltedauer:** Rendite nach 1, 2 und 5 Handelstagen (mehrere Horizonte, da unklar ist, welcher am ehesten relevant ist — kein nachträgliches Aussuchen des besten Horizonts als "das Ergebnis").
3. **Kursdaten:** Bereits vorhandene `AlpacaProvider`-Anbindung (split-bereinigt), wie in den bisherigen Piloten.
4. **Auswertung:** Bei so kleiner Stichprobe (erwartet 10–20 Videos) **kein** formaler Bootstrap/Signifikanztest als Gate — nur deskriptiv (Durchschnitt, Verteilung, wie viele positiv/negativ). Das wird vorab so festgehalten, damit ein zufällig positiver Mittelwert bei n=15 nicht als "bestanden" verkauft wird. Explizit nur eine Erkundung: "gibt es überhaupt einen Hinweis, der eine größere (kostenpflichtige) Version rechtfertigt?"

## Was dieses Protokoll ausdrücklich nicht leistet

- **Keine automatisierte Extraktion** — ich lese/kategorisiere die Transkripte selbst, keine Skalierung auf mehr als eine Handvoll Kanäle möglich, ohne das zu ändern.
- **Keine 100-Kanal-Abdeckung** — nur 6 Kanäle, per Websuche gefunden, nicht vom Nutzer geprüft (analog zur DECISIONS.md-Konvention "Default, nicht individuell bestätigt").
- **Kein statistisches Gate** — bei dieser Stichprobengröße nicht sinnvoll, nur eine Ja/Nein-Erkundung, ob sich ein größerer Test lohnt.
- **Kein Ersatz für K8** oder andere offene Punkte der Übernacht-Auswahlstrategie — komplett unabhängiges Experiment.
- **`youtube-transcript-api` ist eine inoffizielle Bibliothek** (nutzt YouTubes öffentliche Untertitel-Daten, keine offizielle API, kein Key nötig) — falls sie nicht zuverlässig funktioniert, wird das ehrlich dokumentiert, nicht umgangen.
- Bei einem vielversprechenden Ergebnis: **erst mit dem Nutzer klären**, ob `YOUTUBE_API_KEY` angelegt und `ANTHROPIC_API_KEY` befüllt werden soll (echte, wiederkehrende Kosten), bevor auf mehr Kanäle/automatisierte Extraktion ausgeweitet wird — nicht einfach loslegen.

## Änderungsprotokoll

| Datum | Änderung | Vor/nach Kenntnis von Ergebnissen? |
|---|---|---|
| 24.09.2026 | Erstfassung, vor jedem Transkript-Abruf, jeder Video-Auswahl oder jeder Renditeberechnung | Vorher. Die vorangegangene Websuche diente nur der Kanal-Auswahl, lieferte keine Information über die eigentliche Frage (sagt eine Kaufempfehlung eine positive Rendite voraus?). |
