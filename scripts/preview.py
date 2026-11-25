"""Build the owner's single-file review preview from sibling local repositories."""
import argparse
import base64
from datetime import date
from html import escape
import hashlib
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

import markdown
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog.build import ROOT, COMMUNITY_WARNING, LABELS, STATES, badge_svg, project_medal_svg, effective_status, load_records

# Console-shell silver, forest green and blue review ink. Left-aligned reading
# layout, original mascot as the single visual focal point; no remote fonts.
STYLE = """
:root{--paper:#eef2f3;--ink:#1d3028;--green:#176d3b;--blue:#285679;--amber:#805511;--line:#cbd5d1}
*{box-sizing:border-box}html{scroll-padding-top:20px}body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.65 'Trebuchet MS','DejaVu Sans',sans-serif}a{color:var(--blue);text-underline-offset:3px}a:focus-visible,summary:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid #a54b14;outline-offset:4px}button,input{font:inherit}main{max-width:1190px;margin:auto;padding:32px 36px 70px}.notice{margin:0;padding:12px 24px;background:#dbe9e1;text-align:center;font-size:14px;border-bottom:1px solid #a6bdb0}.masthead{display:flex;justify-content:space-between;align-items:center;gap:24px;border-bottom:1px solid var(--line);padding:0 0 22px}.wordmark{font-size:25px;font-weight:700;letter-spacing:-1px}.masthead nav{display:flex;gap:22px;flex-wrap:wrap;font-size:15px}.masthead a{color:var(--ink)}.hero{display:grid;grid-template-columns:1.5fr 1fr;gap:45px;align-items:center;padding:55px 0 44px}.hero h1{font-size:clamp(38px,4.6vw,62px);line-height:1.08;letter-spacing:-2px;margin:0 0 22px;max-width:680px}.hero p{font-size:19px;max-width:620px}.hero .sub{font-size:15px;color:#42584d}.avatar{width:100%;max-width:335px;border-radius:50%;box-shadow:0 0 0 12px #d6e4dc;justify-self:center}.power{display:inline-flex;align-items:center;gap:9px;font-size:15px;font-weight:700}.power::before{content:'⏻';font-size:23px;color:var(--green)}h2{font-size:30px;line-height:1.2;letter-spacing:-.7px;margin:0 0 20px}h3{font-size:21px;line-height:1.3}section{padding:38px 0;border-top:1px solid var(--line)}.lead{max-width:760px;margin:0 0 24px}.level{display:grid;grid-template-columns:225px 1fr;gap:30px;border-top:1px solid var(--line);padding:22px 0}.level h3{margin:0}.level p{margin:0 0 9px;max-width:740px}.level small{font-size:14px}.level .mark{display:inline-block;border-left:5px solid var(--green);padding:6px 0 6px 15px}.level.reviewed .mark{border-color:var(--blue)}.level.community .mark{border-color:#69746f}.warning{background:#f8edd7;border-left:5px solid var(--amber);padding:14px 18px;overflow-wrap:anywhere}.catalog-group{margin:30px 0}.app{display:grid;grid-template-columns:1fr 1.1fr;gap:25px;padding:24px 0;border-top:1px solid var(--line);align-items:center}.app h3{margin:0 0 9px}.app p{font-size:15px;margin:6px 0}.app svg{max-width:100%;height:auto}.status{font-size:14px;font-weight:700}.sample{color:#765011}.quick{display:grid;grid-template-columns:repeat(3,1fr);gap:30px;margin:24px 0}.quick p{font-size:15px;margin:8px 0}.quick b{display:block;font-size:24px}.doc-index{columns:3;column-gap:25px;padding:0;list-style:none;font-size:14px}.doc-index li{break-inside:avoid;padding:4px 0}.doc-filter{display:flex;gap:15px;align-items:center;margin-bottom:20px}.doc-filter input{border:1px solid #82988a;border-radius:5px;background:white;padding:8px 12px;width:min(440px,100%)}.doc-filter button{background:#fff;border:1px solid #82988a;border-radius:5px;padding:8px 12px;cursor:pointer}.document{border:1px solid var(--line);background:white;border-radius:8px;margin:12px 0;scroll-margin-top:20px}.document summary{padding:16px 20px;cursor:pointer;font-size:16px;font-weight:700;overflow-wrap:anywhere}.document[open]>summary{border-bottom:1px solid var(--line)}.prose{padding:12px 28px 28px;font-family:'DejaVu Sans',sans-serif;font-size:15px;overflow-wrap:anywhere}.prose>p,.prose>ul,.prose>ol{max-width:82ch}.prose h1{font-size:30px;line-height:1.2}.prose h2{font-size:24px;margin-top:30px}.prose h3{font-size:20px}.prose svg,.prose img{max-width:100%;height:auto}.prose pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf2f0;padding:18px;border-radius:5px;font-size:13px;line-height:1.6}.prose code{font-size:.9em}.prose table{border-collapse:collapse;display:block;overflow:auto;max-width:100%;font-size:13px}.prose th,.prose td{padding:10px;border:1px solid var(--line);text-align:left;min-width:110px;vertical-align:top}.prose blockquote{border-left:4px solid var(--amber);padding:4px 20px;background:#fff7e6;margin:18px 0}.prose a{overflow-wrap:anywhere}footer{font-size:14px;padding:24px 0 0}.hidden{display:none}.print-note{font-size:14px;color:#42584d}
@media screen and (max-width:760px){main{padding:22px 19px 40px}.masthead{align-items:flex-start;flex-direction:column;gap:10px}.masthead nav{gap:16px}.hero{grid-template-columns:1fr;padding:32px 0;gap:25px}.hero h1{letter-spacing:-1px}.avatar{max-width:230px;grid-row:2}.level,.app{grid-template-columns:1fr;gap:15px}.quick{grid-template-columns:1fr;gap:4px}.doc-index{columns:1}.doc-filter{flex-wrap:wrap}.prose{padding:8px 17px 22px}.notice{text-align:left;padding:12px 19px}}
@media print{body{background:#fff;font-size:11pt}main{max-width:none;padding:0}.masthead nav,.doc-filter,.doc-index{display:none}.hero{padding:20px 0;grid-template-columns:2fr 1fr}.hero h1{font-size:30pt}.avatar{max-width:160px}.document{break-inside:auto;border:0}.document>summary{font-size:15pt;padding:15px 0}.prose{padding:0}.prose table{display:table;table-layout:fixed;width:100%;overflow:visible}.prose th,.prose td{min-width:0;white-space:normal;overflow-wrap:anywhere;padding:5px}.hidden{display:block}.document::details-content{content-visibility:visible}h1,h2,h3{break-after:avoid}svg,img{break-inside:avoid}a{color:#164e34}.notice{background:white;color:#1d3028}section{padding:22px 0}}
"""

