"""Exercise actual browser booking/payment/cancellation; only tagged QA resources."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--real',action='store_true');args=parser.parse_args()
    if not args.real:parser.error('--real required')
    state=json.loads((ROOT/'backend/.demo/macro4-run.json').read_text(encoding='utf-8'));f=state['fixture']
    report={'flows':[],'http_errors':[],'page_errors':[],'accessibility':[]}
    with sync_playwright() as p:
        browser=p.chromium.launch();context=browser.new_context(viewport={'width':1440,'height':1000},timezone_id='America/Argentina/Buenos_Aires',locale='es-AR')
        page=context.new_page()
        page.on('pageerror',lambda e:report['page_errors'].append(str(e)))
        page.on('response',lambda r:report['http_errors'].append({'path':urlparse(r.url).path,'status':r.status}) if urlparse(r.url).hostname=='127.0.0.1' and r.status>=400 else None)
        base='http://127.0.0.1:5500/frontend/'
        page.goto(base+'login.html',wait_until='networkidle')
        page.locator('#login-email').fill(f['users']['TURISTA']['email']);page.locator('#login-password').fill(state['password'])
        page.locator('button[type=submit]').click();page.wait_for_url('**/index.html',timeout=30000)
        def audit(label):
            page.add_script_tag(path=str(ROOT/'backend/.demo/qa-node/node_modules/axe-core/axe.min.js'))
            for width in [1440,1366,1024,768,390]:
                page.set_viewport_size({'width':width,'height':1000})
                result=page.evaluate("async () => { const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}});return {violations:r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),overflow:document.documentElement.scrollWidth>innerWidth+1};}")
                report['accessibility'].append({'state':label,'width':width,**result})
            page.set_viewport_size({'width':1440,'height':1000})
        for kind in ['hotel','actividad']:
            if kind=='hotel':
                page.goto(base+f"hotel.html?id={f['hotel']}",wait_until='networkidle')
                page.locator('#reserva-checkin').fill(f['fecha_desde']);page.locator('#reserva-checkout').fill(f['fecha_hasta'])
                page.locator('#btn-comprobar-disponibilidad').click()
                page.locator(f'input[name="habitacion-tipo"][value="{f["room"]}"]').check()
                page.locator('#btn-reservar-estadia').click()
            else:
                page.goto(base+f"actividad.html?id={f['activity']}",wait_until='networkidle')
                page.locator(f'input[name="turno"][value="{f["turn"]}"]').check()
                page.locator('#actividad-reservar').click()
            page.wait_for_url('**/checkout.html?**',timeout=30000)
            page.locator('#checkout-submit').wait_for(state='visible')
            audit(kind+'_checkout')
            page.locator('input[name="metodo"][value="transferencia"]').check()
            page.locator('#checkout-submit').click()
            page.wait_for_url('**/confirmacion.html?**',timeout=30000)
            page.locator('#confirmation-title').wait_for(state='visible')
            rid=parse_qs(urlparse(page.url).query)['reservaId'][0]
            audit(kind+'_confirmation')
            page.goto(base+'reserva-detalle.html?id='+rid,wait_until='networkidle')
            audit(kind+'_detail')
            page.goto(base+'mis-reservas.html',wait_until='networkidle')
            page.locator(f'[data-cancelar="{rid}"]').click()
            assert page.locator('#reservas-conservar').evaluate('(e)=>e===document.activeElement')
            page.keyboard.press('Escape');assert not page.locator('#reservas-cancel-dialog').is_visible()
            page.locator(f'[data-cancelar="{rid}"]').click();page.locator('#reservas-confirmar-cancelacion').click()
            page.locator('#reservas-cancel-dialog').wait_for(state='hidden')
            assert 'cancelada' in page.locator('#reservas-aviso').inner_text().lower()
            report['flows'].append({'kind':kind,'reservation_id':int(rid),'confirmed':True,'cancelled':True,'keyboard_dialog':True})
        # Execute a DOM sink regression with untrusted text, not just JSON headers.
        xss=page.evaluate('''async () => {
          const {renderizarTarjetaHotel}=await import('./js/components/catalogo.js');
          const e=document.createElement('div');
          e.innerHTML=renderizarTarjetaHotel({nombre:'<img src=x onerror="window.__qaXSS=true">',imagen:'img/hotel-misiones.jpg',precio:100,descuento:0,precioAnterior:0,servicios:['<script>window.__qaXSS=true</script>'],categoria:3,ubicacion:'Centro'}, {href:'hotel.html?id=1" onclick="window.__qaXSS=true'});
          document.body.append(e); const ok=!e.querySelector('script,[onerror],[onclick]') && !window.__qaXSS;e.remove();return ok;
        }''')
        assert xss;report['dom_xss_escaped']=True
        context.close();browser.close()
    output=ROOT/'docs/evidence/system/browser-flows.json';output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    assert not report['page_errors'] and not report['http_errors'],report
    print(json.dumps({'flows':len(report['flows']),'axe_states':len(report['accessibility']),'dom_xss_escaped':xss}))

if __name__=='__main__':main()
