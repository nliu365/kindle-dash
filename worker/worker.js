// Cloudflare Worker: serves the dashboard to the Kindle over plain HTTP
// (the Kindle 4's downloader can't talk to modern HTTPS servers).
//
// Routes (KEY is a secret you choose, so strangers can't see your calendar):
//   GET /<KEY>/dash.png   latest dashboard image (written to KV by GitHub Actions)
//   GET /<KEY>/alarm.png  full-screen alarm image
//   GET /<KEY>/status     one line: "ALARM 06:45" or "OK 16:38"
//
// Bindings (set in wrangler.toml / dashboard):
//   DASH          KV namespace
//   KEY           secret path segment
//   TZ_NAME       e.g. America/Los_Angeles
//   ALARM_MINUTES how long the alarm keeps flashing (default 5)
//   GH_TOKEN      (secret) GitHub fine-grained token, Actions: Read and write
//   GH_REPO       e.g. nliu365/kindle-dash
// A Cron Trigger (every 15 min) asks GitHub to run the render workflow, because
// GitHub's own schedule is best-effort and often skips runs.
// Alarm times come from KV key "alarms" (uploaded by the workflow from the
// ALARMS repo variable) so you only edit them in one place.

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(triggerRender(env));
  },

  async fetch(request, env) {
    const url = new URL(request.url);
    const parts = url.pathname.split("/").filter(Boolean);
    if (parts.length !== 2 || parts[0] !== env.KEY) {
      return new Response("not found", { status: 404 });
    }
    const name = parts[1];

    // Clear setup errors instead of Cloudflare's generic "Error 1101"
    if (!env.DASH || typeof env.DASH.get !== "function") {
      return new Response(
        "Setup error: KV binding missing. In the Worker go to Settings > Bindings > " +
        "Add > KV namespace, variable name DASH (uppercase).\n", { status: 500 });
    }
    try {
      return await handle(name, env);
    } catch (e) {
      return new Response("Worker error: " + (e && e.message ? e.message : e) + "\n", { status: 500 });
    }
  },
};

async function handle(name, env) {
    if (name === "dash.png" || name === "alarm.png") {
      const body = await env.DASH.get(name, "arrayBuffer");
      if (!body) return new Response("not rendered yet", { status: 503 });
      return new Response(body, {
        headers: { "content-type": "image/png", "cache-control": "no-store" },
      });
    }

    if (name === "status") {
      const tz = env.TZ_NAME || "America/Los_Angeles";
      const now = localParts(new Date(), tz);
      const alarms = parseAlarms((await env.DASH.get("alarms")) || "");
      const window = parseInt(env.ALARM_MINUTES || "5", 10);
      const ringing = alarms.find((a) => isRinging(a, now, window));
      const hhmm = pad(now.hour) + ":" + pad(now.minute);
      const line = ringing ? `ALARM ${ringing.hm}` : `OK ${hhmm}`;
      return new Response(line + "\n", {
        headers: { "content-type": "text/plain", "cache-control": "no-store" },
      });
    }

    return new Response("not found", { status: 404 });
}

function pad(n) {
  return String(n).padStart(2, "0");
}

function localParts(date, tz) {
  const f = new Intl.DateTimeFormat("en-US", {
    timeZone: tz, hour12: false, weekday: "short", hour: "2-digit", minute: "2-digit",
  });
  const p = Object.fromEntries(f.formatToParts(date).map((x) => [x.type, x.value]));
  const dow = { Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6, Sun: 7 }[p.weekday];
  return { dow, hour: parseInt(p.hour, 10) % 24, minute: parseInt(p.minute, 10) };
}

// "06:45@1-5,08:30@6-7"  (1 = Monday ... 7 = Sunday; "@..." optional = every day)
function parseAlarms(s) {
  return s.split(",").map((x) => x.trim()).filter(Boolean).map((item) => {
    const [hm, days = "1-7"] = item.split("@");
    const [h, m] = hm.split(":").map(Number);
    const allowed = new Set();
    for (const part of days.split(";")) {
      const [a, b] = part.split("-").map(Number);
      for (let d = a; d <= (b || a); d++) allowed.add(d);
    }
    return { hm, h, m, allowed };
  });
}

function isRinging(a, now, window) {
  const nowMin = now.hour * 60 + now.minute;
  const start = a.h * 60 + a.m;
  let diff = nowMin - start;
  let day = now.dow;
  if (diff < 0) { diff += 1440; day = day === 1 ? 7 : day - 1; } // alarm near midnight
  return diff >= 0 && diff < window && a.allowed.has(day);
}

async function triggerRender(env) {
  if (!env.GH_TOKEN || !env.GH_REPO) {
    console.log("GH_TOKEN / GH_REPO not set; skipping render trigger");
    return;
  }
  const url = `https://api.github.com/repos/${env.GH_REPO}/actions/workflows/render.yml/dispatches`;
  const r = await fetch(url, {
    method: "POST",
    headers: {
      authorization: `Bearer ${env.GH_TOKEN}`,
      accept: "application/vnd.github+json",
      "x-github-api-version": "2022-11-28",
      "user-agent": "kindle-dash-worker",   // GitHub rejects requests without one
      "content-type": "application/json",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  if (r.status !== 204) console.log("render trigger failed", r.status, await r.text());
}
