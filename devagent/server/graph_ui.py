"""On-demand graph visualisation UI.

The HTML is built in memory and served at GET / by fastapi_app.py.
Nothing is ever written to disk — the visualisation exists only while
the server is running and disappears automatically when it stops.
"""

from __future__ import annotations

# Placeholder used in the template — replaced at serve time with the real origin.
_PLACEHOLDER = "___BASE_URL___"

# Single-string template: no f-string so JS braces need no escaping.
_TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>DevAgent — Session Graph</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
  <style>
    :root {
      --bg:#0d1117; --surface:#161b22; --border:#30363d;
      --text:#e6edf3; --muted:#8b949e;
      --cyan:#39d0d8; --green:#3fb950; --red:#f85149; --gray:#484f58;
    }
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:var(--bg);color:var(--text);font-family:-apple-system,ui-monospace,monospace;display:flex;height:100vh;overflow:hidden}
    #graph{flex:1;position:relative}
    svg{width:100%;height:100%}
    #sidebar{width:240px;background:var(--surface);border-left:1px solid var(--border);padding:16px;overflow-y:auto;flex-shrink:0}
    h1{font-size:13px;font-weight:600;color:var(--cyan);margin-bottom:16px;letter-spacing:.3px}
    .metric{margin-bottom:14px}
    .mlabel{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.6px}
    .mvalue{font-size:22px;font-weight:700;color:var(--text)}
    .mrow{display:flex;justify-content:space-between;font-size:11px;padding:3px 0;border-bottom:1px solid var(--border)}
    .dot{width:7px;height:7px;border-radius:50%;display:inline-block;margin-right:5px;vertical-align:middle}
    #detail{position:absolute;bottom:16px;left:16px;background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:12px 14px;font-size:12px;min-width:200px;max-width:280px;display:none;z-index:10}
    #badge{position:absolute;top:12px;right:12px;font-size:11px;color:var(--muted)}
    .ldot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--green);margin-right:4px;animation:pulse 2s infinite}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
    .node circle{stroke-width:1.5px;cursor:pointer;transition:opacity .15s}
    .node circle:hover{stroke-width:3px}
    .node text{font-size:9px;fill:var(--text);pointer-events:none}
    line.link{stroke:var(--border);stroke-opacity:.5}
    #empty{position:absolute;top:50%;left:calc(50% - 120px);transform:translateY(-50%);text-align:center;color:var(--muted);display:none}
    a{color:var(--cyan)}
    section-label{display:block;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.6px;margin:14px 0 6px}
  </style>
</head>
<body>
<div id="graph">
  <div id="badge"><span class="ldot"></span>Live</div>
  <svg></svg>
  <div id="detail"></div>
  <div id="empty">
    <div style="font-size:36px;margin-bottom:8px">&#128202;</div>
    <div>No sessions yet.</div>
    <div style="font-size:11px;margin-top:4px">Run <code>devagent run</code> to start one.</div>
  </div>
</div>
<div id="sidebar">
  <h1>DevAgent Graph</h1>
  <div class="metric"><div class="mlabel">Active sessions</div><div class="mvalue" id="m-active">&#8212;</div></div>
  <div class="metric"><div class="mlabel">Tokens (24h)</div><div class="mvalue" id="m-tokens">&#8212;</div></div>
  <div class="metric"><div class="mlabel">Est. cost (24h)</div><div class="mvalue" id="m-cost">&#8212;</div></div>
  <section-label>By model</section-label>
  <div id="m-models"></div>
  <section-label style="margin-top:18px">Legend</section-label>
  <div style="font-size:12px;line-height:2">
    <div><span class="dot" style="background:var(--cyan)"></span>Running</div>
    <div><span class="dot" style="background:var(--gray)"></span>Completed</div>
    <div><span class="dot" style="background:var(--red)"></span>Failed</div>
  </div>
  <div style="margin-top:14px;font-size:11px;color:var(--muted)">Node size&#160;&#8764;&#160;tokens used</div>
  <div style="margin-top:14px;font-size:11px;color:var(--muted)">Click a node for details</div>
  <div style="margin-top:18px;font-size:11px">
    <a href="___BASE_URL___/api/docs" target="_blank">API docs &#8599;</a>
  </div>
</div>

