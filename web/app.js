/* Funding Atlas page script. Shared by the index and every state page; inlined by scripts/build_site.py.
   Plain browser JavaScript, no build step, no network: everything comes from the JSON block in the page.
   Nothing here invents data. A null stays blank; the only computed things are counts, sort orders and the
   wording of dates relative to the build date. */
(function () {
  'use strict';

  var DATA = JSON.parse(document.getElementById('data').textContent);
  var PAGE = document.body.getAttribute('data-page');
  var ROOT = PAGE === 'state' ? '../' : '';
  var TODAY = DATA.generated_at.slice(0, 10);

  // ---------- helpers ----------

  function h(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function cap(s) { s = String(s || ''); return s.charAt(0).toUpperCase() + s.slice(1); }
  function words(s) { return cap(String(s || '').replace(/_/g, ' ')); }
  function money(n) { return n == null ? '' : '$' + Number(n).toLocaleString('en-US'); }
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function fmtDate(iso, withYear) {
    if (!iso) return '';
    var y = +iso.slice(0, 4), m = +iso.slice(5, 7), d = +iso.slice(8, 10);
    var out = MONTHS[m - 1] + ' ' + d;
    return (withYear === false || (withYear === undefined && String(y) === TODAY.slice(0, 4))) ? out : out + ', ' + y;
  }
  function daysBetween(a, b) {
    return Math.round((Date.UTC(+b.slice(0, 4), +b.slice(5, 7) - 1, +b.slice(8, 10)) -
                       Date.UTC(+a.slice(0, 4), +a.slice(5, 7) - 1, +a.slice(8, 10))) / 86400000);
  }
  function relDays(d) {
    if (d < 0) return 'deadline passed ' + (-d) + (d === -1 ? ' day' : ' days') + ' ago';
    if (d === 0) return 'closes today';
    if (d === 1) return 'closes tomorrow';
    if (d < 14) return 'closes in ' + d + ' days';
    if (d < 60) return 'closes in ' + Math.round(d / 7) + ' weeks';
    return 'closes in ' + Math.round(d / 30) + ' months';
  }
  function isSoon(p) { return p.days_to_close != null && p.days_to_close >= 0 && p.days_to_close <= DATA.rules.closing_days; }
  function stateName(code) {
    var s = (DATA.states || []).filter(function (x) { return x.code === code; })[0];
    return s ? s.name : code;
  }
  function el(id) { return document.getElementById(id); }
  function pill(cls, text) { return '<span class="pill ' + cls + '">' + h(text) + '</span>'; }
  function tierPill(t) { return pill('tier-' + t, t === 'likely' ? 'Likely' : 'Possible'); }
  function statusPill(s) { return pill('st-' + s, cap(s)); }
  function levelPill(p) { return pill('lvl', p.level === 'federal' ? 'Federal' : (p.state ? stateName(p.state) : cap(p.level))); }
  function badges(p) { return (p.is_new ? pill('new', 'New') : '') + (p.is_updated ? pill('upd', 'Updated') : ''); }
  function sourceLine(src) {
    return h(src.label) + (src.last_ok ? ' read ' + fmtDate(src.last_ok) : ' (no successful read yet)');
  }

  // Wording of a change's field diff, for the feed.
  var FIELD_LABEL = {
    status: 'status', closes_at: 'closes', opens_at: 'opens', closes_at_text: 'deadline wording',
    amount_max: 'max award', amount_min: 'min award', match_required: 'match required', match_pct: 'match %',
    name: 'name', summary: 'summary', eligibility_text: 'eligibility text', funding_type: 'funding type',
    administering_agency: 'agency', applicant_types: 'applicant tags', categories: 'categories', alns: 'listings cited',
    rolling: 'rolling', source_url: 'source URL', external_number: 'number'
  };
  function fmtVal(field, v) {
    if (v == null || v === '') return '(blank)';
    if (field === 'amount_max' || field === 'amount_min') return money(v);
    if (field === 'closes_at' || field === 'opens_at') return fmtDate(v);
    if (field === 'match_required' || field === 'rolling') return v ? 'yes' : 'no';
    if (typeof v === 'object') return Array.isArray(v) ? v.length + ' values' : 'changed';
    return String(v).length > 40 ? String(v).slice(0, 39) + '…' : String(v);
  }
  function describe(c) {
    var lead = [], rest = [];
    c.fields.forEach(function (f) {
      if (f.field === 'status' || f.field === 'closes_at' || f.field === 'amount_max' || f.field === 'opens_at') {
        lead.push(h(FIELD_LABEL[f.field]) + ' <b>' + h(fmtVal(f.field, f.old)) + '</b> → <b>' + h(fmtVal(f.field, f.new)) + '</b>');
      } else {
        rest.push(FIELD_LABEL[f.field] || f.field.replace(/_/g, ' '));
      }
    });
    var out = lead.join(' · ');
    if (c.type === 'added') out = 'added to the registry' + (out ? ' · ' + out : '');
    if (c.type === 'missing') out = 'no longer listed by the source' + (out ? ' · ' + out : '');
    if (rest.length) out += (out ? ' · ' : '') + (lead.length || c.type !== 'changed' ? 'also ' : '') + h(rest.join(', '));
    return out || 'changed';
  }

  // Build-and-forget list of the feed, grouped by day. `link(c)` returns the HTML for the program name.
  function renderFeed(list, changes, link) {
    if (!changes.length) {
      list.innerHTML = '<li class="empty">No changes match.</li>';
      return;
    }
    var days = [], byDay = {};
    changes.forEach(function (c) {
      var d = c.at.slice(0, 10);
      if (!byDay[d]) { byDay[d] = []; days.push(d); }
      byDay[d].push(c);
    });
    list.innerHTML = days.map(function (d) {
      var ago = daysBetween(d, TODAY);
      var label = fmtDate(d) + (ago === 0 ? ' (today)' : ago === 1 ? ' (yesterday)' : ago < 14 ? ' (' + ago + ' days ago)' : '');
      return '<li class="day"><h3>' + h(label) + '</h3><ul>' + byDay[d].map(function (c) {
        var who = (c.agency || c.connector) + ' · ' + (c.level === 'federal' ? 'federal' : (c.state ? stateName(c.state) : c.level));
        return '<li class="ev"><span class="type ' + h(c.type) + '">' + h(c.type) + '</span><div>' +
          '<div class="name">' + link(c) + '</div>' +
          '<div class="what">' + describe(c) + '</div>' +
          '<div class="who">' + h(who) + '</div></div></li>';
      }).join('') + '</ul></li>';
    }).join('');
  }

  function renderFooter(extra) {
    var f = el('footer');
    if (!f) return;
    var q = (DATA.questions || []).map(function (x) { return '<li>' + h(x) + '</li>'; }).join('');
    f.innerHTML =
      '<div><h2>About this page</h2>' +
      '<p>This is a registry export, not advice. Each row is one program page or federal notice read by a connector; the status and dates are what that source said on the run date. Programs that only give a month ("Application opens: February") keep that wording rather than a guessed date. Blank fields mean the source did not state the value.</p>' +
      (extra || '') +
      '<p><b>New</b> marks a record first seen in the last ' + DATA.rules.new_days + ' days, after the source\'s first full read. <b>Updated</b> marks one whose source text changed in that window.</p></div>' +
      '<div><h2>What I would like to know from you</h2><ol>' + q + '</ol></div>' +
      '<div><h2>Data and code</h2>' +
      '<p>Records are open data under the <a href="https://opendatacommons.org/licenses/odbl/1-0/">Open Database License</a>; the connectors and this page are MIT licensed. Built ' + h(fmtDate(DATA.generated_at)) + ' from <a href="' + h(ROOT) + 'atlas.db.gz">atlas.db.gz</a> (SQLite, gzipped: every record, every raw payload and every logged change).</p>' +
      '<p><a href="' + h(DATA.repo_url) + '">Source code and connector docs</a> · <a href="' + h(ROOT) + '">All states</a></p></div>';
  }

  // =====================================================================================
  // State page
  // =====================================================================================

  function statePage() {
    var P = DATA.programs, B = DATA.between || [], C = DATA.changes, R = DATA.rules, S = DATA.state;
    P.forEach(function (p) {
      p._text = [p.name, p.agency, p.agency_code, p.number, p.summary].join(' ').toLowerCase();
    });
    var byId = {}, bySlug = {};
    P.concat(B).forEach(function (p) { byId[p.id] = p; bySlug[p.slug] = p; });

    var FACETS = [
      { key: 'tier', label: 'Relevance to a municipality', get: function (p) { return [p.tier]; },
        lab: function (v) { return v === 'likely' ? 'Likely' : 'Possible'; }, order: ['likely', 'possible'], open: true },
      { key: 'level', label: 'Level', get: function (p) { return [p.level]; }, lab: cap, open: true },
      { key: 'status', label: 'Status', get: function (p) { return [p.status]; }, lab: cap, open: true },
      { key: 'deadline', label: 'Deadline', get: function (p) { return [p.closes_at ? 'dated' : p.rolling ? 'rolling' : p.closes_text ? 'text' : 'none']; },
        lab: function (v) { return { dated: 'Has a date', rolling: 'Rolling or year-round', text: 'Described in words', none: 'Not stated' }[v]; },
        order: ['dated', 'rolling', 'text', 'none'], open: true },
      { key: 'category', label: 'Category', get: function (p) { return p.categories.length ? p.categories : ['none']; },
        lab: function (v) { return v === 'none' ? 'Not stated' : words(v); }, open: true },
      { key: 'funding_type', label: 'Funding type', get: function (p) { return [p.funding_type || 'none']; },
        lab: function (v) { return v === 'none' ? 'Not stated' : words(v); }, open: false },
      { key: 'agency', label: 'Agency', get: function (p) { return [p.agency || p.agency_code || 'Not stated']; },
        lab: function (v) { return v; }, open: false, long: true }
    ];
    var DEFAULT_SEL = { tier: ['likely'] };

    var st = { q: '', sort: 'closing', sel: {}, quick: null, tab: 'programs', feed: 'all', between: false };
    function resetSel() { st.sel = {}; Object.keys(DEFAULT_SEL).forEach(function (k) { st.sel[k] = DEFAULT_SEL[k].slice(); }); }
    resetSel();

    // ---- URL state (shareable filters; the detail panel is #p=slug) ----
    function parseHash() {
      var out = {};
      location.hash.replace(/^#/, '').split('&').forEach(function (kv) {
        if (!kv) return;
        var i = kv.indexOf('='), k = decodeURIComponent(i < 0 ? kv : kv.slice(0, i)), v = i < 0 ? '' : decodeURIComponent(kv.slice(i + 1));
        out[k] = v;
      });
      return out;
    }
    function readHash() {
      var hsh = parseHash();
      if (hsh.q !== undefined) st.q = hsh.q;
      if (hsh.sort) st.sort = hsh.sort;
      if (hsh.tab === 'changes') st.tab = 'changes';
      if (hsh.feed) st.feed = hsh.feed;
      if (hsh.quick) st.quick = hsh.quick;
      if (hsh.between === '1') st.between = true;
      var any = false;
      FACETS.forEach(function (f) { if (hsh[f.key] !== undefined) { any = true; st.sel[f.key] = hsh[f.key] ? hsh[f.key].split(',') : []; } });
      if (hsh.all === '1' && !any) st.sel = {};
      return hsh.p || null;
    }
    function writeHash(slug) {
      var parts = [];
      if (st.q) parts.push('q=' + encodeURIComponent(st.q));
      if (st.sort !== 'closing') parts.push('sort=' + st.sort);
      if (st.quick) parts.push('quick=' + st.quick);
      if (st.tab === 'changes') parts.push('tab=changes');
      if (st.feed !== 'all') parts.push('feed=' + st.feed);
      if (st.between) parts.push('between=1');
      var same = true;
      FACETS.forEach(function (f) {
        var cur = (st.sel[f.key] || []).slice().sort().join(','), def = (DEFAULT_SEL[f.key] || []).slice().sort().join(',');
        if (cur !== def) { same = false; if (cur) parts.push(f.key + '=' + encodeURIComponent(cur)); }
      });
      if (!same && !FACETS.some(function (f) { return (st.sel[f.key] || []).length; })) parts.push('all=1');
      if (slug) parts.push('p=' + encodeURIComponent(slug));
      var hash = parts.length ? '#' + parts.join('&') : '';
      if (hash !== location.hash && !(hash === '' && location.hash === '')) {
        history.replaceState(null, '', location.pathname + location.search + hash);
      }
    }

    // ---- matching ----
    function termsOf(q) { return q.toLowerCase().split(/\s+/).filter(Boolean); }
    function matches(p, skip) {
      if (st.quick === 'new' && !p.is_new) return false;
      if (st.quick === 'closing' && !isSoon(p)) return false;
      var terms = termsOf(st.q);
      for (var i = 0; i < terms.length; i++) if (p._text.indexOf(terms[i]) < 0) return false;
      for (var j = 0; j < FACETS.length; j++) {
        var f = FACETS[j];
        if (f.key === skip) continue;
        var sel = st.sel[f.key];
        if (!sel || !sel.length) continue;
        var vals = f.get(p), ok = false;
        for (var k = 0; k < vals.length; k++) if (sel.indexOf(vals[k]) >= 0) { ok = true; break; }
        if (!ok) return false;
      }
      return true;
    }
    function closeKey(p) {
      return p.closes_at ? '0' + p.closes_at : p.closes_text ? '1' : p.rolling ? '2' : '3';
    }
    var SORTS = {
      closing: function (a, b) { return closeKey(a).localeCompare(closeKey(b)) || a.name.localeCompare(b.name); },
      newest: function (a, b) { return b.first_seen.localeCompare(a.first_seen) || a.name.localeCompare(b.name); },
      changed: function (a, b) { return b.last_changed.localeCompare(a.last_changed) || a.name.localeCompare(b.name); },
      amount: function (a, b) { return (b.amount_max || -1) - (a.amount_max || -1) || a.name.localeCompare(b.name); },
      name: function (a, b) { return a.name.localeCompare(b.name); }
    };

    // ---- header ----
    el('title').textContent = S.name + ': open funding for local governments';
    var cov = DATA.coverage, nState = cov.state ? cov.state.open : 0;
    el('lede').textContent = P.length + ' program' + (P.length === 1 ? '' : 's') + ' a town, city or county in ' + S.name +
      ' can apply to now or soon: ' + cov.federal.open + ' federal' + (cov.state ? ' and ' + nState + ' from ' + S.name + ' agencies' : '') +
      '. Sorted by deadline. Open a card for the source\'s own eligibility wording.';
    var covHtml = '<span class="cov"><b>Federal:</b> ' + cov.federal.open + ' open notices' +
      (cov.federal.sources.length ? ' · ' + cov.federal.sources.map(sourceLine).join(' · ') : ' · no sources read yet') + '</span>';
    if (cov.state) {
      covHtml += '<span class="cov"><b>' + h(S.name) + ':</b> ' + cov.state.agencies + (cov.state.agencies === 1 ? ' agency' : ' agencies') +
        ' · ' + cov.state.programs + ' programs read · ' + cov.state.open + ' open for local governments' +
        (cov.state.between ? ' · ' + cov.state.between + ' between rounds' : '') +
        (cov.state.last_ok ? ' · read ' + fmtDate(cov.state.last_ok) : '') + '</span>';
    } else {
      covHtml += '<span class="cov none"><b>' + h(S.name) + ':</b> no state sources yet. Federal notices only.</span>';
    }
    el('coverage').innerHTML = covHtml;

    var sw = el('state-switch');
    sw.innerHTML = DATA.states.map(function (s) { return '<option value="' + h(s.code) + '"' + (s.code === S.code ? ' selected' : '') + '>' + h(s.name) + '</option>'; }).join('');
    sw.addEventListener('change', function () { location.href = ROOT + sw.value.toLowerCase() + '/'; });

    // ---- pulse tiles ----
    var nNew = P.filter(function (p) { return p.is_new; }).length;
    var nClosing = P.filter(isSoon).length;
    var flips = C.filter(function (c) { return c.status_flip && daysBetween(c.at.slice(0, 10), TODAY) <= R.new_days; });
    el('n-new').textContent = nNew; el('n-closing').textContent = nClosing; el('n-changed').textContent = flips.length;
    el('tile-new').querySelector('.d').textContent = 'first seen by the registry in the last ' + R.new_days + ' days';
    el('tile-closing').querySelector('.d').textContent = 'deadline between today and ' + R.closing_days + ' days out';
    el('tile-changed').querySelector('.d').textContent = 'status flipped in the last ' + R.new_days + ' days';
    if (!nNew) el('tile-new').disabled = true;
    if (!nClosing) el('tile-closing').disabled = true;
    if (!flips.length) el('tile-changed').disabled = true;
    el('tab-n-changes').textContent = C.length;
    el('tab-n-programs').textContent = P.length;
    if (cov.state) el('chip-state').textContent = S.name; else el('chip-state').hidden = true;

    // ---- facets (built once; counts updated in place) ----
    var facetsEl = el('facets'), facetList = el('facet-list');
    function buildFacets() {
      facetList.innerHTML = FACETS.map(function (f) {
        var seen = {};
        P.forEach(function (p) { f.get(p).forEach(function (v) { seen[v] = (seen[v] || 0) + 1; }); });
        var vals = Object.keys(seen);
        if (f.order) vals.sort(function (a, b) { return f.order.indexOf(a) - f.order.indexOf(b); });
        else if (f.long) vals.sort(function (a, b) { return seen[b] - seen[a] || a.localeCompare(b); });
        else vals.sort(function (a, b) { return f.lab(a).localeCompare(f.lab(b)); });
        return '<details class="facet" data-facet="' + f.key + '"' + (f.open ? ' open' : '') + '><summary>' + h(f.label) + '</summary>' +
          '<ul' + (f.long ? ' class="long"' : '') + '>' + vals.map(function (v) {
            var id = 'f-' + f.key + '-' + v.replace(/[^a-z0-9]+/gi, '-').toLowerCase();
            return '<li data-v="' + h(v) + '"><label for="' + id + '"><input type="checkbox" id="' + id + '" name="' + h(f.key) + '" value="' + h(v) + '">' +
              '<span class="lbl">' + h(f.lab(v)) + '</span><span class="cnt" aria-label="count"></span></label></li>';
          }).join('') + '</ul></details>';
      }).join('') + '<button class="btn quiet clear" id="clear" type="button">Clear filters</button>';
      facetsEl.addEventListener('change', function (e) {
        var cb = e.target;
        if (cb.type !== 'checkbox') return;
        var sel = st.sel[cb.name] || (st.sel[cb.name] = []);
        var i = sel.indexOf(cb.value);
        if (cb.checked && i < 0) sel.push(cb.value);
        if (!cb.checked && i >= 0) sel.splice(i, 1);
        render();
      });
      el('clear').addEventListener('click', function () { st.sel = {}; st.q = ''; st.quick = null; el('q').value = ''; render(); el('q').focus(); });
    }
    function updateFacets() {
      var active = 0;
      FACETS.forEach(function (f) {
        var sel = st.sel[f.key] || [];
        if (sel.length) active += sel.length;
        var counts = {};
        P.forEach(function (p) { if (matches(p, f.key)) f.get(p).forEach(function (v) { counts[v] = (counts[v] || 0) + 1; }); });
        var det = facetsEl.querySelector('[data-facet="' + f.key + '"]');
        Array.prototype.forEach.call(det.querySelectorAll('li'), function (li) {
          var v = li.getAttribute('data-v'), n = counts[v] || 0, cb = li.querySelector('input');
          li.querySelector('.cnt').textContent = n;
          cb.checked = sel.indexOf(v) >= 0;
          li.classList.toggle('zero', n === 0 && !cb.checked);
        });
      });
      var fn = el('filters-n');
      fn.hidden = !active; fn.textContent = active;
      el('clear').hidden = !active && !st.q && !st.quick;
    }

    // ---- results ----
    function closesHtml(p) {
      if (p.closes_at) {
        var soon = isSoon(p);
        return '<span class="' + (soon ? 'soon' : '') + '"><b>' + h(relDays(p.days_to_close)) + '</b> · ' + h(fmtDate(p.closes_at)) + '</span>';
      }
      if (p.closes_text) return '<span><span class="k">Deadline</span> ' + h(p.closes_text) + '</span>';
      if (p.rolling) return '<span><b>Rolling</b> · applications accepted year-round</span>';
      return '<span class="k">No deadline stated</span>';
    }
    function card(p) {
      var meta = [p.agency || p.agency_code, p.number].filter(Boolean).join(' · ');
      var facts = [closesHtml(p)];
      if (p.amount_max != null) facts.push('<span><span class="k">Max award</span> <b class="num">' + money(p.amount_max) + '</b></span>');
      else if (p.amount_min != null) facts.push('<span><span class="k">From</span> <b class="num">' + money(p.amount_min) + '</b></span>');
      if (p.match_required != null) facts.push('<span><span class="k">Match</span> <b>' + (p.match_required ? 'required' : 'not required') + '</b></span>');
      if (p.funding_type && p.funding_type !== 'grant') facts.push('<span class="k">' + h(words(p.funding_type)) + '</span>');
      return '<article class="card" data-id="' + p.id + '">' +
        '<div class="row">' + tierPill(p.tier) + statusPill(p.status) + levelPill(p) + badges(p) + '</div>' +
        '<h3><button type="button" data-open="' + p.id + '" data-url="' + h(p.source_url) + '" aria-haspopup="dialog">' + h(p.name) + '</button></h3>' +
        (meta ? '<p class="meta">' + h(meta) + '</p>' : '') +
        '<div class="facts">' + facts.join('') + '</div>' +
        (p.categories.length ? '<ul class="chips" aria-label="Categories">' + p.categories.map(function (c) { return '<li>' + h(words(c)) + '</li>'; }).join('') + '</ul>' : '') +
        '<span class="arrow" aria-hidden="true">›</span></article>';
    }
    var resultsEl = el('results');
    resultsEl.tabIndex = -1;
    function renderResults() {
      var rows = P.filter(function (p) { return matches(p, null); }).sort(SORTS[st.sort] || SORTS.closing);
      el('count').textContent = 'Showing ' + rows.length + ' of ' + P.length;
      if (!rows.length) {
        resultsEl.innerHTML = '<div class="empty"><b>Nothing matches.</b><br>Try fewer filters, or include the <b>possible</b> tier.</div>';
        return;
      }
      resultsEl.innerHTML = rows.map(card).join('');
    }
    resultsEl.addEventListener('click', function (e) {
      if (e.target.closest('a')) return;
      var c = e.target.closest('.card');
      if (c) openDetail(byId[c.getAttribute('data-id')], c.querySelector('button'));
    });

    // ---- between rounds: closed or past-deadline state programs, collapsed by default ----
    // Nothing here forecasts: the last deadline is what the source stated, the cycle text is the source's own
    // wording, and "reopened last on" is an observation from the change log (absent until it has happened).
    function agoDays(d) { return d === 1 ? '1 day ago' : d + ' days ago'; }
    function betweenCard(p) {
      var meta = [p.agency || p.agency_code, p.number].filter(Boolean).join(' · ');
      var facts = [];
      if (p.closes_at) facts.push('<span><span class="k">Last deadline</span> <b>' + h(fmtDate(p.closes_at)) + '</b>' + (p.days_since_deadline != null ? ' · ' + h(agoDays(p.days_since_deadline)) : '') + '</span>');
      else facts.push('<span class="k">No deadline date stated</span>');
      if (p.last_reopened) facts.push('<span><span class="k">Reopened last on</span> <b>' + h(fmtDate(p.last_reopened, true)) + '</b></span>');
      if (p.amount_max != null) facts.push('<span><span class="k">Max award</span> <b class="num">' + money(p.amount_max) + '</b></span>');
      if (p.match_required != null) facts.push('<span><span class="k">Match</span> <b>' + (p.match_required ? 'required' : 'not required') + '</b></span>');
      if (p.funding_type && p.funding_type !== 'grant') facts.push('<span class="k">' + h(words(p.funding_type)) + '</span>');
      return '<article class="card between-card" data-id="' + p.id + '">' +
        '<div class="row">' + tierPill(p.tier) + statusPill(p.status) + levelPill(p) + badges(p) + '</div>' +
        '<h3><button type="button" data-open="' + p.id + '" data-url="' + h(p.source_url) + '" aria-haspopup="dialog">' + h(p.name) + '</button></h3>' +
        (meta ? '<p class="meta">' + h(meta) + '</p>' : '') +
        '<div class="facts">' + facts.join('') + '</div>' +
        (p.closes_text ? '<p class="cycle"><span class="k">As written by the source:</span> ' + h(p.closes_text) + '</p>' : '') +
        (p.categories.length ? '<ul class="chips" aria-label="Categories">' + p.categories.map(function (c) { return '<li>' + h(words(c)) + '</li>'; }).join('') + '</ul>' : '') +
        '<span class="arrow" aria-hidden="true">›</span></article>';
    }
    var betweenEl = el('between'), betweenList = el('between-list'), betweenToggle = el('between-toggle');
    el('n-between').textContent = B.length;
    el('between-d').textContent = (cov.state ? S.name + ' programs' : 'State programs') +
      ' for local governments that are closed or past their stated deadline, within ' + (R.between_months || 15) +
      ' months of that deadline, with the last deadline and the agency\'s own wording about its cycle. Nothing here forecasts the next round; the change log shows the day one reopens.';
    betweenList.innerHTML = B.map(betweenCard).join('');
    if (!B.length) betweenEl.hidden = true;
    betweenToggle.addEventListener('click', function () { st.between = !st.between; render(); });
    betweenList.addEventListener('click', function (e) {
      if (e.target.closest('a')) return;
      var c = e.target.closest('.card');
      if (c) openDetail(byId[c.getAttribute('data-id')], c.querySelector('button'));
    });

    // ---- pulse, tabs, feed ----
    Array.prototype.forEach.call(document.querySelectorAll('.tile'), function (t) {
      t.addEventListener('click', function () {
        var k = t.getAttribute('data-quick');
        if (k === 'changed') {
          if (st.tab === 'changes' && st.feed === 'status') { st.feed = 'all'; } else { st.tab = 'changes'; st.feed = 'status'; }
        } else if (st.quick === k) {
          st.quick = null; resetSel();
        } else {
          st.quick = k; st.sel = {}; st.q = ''; el('q').value = ''; st.tab = 'programs';
        }
        render();
      });
    });
    var tabs = [el('tab-programs'), el('tab-changes')];
    tabs.forEach(function (t, i) {
      t.addEventListener('click', function () { st.tab = i ? 'changes' : 'programs'; render(); });
      t.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); var n = tabs[(i + 1) % 2]; n.focus(); n.click(); }
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('.chip'), function (c) {
      c.addEventListener('click', function () { st.feed = c.getAttribute('data-feed'); render(); });
    });
    function feedRows() {
      return C.filter(function (c) {
        if (st.feed === 'status') return c.status_flip;
        if (st.feed === 'federal') return c.state == null;
        if (st.feed === 'state') return c.state === S.code;
        return true;
      });
    }
    var feedEl = el('feed');
    feedEl.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-open]');
      if (b) openDetail(byId[b.getAttribute('data-open')], b);
    });

    // ---- detail dialog ----
    var dlg = el('detail'), lastFocus = null, current = null;
    function fact(k, v, cls) { return v == null || v === '' ? '' : '<div><span class="k">' + h(k) + '</span><span class="v ' + (cls || '') + '">' + v + '</span></div>'; }
    function sect(title, body) { return body ? '<div class="sect"><h3>' + h(title) + '</h3>' + body + '</div>' : ''; }
    function detailHtml(p) {
      var listingName = {};
      p.listings.forEach(function (l) { listingName[l.aln] = l.name; });
      var amount = p.amount_min != null && p.amount_max != null ? money(p.amount_min) + ' to ' + money(p.amount_max)
        : p.amount_max != null ? 'up to ' + money(p.amount_max) : p.amount_min != null ? 'from ' + money(p.amount_min) : null;
      var closes = p.closes_at ? h(fmtDate(p.closes_at)) + ' <span class="muted small">(' + h(relDays(p.days_to_close)) + ')</span>' : null;
      var match = p.match_required == null ? null : (p.match_required ? 'Yes' : 'No') + (p.match_pct != null ? ' (' + p.match_pct + '%)' : '');
      var facts =
        fact('Status', h(cap(p.status))) +
        fact('Closes', closes, isSoon(p) ? 'soon' : '') +
        fact('Opens', p.opens_at ? h(fmtDate(p.opens_at)) : null) +
        fact('Reopened last on', p.last_reopened ? h(fmtDate(p.last_reopened, true)) + ' <span class="muted small">(seen by the registry)</span>' : null) +
        fact('Deadline, as written', p.closes_text && p.closes_text.length <= 80 ? h(p.closes_text) : null) +
        fact('Rolling', p.rolling == null ? null : (p.rolling ? 'Yes, applications accepted year-round' : 'No')) +
        fact('Award', amount ? h(amount) : null) +
        fact('Match required', match ? h(match) : null) +
        fact('Funding type', p.funding_type ? h(words(p.funding_type)) : null) +
        fact('Funding source', p.funding_source ? h(p.funding_source === 'pass_through' ? 'Pass-through' : 'Direct') : null) +
        fact('Agency', p.agency ? h(p.agency) + (p.agency_code ? ' <span class="muted small">' + h(p.agency_code) + '</span>' : '') : (p.agency_code ? h(p.agency_code) : null)) +
        fact('Number', p.number ? h(p.number) : null);
      var alns = p.alns.length ? '<ul class="list">' + p.alns.map(function (a) {
        return '<li><span class="aln">' + h(a) + '</span>' + (listingName[a] ? '<span>' + h(listingName[a]) + '</span>' : '<span class="muted small">not in the catalog read</span>') + '</li>';
      }).join('') + '</ul>' : '';
      var trail = 'First seen ' + fmtDate(p.first_seen, true) +
        (p.last_changed.slice(0, 10) !== p.first_seen.slice(0, 10) ? ' · last changed ' + fmtDate(p.last_changed, true) : '') +
        ' · read by the ' + (DATA.coverage.federal.sources.concat(DATA.coverage.state ? DATA.coverage.state.sources : []).filter(function (s) { return s.connector === p.connector; })[0] || { label: p.connector }).label + ' connector';
      return '<div class="row">' + tierPill(p.tier) + statusPill(p.status) + levelPill(p) + badges(p) + '</div>' +
        '<div class="sect"><div class="facts">' + facts + '</div></div>' +
        sect('Deadline, as written by the source', p.closes_text && p.closes_text.length > 80 ? '<div class="verbatim">' + h(p.closes_text) + '</div>' : '') +
        sect('Summary', p.summary ? '<p class="prose">' + h(p.summary) + '</p>' : '') +
        sect('Eligibility, as written by the source', p.eligibility ? '<div class="verbatim">' + h(p.eligibility) + '</div>' : '') +
        sect('Who can apply (tags read from the text)', p.applicant_types.length ? '<ul class="chips">' + p.applicant_types.map(function (t) { return '<li>' + h(words(t)) + '</li>'; }).join('') + '</ul>' : '') +
        sect('Categories', p.categories.length ? '<ul class="chips">' + p.categories.map(function (t) { return '<li>' + h(words(t)) + '</li>'; }).join('') + '</ul>' : '') +
        sect('Assistance Listings this notice cites', alns) +
        '<p class="trail">' + h(trail) + '</p>';
    }
    function openDetail(p, trigger, viaHistory) {
      if (!p) return;
      current = p;
      lastFocus = trigger || document.activeElement;
      el('detail-title').textContent = p.name;
      el('detail-body').innerHTML = detailHtml(p);
      el('detail-source').href = p.source_url;
      el('detail-copied').hidden = true;
      if (!dlg.open) dlg.showModal();
      el('detail-body').scrollTop = 0;
      el('detail-close').focus();
      if (!viaHistory) {
        var hsh = parseHash();
        hsh.p = p.slug;
        history.pushState({ p: p.slug }, '', location.pathname + location.search + '#' + Object.keys(hsh).map(function (k) { return k + '=' + encodeURIComponent(hsh[k]); }).join('&'));
      }
    }
    dlg.addEventListener('close', function () {
      current = null;
      if (parseHash().p) writeHash(null);
      if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
    });
    dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });
    el('detail-close').addEventListener('click', function () { dlg.close(); });
    el('detail-copy').addEventListener('click', function () {
      var url = location.href;
      var done = function () { el('detail-copied').hidden = false; };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, function () { window.prompt('Copy this link', url); });
      else window.prompt('Copy this link', url);
    });
    window.addEventListener('popstate', function () {
      var slug = parseHash().p;
      if (slug && bySlug[slug]) { if (!current || current.slug !== slug) openDetail(bySlug[slug], null, true); }
      else if (dlg.open) dlg.close();
    });

    // ---- toolbar ----
    var qEl = el('q'), qTimer = null;
    qEl.addEventListener('input', function () {
      clearTimeout(qTimer);
      qTimer = setTimeout(function () { st.q = qEl.value.trim(); render(); }, 120);
    });
    el('sort').addEventListener('change', function () { st.sort = el('sort').value; render(); });
    var ft = el('filters-toggle');
    ft.addEventListener('click', function () {
      var open = ft.getAttribute('aria-expanded') === 'true';
      ft.setAttribute('aria-expanded', String(!open));
      facetsEl.hidden = open;
    });
    function syncFacetsVisibility() {
      var wide = window.matchMedia('(min-width: 900px)').matches;
      facetsEl.hidden = !wide && ft.getAttribute('aria-expanded') !== 'true';
    }
    window.addEventListener('resize', syncFacetsVisibility);

    // ---- render everything from state ----
    function render() {
      tabs.forEach(function (t, i) {
        var on = (i === 1) === (st.tab === 'changes');
        t.setAttribute('aria-selected', String(on));
        t.tabIndex = on ? 0 : -1;
      });
      el('panel-programs').hidden = st.tab === 'changes';
      el('panel-changes').hidden = st.tab !== 'changes';
      el('tile-new').setAttribute('aria-pressed', String(st.quick === 'new'));
      el('tile-closing').setAttribute('aria-pressed', String(st.quick === 'closing'));
      el('tile-changed').setAttribute('aria-pressed', String(st.tab === 'changes' && st.feed === 'status'));
      Array.prototype.forEach.call(document.querySelectorAll('.chip'), function (c) { c.setAttribute('aria-pressed', String(c.getAttribute('data-feed') === st.feed)); });
      el('sort').value = st.sort;
      if (qEl.value.trim() !== st.q) qEl.value = st.q;
      updateFacets();
      renderResults();
      betweenToggle.setAttribute('aria-expanded', String(st.between));
      betweenToggle.textContent = st.between ? 'Hide' : 'Show ' + B.length;
      betweenList.hidden = !st.between;
      renderFeed(feedEl, feedRows(), function (c) {
        return c.listed ? '<button type="button" data-open="' + c.program_id + '" aria-haspopup="dialog">' + h(c.name) + '</button>'
          : h(c.name) + ' <a class="small" href="' + h(c.source_url) + '">source</a>';
      });
      writeHash(current ? current.slug : null);
    }

    buildFacets();
    var slug = readHash();
    syncFacetsVisibility();
    render();
    renderFooter(
      '<p><b>Tier</b> is a rule-based reading of the record, not program data: <i>likely</i> means the source text names local governments or the notice carries a municipal category and a targeted eligibility list; <i>possible</i> means local governments are eligible but the signal is weaker. ' +
      DATA.excluded_unlikely + ' further open records that list local governments as eligible are left off this page as unlikely (research notices, requests for information, foreign-facing programs).</p>' +
      '<p><b>Between rounds</b> lists state programs for local governments that are closed or past their stated deadline, within ' + (R.between_months || 15) + ' months of it, so a town can prepare for the next round. The last deadline and the cycle wording are the source\'s; a reopening date appears only once the registry has seen the record reopen. Federal notices are not listed there: a closed notice is a one-off number, not a recurring program.</p>'
    );
    if (slug && bySlug[slug]) openDetail(bySlug[slug], null, true);
  }

  // =====================================================================================
  // Index page
  // =====================================================================================

  function indexPage() {
    var S = DATA.states, F = DATA.federal;
    var withSources = S.filter(function (s) { return s.programs > 0; });
    el('stats').innerHTML =
      '<div class="stat"><span class="v num">' + F.open + '</span><span class="k">federal notices open to local governments</span></div>' +
      '<div class="stat"><span class="v num">' + F.closing_soon + '</span><span class="k">of them close within ' + DATA.rules.closing_days + ' days</span></div>' +
      '<div class="stat"><span class="v num">' + withSources.length + '</span><span class="k">state' + (withSources.length === 1 ? '' : 's') + ' with state agency sources connected</span></div>' +
      '<div class="stat"><span class="v num">' + withSources.reduce(function (a, s) { return a + s.programs; }, 0) + '</span><span class="k">state programs read, ' + withSources.reduce(function (a, s) { return a + s.open; }, 0) + ' open for local governments, ' + withSources.reduce(function (a, s) { return a + (s.between || 0); }, 0) + ' between rounds</span></div>';

    function covText(s) {
      return s.programs > 0
        ? s.name + ': ' + s.agencies + (s.agencies === 1 ? ' agency' : ' agencies') + ', ' + s.programs + ' programs read, ' + s.open + ' open for local governments' + (s.between ? ', ' + s.between + ' between rounds' : '') + (s.last_ok ? ', read ' + fmtDate(s.last_ok) : '') + '. Plus ' + F.open + ' federal notices.'
        : s.name + ': no state sources yet. ' + F.open + ' federal notices.';
    }
    var map = el('map');
    map.innerHTML = S.map(function (s) {
      return '<a class="t' + (s.programs > 0 ? ' src' : '') + (s.open > 0 ? ' open' : '') + '" href="' + s.code.toLowerCase() + '/" style="grid-row:' + (s.row + 1) + ';grid-column:' + (s.col + 1) + '" data-code="' + s.code + '" title="' + h(s.name) + '">' + s.code + '<span class="sr-only">, ' + h(covText(s)) + '</span></a>';
    }).join('');
    var hover = el('hover');
    function show(e) {
      var a = e.target.closest('a.t');
      if (!a) return;
      var s = S.filter(function (x) { return x.code === a.getAttribute('data-code'); })[0];
      hover.innerHTML = '<b>' + h(s.name) + '</b> · ' + h(covText(s).replace(s.name + ': ', ''));
    }
    map.addEventListener('mouseover', show);
    map.addEventListener('focusin', show);

    var sel = el('goto-select');
    sel.innerHTML = S.slice().sort(function (a, b) { return a.name.localeCompare(b.name); }).map(function (s) {
      return '<option value="' + h(s.code) + '">' + h(s.name) + (s.programs > 0 ? ' (state sources)' : '') + '</option>';
    }).join('');
    el('goto').addEventListener('submit', function (e) { e.preventDefault(); location.href = sel.value.toLowerCase() + '/'; });

    renderFeed(el('feed'), DATA.changes, function (c) {
      var href = c.state && c.listed ? c.state.toLowerCase() + '/#p=' + encodeURIComponent(c.slug) : c.source_url;
      return '<a href="' + h(href) + '">' + h(c.name) + '</a>';
    });
    renderFooter('<p>Each state page carries every federal notice plus that state\'s agency programs where connectors exist. Coverage is stated on the page; a state with no sources yet says so.</p>');
  }

  if (PAGE === 'state') statePage(); else indexPage();
})();
