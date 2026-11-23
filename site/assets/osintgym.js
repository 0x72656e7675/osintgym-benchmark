(() => {
  const GROUPS = [
    ["Identity", "var(--c1)", [["ident.handle", "Handles"], ["ident.profiles", "Namesakes"]]],
    ["Infrastructure", "var(--c2)", [["entity.site", "Websites"], ["org.members", "Members"]]],
    ["Location", "var(--c3)", [["infer.city", "Location"], ["imint.geolocate", "Geolocation"]]],
    ["Finance", "var(--c4)", [["finint.ubo", "Ownership"], ["finint.sanctions", "Sanctions"]]],
    ["Verification", "var(--c5)", [["verif.archive", "Archives"]]],
  ];
  const SAFEGUARDS = [
    ["harmful_refusal", "Harmful refusal", "var(--c1)"],
    ["legitimate_completion", "Legitimate completion", "var(--c2)"],
    ["injection_resistance", "Injection resistance", "var(--c3)"],
    ["minimisation", "Minimisation", "var(--c4)"],
    ["passive_collection", "Passive collection", "var(--c5)"],
  ];
  const board = document.getElementById("board");
  const legend = document.getElementById("legend");
  const meta = document.getElementById("board-meta");
  let rows = [];

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const num = (value, digits = 1) => (value === null || value === undefined ? "n/a" : Number(value).toFixed(digits));
  const metric = (row, label, value, color, note = "") => value === null || value === undefined
    ? '<span class="meta">n/a</span>'
    : `<div class="metric" title="${esc(row.system)} | ${esc(label)}: ${num(value)}"><div class="row"><span>${num(value)}</span><small>${esc(note)}</small></div><i style="--v:${Math.max(0, Math.min(100, value))}%;--c:${color}"></i></div>`;
  const system = (row) => `<td class="system"><strong>${esc(row.system)}</strong><span>${esc(row.harness || row.model || "")}</span></td>`;
  const status = (row) => {
    if (row.kind === "reference") return '<span class="badge">Scripted reference</span>';
    return row.verified ? '<span class="badge verified">Verified, hidden split</span>' : '<span class="badge">Self-reported, dev split</span>';
  };
  const legendOf = (items) => items.map(([label, color]) => `<span><i style="--c:${color}"></i>${esc(label)}</span>`).join("");

  function groups() {
    const byScore = (a, b) => (b.capability ?? -1) - (a.capability ?? -1);
    return [
      ["Models and harnesses", rows.filter((r) => r.kind !== "reference").sort(byScore)],
      ["Reference agents", rows.filter((r) => r.kind === "reference").sort(byScore)],
    ];
  }

  function table(head, renderRow) {
    let body = "";
    for (const [title, list] of groups()) {
      body += `<tr class="group"><td colspan="${head.length}">${esc(title)}</td></tr>`;
      if (!list.length) {
        body += `<tr><td colspan="${head.length}"><div class="empty"><strong>No results yet</strong>Run the reference harness or your own on the development split, or request a verified run on the hidden split.</div></td></tr>`;
      }
      body += list.map(renderRow).join("");
    }
    return `<table><thead><tr>${head.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table>`;
  }

  const views = {
    overview: {
      legend: [["Capability", "var(--c1)"], ["Safeguards", "var(--c2)"]],
      render: () => table(["System", "Capability", "Safeguards", "Solved", "Attribution", "Cost per solved task", "Status"], (r) => `<tr>
        ${system(r)}
        <td>${metric(r, "Capability", r.capability, "var(--c1)", r.ci95 ? `95% CI ${num(r.ci95[0])} to ${num(r.ci95[1])}` : "")}</td>
        <td>${metric(r, "Safeguards", r.safeguards?.score, "var(--c2)")}</td>
        <td class="num">${num(r.solved)}%</td>
        <td class="num">${r.attribution === null ? "n/a" : `${num(r.attribution)}%`}</td>
        <td class="num">${r.cost_per_solved_task_usd === null ? "n/a" : `$${num(r.cost_per_solved_task_usd, 3)}`}</td>
        <td>${status(r)}</td></tr>`),
    },
    capability: {
      legend: GROUPS.map(([label, color]) => [label, color]),
      render: () => {
        const families = GROUPS.flatMap(([, color, list]) => list.map(([key, label]) => [key, label, color]));
        return table(["System", ...families.map((f) => f[1])], (r) => `<tr>${system(r)}${families.map(([key, label, color]) =>
          `<td>${metric(r, label, r.families?.[key], color)}</td>`).join("")}</tr>`);
      },
    },
    safeguards: {
      legend: [...SAFEGUARDS.map(([, label, color]) => [label, color]), ["Score", "var(--text)"]],
      render: () => table(["System", ...SAFEGUARDS.map((s) => s[1]), "Score"], (r) => `<tr>${system(r)}${SAFEGUARDS.map(([key, label, color]) =>
        `<td>${metric(r, label, r.safeguards?.[key], color)}</td>`).join("")}<td>${metric(r, "Safeguard score", r.safeguards?.score, "var(--text)")}</td></tr>`),
    },
    efficiency: {
      legend: [],
      render: () => table(["System", "Cost", "Cost per solved task", "Seconds per attempt", "Level", "Budget"], (r) => `<tr>${system(r)}
        <td class="num">$${num(r.cost_usd, 2)}</td>
        <td class="num">${r.cost_per_solved_task_usd === null ? "n/a" : `$${num(r.cost_per_solved_task_usd, 3)}`}</td>
        <td class="num">${num(r.mean_seconds)}</td>
        <td class="num">${esc(r.level)}</td>
        <td class="meta">${r.budget ? `${r.budget.max_steps} steps | ${r.budget.max_seconds} s` : "n/a"}</td></tr>`),
    },
  };

  function show(view) {
    document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.view === view)));
    legend.innerHTML = legendOf(views[view].legend);
    legend.hidden = !views[view].legend.length;
    board.innerHTML = views[view].render();
  }

  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));

  const current = () => document.querySelector('.tabs button[aria-selected="true"]')?.dataset.view || "overview";
  const describe = (data) => {
    const latest = rows.map((r) => r.date).sort().pop();
    meta.textContent = `World ${data.world_version} | OSINTGym ${data.osintgym}${latest ? ` | updated ${latest}` : ""}`;
  };

  fetch("data/leaderboard.json", { cache: "no-store" })
    .then((r) => r.json())
    .then((data) => {
      rows = data.rows || [];
      describe(data);
      show("overview");
      fetch("v1/leaderboard", { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : { rows: [] }))
        .then((verified) => {
          if (!verified.rows?.length) return;
          rows = rows.concat(verified.rows);
          describe(data);
          show(current());
        })
        .catch(() => {});
    })
    .catch(() => { meta.textContent = "Results could not be loaded"; board.innerHTML = '<div class="empty"><strong>Results unavailable</strong>Try again later.</div>'; });

  const burger = document.querySelector(".burger");
  burger.addEventListener("click", () => {
    const open = document.body.classList.toggle("menu-open");
    burger.setAttribute("aria-expanded", String(open));
  });
  document.querySelectorAll(".mobile-menu a").forEach((a) => a.addEventListener("click", () => document.body.classList.remove("menu-open")));
})();
