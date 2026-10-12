# Bouwprompt: ervaring hergebruiken zonder nieuwe kalibratie

Bouw de volgende mijlpaal voor Experience Forge in `<checkout>`. Werk zelfstandig aan lokale, omkeerbare wijzigingen. Overleg vóór betaalde API-aanroepen, installaties of publicatie. Bewaar bestaande bronversies, ruwe resultaten en onderbroken runs.

## Aanleiding

Lees `docs/EXECUTION-PROTOCOL.md` en `docs/EXECUTION-RESULTS.md`. In versie 0.3 haalden alle zes condities 45/45 correcte afrondingen. De echte lokale agent gebruikte in alle eindtaken de kalibratiehelper. Er is daarom geen aangetoond geheugenvoordeel. Ontwerp een nieuwe proef die meet of opgeslagen ervaring bruikbaar blijft wanneer verse kalibratie ontbreekt. Een positief resultaat is niet vereist.

## Experiment

Gebruik één echte agent en dezelfde familie van synthetische connectorconversies. Controleer opnieuw welke lokale modelruntime beschikbaar is; download niets. Vergelijk geen geheugen, ongevalideerd modelgegenereerd geheugen en onafhankelijk gevalideerd modelgegenereerd geheugen. Alle condities krijgen identieke trainingservaring, modelinstellingen, tools, volgordeprocedures en budgetten. Alleen toegang tot opgeslagen geheugen en het afgesproken validatiefilter verschillen.

Laat de agent tijdens de leerfase beschikbare kalibratie waarnemen en zelf kandidaatregels voorstellen. Gebruik aparte kwalificatievoorbeelden voor validatie. Wis vóór iedere eindtaak gesprekshistorie, procescontext en werkomgeving; open alleen het geheugen van de betreffende conditie opnieuw. Voorkom dat trainingstranscripten of caches impliciet geheugen aan de controleconditie geven.

Gebruik een vaste pilot van vijf nieuwe seeds **60701–60705**, met **12 eindtaken per seed per conditie**: zes bekende contracten met kalibratieuitval, twee gewijzigde of onbekende versies, één ontbrekende invoer, één tegenstrijdig eerder waargenomen contract en twee controles met beschikbare kalibratie. Dit geeft 60 eindtaken per conditie en 180 eindrollouts. Gebruik voor ontwikkeling andere seeds. Controleer vóór bevriezing dat deze seeds niet eerder voor eindruns gebruikt zijn; bij overlap selecteer je mechanisch een ongebruikte aaneengesloten reeks en leg je die vast vóór inference. Verander aantallen of seeds niet op basis van modelresultaten. Leg ook training en kwalificatie vooraf vast; rapporteer hun verbruik apart en reken de gemeenschappelijke leerfase gelijk toe aan alle condities.

Gebruik vooraf vastgelegde eindtaken met nieuwe invoerwaarden:

- Een eerder gezien bron- en versiecontract waarvan de kalibratieservice nu onbereikbaar is: een passende bewaarde regel kan helpen.
- Een gewijzigde of onbekende versie: een oude regel biedt geen geldige onderbouwing; onthouding is vereist zolang nieuwe kalibratie ontbreekt.
- Ontbrekende invoer en tegenstrijdige eerdere observaties: schrijf geen ongefundeerde waarde.
- Een afzonderlijke controle met beschikbare kalibratie, om gewone uitvoering te controleren.

Bron- en versie-identiteiten zijn zichtbaar en betekenisvol. Taaknamen mogen geen juiste actie of categorie verraden. Geheugen bevat alleen waarneembare ervaringen, regelvoorstellen en hun herkomst. Geen eindlabels, trainingsdatasetgenerator, verborgen coefficients of graderinformatie in prompts, tools of uitvoeringcontroles.

Gebruik dezelfde schrijfcontrole in alle drie condities. Een schrijfonderbouwing mag teruggrijpen op werkelijk opgeslagen kalibratieobservaties voor hetzelfde contract. Controleer die onderbouwing met exacte rekenkunde, zonder verborgen verwachte antwoorden. Houd modelgegenereerde regels, opgeslagen observaties, validatiefiltering en uitvoeringscontrole apart in logging en interpretatie. Documenteer als een gedeelde uitvoeringscontrole fouten uit ongevalideerd geheugen alsnog voorkomt; tel zulke pogingen zichtbaar mee.

## Wanneer telt iets als ervaringhergebruik?

Leg deze definitie vóór uitvoering vast. Tel **onderbouwd ervaringhergebruik** alleen als de agent binnen een eindrollout:

1. Via een gelogde geheugenoproep een concreet item met ID en inhoudshash uit het heropende geheugen ophaalt. Het item bestond vóór de eindfase en heeft herkomst naar werkelijk waargenomen leerervaring.
2. Dat item expliciet aanwijst als onderbouwing van een normalisatie voor dezelfde bron en versie, met een nieuwe invoerwaarde. Log regel, observationele onderbouwing, invoer en uitkomst; een geheugenoproep alleen telt niet als gebruik.
3. Een normalisatie uitvoert waarvan de onafhankelijke rekencontrole de onderbouwing accepteert, zonder dat verse kalibratie beschikbaar is of de helper automatisch historische informatie toevoegt.

Deze definitie beschrijft zichtbaar gedrag. Claim geen verborgen intern gebruik van geheugen. Rapporteer ophalen, poging tot gebruik, onderbouwd gebruik en correcte commit als afzonderlijke aantallen. Een geschikte herinnering gebruiken maar daarna falen kan onderbouwd gebruik opleveren zonder taaksucces; een toevallig goed gegokte commit levert geen onderbouwd hergebruik op. Rapporteer hergebruik alleen met de zes bekende-contracttaken met uitval per seed als primaire noemer: 30 kansen per conditie. Rapporteer versiegrenzen en overige taaktypen afzonderlijk.

