"""The browser's Back and Forward buttons (and a trackpad swipe) move through a timeline's pages.

A timeline is one document: opening a detail page, going back to the timeline and the next page
used to change nothing the browser could see, so Back left the timeline altogether and Forward had
nothing to go to. Here every change of what is on screen between the timeline and a detail page
is an entry in the browser's own history (the URL is untouched, so a #find= link, the share link
and everything that reads the hash go on as before):

  * opening a page (a card, a link, the nav bar, prev / next, a search hit) adds an entry;
  * Alto's own Back controls (Back to the timeline, Back to <previous page>) are the browser's
    Back when what they go to is the entry just behind: they step back along the history instead
    of adding to it, so the two always agree and Forward goes to the page just left;
  * the browser's Back / Forward show the page or the timeline of the entry they land on;
  * the entry the timeline was opened on is the timeline itself, so Back from there goes to
    wherever the person came from (the homepage), and Forward from the homepage comes back;
  * a page that is reloaded or comes back from another site opens on the page its entry holds.

Printing builds the picture by stepping the page away and back (print_views.py): it does that
inside window._altoNav.quiet(fn), which leaves the history alone.
"""

HISTORY_NAV = r"""<script id="alto-history-nav">
(function(){
  var H = window.history;
  if(!H || typeof H.pushState !== 'function' || typeof window.showDetail !== 'function' || typeof window.showTimeline !== 'function') return;
  // The private shell can write a newer copy of the page over this one: the window (and this state) survives, the page's own
  // functions do not. Wrap the new ones, and let the new copy start up quietly.
  var N = window._altoNav;
  if(N){ N.rewrap(); return; }
  var quiet = 1, idx = 0, views = [], cur = {v:'tl'};       // quiet while the page starts up: its own start shows the timeline
  function same(a, b){ return !!a && !!b && a.v === b.v && (a.v === 'tl' || (a.type === b.type && a.id === b.id)); }
  function pick(s){ return s.v === 'd' ? {v:'d', type:s.type, id:s.id} : {v:'tl'}; }
  function put(kind, view, i){
    try{ H[kind]({alto:1, v:view.v, type:view.type, id:view.id, i:i}, '', location.href); return true; }catch(e){ return false; }
  }
  function real(){                                                  // what is on screen (a detail page is open when its panel shows)
    var dp = document.getElementById('detail-page');
    return window._currentDetailId && dp && dp.classList.contains('visible') ? {v:'d', type:window._currentDetailType, id:window._currentDetailId} : {v:'tl'};
  }
  try{ if('scrollRestoration' in H) H.scrollRestoration = 'manual'; }catch(e){}

  // The entry this document is on: a fresh one is the timeline; one that is being reloaded, or came back from
  // another site, says which page it was on.
  var s0 = H.state, restore = null;
  if(s0 && s0.alto){ idx = s0.i || 0; cur = pick(s0); if(cur.v === 'd') restore = cur; }
  else if(!put('replaceState', cur, 0)) return;                       // a sandbox that will not take history: leave things as they were
  views[idx] = cur;

  // The page was already moved by the caller; this makes the history say so.
  function record(view){
    if(quiet || same(cur, view)) return;
    var behind = idx > 0 ? views[idx - 1] : null;
    cur = view;
    if(behind && same(behind, view)){                                 // going to the page just left: that is Back
      idx--;
      try{ H.back(); return; }catch(e){ idx++; }
    }
    idx++; views.length = idx; views[idx] = view;
    put('pushState', view, idx);
  }
  function apply(view){
    quiet++;
    try{ if(view.v === 'd') window.showDetail(view.type, view.id); else window.showTimeline(); }
    finally{ quiet--; }
  }
  function wrap(){
    if(!window.showDetail._altoNav){
      var d0 = window.showDetail;
      window.showDetail = function(type, id){
        var r = d0.apply(this, arguments);
        record({v:'d', type:type, id:id});
        return r;
      };
      window.showDetail._altoNav = 1;
    }
    if(!window.showTimeline._altoNav){
      var t0 = window.showTimeline;
      window.showTimeline = function(){
        var r = t0.apply(this, arguments);
        record({v:'tl'});
        return r;
      };
      window.showTimeline._altoNav = 1;
    }
  }
  wrap();

  function onPop(e){
    var s = e.state; if(!s || !s.alto) return;
    var view = pick(s);
    idx = s.i || 0; views[idx] = view;
    if(same(cur, view)) return;                                       // an Alto control already put the page there
    cur = view;
    apply(view);
  }
  window.addEventListener('popstate', onPop);       // (document.open() drops a window's listeners: rewrap adds it again)

  // After the engine's own start-up, which ends by showing the timeline on the second frame (this is registered after it, so it runs
  // after it): the page is then put on the one its entry holds, and from here on what is shown is the person's doing.
  function afterStart(fn){
    if(window.requestAnimationFrame) window.requestAnimationFrame(function(){ window.requestAnimationFrame(function(){ setTimeout(fn, 250); }); });
    else setTimeout(fn, 600);
  }
  afterStart(function(){
    quiet--;
    if(restore && same(cur, restore) && real().v === 'tl'){ apply(restore); return; }
    // a link that opened a page as the page started is where the person is: the history says so too
    if(real().v === 'd') record(real());
  });

  window._altoNav = {
    quiet: function(fn){ quiet++; try{ return fn(); } finally{ quiet--; } },
    state: function(){ return {idx:idx, cur:cur, views:views.slice()}; },
    rewrap: function(){
      quiet++; wrap(); window.addEventListener('popstate', onPop);
      afterStart(function(){ quiet--; cur = real(); views[idx] = cur; put('replaceState', cur, idx); });   // the new copy opens on the timeline
    }
  };
})();
</script>"""


def history_nav() -> str:
    return HISTORY_NAV + "\n"
