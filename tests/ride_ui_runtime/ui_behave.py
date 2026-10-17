"""Behaviour of the aerial / first-person switch against a fake ROAM, in WebKit or Chromium (run through _qa/kit/py). Prints OK / FAIL lines, exit 1 on any failure."""
import sys,json; import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ui_lib import *
eng=sys.argv[1] if len(sys.argv)>1 else 'webkit'
bad=[]
def chk(name,cond,info=''):
    print(('OK   ' if cond else 'FAIL ')+name, info if not cond else ''); 
    if not cond: bad.append(name)
FAKE2=FAKE_ROAM.replace("calls.push(['enter',x,y,h,o&&o.from]);","calls.push(['enter',x,y,h,o&&o.from,o&&o.view]); if(window.__refuse) return false;")
def st(pg): return pg.evaluate("()=>_palRide.ui.state()")
def calls(pg): return pg.evaluate("()=>window.__rc.map(c=>c.slice(0,5))")
def view(pg): return pg.evaluate("()=>{var c=document.getElementById('canvas'); return [c.scrollLeft,c.scrollTop]}")
with page(eng,1,False) as pg:
    pg.evaluate(FAKE2)
    chk('cluster has the switch', pg.evaluate("()=>!!document.querySelector('#pal-ctl .pc-fp [data-fp=aerial]') && !!document.querySelector('#pal-ctl .pc-fp [data-fp=first]') && !!document.querySelector('#pal-ctl .pc-rides')"))
    chk('starts aerial', st(pg)=='aerial' and pg.get_attribute('[data-fp=aerial]','aria-pressed')=='true' and pg.get_attribute('[data-fp=first]','aria-pressed')=='false')
    # F -> placing, Esc cancels
    pg.keyboard.press('f'); pg.wait_for_timeout(200)
    chk('F starts placing', st(pg)=='placing' and pg.get_attribute('[data-fp=first]','aria-pressed')=='true')
    pg.mouse.move(600,400); pg.mouse.move(640,430); pg.wait_for_timeout(250)
    chk('ghost shows over the map', pg.evaluate("()=>document.getElementById('pal-fp-ghost').classList.contains('on')"))
    pg.mouse.move(120,880); pg.wait_for_timeout(250)
    chk('ghost hides over the controls', not pg.evaluate("()=>document.getElementById('pal-fp-ghost').classList.contains('on')"))
    pg.keyboard.press('Escape'); pg.wait_for_timeout(200)
    chk('Esc cancels', st(pg)=='aerial' and calls(pg)==[])
    # a drag across the map does not drop in
    pg.keyboard.press('f'); pg.wait_for_timeout(100)
    pg.mouse.move(700,400); pg.mouse.down(); pg.mouse.move(760,430, steps=4); pg.mouse.up(); pg.wait_for_timeout(300)
    chk('a drag is not a drop', st(pg)=='placing' and calls(pg)==[], str(calls(pg)))
    # click drops
    v0=view(pg); pg.mouse.click(650,430); pg.wait_for_timeout(1600)
    c=calls(pg); chk('click flies then enters roam facing a street', st(pg)=='fp' and len(c)==1 and c[0][0]=='enter' and c[0][4]=='aerial' and isinstance(c[0][3],float), str(c))
    chk('pre-fly view handed to roam', pg.evaluate("()=>window.__rc[0][5]&&typeof window.__rc[0][5].z")=='number' and abs(pg.evaluate("()=>window.__rc[0][5].x")-v0[0])<3, str(v0))
    chk('the map really flew', view(pg)!=v0)
    chk('cluster rises over the ride layer', pg.evaluate("()=>document.documentElement.classList.contains('pal-roam') && getComputedStyle(document.getElementById('pal-ctl')).zIndex")=='430')
    chk('Stay here shows', pg.evaluate("()=>getComputedStyle(document.querySelector('.pc-stay')).display")!='none')
    chk('Aerial/First-person state in fp', pg.get_attribute('[data-fp=first]','aria-pressed')=='true')
    pg.keyboard.press('f'); pg.wait_for_timeout(900)
    c=calls(pg); chk('F leaves (exit without stay)', st(pg)=='aerial' and c[-1]==['exit',False], str(c))
    chk('cluster back down afterwards', pg.evaluate("()=>!document.documentElement.classList.contains('pal-roam')"))
    # Enter drops at the centre; Stay here
    pg.evaluate("()=>window.__rc.length=0"); pg.click('[data-fp=first]'); pg.wait_for_timeout(200); pg.keyboard.press('Enter'); pg.wait_for_timeout(1600)
    chk('Enter drops in at the centre', st(pg)=='fp' and len(calls(pg))==1, str(calls(pg)))
    pg.click('.pc-stay'); pg.wait_for_timeout(900)
    chk('Stay here exits with stay', calls(pg)[-1]==['exit',True] and st(pg)=='aerial', str(calls(pg)))
    # double-click the segment drops in at the centre
    pg.evaluate("()=>window.__rc.length=0"); pg.dblclick('[data-fp=first]'); pg.wait_for_timeout(1600)
    chk('double-click drops in at the centre', st(pg)=='fp' and len(calls(pg))==1, str(calls(pg)))
    pg.click('[data-fp=aerial]'); pg.wait_for_timeout(900)
    chk('Aerial segment leaves', st(pg)=='aerial' and calls(pg)[-1]==['exit',False])
    # an engine that refuses puts the map back
    pg.evaluate("()=>{window.__refuse=1; window.__rc.length=0}"); v1=view(pg); pg.keyboard.press('f'); pg.wait_for_timeout(100); pg.mouse.click(650,430); pg.wait_for_timeout(1800)
    chk('a refusing engine leaves aerial, view put back', st(pg)=='aerial' and abs(view(pg)[0]-v1[0])<4 and abs(view(pg)[1]-v1[1])<4, str((view(pg),v1,st(pg))))
    pg.evaluate("()=>{window.__refuse=0}")
    # the rides setting: V in the aerial view, shared key
    chk('rides default on', pg.evaluate("()=>_palRide.pref()")=='fp' and pg.get_attribute('.pc-rides','aria-checked')=='true')
    pg.keyboard.press('v'); pg.wait_for_timeout(300)
    chk('V toggles First-person rides off (shared key)', pg.evaluate("()=>localStorage.getItem('alto-palace-ride-view')")=='map' and pg.get_attribute('.pc-rides','aria-checked')=='false')
    pg.click('.pc-rides'); pg.wait_for_timeout(300)
    chk('the cluster button toggles it back', pg.evaluate("()=>localStorage.getItem('alto-palace-ride-view')")=='fp' and pg.get_attribute('.pc-rides','aria-checked')=='true')
    pg.evaluate("()=>_palRide.setPref('map')")
    chk('setPref from elsewhere updates the controls', pg.get_attribute('.pc-rides','aria-checked')=='false')
    pg.evaluate("()=>_palRide.setPref('fp')")
    pg.evaluate("()=>_palRide.setPref('map')")
    chk('rides off: a ride from the aerial view is not first-person', pg.evaluate("()=>_palRide.demo('p-trad','n-service','transit')")==False and not pg.evaluate("()=>_palRide.active()"))
    pg.evaluate("()=>_palRide.setPref('fp')")
    chk('rides on: it is', pg.evaluate("()=>_palRide.demo('p-trad','n-service','transit')")==True and pg.evaluate("()=>_palRide.active()"))
    pg.evaluate("()=>_palRide.exit()"); pg.wait_for_timeout(600)
    # a phone has none of it
    pg.evaluate("()=>document.documentElement.classList.add('mobile')"); pg.keyboard.press('f'); pg.wait_for_timeout(200)
    chk('nothing on mobile', st(pg)=='aerial' and pg.evaluate("()=>getComputedStyle(document.getElementById('pal-ctl')).display")=='none')
    pg.evaluate("()=>document.documentElement.classList.remove('mobile')")
    pg.evaluate("()=>document.documentElement.classList.add('printing')")
    chk('nothing when printing', pg.evaluate("()=>getComputedStyle(document.getElementById('pal-ctl')).display")=='none')
    pg.evaluate("()=>document.documentElement.classList.remove('printing')")
    chk('no page errors', not [e for e in pg.errs if 'console:Failed to load' not in e], str(pg.errs))
with page(eng,1,False,reduced=True) as pg:
    pg.evaluate(FAKE2); pg.keyboard.press('f'); pg.wait_for_timeout(100); pg.mouse.click(650,430); pg.wait_for_timeout(500)
    chk('reduced motion: drops in at once', st(pg)=='fp')
    chk('reduced motion: no transitions on the controls', pg.evaluate("()=>getComputedStyle(document.querySelector('#pal-ctl .pc-city')).transitionDuration")in('0s','0.001s'), pg.evaluate("()=>getComputedStyle(document.querySelector('#pal-ctl .pc-city')).transitionDuration"))
print('RESULT','FAIL' if bad else 'PASS')
sys.exit(1 if bad else 0)
