/* Funding Atlas page script. Shared by every page; written beside the pages as app.js by scripts/build_site.py.
   Plain browser JavaScript, no build step, no network: everything comes from the JSON block in the page.
   Nothing here invents data. A null stays blank; the only computed things are counts, sort orders and the
   wording of dates relative to the build date. */
(function () {
  'use strict';

  var DATA = JSON.parse(document.getElementById('data').textContent);
  var PAGE = document.body.getAttribute('data-page');
  var ROOT = PAGE === 'program' ? '../../' : PAGE === 'state' || PAGE === 'about' ? '../' : '';
  var TODAY = DATA.generated_at.slice(0, 10);
  // State pages carry only their own rows; federal notices come once from federal.js (same origin, cached).
  var FEDERAL_LOADED = !!window.FA_FEDERAL;
  if (PAGE === 'state' && FEDERAL_LOADED) {
    DATA.programs = DATA.programs.concat(window.FA_FEDERAL.programs);
    DATA.changes = (DATA.changes || []).concat(window.FA_FEDERAL.changes).sort(function (a, b) { return b.at.localeCompare(a.at) || b.id - a.id; });
  }

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
  // Topic lines (13.17, as words since 13.21): the eleven categories folded into three. A card names its line in a
  // word with a coloured dot, so the colour never carries the meaning alone; "other or not stated" shows nothing.
  // A program in several shows the first line that matches, in this order.
  var TOPIC_LINES = [
    { key: 'env', word: 'Environment', cats: ['water', 'energy', 'parks'] },
    { key: 'inf', word: 'Infrastructure', cats: ['transportation', 'infrastructure', 'broadband'] },
    { key: 'com', word: 'Community', cats: ['housing', 'health', 'workforce', 'public_safety'] }
  ];
  function topicLine(p) {
    for (var i = 0; i < TOPIC_LINES.length; i++) {
      if ((p.categories || []).some(function (c) { return TOPIC_LINES[i].cats.indexOf(c) >= 0; })) return TOPIC_LINES[i];
    }
    return null;
  }
  function topicWord(p) {
    var L = topicLine(p);
    return L ? ' · <span class="tw t-' + L.key + '"><i aria-hidden="true"></i>' + L.word + '</span>' : '';
  }
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
  // Display only: a federal notice whose name opens with its own number ("F26AS00083 Aquatic Invasive ...") shows
  // the name without it; the number has its own line in the detail panel and stays in search. Stored value unchanged.
  function programName(p) {
    var n = p.name || '', num = p.number;
    if (!num || n.length <= num.length || n.indexOf(num) !== 0) return n;
    var rest = n.slice(num.length).replace(/^[\s:.\-\u2013\u2014]+/, '');
    return /^[\s:.\-\u2013\u2014]/.test(n.charAt(num.length)) && rest ? rest : n;
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

  // ---- what changed, in words (13.12): a word-level diff of the wording fields the change log stores in full ----
  var TEXT_FIELDS = { closes_at_text: 'Deadline wording', eligibility_text: 'Eligibility', summary: 'Summary', name: 'Name' };
  function wordDiff(a, b) {
    var x = String(a || '').split(/(\s+)/), y = String(b || '').split(/(\s+)/);
    if (x.length * y.length > 360000) return null;    // too long to diff in the browser: show both in full instead
    var n = x.length, m = y.length, L = [], i, j;
    for (i = 0; i <= n; i++) { L.push(new Uint16Array(m + 1)); }
    for (i = n - 1; i >= 0; i--) for (j = m - 1; j >= 0; j--) L[i][j] = x[i] === y[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    var out = '', del = '', ins = '';
    function flush() { if (del) out += '<del>' + h(del) + '</del>'; if (ins) out += '<ins>' + h(ins) + '</ins>'; del = ins = ''; }
    i = 0; j = 0;
    while (i < n && j < m) {
      if (x[i] === y[j]) { flush(); out += h(x[i]); i++; j++; }
      else if (L[i + 1][j] >= L[i][j + 1]) { del += x[i++]; }
      else { ins += y[j++]; }
    }
    while (i < n) del += x[i++];
    while (j < m) ins += y[j++];
    flush();
    return out;
  }
  function diffHtml(c) {
    var parts = c.fields.filter(function (f) { return TEXT_FIELDS[f.field] && (f.old || f.new); }).map(function (f) {
      var d = wordDiff(f.old, f.new);
      return '<div class="diff-f"><span class="diff-k">' + TEXT_FIELDS[f.field] + '</span>' +
        (d != null ? '<p class="diff-t">' + d + '</p>'
          : '<p class="diff-t"><span class="muted small">Before:</span> <del>' + h(f.old || '(blank)') + '</del></p><p class="diff-t"><span class="muted small">After:</span> <ins>' + h(f.new || '(blank)') + '</ins></p>') + '</div>';
    });
    return parts.length ? '<details class="diff"><summary>Show what changed in the wording</summary>' + parts.join('') + '</details>' : '';
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
          (c.cause === 'code' ? '<div class="cause">After a change to how the registry reads this source: the agency may not have changed anything.</div>' : '') +
          (c.type === 'changed' ? diffHtml(c) : '') +
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
      (PAGE === 'program' ? '<p>Subscribe to this program\'s changes: <a href="' + h(ROOT + feedPath(DATA.program.slug)) + '" type="application/atom+xml">Atom feed</a> · every source: <a href="' + h(ROOT) + 'feed.xml" type="application/atom+xml">Atom feed</a>' :
      PAGE === 'about' ? '<p>Subscribe to the change log of every source: <a href="' + h(ROOT) + 'feed.xml" type="application/atom+xml">Atom feed</a> · <a href="' + h(ROOT) + 'changes.json" type="application/json">JSON</a>' :
      '<p>Subscribe to this page\'s change log: <a href="feed.xml" type="application/atom+xml">Atom feed</a> · <a href="changes.json" type="application/json">JSON</a>') +
      (PAGE === 'state' ? ' · <a href="' + h(ROOT) + 'feed.xml" type="application/atom+xml">every state (Atom)</a>' : '') +
      (PAGE === 'state' ? '. The feed carries the same rows as the Changes tab; its entry ids never change.</p>' : '. Feed entry ids never change.</p>') +
      '<p><a href="' + h(DATA.repo_url) + '">Source code and connector docs</a> · <a href="' + h(ROOT) + '">All states</a> · <a href="' + h(ROOT) + 'about/">About the data</a></p></div>';
  }

  // =====================================================================================
  // Charts (13.14): plain SVG, one shared tooltip, except "what sources state", which is HTML squares. One colour rule
  // (2026-11-27): hue says who (--s-fed federal, --s-state and its --o ramp state), fill says whether the source stated
  // it (solid stated, hatched not), and everything else is ink. Every chart has a legend or direct labels and a table.
  // =====================================================================================

  var tipEl = null;
  function tip(e, html) {
    if (!tipEl) { tipEl = document.createElement('div'); tipEl.className = 'ctip'; tipEl.setAttribute('role', 'tooltip'); document.body.appendChild(tipEl); }
    if (!html) { tipEl.hidden = true; return; }
    tipEl.innerHTML = html; tipEl.hidden = false;
    var x = Math.min(e.clientX + 14, window.innerWidth - tipEl.offsetWidth - 8), y = e.clientY + 14;
    if (y + tipEl.offsetHeight > window.innerHeight) y = e.clientY - tipEl.offsetHeight - 10;
    tipEl.style.left = x + 'px'; tipEl.style.top = y + 'px';
  }
  function wireTips(svgEl) {
    svgEl.addEventListener('mousemove', function (e) { var t = e.target.closest('[data-tip]'); tip(e, t ? t.getAttribute('data-tip') : null); });
    // after a tap the browser sends a mouseleave of its own; that one must not put the note away again
    var touched = 0;
    svgEl.addEventListener('touchstart', function () { touched = Date.now(); }, { passive: true });
    svgEl.addEventListener('mouseleave', function () { if (Date.now() - touched > 800) tip(null, null); });
    // a tap shows the same note (a phone has no hover); a tap anywhere else puts it away
    svgEl.addEventListener('click', function (e) { var t = e.target.closest('[data-tip]'); tip(e, t ? t.getAttribute('data-tip') : null); e.stopPropagation(); });
  }
  document.addEventListener('click', function () { if (tipEl) tipEl.hidden = true; });
  // Charts are drawn at the width they are shown at (2026-11-26), so their 12px labels stay 12px on a phone; under
  // 560px each chart has a narrow layout (labels above the marks, fewer ticks). Redrawn when the width changes.
  function chartW(svgEl, max) { var c = svgEl.parentNode, w = c ? c.clientWidth : 0; return Math.max(280, Math.min(max, w || max)); }
  function onWidthChange(fn) {
    var last = window.innerWidth, timer = null;
    window.addEventListener('resize', function () {
      if (window.innerWidth === last) return;
      last = window.innerWidth; clearTimeout(timer); timer = setTimeout(fn, 150);
    });
  }
  function ctable(head, rows) {
    return '<table class="ctable"><thead><tr>' + head.map(function (x) { return '<th scope="col">' + h(x) + '</th>'; }).join('') + '</tr></thead><tbody>' +
      rows.map(function (r) { return '<tr>' + r.map(function (x, i) { return i ? '<td>' + h(x) + '</td>' : '<th scope="row">' + h(x) + '</th>'; }).join('') + '</tr>'; }).join('') + '</tbody></table>';
  }
  function drawSvg(svgEl, w, hh, inner) {
    svgEl.setAttribute('viewBox', '0 0 ' + w + ' ' + hh); svgEl.setAttribute('width', w);
    svgEl.innerHTML = inner;
    if (!svgEl._tips) { wireTips(svgEl); svgEl._tips = true; }
  }
  function barPath(x, y, w, hh, roundTop) {      // 4px rounded data end, anchored to the baseline
    if (hh <= 0) return '';
    var r = Math.min(4, w / 2, hh);
    return roundTop ? 'M' + x + ',' + (y + hh) + 'V' + (y + r) + 'Q' + x + ',' + y + ' ' + (x + r) + ',' + y + 'H' + (x + w - r) + 'Q' + (x + w) + ',' + y + ' ' + (x + w) + ',' + (y + r) + 'V' + (y + hh) + 'Z'
                    : 'M' + x + ',' + y + 'H' + (x + w) + 'V' + (y + hh) + 'H' + x + 'Z';
  }
  function shortMoney(n) { return n >= 1e9 ? '$' + (n / 1e9) + 'B' : n >= 1e6 ? '$' + (n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace(/\.0$/, '') + 'M' : n >= 1e3 ? '$' + Math.round(n / 1e3) + 'K' : '$' + n; }
  function isoAdd(iso, n) { return new Date(Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10) + n)).toISOString().slice(0, 10); }

  // deadlines: [[state|null, closes_at, placeholder], ...] -> weekly stacked bars, federal below state
  function chartRunway(svgEl, deadlines, weeks, compact) {
    var W = [], i;
    for (i = 0; i < weeks; i++) W.push({ start: isoAdd(TODAY, 7 * i), f: 0, s: 0 });
    var later = 0;
    deadlines.forEach(function (d) {
      if (!d[1] || d[2]) return;
      var k = Math.floor(daysBetween(TODAY, d[1].slice(0, 10)) / 7);
      if (k < 0) return;
      if (k >= weeks) { later++; return; }
      if (d[0]) W[k].s++; else W[k].f++;
    });
    var w = chartW(svgEl, compact ? 760 : 900), narrow = w < 560, hh = compact ? 150 : narrow ? 210 : 250, L = 34, R = 8, T = 10, B = 30, bw = (w - L - R) / weeks, max = 1;
    W.forEach(function (x) { max = Math.max(max, x.f + x.s); });
    var step = max > 20 ? 10 : 5, top = Math.ceil(max / step) * step, y = function (v) { return T + (hh - T - B) * (1 - v / top); }, g = '';
    for (var v = 0; v <= top; v += step) g += '<line class="cgrid" x1="' + L + '" x2="' + (w - R) + '" y1="' + y(v) + '" y2="' + y(v) + '"/><text class="ctext" x="' + (L - 6) + '" y="' + (y(v) + 4) + '" text-anchor="end">' + v + '</text>';
    W.forEach(function (x, j) {
      var x0 = L + j * bw + 1.5, bwi = Math.max(2, bw - 3), base = y(0), hf = base - y(x.f), hs = base - y(x.s);
      var t = 'Week of ' + fmtDate(x.start) + ': ' + (x.f + x.s) + ' deadlines (' + x.s + ' state, ' + x.f + ' federal)';
      g += '<g data-tip="' + h(t) + '"><rect x="' + (L + j * bw) + '" y="' + T + '" width="' + bw + '" height="' + (hh - T - B) + '" fill="transparent"/>';
      if (x.f) g += '<path class="m-fed" d="' + barPath(x0, base - hf, bwi, hf, !x.s) + '"/>';
      if (x.s) g += '<path class="m-st" d="' + barPath(x0, base - hf - hs - (x.f ? 2 : 0), bwi, hs, true) + '"/>';
      g += '</g>';
      if (j % (narrow ? 8 : 4) === 0 && !(narrow && j > weeks - 3)) g += '<text class="ctext" x="' + (L + j * bw + bw / 2) + '" y="' + (hh - B + 18) + '" text-anchor="middle">' + fmtDate(x.start) + '</text>';
    });
    g += '<line class="caxis" x1="' + L + '" x2="' + (w - R) + '" y1="' + y(0) + '" y2="' + y(0) + '"/>';
    drawSvg(svgEl, w, hh, g);
    return { later: later, total: W.reduce(function (a, x) { return a + x.f + x.s; }, 0), week1: W[0].f + W[0].s, weeks: W };
  }

  // rows: [[label, [12 counts]], ...] -> heatmap, each row shaded by its own share
  var RAMP = ['var(--o1)', 'var(--o2)', 'var(--o3)', 'var(--o4)', 'var(--o5)', 'var(--o6)', 'var(--o7)'];   // state data, so the state's hue (2026-11-27)
  function chartSeason(svgEl, rows, compact) {
    var w = chartW(svgEl, compact ? 760 : 900), narrow = w < 560, L = compact ? 10 : narrow ? 92 : 100, T = 22, cw = (w - L - 8) / 12, ch = compact ? 26 : 30, hh = T + rows.length * (ch + 2) + 4, g = '';
    MONTHS.forEach(function (m, i) { g += '<text class="ctext" x="' + (L + i * cw + cw / 2) + '" y="15" text-anchor="middle">' + (narrow && !compact ? m.charAt(0) : m) + '</text>'; });
    rows.forEach(function (r, ri) {
      var tot = r[1].reduce(function (a, b) { return a + b; }, 0), yy = T + ri * (ch + 2);
      if (!compact) g += '<text class="ctext clab" x="' + (L - 10) + '" y="' + (yy + ch / 2 + 4) + '" text-anchor="end">' + h(r[0]) + '</text>';
      r[1].forEach(function (v, i) {
        var share = tot ? v / tot : 0, k = v ? Math.min(6, Math.floor(share / 0.3 * 7)) : -1;
        g += '<rect data-tip="' + h(r[0] + ', ' + MONTHS[i] + ': ' + v + ' of ' + tot + ' deadlines (' + Math.round(share * 100) + '%)') + '" x="' + (L + i * cw + 1) + '" y="' + yy + '" width="' + (cw - 2) + '" height="' + ch + '" rx="3" fill="' + (k < 0 ? 'var(--soft)' : RAMP[k]) + '"/>';
        if (compact && v) g += '<text class="ctext cval' + (k >= 4 ? ' inv' : '') + '" x="' + (L + i * cw + cw / 2) + '" y="' + (yy + ch / 2 + 4) + '" text-anchor="middle">' + v + '</text>';
      });
    });
    drawSvg(svgEl, w, hh, g);
  }
  function seasonLegend() {
    return '<span><i class="sw" style="background:var(--soft)"></i>none</span><span>small share</span>' + RAMP.map(function (c) { return '<i class="sw" style="background:' + c + ';margin:0 1px"></i>'; }).join('') + '<span>26% or more of the row</span>';
  }

  // how a source is read, in the words the index's "what the states publish" block and About's chart both use
  var KIND_ROW = { federal: 'Federal notices', portal: 'State portals', portal_agencies: 'Portal and agency pages', agencies: 'Agency pages', directory: 'Directories' };
  function share(v, n) { return n ? Math.round(100 * v / n) : 0; }
  // "What sources state" (2026-11-27, Saj's pick A2): a hundred squares per kind of source and field, solid for one in
  // a hundred programs whose source states it, hatched for the rest; blue federal, orange state. HTML, not SVG, so its
  // text follows the reader's settings. Each state's own shares are in the table.
  // The atlas (2026-11-27, Saj's pick H1 for the entry piece): every state on the tile map. With `kinds` false, a read
  // state's tile fills from the bottom to the share of its programs whose source states a deadline (solid, the state's
  // hue) and is hatched above; a directory is all hatched; a state that refuses readers or needs a browser script is
  // dashed; a state with no list is an empty outline; DC is out of scope. With `kinds` true the fill says how the state
  // is read instead. Tiles are buttons: a tap or Enter puts the state's sentence in `noteEl`, a live region.
  var READ_AS = { portal: 'a state grants portal', agencies: 'its agencies\' own pages', portal_agencies: 'a state portal and its agencies\' pages', directory: 'a state directory' };
  function atlasClass(s, kinds) {
    if (s.code === 'DC') return 't-oos';
    if (s.kind === 'blocked' || s.kind === 'login' || s.kind === 'stopped') return 't-wall';
    if (s.kind === 'directory') return 't-dir';
    if (READ_AS[s.kind]) return kinds ? 't-k k-' + s.kind : s.n ? 't-read' : 't-none';
    return 't-none';
  }
  function atlasNote(s) {
    if (s.n) return s.name + ': ' + s.date.toLocaleString('en-US') + ' of ' + s.n.toLocaleString('en-US') + ' programs open to local governments state a deadline (' + share(s.date, s.n) + ' in 100). Read from ' + READ_AS[s.kind] + '.';
    if (s.kind === 'directory') return s.name + ': a state directory of ' + s.listed.toLocaleString('en-US') + ' programs that states no status or dates.';
    if (READ_AS[s.kind]) return s.name + ': read from ' + READ_AS[s.kind] + '; none of its programs is open to local governments.';
    return s.name + ': ' + (s.note || 'no state source read.');
  }
  function drawAtlas(el, noteEl, atlas, fed, kinds) {
    var hh = '<div class="atlas">' + atlas.map(function (s, i) {
      var cls = atlasClass(s, kinds), p = share(s.date, s.n), fill = !kinds && cls === 't-read';
      return '<button type="button" class="tile ' + cls + '" style="grid-row:' + (s.row + 1) + ';grid-column:' + (s.col + 1) + '" data-i="' + i + '" aria-label="' + h(atlasNote(s)) + '">' +
        (fill ? '<span class="lv" style="height:' + p + '%"></span>' : '') + '<span class="cd">' + s.code + '</span>' + (fill ? '<span class="pc">' + p + '</span>' : '') + '</button>';
    }).join('') + '</div>';
    if (!kinds && fed) {
      var fp = share(fed.date_stated, fed.n);
      hh = '<div class="atlas-wrap">' + hh + '<div class="atlas-fed"><span class="tile t-read t-fed" aria-hidden="true"><span class="lv" style="height:' + fp + '%"></span><span class="cd">US</span><span class="pc">' + fp + '</span></span>' +
        '<span>Federal notices open now, for comparison: ' + fp + ' in 100 state a deadline (' + fed.date_stated + ' of ' + fed.n + ').</span></div></div>';
    }
    el.innerHTML = hh;
    el.querySelectorAll('.tile[data-i]').forEach(function (t) {
      t.addEventListener('click', function () {
        el.querySelectorAll('.tile.on').forEach(function (x) { x.classList.remove('on'); x.setAttribute('aria-pressed', 'false'); });
        t.classList.add('on'); t.setAttribute('aria-pressed', 'true');
        noteEl.textContent = atlasNote(atlas[+t.getAttribute('data-i')]);
      });
    });
  }
  function chartStated(el, tableEl, kinds, rows) {
    var FIELDS = [['status', 'a status'], ['date', 'a deadline'], ['amount', 'an amount']];
    el.innerHTML = kinds.map(function (k) {
      var fed = k.kind === 'federal', name = KIND_ROW[k.kind] || k.kind;
      return '<div class="wf-group ' + (fed ? 'fed' : 'st') + '"><div class="wf-name"><h3>' + h(name) + '</h3><small class="num">' +
        k.n.toLocaleString('en-US') + ' programs' + (fed ? ', open now' : ' · ' + k.states + (k.states === 1 ? ' state' : ' states')) + '</small></div>' +
        FIELDS.map(function (f) {
          var v = k[f[0]], p = share(v, k.n), cells = '';
          for (var i = 0; i < 100; i++) cells += '<i' + (i < p ? ' class="on"' : '') + '></i>';
          return '<div class="wf"><div class="wf-grid" role="img" aria-label="' + h(name + ': ' + p + ' in 100 state ' + f[1] + ', ' + v + ' of ' + k.n) + '">' + cells + '</div>' +
            '<p><b class="num">' + p + '</b> in 100 state ' + f[1] + '<span class="num">' + v.toLocaleString('en-US') + ' of ' + k.n.toLocaleString('en-US') + '</span></p></div>';
        }).join('') + '</div>';
    }).join('');
    var order = { federal: 0, portal: 1, portal_agencies: 2, agencies: 3, directory: 4 };
    if (tableEl) tableEl.innerHTML = ctable(['Source', 'Read from', 'Programs', 'States a status', 'States a deadline', 'States an amount'],
      rows.slice().sort(function (a, b) { return (order[a.kind] - order[b.kind]) || (b.n - a.n); }).map(function (r) {
        return [r.state === 'US' ? 'Federal, open now' : stateName(r.state), KIND_ROW[r.kind] || r.kind, r.n,
          share(r.status_stated, r.n) + '%', share(r.date_stated, r.n) + '%', share(r.amount_stated, r.n) + '%']; }));
  }

  // flips: [{old_status, new_status, cause, n, first_at, last_at}] -> one bar per change, split by cause
  function chartFlips(svgEl, flips) {
    var pairs = {}, order = [];
    flips.forEach(function (f) {
      var k = (f.old_status || 'unknown') + '>' + (f.new_status || 'unknown');
      if (!pairs[k]) { pairs[k] = { o: f.old_status || 'unknown', n: f.new_status || 'unknown', src: 0, code: 0, other: 0, a: f.first_at, b: f.last_at }; order.push(k); }
      var p = pairs[k];
      if (f.cause === 'code') p.code += f.n; else if (f.cause === 'source') p.src += f.n; else p.other += f.n;
      if (f.first_at < p.a) p.a = f.first_at; if (f.last_at > p.b) p.b = f.last_at;
    });
    var rows = order.map(function (k) { return pairs[k]; }).sort(function (a, b) { return (b.src + b.code + b.other) - (a.src + a.code + a.other); });
    var w = chartW(svgEl, 900), narrow = w < 560, L = narrow ? 8 : 250, R = narrow ? 34 : 60, rh = narrow ? 46 : 30, off = narrow ? 18 : 0, hh = rows.length * rh + 6, max = 1, g = '';
    rows.forEach(function (r) { max = Math.max(max, r.src + r.code + r.other); });
    var x = function (v) { return L + (w - L - R) * v / max; };
    rows.forEach(function (r, i) {
      var top = i * rh + 3, yy = top + off, lab = statusLabel(r.o) + ' → ' + statusLabel(r.n), tot = r.src + r.code + r.other;
      var reopen = (r.o === 'closed' || r.o === 'exhausted') && (r.n === 'open' || r.n === 'forecasted');
      g += narrow ? '<text class="ctext clab" x="' + L + '" y="' + (top + 13) + '">' + h(lab) + (reopen ? ' (reopened)' : '') + '</text>'
        : '<text class="ctext clab" x="' + (L - 12) + '" y="' + (yy + 17) + '" text-anchor="end">' + h(lab) + (reopen ? ' (reopened)' : '') + '</text>';
      var t = lab + ': ' + tot + ' (' + r.src + ' from the source' + (r.code ? ', ' + r.code + ' after a code change' : '') + (r.other ? ', ' + r.other + ' unlabelled' : '') + '), ' + fmtDate(r.a, true) + ' to ' + fmtDate(r.b, true);
      g += '<g data-tip="' + h(t) + '"><rect x="' + L + '" y="' + yy + '" width="' + (w - L - R) + '" height="26" fill="transparent"/>';
      var x0 = L;
      [['src', 'm-ink'], ['other', 'm-ink'], ['code', 'm-maybe']].forEach(function (seg) {
        var v = r[seg[0]]; if (!v) return;
        var x1 = x0 + (x(v) - L), last = x1 >= x(tot) - 0.5;
        g += '<path class="' + seg[1] + '" d="' + (last ? 'M' + x0 + ',' + (yy + 4) + 'H' + (x1 - 4) + 'Q' + x1 + ',' + (yy + 4) + ' ' + x1 + ',' + (yy + 8) + 'V' + (yy + 16) + 'Q' + x1 + ',' + (yy + 20) + ' ' + (x1 - 4) + ',' + (yy + 20) + 'H' + x0 + 'Z'
          : 'M' + x0 + ',' + (yy + 4) + 'H' + (x1 - 2) + 'V' + (yy + 20) + 'H' + x0 + 'Z') + '"/>';
        x0 = x1;
      });
      g += '</g><text class="ctext" x="' + (x(tot) + 8) + '" y="' + (yy + 17) + '">' + tot + '</text>';
    });
    g += '<line class="caxis" x1="' + L + '" x2="' + L + '" y1="0" y2="' + hh + '"/>';
    drawSvg(svgEl, w, hh, g);
    var sums = rows.reduce(function (a, r) { a.src += r.src; a.code += r.code; a.other += r.other; return a; }, { src: 0, code: 0, other: 0 });
    sums.rows = rows;
    return sums;
  }

  // awards: [[state|null, amount, name], ...]
  function chartAwards(svgEl, awards) {
    var w = chartW(svgEl, 900), narrow = w < 560, L = narrow ? 58 : 80, R = narrow ? 12 : 24, T = 18, rh = 74, hh = T + 2 * rh + 30, lo = 3, hi = 9, g = '', med = {};
    var x = function (v) { return L + (w - L - R) * (Math.log10(v) - lo) / (hi - lo); };
    for (var p = lo; p <= hi; p++) g += '<line class="cgrid" x1="' + x(Math.pow(10, p)) + '" x2="' + x(Math.pow(10, p)) + '" y1="' + T + '" y2="' + (T + 2 * rh) + '"/>' + (narrow && p % 2 === 0 ? '' : '<text class="ctext" x="' + x(Math.pow(10, p)) + '" y="' + (T + 2 * rh + 18) + '" text-anchor="' + (p === hi ? 'end' : 'middle') + '">' + shortMoney(Math.pow(10, p)) + '</text>');
    [['fed', 'Federal', 'm-fed'], ['st', 'State', 'm-st']].forEach(function (grp, gi) {
      var pts = awards.filter(function (a) { return (grp[0] === 'st') === !!a[0] && a[1] >= 1000 && a[1] <= 1e9; }).map(function (a) { return a; });
      var vals = pts.map(function (a) { return a[1]; }).sort(function (a, b) { return a - b; });
      var m = vals.length ? (vals.length % 2 ? vals[(vals.length - 1) / 2] : (vals[vals.length / 2 - 1] + vals[vals.length / 2]) / 2) : null;
      med[grp[0]] = { n: vals.length, m: m, lo: vals[0], hi: vals[vals.length - 1] };
      var yy = T + gi * rh + rh / 2, seed = 11;
      g += '<text class="ctext clab" x="' + (L - 12) + '" y="' + (yy + 4) + '" text-anchor="end">' + grp[1] + '</text>';
      pts.forEach(function (a) { seed = (seed * 9301 + 49297) % 233280; var j = (seed / 233280 - 0.5) * (rh - 26);
        g += '<circle class="' + grp[2] + ' cdot" data-tip="' + h(a[2] + ': up to $' + Number(a[1]).toLocaleString('en-US')) + '" cx="' + x(a[1]) + '" cy="' + (yy + j) + '" r="4.5"/>'; });
      if (m) g += '<line class="cmed" x1="' + x(m) + '" x2="' + x(m) + '" y1="' + (yy - rh / 2 + 4) + '" y2="' + (yy + rh / 2 - 4) + '"/><text class="ctext clab" x="' + (x(m) > w - 120 ? x(m) - 6 : x(m) + 6) + '" y="' + (yy - rh / 2 + 14) + '"' + (x(m) > w - 120 ? ' text-anchor="end"' : '') + '>median ' + shortMoney(m) + '</text>';
    });
    drawSvg(svgEl, w, hh, g);
    return med;
  }

  // =====================================================================================
  // About the data page
  // =====================================================================================

  // =====================================================================================
  // The program detail: five answers first, then the source's own words. Shared by the state page's dialog and by
  // each program's own page (p/<slug>/), so the two cannot drift apart.
  // =====================================================================================
  var SOURCES = [];   // the page's source list, for "read from <label>" in the trail
  function feedPath(slug) { return 'p/' + String(slug || '').toLowerCase().replace(/[^a-z0-9-]+/g, '-') + '.xml'; }
  function pagePath(slug) { return 'p/' + String(slug || '').toLowerCase().replace(/[^a-z0-9-]+/g, '-') + '/'; }
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
      ' · read from ' + (SOURCES.filter(function (s) { return s.connector === p.connector; })[0] || { label: p.connector }).label;
    return '<div class="when">' + statusTag(p.status) + '<span class="muted">' + h(levelLabel(p)) + '</span>' + badges(p) + '</div>' +
      answers +
      sect('Deadline, as written by the source', p.closes_text && p.closes_text.length > 120 ? '<div class="verbatim">' + h(p.closes_text) + '</div>' : '') +
      sect('Eligibility, as written by the source', p.eligibility ? '<div class="verbatim">' + h(p.eligibility) + '</div>' : '') +
      sect('Summary', p.summary ? '<p class="prose">' + h(p.summary) + '</p>' : '') +
      sect('History, as the registry saw it', historyHtml(p)) +
      sect('More details', '<div class="facts">' + facts + '</div>') +
      sect('Categories', p.categories.length ? '<ul class="chips">' + p.categories.map(function (t) { return '<li>' + h(words(t)) + '</li>'; }).join('') + '</ul>' : '') +
      sect('Assistance Listings this notice cites', alns) +
      '<p class="trail">' + h(trail) + '</p>';
  }
  // ---- the history strip (13.7): the program's own change log, drawn on a line from first seen to today ----
  function histWords(e) {
    var k = e[1];
    if (k === 'added') return 'First seen by the registry';
    if (k === 'missing') return 'No longer listed by the source';
    if (k === 'edit') return 'Wording or details changed (' + e[2] + (e[2] === 1 ? ' field)' : ' fields)');
    if (k === 'status') {
      var reopen = (e[2] === 'closed' || e[2] === 'exhausted') && (e[3] === 'open' || e[3] === 'forecasted');
      return (reopen ? 'Reopened: ' : 'Status: ') + statusLabel(e[2] || 'unknown') + ' → ' + statusLabel(e[3] || 'unknown');
    }
    var lab = k === 'closes_at' ? 'Deadline' : 'Opening date';
    return lab + ': ' + (e[2] ? fmtDate(e[2], true) : 'not stated') + ' → ' + (e[3] ? fmtDate(e[3], true) : 'not stated');
  }
  function histKind(e) {
    if (e[1] === 'status') return (e[3] === 'open' || e[3] === 'forecasted') ? ((e[2] === 'closed' || e[2] === 'exhausted') ? 'reopen' : 'open') : e[3] === 'closed' ? 'close' : 'other';
    if (e[1] === 'closes_at' || e[1] === 'opens_at') return 'date';
    return e[1];
  }
  function historyHtml(p) {
    var ev = p.history || [];
    if (!ev.length) return '';
    var start = ev[0][0], end = TODAY, dl = p.closes_at && !p.deadline_placeholder ? p.closes_at.slice(0, 10) : null;
    if (dl && dl > end && daysBetween(end, dl) <= 120) end = dl;
    // positions are percentages of the panel's width and there is no viewBox (2026-11-27), so the line fills the
    // panel and the 11px labels stay 11px at every width: no measuring, nothing to redraw
    var span = Math.max(30, daysBetween(start, end)), x = function (d) { return (2 + 96 * Math.min(span, Math.max(0, daysBetween(start, d))) / span).toFixed(2) + '%'; };
    var g = '<line x1="2%" x2="98%" y1="26" y2="26" class="hl"/>';
    var anchor = function (pc) { pc = parseFloat(pc); return pc > 70 ? 'end' : pc < 30 ? 'start' : 'middle'; };
    g += '<line x1="' + x(TODAY) + '" x2="' + x(TODAY) + '" y1="12" y2="40" class="today"/><text x="' + x(TODAY) + '" y="10" text-anchor="' + anchor(x(TODAY)) + '" class="ht">today</text>';
    // a deadline in the left third would sit on the first-seen date's label, so it goes above the line instead
    // ("today" is then at the right, since the strip ends at today or at a deadline still to come)
    if (dl && dl >= start && dl <= end) g += '<line x1="' + x(dl) + '" x2="' + x(dl) + '" y1="18" y2="34" class="dl"/><text x="' + x(dl) + '" y="' + (anchor(x(dl)) === 'start' ? 10 : 52) + '" text-anchor="' + anchor(x(dl)) + '" class="ht">deadline ' + h(fmtDate(dl)) + '</text>';
    ev.forEach(function (e) {
      var k = histKind(e), cx = x(e[0]);
      if (k === 'date') g += '<line x1="' + cx + '" x2="' + cx + '" y1="20" y2="32" class="ev-date"/>';
      else g += '<circle cx="' + cx + '" cy="26" r="' + (k === 'reopen' ? 7 : 5.5) + '" class="ev-' + k + (e[4] === 'code' ? ' ev-code' : '') + '"/>';
    });
    g += '<text x="2%" y="52" class="ht">' + h(fmtDate(start, true)) + '</text>';
    var list = ev.slice().reverse().map(function (e) {
      return '<li><span class="hd">' + h(fmtDate(e[0], true)) + '</span><span class="hk ev-' + histKind(e) + '" aria-hidden="true"></span><span>' + h(histWords(e)) +
        (e[4] === 'code' ? ' <span class="muted small">(the first read after a change to how the registry reads this source)</span>' : '') + '</span></li>';
    }).join('');
    return '<svg class="hist" height="58" aria-hidden="true">' + g + '</svg>' +
      '<ol class="hist-list">' + list + '</ol>' +
      '<p class="muted small">The registry has read this source since ' + h(fmtDate(start, true)) + '. Earlier rounds are not in the log; nothing here predicts the next one.</p>';
  }

  // A listed program's own page (2026-11-26): the same record the state page's panel shows, at an address of its own.
  function programPage() {
    var p = DATA.program;
    SOURCES = DATA.sources || [];
    el('detail-title').textContent = programName(p);
    el('detail-body').innerHTML = detailHtml(p);
    var WKEY = 'fa-watch', watched = {};
    try { watched = JSON.parse(localStorage.getItem(WKEY) || '{}') || {}; } catch (er) { watched = {}; }
    var star = el('detail-star');
    function syncStar() { var on = !!watched[p.slug]; star.setAttribute('aria-pressed', String(on)); star.textContent = on ? '★ Starred' : '☆ Star'; }
    star.addEventListener('click', function () {
      if (watched[p.slug]) delete watched[p.slug];
      else watched[p.slug] = { n: programName(p), s: p.state || null, f: p.state ? p.state : null };
      try { localStorage.setItem(WKEY, JSON.stringify(watched)); } catch (er) { /* private window: the star lasts for this visit */ }
      syncStar();
    });
    syncStar();
    el('detail-copy').addEventListener('click', function () {
      var url = location.href.split('#')[0], done = function () { el('detail-copied').hidden = false; };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, function () { window.prompt('Copy this link', url); });
      else window.prompt('Copy this link', url);
    });
    renderFooter('');
  }

  function aboutPage() {
    var A = DATA, FULL = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    function num(n) { return Number(n).toLocaleString('en-US'); }
    // About as an essay (2026-11-27): every sentence below is built from the payload's counts. A claim heading is used
    // only when the day's counts bear it; otherwise the section keeps the chart's plain title.
    function claim(id, ok, text) { if (ok) el(id).textContent = text; }
    if (A.atlas && el('atlas')) drawAtlas(el('atlas'), el('atlas-note'), A.atlas, (A.stated || []).filter(function (r) { return r.state === 'US'; })[0], false);
    // how each state is read (2026-11-27): the same map by kind, the reasons for the unread states, and the counts
    if (A.atlas && el('kindmap')) {
      drawAtlas(el('kindmap'), el('kindmap-note'), A.atlas, null, true);
      var c = { portal: 0, agencies: 0, portal_agencies: 0, directory: 0, refuse: 0, script: 0, nolist: 0 }, unread = [];
      A.atlas.forEach(function (s) {
        if (s.code === 'DC') return;
        if (c[s.kind] !== undefined) c[s.kind]++;
        else { unread.push(s); if (s.kind === 'stopped') c.script++; else if (s.kind === 'blocked' || s.kind === 'login') c.refuse++; else c.nolist++; }
      });
      // a sentence never opens with a numeral: small counts that start one are written as words
      var WORDS = ['No', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen'];
      function st(n) { return n + (n === 1 ? ' state' : ' states'); }
      function St(n) { return (WORDS[n] || String(n)) + (n === 1 ? ' state' : ' states'); }
      var parts = [c.refuse ? c.refuse + ' refuse automated readers' : '', c.script ? c.script + ' load their lists only in a browser script' : '', c.nolist ? 'in ' + c.nolist + ' the registry found no list to read' : ''].filter(Boolean);
      el('read-sub').textContent = 'The registry reads ' + st(c.portal) + ' from a grants portal with a row for each program, ' + st(c.agencies) + ' from their agencies\' own pages, and ' +
        st(c.portal_agencies) + ' from both. ' + (c.directory ? St(c.directory) + ' keep a directory that lists programs but no dates. ' : '') +
        (unread.length ? St(unread.length) + ' give it nothing to read: ' + (parts.length > 2 ? parts.slice(0, -1).join(', ') + ', and ' + parts[parts.length - 1] : parts.join(' and ')) + '. Each reason is below, as the state page gives it.' : '');
      var ways = [c.portal, c.agencies, c.portal_agencies, c.directory, unread.length].filter(Boolean).length;
      claim('h-read', ways === 5 && A.atlas.length === 51, 'Fifty states, read five ways');
      el('reasons').innerHTML = unread.map(function (s) { return '<li><b aria-hidden="true">' + s.code + '</b><span>' + h(s.note || s.name + ': no state source read.') + '</span></li>'; }).join('');
    }
    var K = {}; (A.stated_kinds || []).forEach(function (k) { K[k.kind] = k; });
    var P = K.portal, G = K.agencies;
    if (P && G) {
      var pd = share(P.date, P.n), gd = share(G.date, G.n);
      el('lede').textContent = 'State portals give a deadline for ' + pd + ' of every 100 programs they list. Agency pages give one for ' + gd +
        '. Funding Atlas reads both every day, shows what each source states, and marks what it leaves out.';
      claim('h-c3', pd - gd >= 20 && share(P.status, P.n) > share(G.status, G.n), 'Portals state the basics. Agency pages mostly do not.');
      el('c3-sub').textContent = 'The registry reads ' + P.states + ' states from a grants portal with structured rows; they state a status for ' + share(P.status, P.n) + '% of the ' +
        num(P.n) + ' programs open to local governments and a deadline for ' + pd + '%. In the ' + G.states + ' states read from agency pages, ' +
        share(G.status, G.n) + '% of ' + num(G.n) + ' programs state a status and ' + gd + '% a deadline. An amount is rarer everywhere: ' +
        share(P.amount, P.n) + '% on portals, ' + num(G.amount) + ' of ' + num(G.n) + ' programs on agency pages.';
    } else {
      el('lede').textContent = 'What the registry reads, what its sources say and leave out, and what the change log has seen.';
      el('c3-sub').textContent = 'Share of programs whose source states a status, a deadline and an amount, by how the registry reads the state.';
    }
    function draw() {
      var r1 = chartRunway(el('c1'), A.deadlines, 26, false);
      el('c1-sub').textContent = num(r1.total) + ' programs open or announced to local governments close in the next 26 weeks, ' + num(r1.week1) + ' of them in the next seven days. ' + num(r1.later) + ' more close later.';
      var rows = Object.keys(A.months).map(function (k) { return [k, A.months[k]]; })
        .filter(function (r) { return r[1].reduce(function (a, b) { return a + b; }, 0) >= 8; })
        .sort(function (a, b) { return b[1].reduce(function (x, y) { return x + y; }, 0) - a[1].reduce(function (x, y) { return x + y; }, 0); })
        .map(function (r) { return [stateName(r[0]), r[1]]; });
      var all = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
      Object.keys(A.months).forEach(function (k) { A.months[k].forEach(function (v, i) { all[i] += v; }); });
      chartSeason(el('c2'), rows.concat([['All states', all]]), false);
      el('c2-leg').innerHTML = seasonLegend();
      var byMonth = all.map(function (v, i) { return [v, i]; }).sort(function (a, b) { return b[0] - a[0] || a[1] - b[1]; }), top = byMonth.slice(0, 3), low = byMonth[11];
      var allTot = all.reduce(function (a, b) { return a + b; }, 0), topTot = top[0][0] + top[1][0] + top[2][0];
      if (allTot) {
        // "bunch" only when the three busiest months hold a third or more of the year's deadlines, and only on enough of
        // them (120, ten a month) that three months cannot hold most of a handful by chance
        var ordered = top.slice().sort(function (a, b) { return a[1] - b[1]; }).map(function (m) { return FULL[m[1]]; });
        claim('h-c2', allTot >= 120 && topTot / allTot >= 0.33, 'State deadlines bunch in ' + ordered[0] + ', ' + ordered[1] + ' and ' + ordered[2]);
        el('c2-sub').textContent = 'Of ' + num(allTot) + ' stated deadlines two years either side of today, ' + FULL[top[0][1]] + ' holds ' + num(top[0][0]) + ', ' +
          FULL[top[1][1]] + ' ' + num(top[1][0]) + ' and ' + FULL[top[2][1]] + ' ' + num(top[2][0]) + '; ' + FULL[low[1]] + ' holds the fewest, ' + num(low[0]) +
          '. This describes the past and predicts nothing.';
      }
      chartStated(el('c3'), el('c3-table'), A.stated_kinds, A.stated);
      var fc = chartFlips(el('c4'), A.flips);
      var tot = fc.src + fc.code + fc.other, re = A.flips.filter(function (r) { return (r.old_status === 'closed' || r.old_status === 'exhausted') && (r.new_status === 'open' || r.new_status === 'forecasted'); }).reduce(function (a, r) { return a + r.n; }, 0);
      el('c4-sub').textContent = 'The registry has logged ' + num(tot) + ' status changes on programs a local government could apply to' + (A.log_since ? ' since ' + fmtDate(A.log_since, true) : '') +
        ', ' + num(re) + ' of them a closed round reopening or announced again. ' + num(fc.src) + ' came from the sources; ' + num(fc.code) +
        ' were the first read after a change to how the registry reads that source, so they may be ours, not the agency\'s.' + (fc.other ? ' ' + num(fc.other) + ' cannot be labelled.' : '');
      var med = chartAwards(el('c5'), A.awards);
      claim('h-c5', med.st.n * 2 < A.open.state, 'Most state programs name no amount');
      el('c5-sub').textContent = 'Only ' + num(med.st.n) + ' of ' + num(A.open.state) + ' open state programs publish a maximum award, against ' + num(med.fed.n) + ' of ' + num(A.open.federal) +
        ' federal notices. Where they do, the state median is ' + shortMoney(med.st.m || 0) + ' and the federal ' + shortMoney(med.fed.m || 0) + '.';
      // every chart has its numbers as a table too: the marks' notes need a pointer, the tables do not
      el('c1-table').innerHTML = ctable(['Week of', 'Federal', 'State', 'All'], r1.weeks.map(function (x) { return [fmtDate(x.start, true), x.f, x.s, x.f + x.s]; }));
      el('c2-table').innerHTML = ctable(['State'].concat(MONTHS), rows.concat([['All states', all]]).map(function (r) { return [r[0]].concat(r[1]); }));
      el('c4-table').innerHTML = ctable(['Change', 'From the source', 'After a code change', 'Not labelled', 'All'], fc.rows.map(function (r) {
        return [statusLabel(r.o) + ' → ' + statusLabel(r.n), r.src, r.code, r.other, r.src + r.code + r.other]; }));
      el('c5-table').innerHTML = ctable(['', 'Programs with a stated maximum', 'Smallest', 'Median', 'Largest'], [['Federal', med.fed], ['State', med.st]].map(function (x) {
        return [x[0], x[1].n, x[1].n ? shortMoney(x[1].lo) : '', x[1].n ? shortMoney(x[1].m) : '', x[1].n ? shortMoney(x[1].hi) : '']; }));
    }
    draw();
    onWidthChange(draw);
    // the limits that depend on the day's data go between the two fixed ones
    var lim = el('limits'), extra = [];
    if (A.unread) extra.push('A program on a page the registry does not read is not here. ' + A.unread + (A.unread === 1 ? ' state has' : ' states have') + ' no state source read yet; each state page says why.');
    if (A.log_since) extra.push('The change log begins with the registry\'s first read, ' + fmtDate(A.log_since, true) + '. Anything a source changed before then is not in it.');
    extra.forEach(function (t) { var li = document.createElement('li'); li.textContent = t; lim.insertBefore(li, lim.lastElementChild); });
    renderFooter('<p>These charts are drawn from the same database as every state page, the day it was built. The SQL behind each is in <code>db/migrations/0009_navigator_stats.sql</code>.</p>');
  }

  // =====================================================================================
  // State page
  // =====================================================================================

  function statePage() {
    var P = DATA.programs, B = DATA.between || [], U = DATA.unstated || [], C = DATA.changes || [], R = DATA.rules, S = DATA.state;
    // The state's own change log is in changes.js and loads when the Changes tab opens (2026-11-26); until then C
    // holds the federal changes from federal.js, and the page carries the count and the week's status changes.
    var changesState = DATA.changes_n ? 'idle' : 'loaded';
    function loadChanges() {
      if (changesState !== 'idle') return;
      changesState = 'loading';
      var sc = document.createElement('script');
      sc.src = 'changes.js?v=' + TODAY;
      sc.onload = function () {
        C = C.concat(window.FA_CHANGES || []).sort(function (a, b) { return b.at.localeCompare(a.at) || b.id - a.id; });
        changesState = 'loaded'; render();
      };
      sc.onerror = function () { changesState = 'failed'; render(); };
      document.head.appendChild(sc);
    }
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
      { key: 'applicant', label: 'Who can apply (read from the text)', get: function (p) { return p.applicant_types.length ? p.applicant_types : ['none']; },
        lab: function (v) { return v === 'none' ? 'Not stated' : words(v); }, open: false },
      { key: 'match', label: 'Matching share', get: function (p) { return [p.match_required == null ? 'unknown' : p.match_required ? 'yes' : 'no']; },
        lab: function (v) { return { yes: 'Match required', no: 'No match required', unknown: 'Not stated' }[v]; }, order: ['no', 'unknown', 'yes'], open: false },
      { key: 'funding_type', label: 'Funding type', get: function (p) { return [p.funding_type || 'none']; },
        lab: function (v) { return v === 'none' ? 'Not stated' : words(v); }, open: false },
      { key: 'agency', label: 'Agency', get: function (p) { return [agencyName(p) || 'Not stated']; },
        lab: function (v) { return v; }, open: false, long: true }
    ];
    var DEFAULT_SEL = { tier: ['likely'] };

    var st = { q: '', sort: 'closing', sel: {}, quick: null, tab: 'programs', feed: 'all', between: false, unstated: false, fed: false, view: 'list' };
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
      if (hsh.tab === 'changes' || hsh.tab === 'digest') st.tab = hsh.tab;
      if (hsh.feed) st.feed = hsh.feed;
      if (hsh.quick) st.quick = hsh.quick;
      if (hsh.between === '1') st.between = true;
      if (hsh.unstated === '1') st.unstated = true;
      if (hsh.fed === '1') st.fed = true;
      if (hsh.view === 'timeline') st.view = 'timeline';
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
      if (st.tab !== 'programs') parts.push('tab=' + st.tab);
      if (st.feed !== 'all') parts.push('feed=' + st.feed);
      if (st.between) parts.push('between=1');
      if (st.unstated) parts.push('unstated=1');
      if (st.fed) parts.push('fed=1');
      if (st.view !== 'list') parts.push('view=' + st.view);
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
      if (st.quick === 'week' && !inWeek(p)) return false;
      if (st.quick === 'starred' && !watched[p.slug]) return false;
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
    el('title').innerHTML = h(S.name) + '<span class="h1-sub">Funding for local governments</span>';
    el('lede').textContent = cov.state
      ? 'Grants and loans a town, city or county in ' + S.name + ' can apply for. ' + S.name + '\'s own programs come first, then federal notices.'
      : 'Federal grants a town, city or county in ' + S.name + ' can apply for. No ' + S.name + ' agency sources are connected yet.';
    var sources = cov.federal.sources.concat(cov.state ? cov.state.sources : []);
    SOURCES = sources;
    var lastRead = sources.map(function (s) { return s.last_ok || ''; }).sort().pop();
    el('coverage-sum').innerHTML = (cov.state
      ? 'Read daily from ' + cov.state.agencies + ' ' + h(S.name) + (cov.state.agencies === 1 ? ' agency' : ' agencies') + ' and Grants.gov'
      : 'Read daily from Grants.gov') +
      '<span class="cov-when">' + (lastRead ? ' · last read ' + h(fmtDate(lastRead)) : '') + ' · built ' + h(fmtDate(DATA.generated_at)) + '</span>';
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

    // ---- the briefing: three or four sentences that each filter the page (13.6). Every number is a count of rows
    // already on the page; a sentence with nothing to say is left out, except the first.
    function plural(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
    function inWeek(p) { return p.closes_at && !p.deadline_placeholder && p.days_to_close != null && p.days_to_close >= 0 && p.days_to_close <= 7; }
    var nWeekState = PS.filter(inWeek).length, nWeekFed = PF.filter(inWeek).length;
    var nNew = P.filter(function (p) { return p.is_new; }).length;
    var nClosing = P.filter(isSoon).length;
    var flips = C.concat(DATA.week_flips || []).filter(function (c) { return c.status_flip && daysBetween(c.at.slice(0, 10), TODAY) <= R.new_days; });
    var opened = flips.filter(function (c) { var f = c.fields.filter(function (x) { return x.field === 'status'; })[0]; return f && (f.new === 'open' || f.new === 'forecasted'); });
    var brief = [];
    if (nWeekState + nWeekFed) {
      // Only the parts that are not zero, the verb agreeing with the total; a state with sources and none closing says so.
      var weekParts = [];
      if (cov.state && nWeekState) weekParts.push(plural(nWeekState, S.name + ' program', S.name + ' programs'));
      if (nWeekFed) weekParts.push(plural(nWeekFed, 'federal notice', 'federal notices'));
      brief.push(['week', weekParts.join(' and ') + (nWeekState + nWeekFed === 1 ? ' closes' : ' close') + ' in the next 7 days' +
        (cov.state && !nWeekState ? '; no ' + S.name + ' program does.' : '.')]);
    } else {
      brief.push([nClosing ? 'closing' : null, 'Nothing on this page closes in the next 7 days' + (nClosing ? '; ' + nClosing + ' close within ' + R.closing_days + '.' : '.')]);
    }
    if (opened.length) brief.push(['opened', plural(opened.length, 'program', 'programs') + ' opened or were announced in the last ' + R.new_days + ' days.']);
    if (nNew) brief.push(['new', plural(nNew, 'program is', 'programs are') + ' new to the registry this week.']);
    if (U.length) brief.push(['unstated', plural(U.length, S.name + ' program has', S.name + ' programs have') + ' no status on the agency\'s page.']);
    el('brief').innerHTML = brief.map(function (b) {
      return '<li>' + (b[0] ? '<button type="button" class="brief-link" data-act="' + b[0] + '">' + h(b[1]) + '</button>' : h(b[1])) + '</li>';
    }).join('') + (brief.length > 1 ? '<li class="brief-more"><button type="button" class="btn quiet small" id="brief-more" aria-expanded="false">' + (brief.length - 1) + ' more this week</button></li>' : '');
    if (el('brief-more')) el('brief-more').addEventListener('click', function () {
      var open = el('brief').classList.toggle('all');
      this.setAttribute('aria-expanded', String(open)); this.textContent = open ? 'Fewer' : (brief.length - 1) + ' more this week';
    });
    el('tab-n-changes').textContent = C.length + (DATA.changes_n || 0);
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

    // ---- fit check (13.11): three questions that set the facets above; nothing hidden, every answer a chip ----
    (function () {
      var who = {}, topics = {};
      P.concat(U, B).forEach(function (p) { p.applicant_types.forEach(function (t) { who[t] = 1; }); p.categories.forEach(function (c) { topics[c] = 1; }); });
      var WHO = ['municipality', 'county', 'special_district', 'housing_authority', 'tribe', 'school'].filter(function (t) { return who[t]; });
      var WHO_LAB = { municipality: 'town or city', county: 'county', special_district: 'special district or authority', housing_authority: 'housing authority', tribe: 'tribal government', school: 'school district or school' };
      el('fit-who').innerHTML += WHO.map(function (t) { return '<option value="' + t + '">' + h(WHO_LAB[t]) + '</option>'; }).join('');
      el('fit-topic').innerHTML += Object.keys(topics).sort().map(function (c) { return '<option value="' + h(c) + '">' + h(words(c)) + '</option>'; }).join('');
      function set(key, val) { if (val) st.sel[key] = val; else delete st.sel[key]; render(); }
      el('fit-who').addEventListener('change', function () { set('applicant', this.value ? [this.value] : null); });
      el('fit-topic').addEventListener('change', function () { set('category', this.value ? [this.value] : null); });
      el('fit-match').addEventListener('change', function () { set('match', this.value === 'no' ? ['no', 'unknown'] : null); });
    })();
    function syncFit() {
      var a = st.sel.applicant || [], c = st.sel.category || [], m = st.sel.match || [];
      el('fit-who').value = a.length === 1 && el('fit-who').querySelector('option[value="' + a[0] + '"]') ? a[0] : '';
      el('fit-topic').value = c.length === 1 ? c[0] : '';
      el('fit-match').value = m.length === 2 && m.indexOf('no') >= 0 && m.indexOf('unknown') >= 0 ? 'no' : '';
    }

    // ---- the active filters, always visible: the default "Likely fit" is a choice the reader can see and undo ----
    var activeEl = el('active');
    function renderActive(shown) {
      var chips = [];
      var QUICK = { 'new': 'New this week', closing: 'Closing within ' + R.closing_days + ' days', week: 'Closing within 7 days', starred: 'Starred' };
      if (st.quick) chips.push('<button class="fchip" data-clear="quick" aria-label="Remove filter: ' + h(QUICK[st.quick] || st.quick) + '">' + h(QUICK[st.quick] || st.quick) + ' <span aria-hidden="true">×</span></button>');
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
      // The default (likely fits only) is said once, in words, with the way out (13.20); any other filter is a chip.
      if (isDefault) {
        activeEl.innerHTML = '<span><span class="lbl">Likely fits only:</span> <b class="num">' + shown + ' of ' + total + '</b>.</span>' +
          '<button class="btn quiet" data-clear="all">Show all ' + total + '</button>';
        return;
      }
      activeEl.innerHTML = '<span class="count num">Showing ' + shown + ' of ' + total + '</span>' +
        (chips.length ? '<span class="lbl">Filtered to</span>' + chips.join('') : '') +
        (chips.length ? '<button class="btn quiet" data-clear="all">Clear all</button>' : '');
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
        // within 7 days: the caution panel (13.17, borrowed from Wayfinding); the words carry it, the yellow repeats it
        if (p.days_to_close <= 7) return '<span class="caution">' + h(cap(relDays(p.days_to_close))) + '</span><span class="sr-only">, ' + h(fmtDate(p.closes_at, true)) + '</span>';
        return '<span class="' + (isSoon(p) ? 'soon' : '') + '">' + h(cap(relDays(p.days_to_close))) + ', ' + h(fmtDate(p.closes_at)) + '</span>';
      }
      if (p.closes_at) return '<span>Last deadline ' + h(fmtDate(p.closes_at, true)) + (p.days_since_deadline != null ? ' (' + h(agoDays(p.days_since_deadline)) + ')' : '') + '</span>';
      if (p.rolling) return '<span>Rolling deadline</span>';
      if (p.closes_text) return '<span>Deadline in the source\'s words below</span>';
      return '<span class="muted">No deadline stated</span>';
    }
    function agoDays(d) { return d === 1 ? '1 day ago' : d + ' days ago'; }
    // While the list holds only likely fits, the filter line says so once and the cards do not repeat it (13.20).
    function onlyLikely() { return (st.sel.tier || []).join(',') === 'likely'; }
    function slot(label, value) {
      return '<div class="slot' + (value ? '' : ' none') + '"><dt>' + label + '</dt><dd' + (value ? ' class="num"' : '') + '>' + (value ? h(value) : 'Source does not say') + '</dd></div>';
    }
    function card(p) {
      var amount = amountText(p);
      // Two slots in the same place on every card (2026-11-26): what the source states is plain, what it does not
      // state is hatched and says so in words.
      var match = p.match_required == null ? null : p.match_required ? 'Required' + (p.match_pct != null ? ', ' + p.match_pct + '%' : '') : 'None required';
      var slots = '<dl class="slots">' + slot('Amount', amount) + slot('Match', match) + '</dl>';
      var facts = [];
      if (p.funding_type && p.funding_type !== 'grant') facts.push('<span>' + h(words(p.funding_type)) + '</span>');
      if (p.last_reopened) facts.push('<span>Reopened last on ' + h(fmtDate(p.last_reopened, true)) + '</span>');
      var cats = p.categories.slice(0, 3).map(function (c) { return '<li>' + h(words(c)) + '</li>'; }).join('') +
        (p.categories.length > 3 ? '<li class="more">+' + (p.categories.length - 3) + '</li>' : '');
      var quoteText = p.closes_text && (!p.closes_at || p.status !== 'open') && !p.rolling ? p.closes_text : null;
      return '<article class="card st-' + h(p.status) + '" data-id="' + p.id + '">' + dateCol(p) + '<div class="cbody">' +
        '<button type="button" class="star" data-star="' + h(p.slug) + '" aria-pressed="' + (watched[p.slug] ? 'true' : 'false') + '" aria-label="Star ' + h(p.name) + '">' + (watched[p.slug] ? '★' : '☆') + '</button>' +
        '<div class="when">' + statusTag(p.status) + deadlineHtml(p) + '</div>' +
        '<h3><button type="button" data-open="' + p.id + '" data-url="' + h(p.source_url) + '" aria-haspopup="dialog">' + h(programName(p)) + '</button></h3>' +
        '<p class="meta">' + h(agencyName(p) || 'Agency not stated') + (p.level === 'federal' ? ' · Federal' : '') + (onlyLikely() && p.tier === 'likely' ? '' : ' · <span class="tier-' + h(p.tier) + '">' + h(TIER_LABEL[p.tier] || p.tier) + '</span>') + topicWord(p) + badges(p) + '</p>' +
        slots + (facts.length ? '<div class="facts">' + facts.join('') + '</div>' : '') +
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
        return '<div class="date' + (isSoon(p) ? ' soon' : '') + (past ? ' past' : '') + '"><span class="m" aria-hidden="true">' + MONTHS[+p.closes_at.slice(5, 7) - 1] +
          '</span><span class="dd" aria-hidden="true">' + (+p.closes_at.slice(8, 10)) + '</span>' + (past ? '<span class="nd" aria-hidden="true">closed</span>' : '') + '</div>';
      }
      var rolling = p.rolling || p.deadline_placeholder;
      return '<div class="date' + (rolling ? '' : ' none') + '"><span class="nd" aria-hidden="true">' + (rolling ? 'Rolling' : 'No date stated') + '</span></div>';
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
    el('g-state-t').textContent = 'Open or announced in ' + S.name;
    el('g-unstated-d').textContent = S.name + ' programs for local governments whose agency page states no open or closed status and no date. They are listed so you know they exist; check the agency page before planning around one.';
    el('g-between-d').textContent = S.name + ' programs for local governments that closed in the last ' + (R.between_months || 15) +
      ' months, with the last deadline and the agency\'s own words about its cycle. Use them to prepare for the next round. Nothing here predicts a date.';
    // Paging (13.16): 30 cards a group until the reader asks for all; filters and search still see every row.
    // Paging: 30 cards a section with "Show all" on wide screens; on a phone 10 at a time (2026-11-26: California
    // ran 26 phone screens), so `more` counts the extra pages asked for.
    var PHONE = !!(window.matchMedia && window.matchMedia('(max-width: 599px)').matches);
    var PAGE_N = PHONE ? 10 : 30, more = {};
    function paged(rows, key) {
      var shown = PHONE ? PAGE_N * (1 + (more[key] || 0)) : (more[key] ? rows.length : PAGE_N);
      if (rows.length <= shown + (PHONE ? 3 : 5)) return { rows: rows, button: '' };
      var left = rows.length - shown;
      return { rows: rows.slice(0, shown), button: '<button class="btn more" type="button" data-more="' + key + '">' +
        (PHONE ? 'Show ' + Math.min(PAGE_N, left) + ' more of ' + rows.length : 'Show all ' + rows.length) + '</button>' };
    }
    // On a phone the federal notices wait behind one line while the page is as it opens (no search, no quick
    // filter, the default filters) and the state has open programs of its own: they are the reason for the page.
    function defaultFilters() {
      return !st.q && !st.quick && FACETS.every(function (f) {
        return (st.sel[f.key] || []).slice().sort().join(',') === (DEFAULT_SEL[f.key] || []).slice().sort().join(',');
      });
    }
    function federalFold(rf, rs) {
      if (!PHONE || st.fed || !FEDERAL_LOADED || !rf.length || !rs.length || !defaultFilters()) return '';
      var wk = rf.filter(inWeek).length;
      return '<div class="fed-fold"><p><b>' + rf.length + ' federal ' + (rf.length === 1 ? 'notice' : 'notices') + ' also fit.</b> ' +
        (wk ? wk + (wk === 1 ? ' closes' : ' close') + ' this week.' : 'None closes this week.') + '</p>' +
        '<button class="btn" type="button" data-fed="1">Show federal notices</button></div>';
    }
    function groupHtml(rows, empty, key) {
      if (!rows.length) return '<p class="empty">' + empty + '</p>';
      var pg = paged(rows, key);
      return bucketed(pg.rows) + pg.button;
    }
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
      el('list-state').innerHTML = groupHtml(rs, stateEmpty, 'state');
      el('g-state-d').hidden = true;
      el('list-federal').innerHTML = FEDERAL_LOADED ? (federalFold(rf, rs) || groupHtml(rf, 'No federal notices match these filters.', 'federal'))
        : '<p class="empty">The federal notices did not load (federal.js). Reload the page, or see them on <a href="https://simpler.grants.gov/search">Grants.gov</a>.</p>';

      el('g-unstated').hidden = !ru.length;
      el('g-between').hidden = !rb.length;
      var pu = paged(ru, 'unstated'), pb = paged(rb, 'between');
      el('list-unstated').innerHTML = pu.rows.map(card).join('') + pu.button;
      el('list-between').innerHTML = pb.rows.map(card).join('') + pb.button;
      [['unstated', 'unstated-toggle', 'list-unstated', ru.length], ['between', 'between-toggle', 'list-between', rb.length]].forEach(function (g) {
        var open = st[g[0]], t = el(g[1]);
        t.setAttribute('aria-expanded', String(open));
        t.textContent = open ? 'Hide' : 'Show ' + g[3];
        el(g[2]).hidden = !open;
      });
      renderActive(rs.length + rf.length + ru.length + rb.length);
      el('tray-done').textContent = 'Show ' + (rs.length + rf.length + ru.length + rb.length) + ' results';
      var tl = st.view === 'timeline';
      ['g-state', 'g-unstated', 'g-between', 'g-federal'].forEach(function (id) { if (tl) el(id).hidden = true; });
      if (!tl) { el('g-state').hidden = false; el('g-federal').hidden = false; }
      el('g-timeline').hidden = !tl;
      if (tl) renderTimeline(rs.concat(rf));
      Array.prototype.forEach.call(document.querySelectorAll('.segb'), function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-view') === st.view)); });
    }

    // ---- the open-window timeline (13.10): a bar from the stated opening date to the stated deadline; a dot at the
    // deadline when no opening date is stated. Nothing is drawn that the source did not state.
    var NS_SVG = 'http://www.w3.org/2000/svg';
    function addDays(iso, n) { return new Date(Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10) + n)).toISOString().slice(0, 10); }
    function renderTimeline(rows) {
      var start = addDays(TODAY, -30), end = addDays(TODAY, 180), span = daysBetween(start, end);
      var inWin = rows.filter(function (p) { return p.closes_at && !p.deadline_placeholder && p.closes_at.slice(0, 10) >= TODAY && p.closes_at.slice(0, 10) <= end; })
        .sort(function (a, b) { return a.closes_at.localeCompare(b.closes_at) || a.name.localeCompare(b.name); });
      el('g-timeline-n').textContent = inWin.length;
      el('tl-state-l').textContent = S.name;
      el('g-timeline-d').textContent = (rows.length - inWin.length) + ' of the ' + rows.length + ' programs matching your filters have no stated deadline in this window and are not drawn. Select a row for its details.';
      var w = 980, L = 320, R = 16, T = 28, rh = 24, hh = T + inWin.length * rh + 8;
      var x = function (iso) { return L + (w - L - R) * Math.max(0, Math.min(span, daysBetween(start, iso))) / span; };
      var g = '';
      for (var m = 0; m < 8; m++) {
        var d = new Date(Date.UTC(+start.slice(0, 4), +start.slice(5, 7) - 1 + m, 1)).toISOString().slice(0, 10);
        if (d < start || d > end) continue;
        g += '<line class="tl-grid" x1="' + x(d) + '" x2="' + x(d) + '" y1="' + (T - 8) + '" y2="' + hh + '"/><text class="tl-t" x="' + (x(d) + 4) + '" y="14">' + MONTHS[+d.slice(5, 7) - 1] + '</text>';
      }
      g += '<line class="tl-today" x1="' + x(TODAY) + '" x2="' + x(TODAY) + '" y1="' + (T - 10) + '" y2="' + hh + '"/><text class="tl-t tl-today-t" x="' + (x(TODAY) + 4) + '" y="' + (T - 12) + '">today</text>';
      inWin.forEach(function (p, i) {
        var yy = T + i * rh, c = p.closes_at.slice(0, 10), cls = p.state ? 'st' : 'fed', pn = programName(p), nm = pn.length > 48 ? pn.slice(0, 47) + '…' : pn;
        var label = pn + ': ' + (p.opens_at ? 'opens ' + fmtDate(p.opens_at, true) + ', ' : 'opening date not stated, ') + 'closes ' + fmtDate(c, true);
        g += '<g class="tl-row" data-id="' + p.id + '" tabindex="0" role="button" aria-label="' + h(label) + '"><rect class="tl-hit" x="0" y="' + yy + '" width="' + w + '" height="' + rh + '"/>' +
          '<text class="tl-n" x="' + (L - 10) + '" y="' + (yy + 16) + '" text-anchor="end">' + h(nm) + '</text>';
        if (p.opens_at) { var x0 = x(p.opens_at.slice(0, 10)), x1 = x(c); g += '<rect class="tl-bar ' + cls + '" x="' + x0 + '" y="' + (yy + 7) + '" width="' + Math.max(4, x1 - x0) + '" height="10" rx="4"/>'; }
        else g += '<circle class="tl-dot ' + cls + '" cx="' + x(c) + '" cy="' + (yy + 12) + '" r="5.5"/>';
        g += '<title>' + h(label) + '</title></g>';
      });
      var svgEl = el('tl-svg');
      svgEl.setAttribute('viewBox', '0 0 ' + w + ' ' + hh); svgEl.setAttribute('width', w); svgEl.innerHTML = g;
    }
    el('tl-svg').addEventListener('click', function (e) { var r = e.target.closest('.tl-row'); if (r) openDetail(byId[r.getAttribute('data-id')], r); });
    el('tl-svg').addEventListener('keydown', function (e) { if (e.key !== 'Enter' && e.key !== ' ') return; var r = e.target.closest('.tl-row'); if (r) { e.preventDefault(); openDetail(byId[r.getAttribute('data-id')], r); } });
    Array.prototype.forEach.call(document.querySelectorAll('.segb'), function (b) {
      b.addEventListener('click', function () { st.view = b.getAttribute('data-view'); render(); });
    });
    el('unstated-toggle').addEventListener('click', function () { st.unstated = !st.unstated; render(); });
    el('between-toggle').addEventListener('click', function () { st.between = !st.between; render(); });
    resultsEl.addEventListener('click', function (e) {
      var mb = e.target.closest('button[data-more]');
      if (mb) { var mk = mb.getAttribute('data-more'); more[mk] = (more[mk] || 0) + 1; render(); return; }
      if (e.target.closest('button[data-fed]')) { st.fed = true; render(); return; }
      var sb = e.target.closest('button[data-star]');
      if (sb) { toggleStar(byId[sb.closest('.card').getAttribute('data-id')]); return; }
      if (e.target.closest('a')) return;
      var c = e.target.closest('.card');
      if (c) openDetail(byId[c.getAttribute('data-id')], c.querySelector('h3 button'));
    });

    // ---- the state-page chart (13.14): when this state's deadlines have fallen (deadlines ahead moved to About in 13.20) ----
    var SEA = DATA.season, seaTot = SEA ? SEA.reduce(function (a, b) { return a + b; }, 0) : 0;
    if (seaTot >= 8) {
      el('season').hidden = false;
      el('season-h').textContent = 'When ' + S.name + '\'s deadlines have fallen:';
      el('season-d').textContent = seaTot + ' stated deadlines of programs open to local governments, two years either side of today, by month. A pattern, not a forecast.';
      chartSeason(el('season-svg'), [[S.name, SEA]], true);
      onWidthChange(function () { chartSeason(el('season-svg'), [[S.name, SEA]], true); });
    }

    // ---- briefing, tabs, feed ----
    el('brief').addEventListener('click', function (e) {
      var b = e.target.closest('button[data-act]');
      if (!b) return;
      var k = b.getAttribute('data-act');
      if (k === 'opened') { st.tab = 'changes'; st.feed = 'status'; }
      else if (k === 'unstated') { st.tab = 'programs'; st.unstated = true; }
      else if (st.quick === k) { st.quick = null; resetSel(); }
      else { st.quick = k; st.sel = {}; st.q = ''; el('q').value = ''; st.tab = 'programs'; }
      render();
      var target = k === 'opened' ? el('panel-changes') : k === 'unstated' ? el('g-unstated') : el('panel-programs');
      if (target && target.scrollIntoView) target.scrollIntoView({ block: 'start' });
    });
    var TABS = ['programs', 'changes', 'digest'], tabs = TABS.map(function (k) { return el('tab-' + k); });
    tabs.forEach(function (t, i) {
      t.addEventListener('click', function () { st.tab = TABS[i]; render(); });
      t.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); var n = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length]; n.focus(); n.click(); }
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('#panel-changes .chip'), function (c) {
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
    function syncDetailStar() {
      var b = el('detail-star'), on = !!(current && watched[current.slug]);
      b.setAttribute('aria-pressed', String(on)); b.textContent = on ? '★ Starred' : '☆ Star';
    }
    el('detail-star').addEventListener('click', function () { toggleStar(current); });
    function openDetail(p, trigger, viaHistory) {
      if (!p) return;
      current = p;
      syncDetailStar();
      lastFocus = trigger || document.activeElement;
      el('detail-title').textContent = programName(p);
      el('detail-body').innerHTML = detailHtml(p);
      el('detail-source').href = p.source_url;
      el('detail-page').href = ROOT + pagePath(p.slug);
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
      // the program's own page (2026-11-26), not this page's #p= address, which still opens the panel
      var url = current ? new URL(ROOT + pagePath(current.slug), location.href).href : location.href;
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
    function setSort(v) { st.sort = v; el('sort').value = v; el('sort-tray').value = v; render(); }
    el('sort').addEventListener('change', function () { setSort(el('sort').value); });
    el('sort-tray').addEventListener('change', function () { setSort(el('sort-tray').value); });
    if (window.matchMedia && matchMedia('(max-width: 480px)').matches) el('q').placeholder = 'Search';
    // On phones the filters are a tray over the results (13.16, NN/g): the result count stays on its button.
    var ft = el('filters-toggle'), backdrop = el('tray-backdrop');
    function setTray(open) {
      ft.setAttribute('aria-expanded', String(open));
      facetsEl.hidden = !open && !window.matchMedia('(min-width: 900px)').matches;
      backdrop.hidden = !open || window.matchMedia('(min-width: 900px)').matches;
      document.body.classList.toggle('tray-open', open && !window.matchMedia('(min-width: 900px)').matches);
      if (open) { var first = facetsEl.querySelector('summary, input, select'); if (first) first.focus(); } else ft.focus();
    }
    ft.addEventListener('click', function () { setTray(ft.getAttribute('aria-expanded') !== 'true'); });
    el('tray-done').addEventListener('click', function () { setTray(false); });
    backdrop.addEventListener('click', function () { setTray(false); });
    facetsEl.addEventListener('keydown', function (e) { if (e.key === 'Escape' && ft.getAttribute('aria-expanded') === 'true') setTray(false); });
    function syncFacetsVisibility() {
      var wide = window.matchMedia('(min-width: 900px)').matches;
      facetsEl.hidden = !wide && ft.getAttribute('aria-expanded') !== 'true';
    }
    window.addEventListener('resize', syncFacetsVisibility);

    // ---- stars and the watchlist (13.9): kept in this browser; each program has its own feed at p/<slug>.xml ----
    var WKEY = 'fa-watch', watched = {};
    try { watched = JSON.parse(localStorage.getItem(WKEY) || '{}') || {}; } catch (er) { watched = {}; }
    function saveWatch() { try { localStorage.setItem(WKEY, JSON.stringify(watched)); } catch (er) { /* private window: stars last for this visit */ } }
    function toggleStar(p) {
      if (!p) return;
      if (watched[p.slug]) delete watched[p.slug];
      else watched[p.slug] = { n: programName(p), s: p.state || S.code, f: p.state ? p.state : null };
      saveWatch(); render();
      if (current && current.slug === p.slug) syncDetailStar();
    }
    function renderWatch() {
      var keys = Object.keys(watched);
      el('watch-n').textContent = keys.length;
      el('watch-list').innerHTML = keys.length ? keys.map(function (k) {
        var w = watched[k], page = ROOT + pagePath(k);
        return '<li><a href="' + h(page) + '">' + h(w.n) + '</a> <span class="muted small">' + h(w.f ? stateName(w.f) : 'Federal') + '</span>' +
          ' · <a class="small" href="' + h(ROOT + feedPath(k)) + '" type="application/atom+xml">feed</a>' +
          ' <button type="button" class="btn quiet small" data-unstar="' + h(k) + '" aria-label="Remove ' + h(w.n) + '">Remove</button></li>';
      }).join('') : '<li class="muted">Nothing starred yet. Use the ☆ on any program.</li>';
      el('watch-only').disabled = el('watch-opml').disabled = !keys.length;
    }
    el('watch-btn').addEventListener('click', function () {
      var w = el('watch'), open = w.hidden; w.hidden = !open; el('watch-btn').setAttribute('aria-expanded', String(open));
    });
    el('watch-list').addEventListener('click', function (e) {
      var b = e.target.closest('button[data-unstar]'); if (!b) return;
      delete watched[b.getAttribute('data-unstar')]; saveWatch(); render();
    });
    el('watch-only').addEventListener('click', function () { st.quick = st.quick === 'starred' ? null : 'starred'; st.tab = 'programs'; render(); });
    el('watch-opml').addEventListener('click', function () {
      var base = DATA.site_url;
      var xml = '<?xml version="1.0" encoding="utf-8"?>\n<opml version="2.0"><head><title>Funding Atlas: starred programs</title></head><body>\n' +
        Object.keys(watched).map(function (k) { var w = watched[k];
          return '  <outline type="rss" text="' + h(w.n) + '" title="' + h(w.n) + '" xmlUrl="' + h(base + feedPath(k)) + '" htmlUrl="' + h(base + String(w.s).toLowerCase() + '/#p=' + encodeURIComponent(k)) + '"/>'; }).join('\n') +
        '\n</body></opml>\n';
      var a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([xml], { type: 'text/x-opml' }));
      a.download = 'funding-atlas-starred.opml';
      document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
    });

    // ---- the digest (13.8): plain text a regional planner can paste into a newsletter. Real rows, their own words
    // and links; the only choices are which rows. Kept out of the URL: it is a tool, not a view to share.
    var dg = { cats: {}, win: 60 };
    (function () {
      var seen = {};
      P.forEach(function (p) { p.categories.forEach(function (c) { seen[c] = (seen[c] || 0) + 1; }); });
      el('dg-cats').innerHTML = Object.keys(seen).sort(function (a, b) { return seen[b] - seen[a]; }).map(function (c) {
        return '<button class="chip" type="button" data-c="' + h(c) + '" aria-pressed="false">' + h(words(c)) + '</button>';
      }).join('');
      el('dg-d').textContent = 'Text to paste into a newsletter or an email to member towns: ' + (cov.state ? S.name + ' programs first, then federal notices' : 'federal notices') +
        ', each with its agency, deadline, amount where stated, and link. Check each agency page before you send.';
      el('dg-cats').addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; var c = b.getAttribute('data-c'); dg.cats[c] = !dg.cats[c]; b.setAttribute('aria-pressed', String(!!dg.cats[c])); renderDigest(); });
      el('dg-win').addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; dg.win = +b.getAttribute('data-w');
        Array.prototype.forEach.call(el('dg-win').children, function (x) { x.setAttribute('aria-pressed', String(x === b)); }); renderDigest(); });
      el('dg-fed').addEventListener('change', renderDigest);
      el('dg-nodate').addEventListener('change', renderDigest);
      if (!cov.state) el('dg-nodate').closest('label').hidden = true;
      el('dg-copy').addEventListener('click', function () {
        var ta = el('dg-out'), msg = el('dg-msg');
        var ok = function () { msg.textContent = 'Copied.'; }, fail = function () { ta.focus(); ta.select(); msg.textContent = 'Selected: press Ctrl+C or Cmd+C.'; };
        try { navigator.clipboard.writeText(ta.value).then(ok, fail); } catch (er) { fail(); }
      });
    })();
    function renderDigest() {
      var on = Object.keys(dg.cats).filter(function (k) { return dg.cats[k]; });
      var topic = function (p) { return !on.length || p.categories.some(function (c) { return on.indexOf(c) >= 0; }); };
      var dated = function (p) { return p.closes_at && !p.deadline_placeholder && p.days_to_close != null && p.days_to_close >= 0 && p.days_to_close <= dg.win; };
      var sortD = function (a, b) { return closeKey(a).localeCompare(closeKey(b)) || a.name.localeCompare(b.name); };
      var st1 = PS.filter(function (p) { return topic(p) && dated(p); }).sort(sortD);
      var st2 = el('dg-nodate').checked ? PS.filter(function (p) { return topic(p) && (!p.closes_at || p.deadline_placeholder); }).sort(sortD) : [];
      var fd = el('dg-fed').checked ? PF.filter(function (p) { return topic(p) && dated(p) && p.tier === 'likely'; }).sort(sortD) : [];
      function line(p) {
        var when = p.closes_at && !p.deadline_placeholder ? 'Closes ' + fmtDate(p.closes_at, true) + '.' : p.rolling ? 'Rolling deadline.' : p.closes_text ? 'Deadline, in the agency\'s words: "' + (p.closes_text.length > 140 ? p.closes_text.slice(0, 139) + '…' : p.closes_text) + '"' : 'No deadline stated.';
        var amt = amountText(p);
        return '- ' + programName(p) + '\n  ' + (agencyName(p) || 'Agency not stated') + '. ' + statusLabel(p.status) + '. ' + when + (amt ? ' ' + amt + '.' : '') + (p.match_required ? ' Match required.' : '') + '\n  ' + p.source_url;
      }
      var head = 'Funding open to ' + S.name + ' local governments, closing in the next ' + dg.win + ' days' + (on.length ? ' (' + on.map(words).join(', ') + ')' : '') +
        '\nFrom Funding Atlas, built ' + fmtDate(DATA.generated_at, true) + '. Status and dates are what each agency\'s page said that day.\n';
      var out = head;
      if (cov.state) out += '\n' + S.name.toUpperCase() + ' PROGRAMS\n' + (st1.length ? st1.map(line).join('\n') : '(none closing in this window)') + '\n';
      if (st2.length) out += '\n' + S.name.toUpperCase() + ' PROGRAMS WITH NO FIXED DATE\n' + st2.map(line).join('\n') + '\n';
      if (el('dg-fed').checked) out += '\nFEDERAL NOTICES\n' + (fd.length ? fd.map(line).join('\n') : '(none closing in this window)') + '\n';
      out += '\nEverything, with filters and a change feed: ' + DATA.site_url + S.code.toLowerCase() + '/';
      el('dg-out').value = out;
      el('dg-msg').textContent = (st1.length + st2.length + fd.length) + ' programs in this digest.';
    }

    // ---- render everything from state ----
    function render() {
      tabs.forEach(function (t, i) {
        var on = TABS[i] === st.tab;
        t.setAttribute('aria-selected', String(on));
        t.tabIndex = on ? 0 : -1;
      });
      TABS.forEach(function (k) { el('panel-' + k).hidden = st.tab !== k; });
      if (st.tab === 'digest') renderDigest();
      Array.prototype.forEach.call(el('brief').querySelectorAll('button[data-act]'), function (b) {
        var k = b.getAttribute('data-act');
        b.setAttribute('aria-pressed', String(k === 'opened' ? st.tab === 'changes' && st.feed === 'status' : k === 'unstated' ? false : st.quick === k));
      });
      Array.prototype.forEach.call(document.querySelectorAll('#panel-changes .chip'), function (c) { c.setAttribute('aria-pressed', String(c.getAttribute('data-feed') === st.feed)); });
      el('sort').value = st.sort; el('sort-tray').value = st.sort;
      if (qEl.value.trim() !== st.q) qEl.value = st.q;
      updateFacets();
      renderGroups();
      renderWatch();
      syncFit();
      if (st.tab === 'changes') loadChanges();
      if (changesState === 'loading' || (changesState === 'idle' && st.tab !== 'changes')) feedEl.innerHTML = '<li class="empty">Loading the change log…</li>';
      else if (changesState === 'failed') feedEl.innerHTML = '<li class="empty">The change log did not load (changes.js). Reload the page, or read it as a <a href="feed.xml" type="application/atom+xml">feed</a>.</li>';
      else renderFeed(feedEl, feedRows(), function (c) {
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
    function n(x) { return '<b class="num">' + x.toLocaleString('en-US') + '</b>'; }
    function sum(k) { return withSources.reduce(function (a, s) { return a + (s[k] || 0); }, 0); }
    el('numbers').innerHTML =
      '<li>' + n(F.open) + ' federal notice' + (F.open === 1 ? ' is' : 's are') + ' open to local governments.</li>' +
      '<li>' + n(F.closing_soon) + ' of them close' + (F.closing_soon === 1 ? 's' : '') + ' within ' + DATA.rules.closing_days + ' days.</li>' +
      '<li>' + n(withSources.length) + ' state' + (withSources.length === 1 ? ' has' : 's have') + ' state agency sources connected.</li>' +
      '<li>' + n(sum('programs')) + ' state programs are read: ' + n(sum('open')) + ' open or announced for local governments, ' + n(sum('between')) + ' closed recently.</li>';
    // ---- the three daily blocks (2026-11-26): counts and names from the build's data, nothing computed beyond shares ----
    var CW = DATA.closing_week, WK = DATA.week, ST = DATA.stated || [];
    if (CW && CW.total) {
      el('t-closing').hidden = false;
      el('t-closing-sum').innerHTML = n(CW.total) + ' program' + (CW.total === 1 ? ' closes' : 's close') + ' in the next 7 days: ' +
        n(CW.state) + ' from states' + (CW.states ? ', in ' + CW.states + (CW.states === 1 ? ' state' : ' states') : '') + ', and ' +
        n(CW.federal) + ' federal notice' + (CW.federal === 1 ? '' : 's') + '.';
      el('t-closing-rows').innerHTML = CW.rows.map(function (p) {
        return '<li><span class="td" aria-hidden="true"><small>' + MONTHS[+p.closes_at.slice(5, 7) - 1] + '</small><b>' + (+p.closes_at.slice(8, 10)) + '</b></span>' +
          '<span><a class="tn" href="' + h(pagePath(p.slug)) + '">' + h(programName(p)) + '</a>' +
          '<span class="tm">' + h(p.state ? stateName(p.state) : 'Federal') + ' · ' + h(agencyName(p) || 'Agency not stated') +
          '<span class="sr-only">, closes ' + h(fmtDate(p.closes_at, true)) + '</span></span></span></li>';
      }).join('');
    }
    var KINDS = [['added', 'First seen'], ['wording', 'Wording or details'], ['status', 'Status'], ['dates', 'Dates'], ['missing', 'No longer listed']];
    if (WK && KINDS.some(function (k) { return WK.kinds[k[0]]; })) {
      el('t-changed').hidden = false;
      el('t-changed-h').textContent = 'What changed in the last ' + WK.days + ' days';
      el('t-kinds').innerHTML = KINDS.map(function (k) { return '<div><dt>' + k[1] + '</dt><dd class="num">' + (WK.kinds[k[0]] || 0).toLocaleString('en-US') + '</dd></div>'; }).join('');
      el('t-flips').innerHTML = WK.status_changes.map(function (c) {
        var name = c.listed ? '<a href="' + h(pagePath(c.slug)) + '">' + h(c.name) + '</a>' : h(c.name);
        return '<li><b>' + h(fmtDate(c.at)) + '</b> · ' + h(c.state ? stateName(c.state) : 'Federal') + ' · ' + name + ': ' +
          h(statusLabel(c.old || 'unknown')) + ' → ' + h(statusLabel(c.new || 'unknown')) + '</li>';
      }).join('');
      el('t-log').addEventListener('click', function () { el('changes').open = true; });
    }
    if (ST.length) {
      el('t-stated').hidden = false;
      el('t-mini').innerHTML = '<span></span><span class="th">Status</span><span class="th">Deadline</span><span class="th">Amount</span>' + ST.map(function (r) {
        function bar(v, what) {
          var pct = Math.round(100 * v / r.n);
          return '<span class="tbar" role="img" aria-label="' + what + ' stated by ' + pct + ' percent"><b style="width:' + pct + '%"></b><i class="num">' + pct + '%</i></span>';
        }
        return '<span class="tl">' + h(KIND_ROW[r.kind] || r.kind) + ' <small class="num">' + r.n.toLocaleString('en-US') + '</small></span>' +
          bar(r.status, 'Status') + bar(r.date, 'Deadline') + bar(r.amount, 'Amount');
      }).join('');
    }
    var wk = DATA.changes_week || 0;
    if (wk) el('feed-sum').textContent += ': ' + wk.toLocaleString('en-US') + ' logged in the last ' + DATA.rules.new_days + ' days';
    if (wk > DATA.changes.length) el('feed-note').insertBefore(document.createTextNode('The newest ' + DATA.changes.length + ' are listed here. '), el('feed-note').firstChild);

    var KIND_TEXT = {
      portal: 'state grants portal read', agencies: 'agency pages read', portal_agencies: 'state portal and agency pages read',
      directory: 'a state directory read (it lists programs but states no status or dates)', blocked: 'state sources blocked',
      login: 'state sources login only', stopped: 'state source needs a browser script; not read', none: 'no state list found', federal: 'no state sources read yet'
    };
    function kindClass(k) { return k === 'portal_agencies' ? 'portal' : (k === 'login' || k === 'stopped') ? 'blocked' : k === 'none' ? 'federal' : k; }
    function covText(s) {
      var head = s.name + ': ' + KIND_TEXT[s.kind] + '. ';
      var body = s.programs > 0
        ? s.agencies + (s.agencies === 1 ? ' agency' : ' agencies') + ', ' + s.programs + ' programs read, ' + s.open + ' open or announced for local governments' + (s.unstated ? ', ' + s.unstated + ' with no status stated' : '') + (s.between ? ', ' + s.between + ' closed recently' : '') + (s.last_ok ? ', read ' + fmtDate(s.last_ok) : '') + '. '
        : (s.note ? s.note + ' ' : '');
      return head + body + 'Plus ' + F.open + ' federal notices.';
    }
    var map = el('map');
    map.innerHTML = S.map(function (s) {
      var k = kindClass(s.kind);
      // The number: programs open or announced; where none is and the source lists programs without a status, that
      // count on a hatched tile (a directory's whole list); 0 only where the source states every round closed.
      var dir = k === 'directory', un = !dir && s.open === 0 && s.unstated > 0;
      var num = dir ? s.programs : un ? s.unstated : s.open;
      return '<a class="t k-' + k + (un ? ' unstated' : '') + '" href="' + s.code.toLowerCase() + '/" style="grid-row:' + (s.row + 1) + ';grid-column:' + (s.col + 1) + '" data-code="' + s.code + '" title="' + h(s.name) + '">' +
        '<span class="c">' + s.code + '</span>' + (s.programs > 0 ? '<span class="o num" aria-hidden="true">' + num + '</span>' : '') +
        '<span class="sr-only">, ' + h(covText(s)) + '</span></a>';
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

  // ---- the theme switch (13.24): automatic (the system's), dark, light, kept in this browser only. The pre-paint
  // script in each page's <head> applies a stored choice before anything draws; charts colour with var(--token), so
  // they follow without a redraw. ----
  function themeSwitch() {
    var btn = el('theme-btn');
    if (!btn) return;
    var root = document.documentElement, metas = document.querySelectorAll('meta[name="theme-color"]');
    var orig = Array.prototype.map.call(metas, function (m) { return m.getAttribute('content'); });
    var NEXT = { auto: 'dark', dark: 'light', light: 'auto' }, NAME = { auto: 'automatic', dark: 'dark', light: 'light' };
    var ICONS = {
      auto: '<circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor"/>',
      dark: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
      light: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'
    };
    function current() { var t = root.getAttribute('data-theme'); return t === 'dark' || t === 'light' ? t : 'auto'; }
    function show() {
      var t = current();
      btn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + ICONS[t] + '</svg>';
      btn.setAttribute('aria-label', 'Theme: ' + NAME[t] + '. Switch to ' + NAME[NEXT[t]] + '.');
      btn.title = 'Theme: ' + NAME[t];
      Array.prototype.forEach.call(metas, function (m, i) { m.setAttribute('content', t === 'auto' ? orig[i] : (t === 'dark' ? '#0f1420' : '#f7f8fa')); });
    }
    btn.addEventListener('click', function () {
      var t = NEXT[current()];
      if (t === 'auto') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', t);
      try { if (t === 'auto') localStorage.removeItem('fa-theme'); else localStorage.setItem('fa-theme', t); } catch (e) { /* storage blocked: the choice lasts this visit */ }
      show();
    });
    show();
  }
  themeSwitch();

  if (PAGE === 'state') statePage(); else if (PAGE === 'about') aboutPage(); else if (PAGE === 'program') programPage(); else indexPage();
})();
