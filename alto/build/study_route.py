"""The palaces' study sheet: the route in order (study_sheet.py places it as page 1).

Where each format keeps its route, in the page (no new data is stored):
  city      window._ALTO_PALACE: units -> buildings -> floors (P.units, P.fl), numbers P.num ("3.4", "3.4-2"),
            the nearest corner of each building P.near[building] ("Walnut St & S 15th St"; a floor uses its building's)
  world     window._ALTO_WORLD: per unit its hub, then its stops (u.st) and the cards clustered round each (cl);
            nodes[id] = {n: number, t: title, c: ISO3, pl: place, k: 'country'|'sub'|'city', par}; names[ISO3]
  building  window._ALTO_BUILDING: order, nodes[id] = {n, t, r: room id}; rooms and floors come from the hosted plan
            (window.AltoBuilding.plan: rm [{id, n, no, l}], lv [{id, n}]) once it has loaded
The numbers are the palace's own (NODE_ORDER_MAP holds the same ones), so the sheet, the palace and the outline pages
after it agree. A stop with no place shows an em dash. No palace saves a picture of its map today: the thumbnail is
shown only when the page holds one (window._altoPalaceThumb, an image URL), otherwise the list takes the full width.
"""

ROUTE_JS = r"""
  var DASH = '—';
  function nodeTitle(id){
    var N = G('NODES') || [];
    for(var i = 0; i < N.length; i++) if(N[i].id === id) return N[i].title || id;
    return id;
  }
  function orderNum(id){ var M = G('NODE_ORDER_MAP') || {}; return M[id] || ''; }
//<city>
  function cityStops(){
    var P = window._ALTO_PALACE || {}, out = [];
    var U = P.units;
    if(!U){                                                     // not drawn yet: rebuild the order from the numbers
      U = [];
      Object.keys(P.num || {}).forEach(function(id){
        if(P.of && P.of[id]) return;
        var m = /^(\d+)\.(\d+)$/.exec(P.num[id]); if(!m) return;
        (U[m[1] - 1] = U[m[1] - 1] || [])[m[2] - 1] = id;
      });
    }
    U.forEach(function(ids){ (ids || []).forEach(function(b){
      if(!b) return;
      [b].concat((P.fl || {})[b] || []).forEach(function(id){
        out.push({n:(P.num || {})[id] || orderNum(id), t:nodeTitle(id), p:(P.near || {})[(P.of || {})[id] || b] || ''});
      });
    }); });
    return out;
  }
//</city>
//<world>
  function worldStops(){
    var W = window._ALTO_WORLD || {}, N = W.nodes || {}, names = W.names || {}, out = [], seen = {};
    function where(id){
      var n = N[id];
      while(n && !n.c && n.par){ n = N[n.par]; }
      if(!n || !n.c){                                           // a unit's own card: its regions, as the Atlas shows it
        var U = W.u || [];
        for(var a = 0; a < U.length; a++) if(U[a].hub === id) return (U[a].reg || []).join(', ');
        return '';
      }
      var cn = names[n.c] || '', pl = n.pl || '';
      if(n.k === 'country' || !pl) return cn || pl;
      return cn && pl !== cn ? cn + ', ' + pl : pl;            // Country, then the city
    }
    function add(id){ if(!id || seen[id] || !N[id]) return; seen[id] = 1; out.push({n:N[id].n || orderNum(id), t:N[id].t || nodeTitle(id), p:where(id)}); }
    (W.u || []).forEach(function(u){
      add(u.hub);
      (u.st || []).forEach(function(id){ add(id); ((W.cl || {})[id] || []).forEach(add); });
    });
    Object.keys(N).forEach(add);                                // anything the tour does not reach still prints, last
    return out;
  }
//</world>
//<building>
  function buildingStops(){
    var B = window._ALTO_BUILDING || {}, N = B.nodes || {};
    var plan = (window.AltoBuilding && window.AltoBuilding.plan) || null, rm = {}, lv = {};
    if(plan){ (plan.rm || []).forEach(function(r){ rm[r.id] = r; }); (plan.lv || []).forEach(function(l){ lv[l.id] = l; }); }
    return (B.order || Object.keys(N)).map(function(id){
      var n = N[id] || {}, r = n.r && rm[n.r], p = '';
      if(r){
        p = r.no && String(r.n || '').indexOf(r.no) < 0 ? 'Room ' + r.no + (r.n ? ', ' + r.n : '') : (r.n || '');   // no "Gallery 101" twice
        if(lv[r.l] && lv[r.l].n) p += ', ' + lv[r.l].n;
      }
      return {n:n.n || orderNum(id), t:n.t || nodeTitle(id), p:p};
    });
  }
  function buildingName(){ return (window._ALTO_BUILDING || {}).name; }
//</building>
  var PLACE_HEAD = {city:'Street', world:'Country', building:'Room'};
  function table(rows){
    return '<table class="ss-tbl"><thead><tr><th>Stop</th><th>Card</th><th>' + PLACE_HEAD[KIND] + '</th></tr></thead><tbody>' +
      rows.map(function(s){
        return '<tr><td class="ss-n">' + esc(s.n) + '</td><td>' + esc(s.t) + '</td><td>' + esc(s.p || DASH) + '</td></tr>';
      }).join('') + '</tbody></table>';
  }
  var STOPS = [];
  function routeBody(S, more){
    var cols = S.length > 14 ? [S.slice(0, Math.ceil(S.length / 2)), S.slice(Math.ceil(S.length / 2))] : [S];
    var t = cols.map(table);
    if(more) t[t.length - 1] = t[t.length - 1].replace('</tbody>', '<tr><td class="ss-more" colspan="3">+ ' + more + ' more: see outline</td></tr></tbody>');
    return t.join('');
  }
  function routeSheet(){
    STOPS = KIND === 'world' ? worldStops() : KIND === 'building' ? buildingStops() : cityStops();
    var th = window._altoPalaceThumb;
    var body = '<p class="ss-intro">Walk these in order.</p><div class="ss-route' + (STOPS.length > 14 ? ' two' : '') + '">' +
      (th ? '<img class="ss-thumb" alt="" src="' + esc(th) + '">' : '') +
      '<div class="ss-cols">' + routeBody(STOPS, 0) + '</div></div>';
    var bn = KIND === 'building' && buildingName();
    return frame(FMT + ' · Study sheet', body, bn);
  }
  function fitRoute(sheet){
    var box = sheet.querySelector('.ss-route'), cols = sheet.querySelector('.ss-cols');
    function over(){ return box.scrollHeight > box.clientHeight + 0.5; }
    var sizes = [10, 9.5, 9, 8.5, 8];
    for(var i = 0; i < sizes.length; i++){
      sheet.style.setProperty('--ss-fs', sizes[i] + 'pt');
      if(!over()) return;
    }
    // still too long at 8 pt: fewer stops, the columns rebalanced, the last line "+ N more: see outline"
    var k = STOPS.length;
    while(k > 0 && over()){ k--; cols.innerHTML = routeBody(STOPS.slice(0, k), STOPS.length - k); }
  }
"""
