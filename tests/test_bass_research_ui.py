"""The opt-in sheet and the Conversation sharing row in the Bass UI (Art's spec ORG/notes-art-bass-optin/SPEC-optin-step.md; Luke
L-1101-115150). Pure `node` on stubs: no browser, no network. The state comes from the balance answer (`research`), so nothing shows while the
server-side switch is off, and nothing is sent to the server unless a button is pressed."""
import json

import pytest

from test_bass_beta_ui import NODE, STUBS, _node
from test_bass_ui import _facts

DRIVER = STUBS + r"""
const fs2=require('fs'); const src=fs2.readFileSync(process.argv[2],'utf8');
(async()=>{ const out={}; const BASE='https://px.test/bass';
  const NV=mk(src).win._altoBass.NOTICE_V, ACK={'alto-bass-ack-u1':NV};
  const OK={ok:true,status:'ok',credits:900,label:'900 beta credits remaining',available:true,beta:true};
  const R=(s,extra)=>Object.assign({},OK,{research:s},extra||{});
  const NEED={available:true,on:false,version:'v7',needs_optin:true}, OFF={available:false,on:false,version:'v7',needs_optin:false};
  const rt=r=>{ const e=r.appended.filter(x=>x.id==='bass-root').pop(); return e?e.innerHTML:''; };   // the Bass window, not a toast appended after it
  const acts=r=>r.fetches.map(f=>f.action), args=(r,a)=>r.fetches.filter(f=>f.action===a).map(f=>JSON.parse(f.init.body).args);
  const go=async(o,mode)=>{ const r=mk(src,Object.assign({base:BASE,user:true,store:Object.assign({},ACK)},o)); r.win._altoBass.open(mode||'panel'); await tick(); return r; };
  // switch off: nothing shows, nothing extra is sent
  let r=await go({answers:{balance:R(OFF)}}); out.off={html:r.html(),acts:acts(r),sheet:r.win._altoBass.state.sharesheet};
  // no research key at all (an older proxy): same
  r=await go({answers:{balance:OK}}); out.none={html:r.html(),sheet:r.win._altoBass.state.sharesheet};
  // first time: the sheet, nothing sent, nothing stored
  r=await go({answers:{balance:R(NEED)}}); out.first={html:r.html(),acts:acts(r),sheet:r.win._altoBass.state.sharesheet,store:Object.keys(r.store)};
  // No thanks: nothing sent to the server, remembered for this version only
  r.win._altoBass.share.no(); await tick(); out.no={acts:acts(r),mark:r.store['alto-bass-share-no-u1'],sheet:r.win._altoBass.state.sharesheet,html:rt(r)};
  r=await go({answers:{balance:R(NEED)},store:Object.assign({},ACK,{'alto-bass-share-no-u1':'v7'})}); out.declined={sheet:r.win._altoBass.state.sharesheet};
  r=await go({answers:{balance:R(NEED)},store:Object.assign({},ACK,{'alto-bass-share-no-u1':'v6'})}); out.newversion={sheet:r.win._altoBass.state.sharesheet};
  // Share: one optin call carrying agree:true and the server's version
  r=await go({answers:{balance:R(NEED),research:{ok:true,status:'ok',research:{on:true,version:'v7'}}}}); r.win._altoBass.share.yes(); await tick();
  out.yes={optin:args(r,'research'),sheet:r.win._altoBass.state.sharesheet,share:r.win._altoBass.state.share,html:rt(r)};
  // a refused opt-in changes nothing
  r=await go({answers:{balance:R(NEED),research:{ok:false,status:'error',code:'research_version'}}}); r.win._altoBass.share.yes(); await tick();
  out.refused={on:r.win._altoBass.state.share.on,sheet:r.win._altoBass.state.sharesheet};
  // the row: On shows Turn off, which withdraws; Off shows Turn on, which shows the same sheet (no one-tap enable)
  r=await go({answers:{balance:R({available:true,on:true,version:'v7',needs_optin:false}),research:{ok:true,status:'ok',research:{on:false}}}}); out.rowOn=r.html();
  r.win._altoBass.share.toggle(); await tick(); out.withdraw={calls:args(r,'research'),on:r.win._altoBass.state.share.on,html:rt(r)};
  r=await go({answers:{balance:R({available:true,on:false,version:'v7',needs_optin:false})}}); out.rowOff=r.html();
  r.win._altoBass.share.toggle(); await tick(); out.turnon={sheet:r.win._altoBass.state.sharesheet,acts:acts(r)};
  // the dev states
  const w=mk(src), B=w.win._altoBass; B.sim.delay=0; B.dev('share','wizard'); out.dev={html:w.html()};
  console.log(JSON.stringify(out)); })();
"""


