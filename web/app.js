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

  // Plain words for the stored values. The data keeps its own vocabulary (forecasted, unknown, between rounds);
  // these are only the labels a reader sees (decision 2026-11-14, docs/design/ux_review_2026-11.md).
  var STATUS_LABEL = {
    open: 'Open', forecasted: 'Announced', unknown: 'Status not confirmed', closed: 'Closed',
    paused: 'Paused', exhausted: 'Funds used up'
  };
  var STATUS_GLOSS = {
    open: 'The source says applications are open.',
    forecasted: 'The agency has announced it. Applications may not be open yet.',
    unknown: 'The agency\'s page does not say whether it is open. Check the page before planning around it.',
    closed: 'The source says this round is closed.',
    paused: 'The source says this program is paused.',
    exhausted: 'The source says the money for this round is used up.'
  };
  var TIER_LABEL = { likely: 'Likely fit', possible: 'May fit' };
  var TIER_LONG = {
    likely: 'Likely fits local governments: the source names towns, cities or counties as eligible.',
    possible: 'May fit: local governments are eligible, but the source is less specific. Check eligibility.'
  };
  function statusLabel(s) { return STATUS_LABEL[s] || cap(s); }
  function statusTag(s) { return '<span class="tag st-' + h(s) + '">' + h(statusLabel(s)) + '</span>'; }
  function levelLabel(p) { return p.level === 'federal' ? 'Federal' : (p.state ? stateName(p.state) : cap(p.level)); }
  function badges(p) { return (p.is_new ? '<span class="tag new">New</span>' : '') + (p.is_updated ? '<span class="tag upd">Updated</span>' : ''); }
  function sourceLine(src) {
    return h(src.label) + (src.last_ok ? ' read ' + fmtDate(src.last_ok) : ' (no successful read yet)');
  }

  // Display only: an agency name the source writes in capitals reads as shouting, and a leading office code
  // ("69A345 Office of ...") is a portal key, not a name. Nothing is invented; the stored value is unchanged.
  var KEEP_UPPER = { US: 1, USA: 1, USDA: 1, HUD: 1, EPA: 1, FEMA: 1, NASA: 1, NOAA: 1, NIH: 1, NSF: 1, DOE: 1, DOJ: 1,
    DOI: 1, DOT: 1, HHS: 1, ACF: 1, OJP: 1, BJA: 1, NEA: 1, NEH: 1, IMLS: 1, CDC: 1, FAA: 1, FTA: 1, FHWA: 1, NPS: 1,
    BLM: 1, ARC: 1, EDA: 1, SBA: 1, DHS: 1, II: 1, III: 1 };
  var SMALL = { OF: 1, THE: 1, AND: 1, FOR: 1, TO: 1, IN: 1, ON: 1, AT: 1, BY: 1, A: 1, AN: 1, OR: 1 };
  function agencyName(p) {
    var s = p.agency || p.agency_code || '';
    s = s.replace(/^(?=\S*\d)\S+\s+(?=\S)/, '');
    if (/[a-z]/.test(s)) return s;
    var first = true;
    return s.replace(/[A-Z][A-Z']*/g, function (w) {
      var out = KEEP_UPPER[w] ? w : (SMALL[w] && !first) ? w.toLowerCase() : w.charAt(0) + w.slice(1).toLowerCase();
      first = false;
      return out;
    });
  }
  function amountText(p) {
    var lo = p.amount_min, hi = p.amount_max;
    if (lo === 0) lo = null;   // "$0 to $500,000" is a form default, not a floor
    if (lo != null && hi != null && lo !== hi) return money(lo) + ' to ' + money(hi);
    if (hi != null) return 'Up to ' + money(hi);
    if (lo != null) return 'From ' + money(lo);
    return null;
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
        var who = (agencyName({ agency: c.agency }) || c.connector) + ' · ' + (c.level === 'federal' ? 'federal' : (c.state ? stateName(c.state) : c.level));
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
      '<p>Subscribe to this page\'s change log: <a href="feed.xml" type="application/atom+xml">Atom feed</a> · <a href="changes.json" type="application/json">JSON</a>' +
      (PAGE === 'state' ? ' · <a href="' + h(ROOT) + 'feed.xml" type="application/atom+xml">every state (Atom)</a>' : '') +
      '. The feed carries the same rows as the Changes tab; its entry ids never change.</p>' +
      '<p><a href="' + h(DATA.repo_url) + '">Source code and connector docs</a> · <a href="' + h(ROOT) + '">All states</a></p></div>';
  }

  // =====================================================================================
  // State page
  // =====================================================================================

  function statePage() {
    var P = DATA.programs, B = DATA.between || [], U = DATA.unstated || [], C = DATA.changes, R = DATA.rules, S = DATA.state;
    var cov = DATA.coverage;
    P.concat(B, U).forEach(function (p) {
      p._text = [p.name, p.agency, agencyName(p), p.agency_code, p.number, p.summary].join(' ').toLowerCase();
    });
    var byId = {}, bySlug = {};
    P.concat(B, U).forEach(function (p) { byId[p.id] = p; bySlug[p.slug] = p; });

    var FACETS = [
      { key: 'tier', label: 'Fit for a local government', get: function (p) { return [p.tier]; },
        lab: function (v) { return v === 'likely' ? 'Likely fit' : 'May fit: check eligibility'; }, chip: function (v) { return TIER_LABEL[v]; },
        order: ['likely', 'possible'], open: true },
      { key: 'level', label: 'Level', get: function (p) { return [p.level]; }, lab: function (v) { return v === 'state' ? S.name : cap(v); }, open: true },
      { key: 'status', label: 'Status', get: function (p) { return [p.status]; }, lab: statusLabel, open: true, openOnly: true },
      { key: 'deadline', label: 'Deadline', get: function (p) { return [p.closes_at && !p.deadline_placeholder ? 'dated' : p.rolling ? 'rolling' : p.closes_text ? 'text' : 'none']; },
        lab: function (v) { return { dated: 'Has a date', rolling: 'Rolling or year-round', text: 'Described in words', none: 'Not stated' }[v]; },
        order: ['dated', 'rolling', 'text', 'none'], open: true, openOnly: true },
      { key: 'category', label: 'Category', get: function (p) { return p.categories.length ? p.categories : ['none']; },
        lab: function (v) { return v === 'none' ? 'Not stated' : words(v); }, open: true },
      { key: 'funding_type', label: 'Funding type', get: function (p) { return [p.funding_type || 'none']; },
        lab: function (v) { return v === 'none' ? 'Not stated' : words(v); }, open: false },
      { key: 'agency', label: 'Agency', get: function (p) { return [agencyName(p) || 'Not stated']; },
        lab: function (v) { return v; }, open: false, long: true }
    ];
    var DEFAULT_SEL = { tier: ['likely'] };

    var st = { q: '', sort: 'closing', sel: {}, quick: null, tab: 'programs', feed: 'all', between: false, unstated: false };
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
      if (hsh.unstated === '1') st.unstated = true;
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
      if (st.unstated) parts.push('unstated=1');
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
    // `skip` leaves one facet out (for its own counts). `folded` marks the closed and status-not-confirmed groups:
    // the status and deadline facets describe open rows, so they do not filter those groups.
    function termsOf(q) { return q.toLowerCase().split(/\s+/).filter(Boolean); }
    function matches(p, skip, folded) {
      if (st.quick === 'new' && !p.is_new) return false;
      if (st.quick === 'closing' && !isSoon(p)) return false;
      var terms = termsOf(st.q);
      for (var i = 0; i < terms.length; i++) if (p._text.indexOf(terms[i]) < 0) return false;
      for (var j = 0; j < FACETS.length; j++) {
        var f = FACETS[j];
        if (f.key === skip || (folded && f.openOnly)) continue;
        var sel = st.sel[f.key];
        if (!sel || !sel.length) continue;
        var vals = f.get(p), ok = false;
        for (var k = 0; k < vals.length; k++) if (sel.indexOf(vals[k]) >= 0) { ok = true; break; }
        if (!ok) return false;
      }
      return true;
    }
    function closeKey(p) {
      return p.closes_at && !p.deadline_placeholder ? '0' + p.closes_at : p.closes_text ? '1' : p.rolling ? '2' : '3';
    }
    var SORTS = {
      closing: function (a, b) { return closeKey(a).localeCompare(closeKey(b)) || a.name.localeCompare(b.name); },
      newest: function (a, b) { return b.first_seen.localeCompare(a.first_seen) || a.name.localeCompare(b.name); },
      changed: function (a, b) { return b.last_changed.localeCompare(a.last_changed) || a.name.localeCompare(b.name); },
      amount: function (a, b) { return (b.amount_max || -1) - (a.amount_max || -1) || a.name.localeCompare(b.name); },
      name: function (a, b) { return a.name.localeCompare(b.name); }
    };

    // ---- header ----
    var PS = P.filter(function (p) { return p.state; }), PF = P.filter(function (p) { return !p.state; });
    el('title').textContent = S.name + ': funding for local governments';
    el('lede').textContent = cov.state
      ? 'Grants and loans a town, city or county in ' + S.name + ' can apply for. ' + S.name + '\'s own programs come first, then federal notices.'
      : 'Federal grants a town, city or county in ' + S.name + ' can apply for. No ' + S.name + ' agency sources are connected yet.';
    var sources = cov.federal.sources.concat(cov.state ? cov.state.sources : []);
    var lastRead = sources.map(function (s) { return s.last_ok || ''; }).sort().pop();
    el('coverage-sum').innerHTML = (cov.state
      ? 'Read daily from ' + cov.state.agencies + ' ' + h(S.name) + (cov.state.agencies === 1 ? ' agency' : ' agencies') + ' and Grants.gov'
      : 'Read daily from Grants.gov') +
      (lastRead ? ' · last read ' + h(fmtDate(lastRead)) : '') + ' · built ' + h(fmtDate(DATA.generated_at));
    el('coverage-body').innerHTML =
      '<p><b>Federal:</b> ' + cov.federal.open + ' open or announced notices · ' +
      (cov.federal.sources.length ? cov.federal.sources.map(sourceLine).join(' · ') : 'no sources read yet') + '</p>' +
      (cov.state
        ? '<p><b>' + h(S.name) + ':</b> ' + cov.state.programs + ' programs read from ' + cov.state.agencies + (cov.state.agencies === 1 ? ' agency' : ' agencies') +
          '; ' + cov.state.open + ' open or announced for local governments, ' + (cov.state.unstated || 0) + ' with no status stated, ' +
          cov.state.between + ' closed recently.</p><ul class="srcs">' + cov.state.sources.map(function (s) { return '<li>' + sourceLine(s) + '</li>'; }).join('') + '</ul>'
        : '<p><b>' + h(S.name) + ':</b> no state agency sources yet. Federal notices only.</p>');

    var sw = el('state-switch');
    sw.innerHTML = DATA.states.map(function (s) { return '<option value="' + h(s.code) + '"' + (s.code === S.code ? ' selected' : '') + '>' + h(s.name) + '</option>'; }).join('');
    sw.addEventListener('change', function () { location.href = ROOT + sw.value.toLowerCase() + '/'; });

    // ---- pulse tiles ----
    var nNew = P.filter(function (p) { return p.is_new; }).length;
    var nClosing = P.filter(isSoon).length;
    var flips = C.filter(function (c) { return c.status_flip && daysBetween(c.at.slice(0, 10), TODAY) <= R.new_days; });
    el('n-new').textContent = nNew; el('n-closing').textContent = nClosing; el('n-changed').textContent = flips.length;
    el('tile-new').querySelector('.d').textContent = 'first seen in the last ' + R.new_days + ' days';
    el('tile-closing').querySelector('.d').textContent = 'deadline in the next ' + R.closing_days + ' days';
    el('tile-changed').querySelector('.d').textContent = 'opened, closed or announced in the last ' + R.new_days + ' days';
    if (!nNew) el('tile-new').disabled = true;
    if (!nClosing) el('tile-closing').disabled = true;
    if (!flips.length) el('tile-changed').disabled = true;
    el('tab-n-changes').textContent = C.length;
    el('tab-n-programs').textContent = P.length + B.length + U.length;
    if (cov.state) el('chip-state').textContent = S.name; else el('chip-state').hidden = true;

    // ---- facets (built once over the open rows; counts updated in place) ----
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
      }).join('') + '<p class="facet-note">Counts are open and announced programs.</p>';
      facetsEl.addEventListener('change', function (e) {
        var cb = e.target;
        if (cb.type !== 'checkbox') return;
        var sel = st.sel[cb.name] || (st.sel[cb.name] = []);
        var i = sel.indexOf(cb.value);
        if (cb.checked && i < 0) sel.push(cb.value);
        if (!cb.checked && i >= 0) sel.splice(i, 1);
        render();
      });
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
    }

    // ---- the active filters, always visible: the default "Likely fit" is a choice the reader can see and undo ----
    var activeEl = el('active');
    function renderActive(shown) {
      var chips = [];
      if (st.quick) chips.push('<button class="fchip" data-clear="quick" aria-label="Remove filter: ' + (st.quick === 'new' ? 'new this week' : 'closing soon') + '">' + (st.quick === 'new' ? 'New this week' : 'Closing soon') + ' <span aria-hidden="true">×</span></button>');
      if (st.q) chips.push('<button class="fchip" data-clear="q" aria-label="Clear the search">“' + h(st.q) + '” <span aria-hidden="true">×</span></button>');
      FACETS.forEach(function (f) {
        (st.sel[f.key] || []).forEach(function (v) {
          var t = f.chip ? f.chip(v) : f.lab(v);
          chips.push('<button class="fchip" data-facet="' + f.key + '" data-v="' + h(v) + '" aria-label="Remove filter: ' + h(t) + '">' + h(t) + ' <span aria-hidden="true">×</span></button>');
        });
      });
      var total = P.length + B.length + U.length;
      var isDefault = !st.q && !st.quick && FACETS.every(function (f) {
        return (st.sel[f.key] || []).slice().sort().join(',') === (DEFAULT_SEL[f.key] || []).slice().sort().join(',');
      });
      activeEl.innerHTML = '<span class="count num">Showing ' + shown + ' of ' + total + '</span>' +
        (chips.length ? '<span class="lbl">Filtered to</span>' + chips.join('') : '') +
        (chips.length ? '<button class="btn quiet" data-clear="all">' + (isDefault ? 'Show all ' + total : 'Clear all') + '</button>' : '');
    }
    activeEl.addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (!b) return;
      var c = b.getAttribute('data-clear'), fk = b.getAttribute('data-facet');
      if (c === 'all') { st.sel = {}; st.q = ''; st.quick = null; }
      else if (c === 'q') st.q = '';
      else if (c === 'quick') st.quick = null;
      else if (fk) { var sel = st.sel[fk] || []; sel.splice(sel.indexOf(b.getAttribute('data-v')), 1); }
      render();
      el('q').focus();
    });

    // ---- cards: one layout everywhere, status and deadline first, then name, agency, money ----
    function deadlineHtml(p) {
      if (p.closes_at && p.deadline_placeholder) return '<span>' + (p.rolling ? 'Rolling deadline' : 'No deadline stated') + '</span>';
      if (p.closes_at && p.days_to_close != null && p.days_to_close >= 0) {
        return '<span class="' + (isSoon(p) ? 'soon' : '') + '">' + h(cap(relDays(p.days_to_close))) + ', ' + h(fmtDate(p.closes_at)) + '</span>';
      }
      if (p.closes_at) return '<span>Last deadline ' + h(fmtDate(p.closes_at, true)) + (p.days_since_deadline != null ? ' (' + h(agoDays(p.days_since_deadline)) + ')' : '') + '</span>';
      if (p.rolling) return '<span>Rolling deadline</span>';
      if (p.closes_text) return '<span>Deadline in the source\'s words below</span>';
      return '<span class="muted">No deadline stated</span>';
    }
    function agoDays(d) { return d === 1 ? '1 day ago' : d + ' days ago'; }
    function card(p) {
      var amount = amountText(p);
      var facts = [
        '<span>' + (amount ? '<b class="num">' + h(amount) + '</b>' : '<span class="muted">Amount not published</span>') + '</span>'
      ];
      if (p.match_required != null) facts.push('<span>' + (p.match_required ? 'Match required' : 'No match required') + '</span>');
      if (p.funding_type && p.funding_type !== 'grant') facts.push('<span>' + h(words(p.funding_type)) + '</span>');
      if (p.last_reopened) facts.push('<span>Reopened last on ' + h(fmtDate(p.last_reopened, true)) + '</span>');
      var cats = p.categories.slice(0, 3).map(function (c) { return '<li>' + h(words(c)) + '</li>'; }).join('') +
        (p.categories.length > 3 ? '<li class="more">+' + (p.categories.length - 3) + '</li>' : '');
      var quoteText = p.closes_text && (!p.closes_at || p.status !== 'open') && !p.rolling ? p.closes_text : null;
      return '<article class="card st-' + h(p.status) + '" data-id="' + p.id + '">' + dateCol(p) + '<div class="cbody">' +
        '<div class="when">' + statusTag(p.status) + deadlineHtml(p) + '</div>' +
        '<h3><button type="button" data-open="' + p.id + '" data-url="' + h(p.source_url) + '" aria-haspopup="dialog">' + h(p.name) + '</button></h3>' +
        '<p class="meta">' + h(agencyName(p) || 'Agency not stated') + (p.level === 'federal' ? ' · Federal' : '') + ' · <span class="tier-' + h(p.tier) + '">' + h(TIER_LABEL[p.tier] || p.tier) + '</span>' + badges(p) + '</p>' +
        '<div class="facts">' + facts.join('') + '</div>' +
        (quoteText ? '<p class="cycle"><span class="k">The source says:</span> ' + h(quoteText.length > 220 ? quoteText.slice(0, 219) + '…' : quoteText) + '</p>' : '') +
        (cats ? '<ul class="chips" aria-label="Categories">' + cats + '</ul>' : '') +
        '</div></article>';
    }
    // The date column (13.2, direction A): month and day of a stated deadline, or a word when there is none.
    // Decorative for screen readers: the same date is in words on the card's first line.
    function dateCol(p) {
      var dated = p.closes_at && !p.deadline_placeholder;
      if (dated) {
        var past = p.days_to_close != null && p.days_to_close < 0;
        return '<div class="date' + (isSoon(p) ? ' soon' : '') + (past ? ' past' : '') + '" aria-hidden="true"><span class="m">' + MONTHS[+p.closes_at.slice(5, 7) - 1] +
          '</span><span class="dd">' + (+p.closes_at.slice(8, 10)) + '</span>' + (past ? '<span class="nd">closed</span>' : '') + '</div>';
      }
      return '<div class="date" aria-hidden="true"><span class="nd">' + (p.rolling || p.deadline_placeholder ? 'Rolling' : 'No date') + '</span></div>';
    }
    // Under "Closing soonest", the open lists get plain time headings (13.2, borrowed from direction C).
    var BUCKETS = [
      ['Closes within 7 days', function (p) { return p.closes_at && !p.deadline_placeholder && p.days_to_close >= 0 && p.days_to_close <= 7; }],
      ['Closes within 30 days', function (p) { return p.closes_at && !p.deadline_placeholder && p.days_to_close > 7 && p.days_to_close <= R.closing_days; }],
      ['Closes later', function (p) { return p.closes_at && !p.deadline_placeholder && p.days_to_close > R.closing_days; }],
      ['No fixed date', function (p) { return !p.closes_at || p.deadline_placeholder; }]
    ];
    function bucketed(rows) {
      if (st.sort !== 'closing') return rows.map(card).join('');
      return BUCKETS.map(function (b) {
        var r = rows.filter(b[1]);
        return r.length ? '<p class="bucket" role="heading" aria-level="3">' + h(b[0]) + ' · ' + r.length + '</p>' + r.map(card).join('') : '';
      }).join('');
    }

    // ---- the four groups ----
    var resultsEl = el('results');
    resultsEl.tabIndex = -1;
    el('g-state-t').textContent = S.name + ' programs open or announced';
    el('g-unstated-d').textContent = S.name + ' programs for local governments whose agency page states no open or closed status and no date. They are listed so you know they exist; check the agency page before planning around one.';
    el('g-between-d').textContent = S.name + ' programs for local governments that closed in the last ' + (R.between_months || 15) +
      ' months, with the last deadline and the agency\'s own words about its cycle. Use them to prepare for the next round. Nothing here predicts a date.';
    function groupHtml(rows, empty) { return rows.length ? bucketed(rows) : '<p class="empty">' + empty + '</p>'; }
    function renderGroups() {
      var sort = SORTS[st.sort] || SORTS.closing;
      var rs = PS.filter(function (p) { return matches(p, null); }).sort(sort);
      var rf = PF.filter(function (p) { return matches(p, null); }).sort(sort);
      var ru = U.filter(function (p) { return matches(p, null, true); }).sort(st.sort === 'closing' ? function () { return 0; } : sort);
      var rb = B.filter(function (p) { return matches(p, null, true); }).sort(st.sort === 'closing' ? function () { return 0; } : sort);
      el('g-state-n').textContent = rs.length;
      el('g-federal-n').textContent = rf.length;
      el('g-unstated-n').textContent = ru.length;
      el('g-between-n').textContent = rb.length;

      var stateEmpty;
      if (!cov.state) stateEmpty = 'No ' + h(S.name) + ' agency sources are connected yet, so this page lists federal notices only.';
      else if (!PS.length) stateEmpty = 'No ' + h(S.name) + ' programs are open or announced right now.' +
        (ru.length || rb.length ? ' ' + [ru.length ? ru.length + (ru.length === 1 ? ' has' : ' have') + ' no status on the agency\'s page' : '', rb.length ? rb.length + ' closed recently' : ''].filter(Boolean).join(' and ') + ': see below.' : '');
      else stateEmpty = 'No ' + h(S.name) + ' programs match these filters.';
      el('list-state').innerHTML = groupHtml(rs, stateEmpty);
      el('g-state-d').hidden = true;
      el('list-federal').innerHTML = groupHtml(rf, 'No federal notices match these filters.');

      el('g-unstated').hidden = !ru.length;
      el('g-between').hidden = !rb.length;
      el('list-unstated').innerHTML = ru.map(card).join('');
      el('list-between').innerHTML = rb.map(card).join('');
      [['unstated', 'unstated-toggle', 'list-unstated', ru.length], ['between', 'between-toggle', 'list-between', rb.length]].forEach(function (g) {
        var open = st[g[0]], t = el(g[1]);
        t.setAttribute('aria-expanded', String(open));
        t.textContent = open ? 'Hide' : 'Show ' + g[3];
        el(g[2]).hidden = !open;
      });
      renderActive(rs.length + rf.length + ru.length + rb.length);
    }
    el('unstated-toggle').addEventListener('click', function () { st.unstated = !st.unstated; render(); });
    el('between-toggle').addEventListener('click', function () { st.between = !st.between; render(); });
    resultsEl.addEventListener('click', function (e) {
      if (e.target.closest('a')) return;
      var c = e.target.closest('.card');
      if (c) openDetail(byId[c.getAttribute('data-id')], c.querySelector('h3 button'));
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

    // ---- detail dialog: five answers first, then the source's own words ----
    var dlg = el('detail'), lastFocus = null, current = null;
    function fact(k, v, cls) { return v == null || v === '' ? '' : '<div><span class="k">' + h(k) + '</span><span class="v ' + (cls || '') + '">' + v + '</span></div>'; }
    function sect(title, body) { return body ? '<div class="sect"><h3>' + h(title) + '</h3>' + body + '</div>' : ''; }
    function host(url) { var m = /^https?:\/\/([^/]+)/.exec(url || ''); return m ? m[1].replace(/^www\./, '') : 'the agency\'s site'; }
    var NOT_PUBLISHED = '<span class="muted">Not published: see the agency page</span>';
    function detailHtml(p) {
      var listingName = {};
      p.listings.forEach(function (l) { listingName[l.aln] = l.name; });
      var amount = amountText(p);
      var closes;
      if (p.closes_at && p.deadline_placeholder) closes = p.rolling ? 'Rolling deadline' : 'No deadline stated';
      else if (p.closes_at) closes = h(fmtDate(p.closes_at, true)) + ' <span class="muted small">(' + h(relDays(p.days_to_close)) + ')</span>';
      else if (p.rolling) closes = 'Rolling deadline';
      else if (p.closes_text && p.closes_text.length <= 120) closes = '“' + h(p.closes_text) + '”';
      else if (p.closes_text) closes = 'In the source\'s words, below';
      else closes = NOT_PUBLISHED;
      var who = p.applicant_types.length ? h(p.applicant_types.map(words).join(', ')) + ' <span class="muted small">(read from the source\'s text)</span>' : NOT_PUBLISHED;
      var answers =
        '<dl class="answers">' +
        '<div><dt>Is it open?</dt><dd><b>' + h(statusLabel(p.status)) + '.</b> ' + h(STATUS_GLOSS[p.status] || '') + '</dd></div>' +
        '<div><dt>When does it close?</dt><dd class="' + (isSoon(p) ? 'soon' : '') + '">' + closes + '</dd></div>' +
        '<div><dt>How much?</dt><dd>' + (amount ? h(amount) : NOT_PUBLISHED) + '</dd></div>' +
        '<div><dt>Who can apply?</dt><dd>' + who + '</dd></div>' +
        '<div><dt>Where do I apply?</dt><dd><a href="' + h(p.source_url) + '" target="_blank" rel="noopener">On ' + h(host(p.source_url)) + '</a></dd></div>' +
        '</dl>';
      var match = p.match_required == null ? null : (p.match_required ? 'Yes' : 'No') + (p.match_pct != null ? ' (' + p.match_pct + '%)' : '');
      var facts =
        fact('Fit', h(TIER_LONG[p.tier] || p.tier)) +
        fact('Match required', match ? h(match) : null) +
        fact('Opens', p.opens_at ? h(fmtDate(p.opens_at, true)) : null) +
        fact('Reopened last on', p.last_reopened ? h(fmtDate(p.last_reopened, true)) + ' <span class="muted small">(seen by the registry)</span>' : null) +
        fact('Funding type', p.funding_type ? h(words(p.funding_type)) : null) +
        fact('Where the money comes from', p.funding_source ? (p.funding_source === 'pass_through' ? 'Federal money passed through the state' : 'Direct from the agency') : null) +
        fact('Agency', agencyName(p) ? h(agencyName(p)) : null) +
        fact('Number', p.number ? h(p.number) : null);
      var alns = p.alns.length ? '<ul class="list">' + p.alns.map(function (a) {
        return '<li><span class="aln">' + h(a) + '</span>' + (listingName[a] ? '<span>' + h(listingName[a]) + '</span>' : '<span class="muted small">not in the catalog read</span>') + '</li>';
      }).join('') + '</ul>' : '';
      var trail = 'First seen ' + fmtDate(p.first_seen, true) +
        (p.last_changed.slice(0, 10) !== p.first_seen.slice(0, 10) ? ' · last changed ' + fmtDate(p.last_changed, true) : '') +
        ' · read from ' + (sources.filter(function (s) { return s.connector === p.connector; })[0] || { label: p.connector }).label;
      return '<div class="when">' + statusTag(p.status) + '<span class="muted">' + h(levelLabel(p)) + '</span>' + badges(p) + '</div>' +
        answers +
        sect('Deadline, as written by the source', p.closes_text && p.closes_text.length > 120 ? '<div class="verbatim">' + h(p.closes_text) + '</div>' : '') +
        sect('Eligibility, as written by the source', p.eligibility ? '<div class="verbatim">' + h(p.eligibility) + '</div>' : '') +
        sect('Summary', p.summary ? '<p class="prose">' + h(p.summary) + '</p>' : '') +
        sect('More details', '<div class="facts">' + facts + '</div>') +
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
      renderGroups();
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
      '<p><b>Likely fit</b> and <b>May fit</b> are rule-based readings of each record, not program data: <i>likely</i> means the source text names local governments or the notice carries a municipal category and a targeted eligibility list; <i>may fit</i> means local governments are eligible but the signal is weaker. ' +
      DATA.excluded_unlikely + ' further open records that list local governments as eligible are left off this page as unlikely (research notices, requests for information, foreign-facing programs).</p>' +
      '<p><b>Announced</b> is what Grants.gov and state portals call forecasted: the agency has said the program is coming. <b>Status not confirmed</b> means the agency\'s page states no status and no date; the page is listed, not judged. <b>Closed recently</b> lists state programs for local governments that closed within ' + (R.between_months || 15) + ' months, so a town can prepare for the next round. The last deadline and the cycle wording are the source\'s; a reopening date appears only once the registry has seen the record reopen. Federal notices are not listed there: a closed notice is a one-off number, not a recurring program.</p>'
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
      '<div class="stat"><span class="v num">' + withSources.reduce(function (a, s) { return a + s.programs; }, 0) + '</span><span class="k">state programs read, ' + withSources.reduce(function (a, s) { return a + s.open; }, 0) + ' open or announced for local governments, ' + withSources.reduce(function (a, s) { return a + (s.between || 0); }, 0) + ' closed recently</span></div>';

    function covText(s) {
      return s.programs > 0
        ? s.name + ': ' + s.agencies + (s.agencies === 1 ? ' agency' : ' agencies') + ', ' + s.programs + ' programs read, ' + s.open + ' open or announced for local governments' + (s.unstated ? ', ' + s.unstated + ' with no status stated' : '') + (s.between ? ', ' + s.between + ' closed recently' : '') + (s.last_ok ? ', read ' + fmtDate(s.last_ok) : '') + '. Plus ' + F.open + ' federal notices.'
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