## Informatiegrenzen en uitvoeringscontrole

Maak vóór de run een tabel van informatie die prompt, agenttools, geheugen, schrijfcontrole en grader kunnen inzien. De conditie zonder geheugen krijgt bij een eindtaak geen historische observaties, regels, trainingstranscripten of een gedeelde historische lookup. Ongevalideerd geheugen krijgt de modelvoorstellen en hun observationele herkomst; gevalideerd geheugen krijgt dezelfde kandidaten na het vooraf vastgelegde kwalificatiefilter. Log ook verworpen kandidaten en gebruik geen eindtaakuitkomsten om dat filter te veranderen.

Laat de schrijfcontrole uitsluitend controleren wat voor de huidige handeling expliciet als onderbouwing wordt aangeleverd. Bij historische onderbouwing moet het om werkelijk opgehaalde, ongewijzigde leerobservaties gaan. De controle mag geen regel selecteren, nieuwe kalibratie aanbieden, foutieve coefficients corrigeren of de grader raadplegen. Bind een geaccepteerd bewijs aan bron, versie, invoer en uitkomst; een mislukte nieuwe berekening maakt een eerder bewijs ongeldig. Log welke fouten uit ongevalideerd geheugen door deze gedeelde controle worden tegengehouden. Meet daardoor zowel geheugenbruikbaarheid als foutpogingen; een nulverschil in foutieve commits kan het effect van de controle zijn.

De proef meet het nut van externe informatie na een herstart. Zonder geheugen zijn bekende-contracttaken met uitval mogelijk niet onderbouwd oplosbaar; beschrijf dit informatieverschil expliciet. Maak van een daardoor verkregen voordeel geen claim over algemene intelligentie of gewijzigde modelgewichten. Een model dat terechte onzekerheid toont heeft ander gedrag dan een model dat zonder onderbouwing schrijft; tel die apart, ook als beide de gewenste commit niet bereiken.

## Bewijs en oplevering

Leg protocol, bronhashes, nieuwe seeds, taakverdeling en scoringsregels vast vóór de eindrun. Gebruik ontwikkelgevallen apart. Neem fouten mee in de noemer en herhaal geen onzekere modelaanroepen automatisch. Bewaar incomplete runs en hun verbruik.

Rapporteer per conditie correcte afrondingen, terechte onthoudingen, foutieve commits, ongefundeerde en geblokkeerde pogingen, de vier bovenstaande geheugenmetingen, kalibratieverzoeken, inference-aanroepen, tokens en tijd. Toon gepaarde verschillen en resultaten per seed, met aantallen en expliciete noemers per taaktype. Behandel de vijf seeds als onafhankelijke eenheden voor onzekerheidsanalyse; presenteer meerdere taken binnen dezelfde seed niet als onafhankelijke herhalingen. Noem de studie een pilot en trek bij onvoldoende precisie geen superioriteitsconclusie. De Jev-beoordeling hieronder is een ontwerpadvies en geen onderdeel van de experimentele benchmarkkosten; log die afzonderlijk.

Lever gerichte tests voor geheugenscheiding, herstart, versiegrenzen, verborgen-labelonafhankelijkheid en onderbouwde writes. Bewaar werkelijke modelrequests en outputs en bouw verificatie die die outputs offline opnieuw afspeelt zonder nieuwe modelcalls. Houd gescripte controles buiten modelscores. Werk README en onderzoeksrapport bij met resultaten, nulresultaten en beperkingen. Maak een lokaal reproduceerbaar releasepakket; publiceer niet zonder toestemming.

## Verwerkte Jev-beoordeling

Op 12 oktober 2026 beoordeelde **jev-1.13.0** de eerdere versie van deze prompt in één door de gebruiker toegestane betaalde aanvraag met drie vragen. Het oorspronkelijke verzoek, de prompt vóór wijzigingen, het volledige antwoord en de procesmetingen staan in `reviews/jev-prompt-20261012/`.

- Bouwrichting: `kalibratieuitval`, antwoordkans 1,00 en confidence 1,00.
- Eerlijkheid: score **3,96 op een semantische schaal van 0–4**; kans 0,96 voor de sterkste beschrijving en 0,04 voor de eerstvolgende. Confidence 0,97. Dit beoordeelt het beschreven ontwerp, niet de nog ongebouwde implementatie.
- Prioriteit: `operationeel_hergebruik` 0,61; `bewijsscheiding` 0,29; `steekproef` 0,07; `geen_aanscherping` 0,02; `onvoldoende_informatie` 0,01. Confidence 0,51: de prioritering is minder uitgesproken dan de gekozen bouwrichting.

Codex heeft dit advies verwerkt in de expliciete definitie van hergebruik. Daarnaast heeft Codex de informatiegrenzen en pilotomvang concreter gemaakt. Jev heeft deze nieuwe tekst niet opnieuw beoordeeld en schreef de bouwprompt niet zelf. De antwoordkansen zijn modeluitvoer, geen bewezen juistheidspercentages. Verbruik: **2.281 inputtokens en 179 outputtokens**, één provider-aanvraag, nul retries; het geldbedrag is niet bekend. Deze ontwerpbeoordeling voerde geen benchmark uit en gaf geen toestemming voor extra betaalde aanroepen. De gebruiker heeft daarna apart toestemming gegeven om deze mijlpaal lokaal te bouwen en uit te voeren; zie het bevroren protocol en de resultaten van versie 0.4.