<script>
(function () {
  const BASE = "___BASE_URL___";

  // ── colour by status ────────────────────────────────────────────────────────
  function colour(s) {
    if (s === "running")  return "var(--cyan)";
    if (s === "failed")   return "var(--red)";
    return "var(--gray)";
  }

  // ── radius from tokens ──────────────────────────────────────────────────────
  const rScale = d3.scaleSqrt().domain([0, 60000]).range([9, 38]).clamp(true);

  // ── SVG + simulation ────────────────────────────────────────────────────────
  const svg  = d3.select("svg");
  const W    = () => svg.node().clientWidth;
  const H    = () => svg.node().clientHeight;

  const root = svg.append("g");
  const linkG = root.append("g");
  const nodeG = root.append("g");

  svg.call(
    d3.zoom().scaleExtent([0.15, 5])
      .on("zoom", e => root.attr("transform", e.transform))
  );

  const sim = d3.forceSimulation()
    .force("link",      d3.forceLink().id(d => d.id).distance(120))
    .force("charge",    d3.forceManyBody().strength(-260))
    .force("center",    d3.forceCenter(W() / 2, H() / 2))
    .force("collision", d3.forceCollide(d => rScale(d.tokens || 0) + 8));

  sim.on("tick", () => {
    nodeG.selectAll(".node").attr("transform", d => `translate(${d.x || 0},${d.y || 0})`);
    linkG.selectAll(".link")
      .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  });

  window.addEventListener("resize", () => {
    sim.force("center", d3.forceCenter(W() / 2, H() / 2)).restart();
  });

  // ── render ──────────────────────────────────────────────────────────────────
  function render(sessions) {
    document.getElementById("empty").style.display = sessions.length ? "none" : "block";

    const nodes = sessions.map(s => ({
      id:     s.id,
      label:  (s.title || s.id).slice(0, 12),
      tokens: (s.token_input || 0) + (s.token_output || 0),
      status: s.status || "completed",
      model:  s.model  || "—",
      cost:   s.cost_usd || 0,
    }));

    // node join
    const node = nodeG.selectAll(".node").data(nodes, d => d.id);
    const entered = node.enter().append("g").attr("class", "node")
      .call(d3.drag()
        .on("start", (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on("drag",  (e, d) => { d.fx = e.x; d.fy = e.y; })
        .on("end",   (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; })
      )
      .on("click", (_, d) => showDetail(d));
    entered.append("circle");
    entered.append("text").attr("dy", "0.35em").attr("text-anchor", "middle");
    node.exit().remove();

    nodeG.selectAll(".node").select("circle")
      .attr("r",            d => rScale(d.tokens))
      .attr("fill",         d => colour(d.status))
      .attr("fill-opacity", 0.22)
      .attr("stroke",       d => colour(d.status));
    nodeG.selectAll(".node").select("text").text(d => d.label);

    sim.nodes(nodes);
    sim.force("link").links([]);
    sim.alpha(0.4).restart();
  }

  // ── detail panel ─────────────────────────────────────────────────────────────
  function showDetail(d) {
    const el  = document.getElementById("detail");
    const tok = (d.tokens || 0).toLocaleString();
    const c   = d.cost ? `$${d.cost.toFixed(5)}` : "free";
    el.style.display = "block";
    el.innerHTML = `
      <div style="font-weight:600;margin-bottom:5px">${d.label}</div>
      <div style="color:var(--muted);font-size:11px;margin-bottom:6px">${d.id.slice(0, 20)}&hellip;</div>
      <div><span class="dot" style="background:${colour(d.status)}"></span>${d.status}</div>
      <div style="margin-top:5px">Model: ${d.model}</div>
      <div>Tokens: ${tok}</div>
      <div>Cost: ${c}</div>
      <a href="${BASE}/api/v1/sessions/${d.id}" target="_blank"
         style="display:block;margin-top:8px;font-size:11px">View in API &#8599;</a>
      <div onclick="document.getElementById('detail').style.display='none'"
           style="margin-top:8px;cursor:pointer;font-size:11px;color:var(--muted)">&#10005; close</div>`;
  }

  // ── sidebar metrics ──────────────────────────────────────────────────────────
  async function loadMetrics() {
    try {
      const r = await fetch(BASE + "/api/v1/metrics?period=24h");
      const d = await r.json();
      document.getElementById("m-active").textContent = d.active_sessions ?? "—";
      document.getElementById("m-tokens").textContent = (d.total_tokens || 0).toLocaleString();
      document.getElementById("m-cost").textContent   =
        d.total_cost_usd ? `$${d.total_cost_usd.toFixed(4)}` : "$0";
      document.getElementById("m-models").innerHTML =
        (d.by_model || []).slice(0, 8).map(m =>
          `<div class="mrow"><span>${m.model.slice(0, 22)}</span>
           <span>${(m.tokens || 0).toLocaleString()}</span></div>`
        ).join("");
    } catch (_) {}
  }

  // ── session fetch ─────────────────────────────────────────────────────────────
  async function loadSessions() {
    try {
      const r = await fetch(BASE + "/api/v1/sessions?limit=60");
      const d = await r.json();
      render(d.sessions || []);
    } catch (_) {}
  }

  // ── boot ─────────────────────────────────────────────────────────────────────
  loadSessions();
  loadMetrics();
  setInterval(() => { loadSessions(); loadMetrics(); }, 30000);
}());
</script>
</body>
</html>
"""


def build_html(host: str = "127.0.0.1", port: int = 7331) -> str:
    """Return the graph UI HTML with the correct API base URL injected."""
    base = f"http://{host}:{port}"
    return _TEMPLATE.replace(_PLACEHOLDER, base)
