"""Three synthetic users: shared ledger, personal privacy and immediate revocation."""
import os
import secrets
import socket
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright, expect

base = os.getenv('E2E_BASE_URL', 'http://localhost:5173')
artifacts = Path(__file__).resolve().parent / 'artifacts'
artifacts.mkdir(exist_ok=True)
args = []
expect.set_options(timeout=20000)
if os.getenv('E2E_DOCKER') == 'true':
    args = [f'--host-resolver-rules=MAP localhost {socket.gethostbyname("host.docker.internal")}', '--no-proxy-server']


def api(page, path, method='GET', data=None):
    return page.evaluate('''async ({path, method, data}) => {
      const headers = {Accept: 'application/json'};
      if (method !== 'GET') {
        const csrf = await fetch('http://localhost:8000/api/v1/auth/csrf/', {credentials:'include'}).then(r=>r.json());
        headers['X-CSRFToken'] = csrf.csrfToken; headers['Content-Type']='application/json';
      }
      const r = await fetch('http://localhost:8000/api/v1'+path, {method,headers,credentials:'include',...(data!==null ? {body:JSON.stringify(data)} : {})});
      return {status:r.status,data:r.status===204?null:await r.json()};
    }''', {'path':path, 'method':method, 'data':data})


with sync_playwright() as pw:
    browser=pw.chromium.launch(args=args)
    contexts=[browser.new_context(viewport={'width':1440,'height':1000}) for _ in range(3)]
    pages=[context.new_page() for context in contexts]
    for page in pages:
        page.set_default_navigation_timeout(90000)
    errors=[]
    original_hook = sys.excepthook
    def capture_failure(kind, value, trace):
        for index, candidate in enumerate(pages):
            try:
                candidate.screenshot(path=str(artifacts / f'families-failure-{index}.png'), full_page=True, timeout=10000)
            except Exception:
                pass
        original_hook(kind, value, trace)
    sys.excepthook = capture_failure
    credentials=[]
    for index,page in enumerate(pages):
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('dialog', lambda dialog:dialog.accept())
        page.goto(base+'/login')
        email=f'cg-family-{secrets.token_hex(6)}@example.test'
        password='QA!'+secrets.token_urlsafe(24)
        name=['Ana F7','Bruno F7','Carla F7'][index]
        assert api(page,'/auth/register/','POST',{'email':email,'password':password,'first_name':name,'last_name':'Sintético'})['status']==201
        page.get_by_label('Correo electrónico',exact=True).fill(email)
        page.get_by_label('Contraseña',exact=True).fill(password)
        page.get_by_role('button',name='Iniciar sesión',exact=True).click()
        page.wait_for_url('**/dashboard')
        expect(page.get_by_role('heading',name=f'Bienvenido, {name}')).to_be_visible()
        credentials.append(email)
    a,b,c=pages
    private_ids=[]
    for page,label in [(a,'Privado-A-F7'),(b,'Privado-B-F7')]:
        account=api(page,'/accounts/','POST',{'name':label,'kind':'BANK','initial_balance':'500.00'})['data']
        categories=api(page,'/categories/?kind=EXPENSE')['data']['results']
        category=categories[0]
        movement=api(page,'/transactions/','POST',{'account':account['id'],'kind':'EXPENSE','area':category['area'],'category':category['id'],'amount':'7.77','description':label,'occurred_at':(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat()})
        assert movement['status']==201
        private_ids.append(movement['data']['id'])
    a.goto(base+'/familias/nueva')
    a.get_by_label('Nombre de familia',exact=True).fill('Hogar sintético F7')
    a.get_by_role('button',name='Crear espacio familiar').click()
    a.wait_for_url('**/familias/*/dashboard')
    family_id=a.url.split('/familias/')[1].split('/')[0]
    prefix=f'/families/{family_id}'
    root=f'/familias/{family_id}'
    expect(a.get_by_text('Espacio familiar: Hogar sintético F7')).to_be_visible()
    account=api(a,prefix+'/accounts/','POST',{'name':'Fondo familiar F7','kind':'BANK','initial_balance':'100.00'})['data']
    area=api(a,prefix+'/areas/','POST',{'name':'Hogar F7'})['data']
    category=api(a,prefix+'/categories/','POST',{'name':'Servicios F7','area':area['id'],'kind':'EXPENSE'})['data']
    a.goto(base+root+'/integrantes')
    a.get_by_label('Correo del familiar registrado').fill(credentials[1])
    a.get_by_role('button',name='Enviar invitación interna').click()
    expect(a.get_by_role('status').filter(has_text='Solicitud procesada')).to_be_visible()
    assert api(b,prefix+'/accounts/')['status']==404
    b.goto(base+'/familias/invitaciones')
    b.get_by_role('button',name='Aceptar invitación',exact=True).click()
    expect(b.get_by_text('ACCEPTED',exact=False)).to_be_visible()
    b.goto(base+root+'/gastos/nuevo')
    expect(b.get_by_text('Espacio familiar: Hogar sintético F7')).to_be_visible()
    b.get_by_label('Cuenta',exact=True).select_option(account['id'])
    b.get_by_label('Área',exact=True).select_option(area['id'])
    b.get_by_label('Categoría',exact=True).select_option(category['id'])
    b.get_by_label('Importe (PEN)',exact=True).fill('25.50')
    b.get_by_label('Descripción',exact=True).fill('Gasto compartido F7')
    b.get_by_role('button',name='Guardar gasto',exact=True).click()
    b.wait_for_url('**/movimientos/*')
    expect(b.get_by_text('Bruno F7 Sintético',exact=True)).to_be_visible()
    family_movement=b.url.split('/')[-1]
    a.goto(base+root+'/movimientos')
    expect(a.get_by_text('Gasto compartido F7',exact=True)).to_be_visible()
    expect(a.get_by_text('Registrado por Bruno F7 Sintético')).to_be_visible()
    for page,other_id in [(a,private_ids[1]),(b,private_ids[0])]:
        assert api(page,f'/transactions/{other_id}/')['status']==404
        assert api(page,prefix+f'/transactions/{other_id}/')['status']==404
        personal=api(page,'/transactions/')['data']['results']
        assert all(row['id']!=family_movement for row in personal)
    assert api(c,prefix+'/accounts/')['status']==404
    assert api(c,prefix+'/reports/preview/')['status']==404
    c.goto(base+root+'/dashboard')
    expect(c.get_by_role('alert')).to_be_visible()
    print('PASS: tres usuarios, invitación aceptada, gasto compartido y aislamiento personal/familiar')
    b.goto(base+root+'/cuentas')
    expect(b.get_by_role('button',name='Guardar cuenta',exact=True)).to_be_disabled()
    b.get_by_label('Espacio activo').select_option('')
    b.wait_for_url('**/dashboard')
    expect(b.get_by_text('Espacio familiar: Hogar sintético F7')).to_have_count(0)
    assert api(b,'/reports/summary/')['data']['expense']=='7.77'
    b.get_by_label('Espacio activo').select_option(family_id)
    b.wait_for_url('**'+root+'/dashboard')
    expect(b.get_by_text('Gasto compartido F7',exact=False)).to_be_visible()
    summary=api(b,prefix+'/reports/summary/')['data']
    assert summary['expense']=='25.50' and summary['net_worth']=='74.50'
    b.goto(base+root+'/reportes')
    expect(b.get_by_role('heading',name='Tus reportes financieros')).to_be_visible()
    expect(b.get_by_text('Gasto compartido F7',exact=True)).to_be_visible()
    with b.expect_download() as download:
        b.get_by_role('button',name='Exportar CSV',exact=True).click()
    download.value.save_as(artifacts/'families-export.csv')
    exported=(artifacts/'families-export.csv').read_text(encoding='utf-8-sig')
    assert 'Gasto compartido F7' in exported and 'Bruno F7' in exported and 'Privado-' not in exported
    b.set_viewport_size({'width':390,'height':844})
    b.goto(base+root+'/dashboard')
    expect(b.get_by_text('Espacio familiar: Hogar sintético F7')).to_be_visible()
    expect(b.get_by_role('heading', name='Movimientos familiares recientes')).to_be_visible()
    expect(b.get_by_text('Gasto compartido F7', exact=False)).to_be_visible()
    b.wait_for_function('document.documentElement.scrollWidth <= window.innerWidth')
    b.screenshot(path=str(artifacts/'families-dashboard-mobile.png'),full_page=True)
    print('PASS: cambio de espacio, saldos independientes, reporte compartido y vista móvil')
    a.goto(base+root+'/integrantes')
    member=a.get_by_role('article').filter(has=a.get_by_role('heading',name='Bruno F7 Sintético',exact=True))
    member.get_by_role('button',name='Retirar integrante',exact=True).click()
    expect(member.get_by_text('Integrante · Retirado')).to_be_visible()
    b.goto(base+root+'/movimientos')
    expect(b.get_by_role('alert')).to_be_visible()
    for path in ('accounts/','transactions/','audit/events/','reports/preview/'):
        assert api(b,prefix+'/'+path)['status']==404
    preserved=api(a,prefix+f'/transactions/{family_movement}/')
    assert preserved['status']==200 and preserved['data']['amount']=='25.50'
    assert api(b,'/reports/summary/')['data']['expense']=='7.77'
    assert not errors, 'Browser JavaScript errors detected'
    print('PASS: retirada revoca consultas y exportaciones; historial familiar y personal conservado')
    browser.close()
