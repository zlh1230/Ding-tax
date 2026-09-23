"""Read-only buyer/seller control structure probe."""
import json
from urllib.parse import urlsplit
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

DRIVER = r"C:\DingInvoiceMVP\agent\tools\chromedriver\153.0.8010.52\chromedriver-win64\chromedriver.exe"

def main():
    options = webdriver.ChromeOptions(); options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    driver = webdriver.Chrome(service=Service(DRIVER), options=options)
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        url = urlsplit(driver.current_url)
        if url.hostname == "dppt.shanghai.chinatax.gov.cn" and url.path.startswith("/blue-invoice-makeout/"): break
    print(json.dumps(driver.execute_script("""
const n=s=>(s||'').replace(/\\s+/g,' ').trim(),v=e=>!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length);
const info=e=>{let r=e.getBoundingClientRect();return {tag:e.tagName.toLowerCase(),class:typeof e.className==='string'?e.className:'',placeholder:e.getAttribute('placeholder')||'',role:e.getAttribute('role')||'',type:e.getAttribute('type')||'',checked:e.checked===true,x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)}};
const heading=t=>[...document.querySelectorAll('*')].find(e=>v(e)&&n(e.innerText)===t);
const section=t=>{let h=heading(t),a=[];for(let p=h;p;p=p.parentElement){let c=[...p.querySelectorAll('input,[role=combobox],[role=checkbox]')].filter(v);if(c.length>=2)a.push({class:typeof p.className==='string'?p.className:'',controls:c.map(info),labels:[...p.querySelectorAll('label,span,div')].filter(v).map(e=>n(e.innerText)).filter(x=>['名称','电话','是否展示','地址/电话','开户行/账号'].includes(x))});}return a};
return {buyer:section('购买方信息'),seller:section('销售方信息')};
"""),ensure_ascii=False))
if __name__=='__main__': main()
