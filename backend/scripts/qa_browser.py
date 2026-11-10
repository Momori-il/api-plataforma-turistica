"""Playwright + axe WCAG 2.1 AA audit of real local integration pages."""
import argparse
import json
from pathlib import Path
import time
import requests
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]

def run():
    parser=argparse.ArgumentParser();parser.add_argument('--real',action='store_true');args=parser.parse_args()
    if not args.real:parser.error('--real required: local Docker integration only')
    state_path=ROOT/'backend/.demo/macro4-run.json'
    state=json.loads(state_path.read_text(encoding='utf-8'));f=state['fixture']
    api=requests.Session();api.trust_env=False
    sessions={}
    for role,user in f['users'].items():
        response=api.post('http://127.0.0.1:8000/auth/login',json={'email':user['email'],'password':state['password']},timeout=15)
        assert response.status_code==200,(role,response.status_code)
        sessions[role]={**user,'modo':'api','accessToken':response.json()['access_token']}
    state['sessions']=sessions;state_path.write_text(json.dumps(state),encoding='utf-8')
    paths={
      'PUBLIC':['index.html',f"hotel.html?id={f['hotel']}",'actividades.html',f"actividad.html?id={f['activity']}",'ofertas.html','login.html','registro-usuario.html','recuperar-password.html'],
      'TURISTA':['perfil.html','mis-reservas.html','checkout.html','confirmacion.html','reserva-detalle.html'],
      'PRESTADOR':['prestador.html','prestador-hoteles.html',f"prestador-habitaciones.html?hotelId={f['hotel']}",'prestador-actividades.html',f"prestador-turnos.html?actividadId={f['activity']}",'prestador-reservas.html','registro-hotel.html'],
      'ADMIN':['admin.html','admin-usuarios.html','admin-hoteles.html','admin-actividades.html','admin-reservas.html']}
    result={'engine':'Chromium/Playwright','axe_version':None,'wcag':['wcag2a','wcag2aa','wcag21a','wcag21aa'],
            'scans':[],'responsive':[],'keyboard':[],'page_errors':[],'console_errors':[]}
    axe=ROOT/'backend/.demo/qa-node/node_modules/axe-core/axe.min.js'
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        result['browser_version']=browser.version
        for role,pages in paths.items():
            context=browser.new_context(viewport={'width':1440,'height':1000},locale='es-AR',timezone_id='America/Argentina/Buenos_Aires')
            if role!='PUBLIC':
                context.add_init_script('localStorage.setItem("posadasTurismoSesionDemo",'+json.dumps(json.dumps(sessions[role]))+');')
            page=context.new_page()
            page.on('pageerror',lambda error:result['page_errors'].append(str(error)))
            page.on('console',lambda msg:result['console_errors'].append(msg.text[:250]) if msg.type=='error' else None)
            for path in pages:
                page.goto('http://127.0.0.1:5500/frontend/'+path,wait_until='networkidle',timeout=30000)
                page.wait_for_timeout(200)
                page.add_script_tag(path=str(axe))
                audit=page.evaluate("async () => {const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}}); return {version:axe.version,violations:r.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>({target:n.target,html:n.html,summary:n.failureSummary,checks:n.any.map(c=>({id:c.id,data:c.data}))}))})),passes:r.passes.length,incomplete:r.incomplete.length};}")
                result['axe_version']=audit.pop('version')
                result['scans'].append({'role':role,'page':path,**audit})
                for width in [1440,1366,1024,768,390]:
                    page.set_viewport_size({'width':width,'height':1000});page.wait_for_timeout(50)
                    dimensions=page.evaluate('({viewport:innerWidth,document:document.documentElement.scrollWidth})')
                    result['responsive'].append({'role':role,'page':path,'width':width,'overflow':dimensions['document']>width+1,'document_width':dimensions['document']})
                page.set_viewport_size({'width':1440,'height':1000})
                page.evaluate('document.activeElement?.blur()')
                page.keyboard.press('Tab')
                focus=page.evaluate("() => {const e=document.activeElement,s=getComputedStyle(e);return {tag:e.tagName,visible:!!e.getClientRects().length,outline:s.outlineStyle,outlineWidth:s.outlineWidth,boxShadow:s.boxShadow}}")
                result['keyboard'].append({'page':path,**focus})
                print(role+' '+path+' violations='+str(len(audit['violations'])),flush=True)
            context.close()
        browser.close()
    target=ROOT/'docs/evidence/accessibility/browser.json';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'pages':len(result['scans']),'violations':sum(len(x['violations']) for x in result['scans']),
                      'overflow':sum(x['overflow'] for x in result['responsive']),'page_errors':len(result['page_errors'])}))

if __name__=='__main__':run()
