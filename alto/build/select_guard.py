"""No accidental page selection on any board (Luke, 2026-11-05: "whatever happens here with accidental highlighting of the whole page, please
fix. I've noticed this problem in other formats as well"; his Safari shot of the Torts System, 3D Star chart: selection boxes behind the
body labels, the bottom bar's text, a stair-step block near Damages).

ONE rule set for every format and style, added to every page by builder._add_tail (timeline, lanes, outline, System in all its looks,
City map, Blueprint, Atlas, Museum): a board is a surface you drag, zoom and enlarge, never one you read by selecting it.

  * Everything on the page (board and canvas labels, every bar, chip, toggle, the minimap, the bottom bar) is user-select:none; only the
    places where text is READ or WRITTEN opt back in: the detail page, the Overview, the Notes rail, the share dialog (each only while it is OPEN: parked off the
    board its text would otherwise ride along with select-all), an enlarged card (computers), every input / textarea / select and every editable (Edit mode, Freewrite).
  * A mouse press on the board does not start a selection (preventDefault on mousedown, which also stops the double- and triple-click
    word / line pick), a double-click on the board clears whatever selection there is, and selectstart from the board is refused. None of it
    touches a press that begins in a field or in an editable (their focus and caret stay as the browser has them), on a button or link,
    or while a field holds the focus.
  * A phone (html.mobile): the same user-select rules, plus -webkit-touch-callout:none on the board so a long press there shows no
    selection or callout; readable text (detail page, Overview, notes, fields) keeps it. The mouse script does not run there.
"""

OK = ('input,textarea,select,[contenteditable]:not([contenteditable="false"]),#detail-page.visible,#summary-wrap.open,#notes-panel.open,'
      '#share-dialog.visible,[data-alto-select]')

CSS = r"""
html body{-webkit-user-select:none;user-select:none;-webkit-touch-callout:none}
html body :is(input,textarea,select,[contenteditable]:not([contenteditable="false"]),[contenteditable]:not([contenteditable="false"]) *,
#detail-page.visible,#detail-page.visible *,#summary-wrap.open,#summary-wrap.open *,#notes-panel.open,#notes-panel.open *,#share-dialog.visible,#share-dialog.visible *,[data-alto-select],[data-alto-select] *){
-webkit-user-select:text;user-select:text;-webkit-touch-callout:default}
html:not(.mobile) body :is(.node.focused .node-card,.node.focused .node-card *){-webkit-user-select:text;user-select:text}
"""

JS = r"""(function(){
var H=document.documentElement,OK='__OK__,.node.focused .node-card',CT='button,a,summary,label,[role=button],[role=tab],[role=menuitem],[tabindex]';
function E(t){return t&&t.nodeType===1?t:t&&t.parentElement}
function ok(t){t=E(t);return !!(t&&t.closest&&t.closest(OK))}
function ed(a){return !!a&&a!==document.body&&(/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)||a.isContentEditable)}
document.addEventListener('mousedown',function(e){
if(H.classList.contains('mobile')||e.button||ed(document.activeElement))return;
var t=E(e.target);if(!t||!t.closest||t.closest(OK)||t.closest(CT))return;
e.preventDefault()},true);
document.addEventListener('dblclick',function(e){
if(H.classList.contains('mobile')||ok(e.target))return;
var s=window.getSelection&&window.getSelection();if(s&&s.rangeCount&&!ed(document.activeElement))s.removeAllRanges()},true);
document.addEventListener('selectstart',function(e){
var t=E(e.target);if(!t||t===document.body||t===H||ok(t)||ed(document.activeElement))return;
e.preventDefault()},true);
})();"""


def block() -> str:
    from .backgrounds import _lean
    import re
    return ('<style id="alto-select-css">' + _lean(CSS, css=True) + '</style><script id="alto-select-js">'
            + _lean(re.sub(r"/\*.*?\*/", "", JS.replace("__OK__", OK), flags=re.S)) + "</script>")
