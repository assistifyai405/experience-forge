# Bouwprompt: ervaring hergebruiken zonder nieuwe kalibratie

Bouw de volgende mijlpaal voor Experience Forge in `<checkout>`. Werk zelfstandig aan lokale, omkeerbare wijzigingen. Overleg vóór betaalde API-aanroepen, installaties of publicatie. Bewaar bestaande bronversies, ruwe resultaten en onderbroken runs.

## Aanleiding

Lees `docs/EXECUTION-PROTOCOL.md` en `docs/EXECUTION-RESULTS.md`. In versie 0.3 haalden alle zes condities 45/45 correcte afrondingen. De echte lokale agent gebruikte in alle eindtaken de kalibratiehelper. Er is daarom geen aangetoond geheugenvoordeel. Ontwerp een nieuwe proef die meet of opgeslagen ervaring bruikbaar blijft wanneer verse kalibratie ontbreekt. Een positief resultaat is niet vereist.

## Experiment

Gebruik één echte agent en dezelfde familie van synthetische connectorconversies. Controleer opnieuw welke lokale modelruntime beschikbaar is; download niets. Vergelijk geen geheugen, ongevalideerd modelgegenereerd geheugen en onafhankelijk gevalideerd modelgegenereerd geheugen. Alle condities krijgen identieke trainingservaring, modelinstellingen, tools, volgordeprocedures en budgetten. Alleen toegang tot opgeslagen geheugen en het afgesproken validatiefilter verschillen.

Laat de agent tijdens de leerfase beschikbare kalibratie waarnemen en zelf kandidaatregels voorstellen. Gebruik aparte kwalificatievoorbeelden voor validatie. Wis vóór iedere eindtaak gesprekshistorie, procescontext en werkomgeving; open alleen het geheugen van de betreffende conditie opnieuw. Voorkom dat trainingstranscripten of caches impliciet geheugen aan de controleconditie geven.

Gebruik vooraf vastgelegde eindtaken met nieuwe invoerwaarden:

- Een eerder gezien bron- en versiecontract waarvan de kalibratieservice nu onbereikbaar is: een passende bewaarde regel kan helpen.
- Een gewijzigde of onbekende versie: een oude regel biedt geen geldige onderbouwing; onthouding is vereist zolang nieuwe kalibratie ontbreekt.
- Ontbrekende invoer en tegenstrijdige eerdere observaties: schrijf geen ongefundeerde waarde.
- Een afzonderlijke controle met beschikbare kalibratie, om gewone uitvoering te controleren.

Bron- en versie-identiteiten zijn zichtbaar en betekenisvol. Taaknamen mogen geen juiste actie of categorie verraden. Geheugen bevat alleen waarneembare ervaringen, regelvoorstellen en hun herkomst. Geen eindlabels, trainingsdatasetgenerator, verborgen coefficients of graderinformatie in prompts, tools of uitvoeringcontroles.

Gebruik dezelfde schrijfcontrole in alle drie condities. Een schrijfonderbouwing mag teruggrijpen op werkelijk opgeslagen kalibratieobservaties voor hetzelfde contract. Controleer die onderbouwing met exacte rekenkunde, zonder verborgen verwachte antwoorden. Houd modelgegenereerde regels, opgeslagen observaties, validatiefiltering en uitvoeringscontrole apart in logging en interpretatie. Documenteer als een gedeelde uitvoeringscontrole fouten uit ongevalideerd geheugen alsnog voorkomt; tel zulke pogingen zichtbaar mee.

## Bewijs en oplevering

Leg protocol, bronhashes, nieuwe seeds, taakverdeling en scoringsregels vast vóór de eindrun. Gebruik ontwikkelgevallen apart. Neem fouten mee in de noemer en herhaal geen onzekere modelaanroepen automatisch. Bewaar incomplete runs en hun verbruik.

Rapporteer per conditie correcte afrondingen, terechte onthoudingen, foutieve commits, ongefundeerde en geblokkeerde pogingen, geheugenhergebruik, kalibratieverzoeken, inference-aanroepen, tokens en tijd. Toon gepaarde verschillen en resultaten per seed. Kies omvang vooraf en noem de studie een pilot als ze geen stevige statistische conclusie toelaat.

Lever gerichte tests voor geheugenscheiding, herstart, versiegrenzen, verborgen-labelonafhankelijkheid en onderbouwde writes. Bewaar werkelijke modelrequests en outputs en bouw verificatie die die outputs offline opnieuw afspeelt zonder nieuwe modelcalls. Houd gescripte controles buiten modelscores. Werk README en onderzoeksrapport bij met resultaten, nulresultaten en beperkingen. Maak een lokaal reproduceerbaar releasepakket; publiceer niet zonder toestemming.

## Voorgestelde Jev-beoordeling

Dit document is door Codex opgesteld en nog niet door Jev beoordeeld. Stuur bij toestemming uitsluitend deze prompt en de hierboven beschreven 0.3-uitkomst als context. Vraag een getypeerde beoordeling of de proef ervaringhergebruik eerlijk isoleert, en of verborgen antwoorden of uitvoeringscontrole het geheugenvoordeel kunnen vertekenen. Geef expliciet een keuze voor onvoldoende informatie. Jevs oordeel is advies, geen experimentresultaat of toestemming.