SCRIPT = """
const docs=[...document.querySelectorAll('details.document')];
document.getElementById('filter').addEventListener('input',e=>{const q=e.target.value.toLocaleLowerCase();docs.forEach(d=>d.classList.toggle('hidden',!d.dataset.label.includes(q)));});
document.getElementById('expand').addEventListener('click',()=>{const expand=docs.some(d=>!d.open);docs.forEach(d=>d.open=expand);document.getElementById('expand').textContent=expand?'Recolher documentos':'Abrir documentos';});
function revealHash(){const el=document.getElementById(decodeURIComponent(location.hash.slice(1)));if(el){const parent=el.closest('details');if(parent){parent.open=true;parent.classList.remove('hidden');}el.scrollIntoView();}}
addEventListener('hashchange',revealHash);if(location.hash)revealHash();
let printState=[];addEventListener('beforeprint',()=>{printState=docs.map(d=>d.open);docs.forEach(d=>d.open=true)});addEventListener('afterprint',()=>docs.forEach((d,i)=>d.open=printState[i]));
"""

# Let the neon Project medal carry the visual emphasis; other levels stay quiet.
STYLE += """
.badge-showcase{display:grid;grid-template-columns:340px 1fr;gap:38px;align-items:start}.medal-demo{margin:0;padding:22px;background:#14200f;border:3px solid #080c07;border-radius:25px;color:#e5f4de;text-align:center}.medal-demo svg{display:block;width:100%;height:auto}.medal-demo a{color:#c2ff8a}.medal-demo figcaption{font-size:15px}.badge-samples{display:grid;gap:16px}.badge-sample{display:grid;grid-template-columns:minmax(0,315px) 1fr;align-items:center;gap:15px;padding:12px 0;border-bottom:1px solid var(--line)}.badge-sample p{margin:0;font-size:14px}.badge-sample svg{display:block;max-width:100%;height:auto}.demo-tag{display:inline-block;margin:6px 0;font-size:12px;font-weight:700;color:#65440c;background:#fff0bf;padding:2px 8px;border-radius:4px}
@media screen and (max-width:760px){.badge-showcase{grid-template-columns:1fr;gap:25px}.medal-demo{max-width:340px}.badge-samples{gap:10px}.badge-sample{grid-template-columns:1fr;gap:9px}}@media print{.badge-showcase{grid-template-columns:230px 1fr}}
"""


