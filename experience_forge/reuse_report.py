"""Standalone local viewer for the captured outage pilot."""
from html import escape
import json


def render_reuse(report):
    labels = {'no_memory': 'Geen geheugen', 'unvalidated_memory': 'Ongevalideerd', 'validated_memory': 'Gevalideerd'}
    cells = report['results']['variants']
    rows = ''.join(f'<tr><th>{labels[v]}</th><td>{c["successful"]}/{c["total"]}</td>'
        f'<td>{c["primary_retrieved_any"]}/{c["primary_reuse_denominator"]}</td>'
        f'<td>{c["primary_attempted_reuse"]}/{c["primary_reuse_denominator"]}</td>'
        f'<td>{c["primary_reused_any"]}/{c["primary_reuse_denominator"]}</td>'
        f'<td>{c["primary_correct_reuse_commit"]}/{c["primary_reuse_denominator"]}</td>'
        f'<td>{c["wrong_write_commits"]}</td><td>{c["blocked_writes"]}</td></tr>' for v, c in cells.items())
    categories = ''.join(f'<tr><th>{escape(category)}</th>' + ''.join(f'<td>{c["by_category"][category]["successful"]}/{c["by_category"][category]["total"]}</td>' for c in cells.values()) + '</tr>' for category in next(iter(cells.values()))['by_category'])
    seeds = ''.join(f'<tr><th>{entry["seed"]}</th>' + ''.join(f'<td>{c["per_seed"][i]["successful"]}/{c["per_seed"][i]["total"]} · hergebruik {c["per_seed"][i]["primary_reuse"]}/{c["per_seed"][i]["primary_denominator"]}</td>' for c in cells.values()) + '</tr>' for i, entry in enumerate(next(iter(cells.values()))['per_seed']))
    costs = ''.join(f'<tr><th>{labels[v]}</th><td>{c["model_calls"]}</td><td>{c["input_tokens"]:,}</td><td>{c["output_tokens"]:,}</td><td>{c["calibration_reads"]}</td><td>{c["wall_seconds"]:.2f}s</td></tr>' for v, c in cells.items())
    limits = ''.join('<li>' + escape(line) + '</li>' for line in report['limitations'])
    return f'''<!doctype html><html lang="nl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Experience Forge · ervaring hergebruiken</title>
<style>body{{margin:0;background:#10151d;color:#eaf0f7;font:16px/1.6 system-ui}}main{{max-width:1150px;margin:auto;padding:32px 20px}}h1{{font-size:clamp(28px,5vw,44px)}}.card{{background:#1b2330;border:1px solid #354254;border-radius:14px;padding:20px;margin:20px 0}}.scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse;white-space:nowrap}}th,td{{text-align:left;border-bottom:1px solid #354254;padding:12px}}th{{color:#81dfc2}}small{{color:#bcc9d8}}summary{{cursor:pointer;color:#81dfc2}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}a{{color:#81dfc2}}</style>
<main><small>Experience Forge 0.4 · lokale echte agent · bevroren pilot</small><h1>Ervaring gebruiken wanneer kalibratie ontbreekt</h1>
<p>Een zichtbaar opgehaalde herinnering is pas hergebruikt als de agent haar regel met passende observaties toepast op een nieuwe invoer. Een correcte commit wordt apart geteld.</p>
<div class="card scroll"><table><thead><tr><th>Geheugen</th><th>Alle taken</th><th>Opgehaald</th><th>Gebruik geprobeerd</th><th>Onderbouwd gebruikt</th><th>Correct opgeslagen</th><th>Foute commits</th><th>Geblokkeerd</th></tr></thead><tbody>{rows}</tbody></table><small>De vier geheugenkolommen gebruiken uitsluitend bekende contracten met uitval als noemer. Fouten en blokkades tellen alle taken.</small></div>
<div class="card scroll"><table><thead><tr><th>Taaktype</th><th>Geen geheugen</th><th>Ongevalideerd</th><th>Gevalideerd</th></tr></thead><tbody>{categories}</tbody></table></div>
<details class="card" open><summary>Resultaten per onafhankelijke seed</summary><div class="scroll"><table><thead><tr><th>Seed</th><th>Geen geheugen</th><th>Ongevalideerd</th><th>Gevalideerd</th></tr></thead><tbody>{seeds}</tbody></table></div><pre>{escape(json.dumps(report['results']['paired_vs_no_memory'], indent=2))}</pre></details>
<details class="card"><summary>Werkelijk verbruik</summary><div class="scroll"><table><thead><tr><th>Geheugen</th><th>Modelcalls</th><th>Inputtokens</th><th>Outputtokens</th><th>Kalibratieverzoeken</th><th>Tijd</th></tr></thead><tbody>{costs}</tbody></table></div><p>Gemeenschappelijk leren: {report['shared_learning']['model_calls']} modelcalls, {report['shared_learning']['input_tokens']} inputtokens, {report['shared_learning']['output_tokens']} outputtokens. Fysiek eenmaal verzameld, gelijk toegerekend aan elke conditie.</p><p>Fysiek totaal: {report['total_actual_model_calls']} lokale modelcalls. Betaalde API-aanroepen in deze benchmark: {report['paid_api_calls']}.</p></details>
<details class="card" open><summary>Wat deze proef wel en niet aantoont</summary><ul>{limits}</ul></details>
<footer><small>Model: {escape(report['runtime']['model']['name'])} · digest {escape(report['runtime']['model']['digest'])}<br>Ruwe bewijzen: <a href="report.json">report.json</a>, <a href="protocol.json">protocol.json</a>, <a href="rollouts.jsonl">rollouts.jsonl</a>. Verificatie gebruikt opgeslagen antwoorden en doet geen nieuwe modelcalls.</small></footer></main></html>'''
