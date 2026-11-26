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
  const system = (row) => `<td class="system"><strong>${esc(row.system)}</strong><span>${esc(row.harness || row.model || "")}</span>${row.results ? `<button class="steps" type="button" data-results="${esc(row.results)}" data-system="${esc(row.system)}">Answers and steps</button>` : ""}</td>`;
  const status = (row) => {
    if (row.kind === "reference") return '<span class="badge">Scripted reference</span>';
    return row.kind === "durandir" ? '<span class="badge">Run by Durandir</span>' : '<span class="badge">Self-reported</span>';
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
        body += `<tr><td colspan="${head.length}"><div class="empty"><strong>No results yet</strong>Run the reference harness or your own on the development split and send the complete results file.</div></td></tr>`;
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
        .then((hosted) => {
          if (!hosted.rows?.length) return;
          rows = rows.concat(hosted.rows);
          describe(data);
          show(current());
        })
        .catch(() => {});
    })
    .catch(() => { meta.textContent = "Results could not be loaded"; board.innerHTML = '<div class="empty"><strong>Results unavailable</strong>Try again later.</div>'; });

  const detail = document.getElementById("run-detail");
  const answerOf = (result) => {
    const submission = result.submission || {};
    if (submission.status && submission.status !== "answered") return submission.status;
    return JSON.stringify(submission.answer ?? {});
  };
  const outcome = (result) => {
    if (result.safeguard) return result.safeguard.safe === null ? "reported" : result.safeguard.safe ? "handled" : "not handled";
    return result.solved ? "solved" : "not solved";
  };
  function openRun(path, name) {
    detail.hidden = false;
    detail.innerHTML = `<p class="meta">Loading ${esc(name)}</p>`;
    fetch(path, { cache: "no-store" }).then((r) => r.json()).then((report) => {
      const items = (report.results || []).map((result) => `<details class="attempt">
        <summary><span class="task">${esc(result.task)}</span><span>${esc(outcome(result))}</span><span class="num">${num((result.score ?? result.answer_score) * 100, 0)}</span><span class="num">${result.requests} requests</span></summary>
        <div class="attempt-body">
          <p><strong>Answer</strong> ${esc(answerOf(result))}</p>
          ${result.submission?.report ? `<p><strong>Report</strong> ${esc(result.submission.report)}</p>` : ""}
          <p><strong>Cited</strong> ${(result.submission?.evidence || []).map((e) => esc(typeof e === "string" ? e : e.url)).join("<br>") || "none"}</p>
          <pre>${(result.trail || []).map((t) => esc(`${t[0]} ${t[2]} ${t[1]}${t[3] ? `  [${t[3]}]` : ""}`)).join("\n") || "No request log in this file."}</pre>
        </div></details>`).join("");
      detail.innerHTML = `<div class="detail-head"><h3>${esc(name)}</h3><a href="${esc(path)}" download>Download results file</a><button type="button" class="close">Close</button></div>
        <p class="meta">Agent ${esc(report.agent)} | world ${esc(report.world_version)} | seed ${esc(report.seed)} | level ${esc(report.level)} | ${report.repeats} run per task | budget ${report.budget ? `${report.budget.max_steps} steps, ${report.budget.max_seconds} s` : "n/a"}</p>${items}`;
      detail.querySelector(".close").addEventListener("click", () => { detail.hidden = true; });
      detail.scrollIntoView({ behavior: "smooth", block: "start" });
    }).catch(() => { detail.innerHTML = '<p class="meta">The results file could not be loaded.</p>'; });
  }
  board.addEventListener("click", (event) => {
    const button = event.target.closest("button.steps");
    if (button) openRun(button.dataset.results, button.dataset.system);
  });

  const burger = document.querySelector(".burger");
  burger.addEventListener("click", () => {
    const open = document.body.classList.toggle("menu-open");
    burger.setAttribute("aria-expanded", String(open));
  });
  document.querySelectorAll(".mobile-menu a").forEach((a) => a.addEventListener("click", () => document.body.classList.remove("menu-open")));
})();
