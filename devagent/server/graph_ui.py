"""On-demand graph visualisation UI.

The HTML is built in memory and served at GET / by fastapi_app.py.
Nothing is ever written to disk — the visualisation exists only while
the server is running and disappears automatically when it stops.
"""

from __future__ import annotations

_PLACEHOLDER = "___BASE_URL___"

# Plain string (not f-string) — JS braces need no escaping.
_TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>DevAgent — Live Graph</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
  <style>
    :root {
      --bg:      #09090b;
      --bg1:     #111113;
      --bg2:     #18181b;
      --bg3:     #222226;
      --border:  #27272a;
      --borderH: #3f3f46;
      --text:    #fafafa;
      --text2:   #a1a1aa;
      --text3:   #71717a;
      --accent:  #6366f1;
      --accentL: rgba(99,102,241,.18);
      --green:   #22c55e;
      --red:     #ef4444;
      --nav-h:   52px;
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { height: 100%; overflow: hidden; background: var(--bg); }
    body {
      color: var(--text);
      font-family: 'Inter', system-ui, sans-serif;
      font-size: 13px;
      line-height: 1.5;
    }

    /* ── Nav ─────────────────────────────────────────────────────────────── */
    .nav {
      position: fixed; top: 0; left: 0; right: 0; z-index: 100;
      height: var(--nav-h);
      background: rgba(9,9,11,.88);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      display: flex; align-items: center; padding: 0 14px; gap: 10px;
    }
    .nav-brand {
      display: flex; align-items: center; gap: 7px;
      font-weight: 600; font-size: 14px; flex-shrink: 0; color: var(--text);
    }
    .nav-brand svg { width: 20px; height: 20px; flex-shrink: 0; }
    .nav-divider { width: 1px; height: 18px; background: var(--border); flex-shrink: 0; }
    .nav-url {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px; color: var(--text3);
      background: var(--bg2); border: 1px solid var(--border);
      border-radius: 5px; padding: 2px 8px; flex-shrink: 0;
    }
    .nav-spacer { flex: 1; }
    .nav-hint { font-size: 11px; color: var(--text3); flex-shrink: 0; }
    .btn-refresh {
      display: flex; align-items: center; gap: 5px;
      background: var(--bg3); border: 1px solid var(--border);
      border-radius: 6px; padding: 5px 10px;
      color: var(--text2); font-size: 12px; cursor: pointer;
      transition: border-color .15s, color .15s; flex-shrink: 0;
    }
    .btn-refresh:hover { border-color: var(--borderH); color: var(--text); }
    .conn-dot {
      width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
      transition: background .3s, box-shadow .3s;
    }
    .conn-dot.ok  { background: var(--green); box-shadow: 0 0 0 2px rgba(34,197,94,.2); }
    .conn-dot.err { background: var(--red); }
    .conn-dot.unknown { background: var(--text3); }

    /* ── Layout ──────────────────────────────────────────────────────────── */
    .layout {
      display: flex; height: 100vh; padding-top: var(--nav-h);
    }

    /* ── Sidebar ──────────────────────────────────────────────────────────── */
    .sidebar {
      width: 224px; flex-shrink: 0;
      background: var(--bg1); border-right: 1px solid var(--border);
      overflow-y: auto; padding: 14px 12px;
      display: flex; flex-direction: column; gap: 18px;
    }
    .sidebar::-webkit-scrollbar { width: 3px; }
    .sidebar::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

    .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
    .stat-tile {
      background: var(--bg2); border: 1px solid var(--border);
      border-radius: 8px; padding: 10px 10px 8px;
    }
    .stat-tile.span2 { grid-column: span 2; }
    .stat-label { font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: .5px; }
    .stat-value { font-size: 20px; font-weight: 600; color: var(--text); margin-top: 2px; line-height: 1.2; }
    .stat-value.sm { font-size: 15px; }

    .sec-title {
      font-size: 10px; font-weight: 500; color: var(--text3);
      text-transform: uppercase; letter-spacing: .5px; margin-bottom: 8px;
    }
    .bar-row {
      display: flex; align-items: center; gap: 6px; margin-bottom: 5px; font-size: 11px;
    }
    .bar-name { color: var(--text2); width: 68px; flex-shrink: 0; }
    .bar-track { flex: 1; height: 4px; background: var(--bg3); border-radius: 2px; overflow: hidden; }
    .bar-fill  { height: 100%; border-radius: 2px; transition: width .4s; }
    .bar-count { color: var(--text3); font-size: 10px; width: 20px; text-align: right; flex-shrink: 0; }

    .model-row { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; font-size: 11px; }
    .model-name  { color: var(--text2); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .model-toks  { color: var(--text3); font-size: 10px; flex-shrink: 0; font-family: 'JetBrains Mono', monospace; }

    .legend-item {
      display: flex; align-items: center; gap: 7px;
      font-size: 11px; color: var(--text2); margin-bottom: 5px;
    }
    .legend-item.hint { color: var(--text3); font-size: 10px; font-style: italic; }
    .ldot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
    .ldot.running   { background: var(--accent); box-shadow: 0 0 5px var(--accentL); }
    .ldot.completed { background: var(--text3); }
    .ldot.failed    { background: var(--red); }

    .api-link {
      display: block; text-align: center; font-size: 11px;
      color: var(--text3); padding: 7px; border: 1px solid var(--border);
      border-radius: 6px; text-decoration: none; margin-top: auto;
      transition: color .15s, border-color .15s;
    }
    .api-link:hover { color: var(--accent); border-color: var(--accent); }

    /* ── Graph ────────────────────────────────────────────────────────────── */
    .graph-main { flex: 1; position: relative; overflow: hidden; }
    #graph-svg  { width: 100%; height: 100%; display: block; }

    /* SVG node styles */
    .g-node { cursor: pointer; }
    .n-circle {
      stroke-width: 1.5; transition: stroke-width .15s, filter .15s;
    }
    .g-node:hover .n-circle { stroke-width: 3; }
    .n-ring {
      fill: none; pointer-events: none;
      transform-box: fill-box; transform-origin: center;
      animation: ring-breathe 2.4s ease-in-out infinite;
    }
    @keyframes ring-breathe {
      0%, 100% { stroke-opacity: .55; }
      50%       { stroke-opacity: .1;  }
    }
    .n-label {
      font-size: 10px; font-family: 'JetBrains Mono', monospace;
      fill: var(--text2); pointer-events: none; text-anchor: middle;
    }
    .e-link { stroke: var(--border); stroke-opacity: .5; fill: none; }

    /* ── Graph controls ───────────────────────────────────────────────────── */
    .graph-controls {
      position: absolute; bottom: 20px; right: 20px; z-index: 10;
      display: flex; flex-direction: column; gap: 4px;
    }
    .ctrl-btn {
      width: 32px; height: 32px;
      background: var(--bg2); border: 1px solid var(--border);
      border-radius: 6px; color: var(--text2); cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      font-size: 15px; transition: background .15s, color .15s, border-color .15s;
    }
    .ctrl-btn:hover { background: var(--bg3); color: var(--text); border-color: var(--borderH); }

    /* ── Tooltip ─────────────────────────────────────────────────────────── */
    .tooltip {
      position: absolute; pointer-events: none; z-index: 50;
      background: var(--bg2); border: 1px solid var(--borderH);
      border-radius: 8px; padding: 9px 12px;
      min-width: 160px; max-width: 230px;
      box-shadow: 0 8px 24px rgba(0,0,0,.45);
      opacity: 0; transition: opacity .1s;
      font-size: 12px;
    }
    .tooltip.vis { opacity: 1; }
    .tt-name { font-weight: 600; color: var(--text); margin-bottom: 5px; }
    .tt-row  { display: flex; justify-content: space-between; gap: 12px; font-size: 11px; margin-top: 2px; }
    .tt-row .tk { color: var(--text2); }
    .tt-row .tv { color: var(--text3); }

    /* ── Empty ────────────────────────────────────────────────────────────── */
    .empty-state {
      position: absolute; top: 50%; left: 50%;
      transform: translate(-50%, -50%);
      text-align: center; display: none; pointer-events: none;
    }
    .empty-icon  { font-size: 40px; opacity: .12; margin-bottom: 12px; }
    .empty-title { font-size: 15px; font-weight: 500; color: var(--text2); }
    .empty-sub   { font-size: 12px; color: var(--text3); margin-top: 5px; }
    .empty-sub code { font-family: 'JetBrains Mono', monospace; font-size: 11px; }

    /* ── Detail panel ─────────────────────────────────────────────────────── */
    .detail-panel {
      position: absolute; right: 0; top: 0; bottom: 0;
      width: 256px;
      background: var(--bg1); border-left: 1px solid var(--border);
      display: flex; flex-direction: column;
      transform: translateX(100%); transition: transform .22s ease;
    }
    .detail-panel.open { transform: translateX(0); }
    .panel-hdr {
      display: flex; align-items: center; justify-content: space-between;
      padding: 12px 14px; border-bottom: 1px solid var(--border); flex-shrink: 0;
    }
    .panel-title { font-weight: 600; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .panel-close {
      background: none; border: none; color: var(--text3);
      cursor: pointer; font-size: 14px; padding: 2px 4px; line-height: 1; flex-shrink: 0;
    }
    .panel-close:hover { color: var(--text); }
    .panel-body { padding: 12px 14px; overflow-y: auto; flex: 1; }
    .dp-row {
      display: flex; justify-content: space-between; align-items: baseline;
      padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 12px;
    }
    .dp-k { color: var(--text3); }
    .dp-v { color: var(--text2); font-family: 'JetBrains Mono', monospace; font-size: 11px; text-align: right; }
    .dp-badge {
      display: inline-block; padding: 1px 8px; border-radius: 20px; font-size: 11px; font-weight: 500;
    }
    .dp-badge.running   { background: var(--accentL); color: var(--accent); }
    .dp-badge.completed { background: rgba(113,113,122,.2); color: var(--text3); }
    .dp-badge.failed    { background: rgba(239,68,68,.15); color: var(--red); }
    .dp-api {
      display: block; margin-top: 14px; text-align: center; font-size: 11px;
      color: var(--text3); padding: 7px; border: 1px solid var(--border);
      border-radius: 6px; text-decoration: none;
    }
    .dp-api:hover { color: var(--accent); border-color: var(--accent); }
  </style>
</head>
<body>

<!-- ── Navigation ─────────────────────────────────────────────────────── -->
<header class="nav">
  <div class="nav-brand">
    <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="2" y="2" width="7" height="7" rx="1.5" fill="#6366f1"/>
      <rect x="11" y="2" width="7" height="7" rx="1.5" fill="#6366f1" opacity=".55"/>
      <rect x="2" y="11" width="7" height="7" rx="1.5" fill="#6366f1" opacity=".55"/>
      <rect x="11" y="11" width="7" height="7" rx="1.5" fill="#6366f1" opacity=".25"/>
    </svg>
    DevAgent
  </div>
  <div class="nav-divider"></div>
  <code class="nav-url">___BASE_URL___</code>
  <div class="nav-spacer"></div>
  <span class="nav-hint" id="refresh-info">—</span>
  <button class="btn-refresh" id="refresh-btn">
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <polyline points="23 4 23 10 17 10"/>
      <polyline points="1 20 1 14 7 14"/>
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
    </svg>
    Refresh
  </button>
  <span class="conn-dot unknown" id="conn-dot" title="Checking…"></span>
</header>

<!-- ── Layout ─────────────────────────────────────────────────────────── -->
<div class="layout">

  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="stats-grid">
      <div class="stat-tile">
        <div class="stat-label">Active</div>
        <div class="stat-value" id="s-active">—</div>
      </div>
      <div class="stat-tile">
        <div class="stat-label">Total</div>
        <div class="stat-value" id="s-total">—</div>
      </div>
      <div class="stat-tile span2">
        <div class="stat-label">Tokens (24 h)</div>
        <div class="stat-value sm" id="s-tokens">—</div>
      </div>
      <div class="stat-tile span2">
        <div class="stat-label">Est. Cost (24 h)</div>
        <div class="stat-value sm" id="s-cost">—</div>
      </div>
    </div>

    <div>
      <div class="sec-title">Session Status</div>
      <div id="status-bars"></div>
    </div>

    <div>
      <div class="sec-title">Models</div>
      <div id="model-list"><div style="font-size:11px;color:var(--text3)">No data yet</div></div>
    </div>

    <div>
      <div class="sec-title">Legend</div>
      <div class="legend-item"><span class="ldot running"></span>Running</div>
      <div class="legend-item"><span class="ldot completed"></span>Completed</div>
      <div class="legend-item"><span class="ldot failed"></span>Failed</div>
      <div class="legend-item hint">Node size ≈ token count · drag to pin</div>
    </div>

    <a class="api-link" href="___BASE_URL___/api/docs" target="_blank">Open API Docs ↗</a>
  </aside>

  <!-- Graph canvas -->
  <main class="graph-main" id="graph-main">
    <div class="graph-controls">
      <button class="ctrl-btn" id="btn-zi" title="Zoom in">+</button>
      <button class="ctrl-btn" id="btn-zo" title="Zoom out">−</button>
      <button class="ctrl-btn" id="btn-fit" title="Fit to view" style="font-size:13px">⊡</button>
      <button class="ctrl-btn" id="btn-rst" title="Re-heat simulation" style="font-size:12px">⟳</button>
    </div>
    <svg id="graph-svg"></svg>
    <div class="tooltip" id="tooltip"></div>
    <div class="empty-state" id="empty">
      <div class="empty-icon">&#11041;</div>
      <div class="empty-title">No sessions yet</div>
      <div class="empty-sub">Run <code>devagent run</code> to start one.</div>
    </div>

    <!-- Detail panel (inside graph-main for correct absolute positioning) -->
    <div class="detail-panel" id="detail-panel">
      <div class="panel-hdr">
        <span class="panel-title" id="dp-title">Session</span>
        <button class="panel-close" id="dp-close">✕</button>
      </div>
      <div class="panel-body" id="dp-body"></div>
    </div>
  </main>
</div>

<script>
(function () {
  'use strict';

  const BASE = '___BASE_URL___';

  // ── Colour helpers ─────────────────────────────────────────────────────────
  const C_ACCENT = '#6366f1';
  const C_GRAY   = '#3f3f46';
  const C_RED    = '#ef4444';

  function nodeColour(status) {
    if (status === 'running') return C_ACCENT;
    if (status === 'failed')  return C_RED;
    return C_GRAY;
  }

  const rScale = d3.scaleSqrt().domain([0, 80_000]).range([10, 42]).clamp(true);

  // ── D3 setup ───────────────────────────────────────────────────────────────
  const mainEl = document.getElementById('graph-main');
  const W = () => mainEl.clientWidth;
  const H = () => mainEl.clientHeight;

  const svg   = d3.select('#graph-svg');
  const gRoot = svg.append('g');
  const gLink = gRoot.append('g');
  const gNode = gRoot.append('g');

  const zoomB = d3.zoom()
    .scaleExtent([0.08, 8])
    .on('zoom', e => gRoot.attr('transform', e.transform));
  svg.call(zoomB).on('dblclick.zoom', null);

  const sim = d3.forceSimulation()
    .force('link',      d3.forceLink().id(d => d.id).distance(150))
    .force('charge',    d3.forceManyBody().strength(-300))
    .force('center',    d3.forceCenter(W() / 2, H() / 2))
    .force('collision', d3.forceCollide(d => rScale(d.tokens || 0) + 12));

  sim.on('tick', () => {
    gNode.selectAll('.g-node').attr('transform', d => `translate(${d.x || 0},${d.y || 0})`);
    gLink.selectAll('.e-link')
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
  });

  window.addEventListener('resize', () => {
    sim.force('center', d3.forceCenter(W() / 2, H() / 2)).alpha(0.1).restart();
  });

  // ── Zoom controls ──────────────────────────────────────────────────────────
  function zoomBy(k) { svg.transition().duration(220).call(zoomB.scaleBy, k); }

  function fitAll(nodes) {
    if (!nodes.length) return;
    const pad = 60;
    const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y);
    const x0 = Math.min(...xs) - pad, x1 = Math.max(...xs) + pad;
    const y0 = Math.min(...ys) - pad, y1 = Math.max(...ys) + pad;
    const w = W(), h = H();
    const k = Math.min(w / (x1 - x0 || 1), h / (y1 - y0 || 1), 3);
    const tx = (w - k * (x1 + x0)) / 2;
    const ty = (h - k * (y1 + y0)) / 2;
    svg.transition().duration(380).call(zoomB.transform, d3.zoomIdentity.translate(tx, ty).scale(k));
  }

  document.getElementById('btn-zi').addEventListener('click', () => zoomBy(1.4));
  document.getElementById('btn-zo').addEventListener('click', () => zoomBy(0.7));
  document.getElementById('btn-fit').addEventListener('click', () => {
    const nodes = gNode.selectAll('.g-node').data().filter(d => d.x !== undefined);
    fitAll(nodes);
  });
  document.getElementById('btn-rst').addEventListener('click', () => sim.alpha(0.7).restart());

  // ── Tooltip ────────────────────────────────────────────────────────────────
  const tipEl = document.getElementById('tooltip');

  function showTip(event, d) {
    const tok  = (d.tokens || 0).toLocaleString();
    const cost = d.cost ? `$${d.cost.toFixed(5)}` : 'free';
    tipEl.innerHTML = `
      <div class="tt-name">${d.label}</div>
      <div class="tt-row"><span class="tk">Status</span><span class="tv">${d.status}</span></div>
      <div class="tt-row"><span class="tk">Model</span><span class="tv">${d.model}</span></div>
      <div class="tt-row"><span class="tk">Tokens</span><span class="tv">${tok}</span></div>
      <div class="tt-row"><span class="tk">Cost</span><span class="tv">${cost}</span></div>`;
    tipEl.classList.add('vis');
    moveTip(event);
  }
  function moveTip(event) {
    const rect = mainEl.getBoundingClientRect();
    const x = event.clientX - rect.left + 14;
    const y = event.clientY - rect.top  + 14;
    tipEl.style.left = Math.min(x, rect.width  - 240) + 'px';
    tipEl.style.top  = Math.min(y, rect.height - 130) + 'px';
  }
  function hideTip() { tipEl.classList.remove('vis'); }

  // ── Detail panel ───────────────────────────────────────────────────────────
  const detailEl = document.getElementById('detail-panel');

  function openDetail(d) {
    const tok  = (d.tokens || 0).toLocaleString();
    const tIn  = (d.t_in  || 0).toLocaleString();
    const tOut = (d.t_out || 0).toLocaleString();
    const cost = d.cost ? `$${d.cost.toFixed(5)}` : 'free';
    document.getElementById('dp-title').textContent = d.label;
    document.getElementById('dp-body').innerHTML = `
      <div class="dp-row"><span class="dp-k">ID</span><span class="dp-v">${d.id.slice(0, 16)}…</span></div>
      <div class="dp-row"><span class="dp-k">Status</span><span><span class="dp-badge ${d.status}">${d.status}</span></span></div>
      <div class="dp-row"><span class="dp-k">Model</span><span class="dp-v">${d.model}</span></div>
      <div class="dp-row"><span class="dp-k">Tokens in</span><span class="dp-v">${tIn}</span></div>
      <div class="dp-row"><span class="dp-k">Tokens out</span><span class="dp-v">${tOut}</span></div>
      <div class="dp-row"><span class="dp-k">Total tokens</span><span class="dp-v">${tok}</span></div>
      <div class="dp-row"><span class="dp-k">Est. cost</span><span class="dp-v">${cost}</span></div>
      <a class="dp-api" href="${BASE}/api/v1/sessions/${d.id}" target="_blank">View raw session ↗</a>`;
    detailEl.classList.add('open');
  }

  function closeDetail() { detailEl.classList.remove('open'); }
  document.getElementById('dp-close').addEventListener('click', closeDetail);
  svg.on('click', closeDetail);

  // ── Graph render ───────────────────────────────────────────────────────────
  let _prev = [];

  function render(sessions) {
    document.getElementById('empty').style.display = sessions.length ? 'none' : 'block';

    const next = sessions.map(s => {
      const tIn  = s.token_input  || 0;
      const tOut = s.token_output || 0;
      return {
        id:     s.id,
        label:  (s.title || s.id).slice(0, 14),
        tokens: tIn + tOut,
        t_in:   tIn, t_out: tOut,
        status: s.status   || 'completed',
        model:  s.model    || '—',
        cost:   s.cost_usd || 0,
      };
    });

    // carry positions from previous render
    const posMap = Object.fromEntries(_prev.map(n => [n.id, n]));
    next.forEach(n => {
      const p = posMap[n.id];
      if (p && p.x !== undefined) { n.x = p.x; n.y = p.y; n.vx = p.vx; n.vy = p.vy; }
    });
    _prev = next;

    const node = gNode.selectAll('.g-node').data(next, d => d.id);
    node.exit().transition().duration(200).style('opacity', 0).remove();

    const entered = node.enter().append('g').attr('class', 'g-node')
      .style('opacity', 0)
      .call(d3.drag()
        .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y; })
        .on('end',   (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; })
      )
      .on('mouseenter', showTip)
      .on('mousemove',  moveTip)
      .on('mouseleave', hideTip)
      .on('click', (e, d) => { e.stopPropagation(); hideTip(); openDetail(d); });

    entered.append('circle').attr('class', 'n-ring');
    entered.append('circle').attr('class', 'n-circle');
    entered.append('text').attr('class', 'n-label');
    entered.transition().duration(300).style('opacity', 1);

    const all = gNode.selectAll('.g-node');

    all.select('.n-ring')
      .attr('r', d => rScale(d.tokens) + 9)
      .attr('stroke', d => nodeColour(d.status))
      .attr('stroke-width', 1.5)
      .style('display', d => d.status === 'running' ? null : 'none');

    all.select('.n-circle')
      .attr('r', d => rScale(d.tokens))
      .attr('fill', d => nodeColour(d.status))
      .attr('fill-opacity', d => d.status === 'running' ? 0.22 : 0.16)
      .attr('stroke', d => nodeColour(d.status))
      .attr('stroke-opacity', d => d.status === 'running' ? 1 : 0.6);

    all.select('.n-label')
      .text(d => d.label)
      .attr('dy', d => rScale(d.tokens) + 15);

    sim.nodes(next);
    sim.force('link').links([]);
    const isNew = next.some(n => n.x === undefined);
    sim.alpha(isNew ? 0.5 : 0.08).restart();
  }

  // ── Sidebar ────────────────────────────────────────────────────────────────
  function updateSidebar(sessions, metrics) {
    const running   = sessions.filter(s => s.status === 'running').length;
    const failed    = sessions.filter(s => s.status === 'failed').length;
    const completed = sessions.length - running - failed;
    const total     = sessions.length || 1;

    document.getElementById('s-active').textContent = metrics.active_sessions ?? running;
    document.getElementById('s-total').textContent  = sessions.length;
    document.getElementById('s-tokens').textContent = (metrics.total_tokens || 0).toLocaleString();
    document.getElementById('s-cost').textContent   =
      metrics.total_cost_usd ? `$${metrics.total_cost_usd.toFixed(4)}` : '$0.0000';

    document.getElementById('status-bars').innerHTML = [
      ['Running',   running,   C_ACCENT],
      ['Completed', completed, '#52525b'],
      ['Failed',    failed,    C_RED],
    ].map(([name, count, col]) => `
      <div class="bar-row">
        <span class="bar-name">${name}</span>
        <div class="bar-track">
          <div class="bar-fill" style="width:${((count / total) * 100).toFixed(1)}%;background:${col}"></div>
        </div>
        <span class="bar-count">${count}</span>
      </div>`).join('');

    const models = (metrics.by_model || []).slice(0, 7);
    document.getElementById('model-list').innerHTML = models.length
      ? models.map(m => `
          <div class="model-row">
            <span class="model-name" title="${m.model}">${m.model.slice(0, 22)}</span>
            <span class="model-toks">${(m.tokens || 0).toLocaleString()}</span>
          </div>`).join('')
      : '<div style="font-size:11px;color:var(--text3)">No model data yet</div>';
  }

  // ── Connection status ──────────────────────────────────────────────────────
  function setConn(ok) {
    const dot = document.getElementById('conn-dot');
    dot.className = 'conn-dot ' + (ok ? 'ok' : 'err');
    dot.title = ok ? 'Server reachable' : 'Server unreachable';
  }

  // ── Refresh label ──────────────────────────────────────────────────────────
  let _lastMs = 0;
  function tickRefreshLabel() {
    if (!_lastMs) return;
    const sec = Math.round((Date.now() - _lastMs) / 1000);
    const lbl = sec < 5 ? 'Updated just now' : `Updated ${sec}s ago`;
    document.getElementById('refresh-info').textContent = lbl;
  }

  // ── Data fetch ─────────────────────────────────────────────────────────────
  async function refresh() {
    try {
      const [sRes, mRes] = await Promise.all([
        fetch(`${BASE}/api/v1/sessions?limit=80`),
        fetch(`${BASE}/api/v1/metrics?period=24h`),
      ]);
      const [sData, mData] = await Promise.all([sRes.json(), mRes.json()]);
      render(sData.sessions || []);
      updateSidebar(sData.sessions || [], mData);
      setConn(true);
      _lastMs = Date.now();
      tickRefreshLabel();
    } catch (_) {
      setConn(false);
    }
  }

  // ── Boot ───────────────────────────────────────────────────────────────────
  refresh();
  setInterval(refresh, 30_000);
  setInterval(tickRefreshLabel, 5_000);
  document.getElementById('refresh-btn').addEventListener('click', refresh);
}());
</script>
</body>
</html>
"""


def build_html(host: str = "127.0.0.1", port: int = 7331) -> str:
    """Return the graph UI HTML with the correct API base URL injected."""
    base = f"http://{host}:{port}"
    return _TEMPLATE.replace(_PLACEHOLDER, base)