def namespace_svg(svg: str, prefix: str) -> str:
    ids = re.findall(r'\bid="([^"]+)"', svg)
    for original in ids:
        svg = svg.replace(f'id="{original}"', f'id="{prefix}-{original}"').replace(f'url(#{original})', f'url(#{prefix}-{original})')
    return svg


def document_id(path: Path, workspace: Path) -> str:
    return 'doc-' + hashlib.sha256(str(path.relative_to(workspace)).encode()).hexdigest()[:16]


def gather(workspace: Path) -> list[Path]:
    result = []
    for repo in ('.github', 'devkit', 'catalog'):
        root = workspace / repo
        for path in root.rglob('*.md'):
            relative = path.relative_to(root)
            if any(part in ('.git', '.deps', '.venv', '.work', 'build', 'dist', '__pycache__') for part in relative.parts):
                continue
            result.append(path.resolve())
    result.extend(path.resolve() for path in (workspace / '.github/.github/ISSUE_TEMPLATE').glob('*.yml'))
    return sorted(result, key=lambda p: str(p.relative_to(workspace)))


def render_document(path: Path, ids: dict[Path, str]) -> str:
    if path.suffix == '.yml':
        form = yaml.safe_load(path.read_text())
        chunks = [f'<h1>{escape(form.get("name", "Onde trocar ideia"))}</h1>',
                  f'<p>{escape(form.get("description", "Cola no canal certo e traz o que precisa."))}</p>']
        for field in form.get('body', []):
            attributes = field['attributes']
            if field['type'] == 'markdown':
                chunks.append(f'<p>{escape(attributes["value"])}</p>')
                continue
            chunks.append(f'<h3>{escape(attributes["label"])}</h3>')
            if attributes.get('description'):
                chunks.append(f'<p>{escape(attributes["description"])}</p>')
            for option in attributes.get('options', []):
                label = option['label'] if isinstance(option, dict) else option
                chunks.append(f'<p>• {escape(label)}</p>')
            if field.get('validations', {}).get('required'):
                chunks.append('<small>Campo obrigatório</small>')
        for contact in form.get('contact_links', []):
            chunks.append(f'<h3><a href="{escape(contact["url"], quote=True)}">{escape(contact["name"])}</a></h3><p>{escape(contact["about"])}</p>')
        return ''.join(chunks)
    body = markdown.markdown(path.read_text(), extensions=['fenced_code', 'tables'])
    def local_link(match):
        raw = match.group(1)
        if urlsplit(raw).scheme or raw.startswith('#'):
            return match.group(0)
        target = (path.parent / unquote(raw.split('#')[0])).resolve()
        if target in ids:
            return f'href="#{ids[target]}"'
        # Sources not embedded (code, schema) remain explicit repo links.
        for repo in ('.github', 'devkit', 'catalog'):
            root = ROOT.parent / repo
            if target.is_relative_to(root):
                rel = target.relative_to(root).as_posix()
                return f'href="https://github.com/revive360/{repo}/blob/main/{escape(rel,quote=True)}"'
        return match.group(0)
    body = re.sub(r'href="([^"]+)"', local_link, body)
    def local_image(match):
        src = match.group(1)
        if urlsplit(src).scheme:
            return match.group(0)
        target = (path.parent / unquote(src)).resolve()
        if target.is_file() and target.is_relative_to(ROOT):
            if target.suffix == '.svg':
                return target.read_text()
            encoded = base64.b64encode(target.read_bytes()).decode()
            return f'<img alt="Revive360" src="data:image/jpeg;base64,{encoded}">'
        return match.group(0)
    body = re.sub(r'<img[^>]*src="([^"]+)"[^>]*>', local_image, body)
    # Each embedded record has distinct clip IDs across gallery/cards/documents.
    body = namespace_svg(body, ids[path])
    return body