@pytest.fixture(scope="module")
def ui(tmp_path_factory):
    if not NODE:
        pytest.skip("node is not installed")
    return _node(tmp_path_factory.mktemp("bassshare"), DRIVER, _facts(True)["bundle"])


def test_nothing_shows_and_nothing_is_sent_while_the_switch_is_off(ui):
    for k in ("off", "none"):
        assert "Conversation sharing" not in ui[k]["html"] and ui[k]["sheet"] is False
    assert ui["off"]["acts"] == ["balance"]                      # the state rides the balance answer: no extra call


def test_the_first_sheet_has_the_arts_words_two_equal_buttons_and_no_preselected_control(ui):
    h = ui["first"]["html"]
    assert ui["first"]["sheet"] is True and ui["first"]["acts"] == ["balance"]       # nothing sent, nothing stored by opening it
    for s in ("Help improve Bass?", "we save what you type to Bass and Bass's replies (not the files you add)", "people he asks to help, including AI tools",
              "we can't catch everything, so please don't type other people's private information", "We keep them until 15 February 2027.",
              "Nothing of your conversations is saved.", "Bass menu, then Conversation sharing", "deleted within 7 days", "Read the details"):
        assert s in h, s
    assert "to help improve Alto" not in h and "a small team" not in h and "Nothing is saved." not in h
    from alto.build import bass_ui_js
    import re as _re
    l3 = lambda n: _re.search(r"var SHARE_L3" + n + r"='(.*?)';", bass_ui_js.JS).group(1)
    assert l3("A") + " " + l3("B") == ("Bass works exactly the same if you say no. Nothing of your conversations is saved. You can stop any time: Bass menu, then "
                                       "Conversation sharing. Saving stops at once and what we saved is deleted within 7 days.")     # Strategy's stamped L3, word for word
    assert "Bass works exactly the same if you say no. Nothing of your conversations is saved." in h and "bs-promise" not in h        # stamped order, one paragraph
    assert 'var SHARE_SPLIT=false' in bass_ui_js.JS.replace("/* ", "/*") or "var SHARE_SPLIT=false" in bass_ui_js.JS
    assert h.count("15 February 2027") == 1                                                # the date is typed in one place (the constant), shown once
    assert 'href="/privacy"' in h and "#bass-conversations" not in h                        # the Privacy page itself: no fragment
    assert h.index("No thanks</button>") < h.index("Share my conversations</button>")                  # No thanks first
    sheet = h[h.index('class="bs-sheet bs-share"'):]                                   # the sheet itself (the window behind it has its own chat input)
    for bad in ("checked", "selected", "autofocus", "<input", "<select", "countdown", "Are you sure"):
        assert bad not in sheet, bad
    assert h.count('class="bs-btn bs-sbtn"') == 1 and h.count("bs-sbtn bs-syes") == 1                  # the two buttons share one class
    assert 'id="bs-sh" tabindex="-1"' in h and 'aria-modal="true"' in h
    assert not [k for k in ui["first"]["store"] if "share" in k]                         # opening the sheet stores nothing about sharing


def test_no_thanks_sends_nothing_and_does_not_return_until_the_version_changes(ui):
    n = ui["no"]
    assert n["acts"] == ["balance"] and n["mark"] == "v7" and n["sheet"] is False and "Help improve Bass?" not in n["html"]
    assert ui["declined"]["sheet"] is False and ui["newversion"]["sheet"] is True


def test_share_sends_one_optin_with_agree_true_and_the_servers_version(ui):
    y = ui["yes"]
    assert y["optin"] == [{"op": "optin", "agree": True, "version": "v7"}] and y["sheet"] is False and y["share"]["on"] is True
    assert ui["refused"]["on"] is False and ui["refused"]["sheet"] is False


def test_the_row_turns_off_at_once_and_turning_on_shows_the_same_sheet(ui):
    assert "Conversation sharing: <b>On</b>" in ui["rowOn"] and "Turn off" in ui["rowOn"] and "stops saving new conversations straight away; saved ones are deleted within 7 days" in ui["rowOn"]
    assert ui["withdraw"]["calls"] == [{"op": "withdraw"}] and ui["withdraw"]["on"] is False and "<b>Off</b>" in ui["withdraw"]["html"]
    assert "<b>Off</b>" in ui["rowOff"] and "Turn on" in ui["rowOff"]
    assert ui["turnon"]["sheet"] is True and ui["turnon"]["acts"] == ["balance"]            # nothing sent until Share is pressed


def test_the_dev_state_renders_the_sheet(ui):
    assert "Help improve Bass?" in ui["dev"]["html"]
