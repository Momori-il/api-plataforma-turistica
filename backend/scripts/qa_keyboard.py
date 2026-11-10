"""Keyboard-only checks of public navigation and auth forms; no submissions or writes."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]

def main():
    results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={'width':390,'height':844})
        page.goto('http://127.0.0.1:5500/frontend/index.html',wait_until='networkidle')
        for _ in range(5):
            page.keyboard.press('Tab')
            if page.locator('.mobile-nav-toggle').evaluate('(e)=>e===document.activeElement'):break
        assert page.locator('.mobile-nav-toggle').evaluate('(e)=>e===document.activeElement')
        page.keyboard.press('Space');assert page.locator('.mobile-nav-toggle').get_attribute('aria-expanded')=='true'
        page.keyboard.press('Tab');assert page.locator('#primary-navigation a').first.evaluate('(e)=>e===document.activeElement')
        page.keyboard.press('Escape');assert page.locator('.mobile-nav-toggle').get_attribute('aria-expanded')=='false'
        assert page.locator('.mobile-nav-toggle').evaluate('(e)=>e===document.activeElement')
        results.append({'check':'mobile_menu_Tab_Space_Escape_focus_return','passed':True})
        page.set_viewport_size({'width':1366,'height':900})
        for path in ['login.html','registro-usuario.html']:
            page.goto('http://127.0.0.1:5500/frontend/'+path,wait_until='networkidle')
            required=set(page.locator('form input[required]').evaluate_all('(elements)=>elements.map(e=>e.id)'))
            reached=set()
            for _ in range(45):
                page.keyboard.press('Tab')
                focused=page.evaluate("() => {const e=document.activeElement,s=getComputedStyle(e);return {id:e.id,visible:!!e.getClientRects().length,outline:s.outlineStyle,shadow:s.boxShadow}}")
                if focused['id'] in required:
                    assert focused['visible'] and (focused['outline']!='none' or focused['shadow']!='none')
                    reached.add(focused['id'])
                if reached==required:break
            assert required and reached==required,(path,required,reached)
            page.keyboard.press('Shift+Tab')
            results.append({'check':path+'_required_fields_reachable_visible_focus','fields':len(required),'passed':True})
        browser.close()
    target=ROOT/'docs/evidence/accessibility/keyboard.json'
    target.write_text(json.dumps({'checks':results,'writes':0},indent=2),encoding='utf-8')
    print(json.dumps(results))

if __name__=='__main__':main()