def generate(output: Path, today: date) -> int:
    workspace = ROOT.parent.resolve()
    records = load_records(ROOT / 'data/apps', today)
    documents = gather(workspace)
    ids = {p: document_id(p, workspace) for p in documents}
    avatar = base64.b64encode((ROOT / 'assets/mascot.jpg').read_bytes()).decode()
    html = ['<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Revive360 · prévia R2</title><style>' + STYLE + '</style></head><body>',
            '<p class="notice">Prévia local R2 · 25 de novembro de 2026 · Nenhuma publicação ou configuração do GitHub foi executada.</p><main>',
            '<header class="masthead"><div class="wordmark">Revive360</div><nav aria-label="Seções"><a href="#niveis">Três níveis</a><a href="#selos">Selos</a><a href="#catalogo">Catálogo</a><a href="#perfil">Perfil</a><a href="#documentos">Documentos</a></nav></header>',
            '<div class="hero"><div><span class="power">Código aberto. Feito pra rodar.</span><h1>O 360 tá vivo.<br>Cola pra construir.</h1><p>App pro 360, fonte na mesa e teste no console. Chega com uma ideia que soma, traz o código e responde por ele. Lê as onze regras da casa.</p><p class="sub">Organização: <a href="https://github.com/revive360">github.com/revive360</a><br>Fundador e único dono hoje: Pedro.</p></div>',
            f'<img class="avatar" src="data:image/jpeg;base64,{avatar}" alt="Mascote original Revive360, um console com controle e uma xícara"></div>',
            '<section id="niveis"><h2>Escolhe o caminho. Assume a responsa.</h2><p class="lead">A ficha no catálogo é a fonte da verdade. Ser membro não é selo. Uma imagem copiada não substitui a conferência do link, da versão e do hash.</p>',
            '<div class="level"><h3><span class="mark">Revive360 Project</span></h3><div><p>Repo dentro da org, com nossas regras de segurança, PR revisado e release construída no CI com hash e assinatura/atestação. Validade contínua enquanto cumprir as regras.</p><small>Selo verde com mascote. O nível mais forte.</small></div></div>',
            '<div class="level reviewed"><h3><span class="mark">Reviewed · vX.Y.Z</span></h3><div><p>Repo fica com o autor. A revisão cobre só a versão e o hash na data registrada. O autor compila; a org confere o binário e o vínculo ao fonte. Não há canal de atualização da org.</p><p>Versão nova volta à fila manual. Até o aceite: <strong>versão atual não revisada</strong>. Se o autor sumir, o selo expira.</p><small>Prioridade menor e mais trabalho manual; o caminho Project é o preferencial.</small></div></div>',
            '<div class="level community"><h3><span class="mark">Community list</span></h3><div><p>Descoberta para manter a comunidade viva. Sem selo; pode sair a qualquer momento.</p><p class="warning">Não verificado pela Revive360, não é recomendação, use por sua conta e risco.</p></div></div>',
            '<div class="quick"><div><b>48 horas</b><p>Resposta a segurança em qualquer nível. Revogação imediata se grave.</p></div><div><b>CI automático</b><p>Release Project após revisão e teste do binário exato em console real.</p></div><div><b>14 dias</b><p>Alvo da fila externa, por chegada. Community entra quando der.</p></div></div>',
            '<p>Revisão não é auditoria completa nem garantia. Software fornecido como está, pela licença. Ninguém revisa o próprio app, exceto o fundador Pedro, inclusive no nível máximo, com a exceção registrada.</p></section>',
            '<section id="selos"><h2>O selo chama. A ficha responde.</h2><p class="lead">Project ganha a medalha com o mascote e verde neon. Os demais ficam no selo de linha. Cada estado tem sua palavra, seu ícone vetorial e sua cor: Official verde neon, Reviewed azul-petróleo, Outdated âmbar, Expired cinza e Revoked vermelho. Official identifica o nível máximo Project, com validade contínua enquanto cumprir as regras. A ficha registra o escopo completo.</p><p><span class="demo-tag">Demo only · exemplos locais</span> Esta indicação fica na prévia, fora das imagens de README.</p><div class="badge-showcase">']
    project = next(r for r in records if r['tier'] == 'project')
    project_target = ids[(ROOT / 'generated/apps' / (project['id']+'.md')).resolve()]
    medal_svg = namespace_svg(project_medal_svg(project,today), 'showcase')
    medal_png = base64.b64encode((ROOT/'generated/badges'/f'{project["id"]}-medal.png').read_bytes()).decode()
    html += [f'<figure class="medal-demo"><a href="#{project_target}">{medal_svg}</a><figcaption>Medalha exclusiva Project<br><a download="{project["id"]}-medal.png" href="data:image/png;base64,{medal_png}">Baixar PNG</a> · <a href="#{project_target}">Markdown de uso</a></figcaption></figure><div class="badge-samples">']
    by_id = {r['id']:r for r in records}
    for slug,label in [('tube360','Project oficial: nível máximo, validade contínua'),('sample-reviewed','Versão revisada: vale para a versão e o hash registrados'),('sample-unreviewed','Versão atual não revisada: v1.2.3 é a versão antes revisada'),('sample-expired','Expirado: o prazo de confirmação do autor terminou'),('sample-revoked','Revogado: a revisão foi retirada; confira a ficha')]:
        r=by_id[slug]; target=ids[(ROOT/'generated/apps'/f'{slug}.md').resolve()]
        html += [f'<div class="badge-sample"><a href="#{target}" aria-label="Conferir {escape(label,quote=True)}">{namespace_svg(badge_svg(r,today),"showcase")}</a><p>{label}</p></div>']
    html += ['</div></div></section><section id="catalogo"><h2>Puxa a ficha antes de rodar.</h2><p class="warning"><strong>Todos os registros abaixo são demonstrações.</strong> Tube360 continua na conta do autor. Seu exemplo Project mostra um futuro repo na org; não afirma transferência, teste físico ou revisão concluída. Os outros apps e as evidências são fictícios.</p>']
    for tier in ('project', 'reviewed', 'community'):
        html += [f'<div class="catalog-group"><h3>{LABELS[tier]}</h3>']
        for r in records:
            if r['tier'] != tier:
                continue
            target = ids[(ROOT / 'generated/apps' / (r['id'] + '.md')).resolve()]
            badge = badge_svg(r, today) or '<p class="warning">Não verificado pela Revive360, não é recomendação, use por sua conta e risco.</p>'
            badge = namespace_svg(badge, 'card')
            html += [f'<article class="app"><div><h3><a href="#{target}">{escape(r["name"])}</a></h3><p>{escape(r["summary"])}</p><p class="status">{STATES[effective_status(r,today)]} <span class="sample">· Exemplo</span></p><p><a href="#{target}">Conferir ficha, hash e escopo</a></p></div><a href="#{target}" aria-label="Conferir ficha de {escape(r["name"],quote=True)}">{badge}</a></article>']
        html += ['</div>']
    html += ['</section><section id="perfil"><h2>A cara da casa, nos três idiomas</h2><p class="lead">Inglês, português e espanhol. Escolhe o teu. Mesma casa, onze regras; critérios, prazos e responsabilidade continuam explícitos.</p>']
    profiles = []
    for file, language in [('README.md', 'English'), ('README.pt-BR.md', 'Português'), ('README.es.md', 'Español')]:
        path = (workspace / '.github/profile' / file).resolve(); profiles.append(path)
        html += [f'<details class="document" data-label="perfil {language.lower()}" id="{ids[path]}"'+ (' open' if language == 'English' else '') + f'><summary>Perfil · {language}</summary><div class="prose">{render_document(path,ids)}</div></details>']
    html += ['</section><section id="documentos"><h2>O combinado tá aqui.</h2>',
             f'<p class="lead">{len(documents)} documentos embutidos de .github, devkit e catalog. Os links internos abrem o documento correspondente; código e fontes externos continuam como links explícitos ao GitHub.</p>',
             '<div class="doc-filter"><label for="filter">Filtrar título</label><input id="filter" type="search" placeholder="Ex.: SETUP, governança, console"><button id="expand" type="button">Abrir documentos</button></div>', '<ul class="doc-index">']
    for path in documents:
        if path not in profiles:
            label = str(path.relative_to(workspace))
            html += [f'<li><a href="#{ids[path]}">{escape(label)}</a></li>']
    html += ['</ul>']
    for path in documents:
        if path in profiles:
            continue
        label = str(path.relative_to(workspace))
        html += [f'<details class="document" data-label="{escape(label.lower(),quote=True)}" id="{ids[path]}"><summary>{escape(label)}</summary><div class="prose">{render_document(path,ids)}</div></details>']
    html += ['</section><footer><p><strong>Risco ao usuário:</strong> homebrew pode causar banimento no Xbox Live, perda de dados ou dano ao console. Nada de coleta sem opt-in; login e tokens ficam no console. Nenhum bypass de DRM/paywall. Risco dos termos de terceiros é do autor.</p><p>A org não recebe nem divide doações. Até dezembro, segurança por private vulnerability reporting; comunidade em <a href="https://github.com/orgs/revive360/discussions">Discussions oficiais</a>. <code>CONTACT_DECEMBER_2026_TODO</code>.</p><p>Créditos: xenosworks (xsdk, vulkan4xenon, SDL-xenon), Free60/libxenon. Xbox e Xbox 360 são marcas da Microsoft. Revive360 é independente, sem endosso da Microsoft ou Google.</p><p class="print-note">Abre sem internet. Pra imprimir, o arquivo abre os documentos e leva o conteúdo junto.</p></footer></main><script>' + SCRIPT + '</script></body></html>']
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(''.join(html))
    return len(documents)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--as-of', type=date.fromisoformat, default=date(2026, 11, 25))
    args = parser.parse_args()
    print(f'Embedded {generate(args.output,args.as_of)} documents in {args.output}')
