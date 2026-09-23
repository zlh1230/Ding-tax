"""Read-only structural probe for the attached blue-invoice form."""

import json
from urllib.parse import urlsplit

from selenium import webdriver
from selenium.webdriver.chrome.service import Service


DRIVER = r"C:\DingInvoiceMVP\agent\tools\chromedriver\153.0.8010.52\chromedriver-win64\chromedriver.exe"


def main() -> None:
    options = webdriver.ChromeOptions()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    driver = webdriver.Chrome(service=Service(DRIVER), options=options)
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        url = urlsplit(driver.current_url)
        if url.hostname == "dppt.shanghai.chinatax.gov.cn" and url.path.startswith("/blue-invoice-makeout/"):
            break
    else:
        print("INVOICE_TABLE_FOUND=NO")
        return

    result = driver.execute_script("""
const norm = s => (s || '').replace(/\\s+/g, ' ').trim();
const visible = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
const attrs = e => {
  const out = {tag:e.tagName.toLowerCase()};
  for (const k of ['role','type','placeholder','aria-label','id','name']) if (e.getAttribute(k)) out[k]=e.getAttribute(k);
  for (const a of e.attributes) if (a.name.startsWith('data-')) out[a.name]=a.value;
  if (e.className && typeof e.className === 'string') out.class=e.className.split(/\\s+/).slice(0,4).join(' ');
  if (['th','button'].includes(out.tag)) out.text=norm(e.innerText).slice(0,80);
  return out;
};
const heading = [...document.querySelectorAll('*')].find(e => visible(e) && norm(e.innerText) === '开票信息');
if (!heading) return {found:false, iframes:document.querySelectorAll('iframe').length, shadows:[...document.querySelectorAll('*')].filter(e=>e.shadowRoot).length};
let container = heading.parentElement;
while (container && container.querySelectorAll('input,button,tr').length < 3) container = container.parentElement;
const tables = [...container.querySelectorAll('table,[role=grid]')].filter(visible);
const table = tables[0] || container;
const headers = [...table.querySelectorAll('th,[role=columnheader]')].filter(visible).map(e=>norm(e.innerText));
const rows = [...table.querySelectorAll('tbody tr')].filter(visible);
const row = rows.find(r=>r.querySelectorAll('td').length >= headers.length-1);
const cells = row ? [...row.querySelectorAll(':scope > td')].map((c,i)=>({dom:i,visible:visible(c),attrs:attrs(c),inputs:c.querySelectorAll('input').length,buttons:c.querySelectorAll('button,[role=button]').length,icons:c.querySelectorAll('svg,[class*=icon]').length,interactive:[...c.querySelectorAll('input,button,a,svg,[role=button],[tabindex],[title],[aria-label]')].filter(visible).map(attrs)})) : [];
const section = title => { const h=[...document.querySelectorAll('*')].find(e=>visible(e)&&norm(e.innerText)===title); let p=h&&h.parentElement; while(p&&!p.querySelector('input,select,[role=combobox]'))p=p.parentElement; return p; };
const buyer=section('购买方信息'), seller=section('销售方信息');
const sectionControls = p => p?[...p.querySelectorAll('input,select,[role=combobox],[type=checkbox]')].filter(visible).map(attrs):[];
const headerGeo=[...table.querySelectorAll('th,[role=columnheader]')].filter(visible).map(e=>{const r=e.getBoundingClientRect();return {text:norm(e.innerText),x:Math.round(r.x),width:Math.round(r.width),bottom:Math.round(r.bottom)}});
const controls=[...container.querySelectorAll('input,textarea,select,button,[role=button],[role=combobox],[role=spinbutton],[contenteditable=true],[tabindex],svg')].filter(visible).map(e=>{const r=e.getBoundingClientRect(), a=attrs(e); a.x=Math.round(r.x);a.y=Math.round(r.y);a.width=Math.round(r.width);a.height=Math.round(r.height);a.header=(headerGeo.find(h=>r.y>=h.bottom&&r.x+r.width/2>=h.x&&r.x+r.width/2<=h.x+h.width)||{}).text||'';return a});
const frame=[...document.querySelectorAll('iframe')][0]; const fu=frame?new URL(frame.src,location.href):null;
return {found:true, iframes:document.querySelectorAll('iframe').length, iframe:fu?{host:fu.hostname,path:fu.pathname,title:frame.title||''}:null, shadows:[...document.querySelectorAll('*')].filter(e=>e.shadowRoot).length, container:attrs(container), table:attrs(table), counts:['table','thead','tbody','tr','th','td','div','input','textarea','select','button','svg'].reduce((o,k)=>(o[k]=container.querySelectorAll(k).length,o),{}), headers, headerGeo, controls, cells, buyer:sectionControls(buyer), seller:sectionControls(seller)};
""")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
