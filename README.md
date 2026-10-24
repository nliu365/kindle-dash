# Kindle 4 (D01100) Calendar + Weather + Alarm Dashboard

Turns a Kindle 4 (firmware 4.1.2) into a wall or bedside display showing:
- the date, current weather and today's high/low
- a 12-hour forecast strip and a 3-day outlook
- your Google Calendar for the next few days, with Chinese titles supported
- your next alarm. At alarm time the screen flashes a full-screen **WAKE UP** card for 5 minutes.

> **About the alarm:** the Kindle 4 has no speaker, so the alarm is visual only. Keep a phone alarm as backup if you need sound.

Everything runs on free tiers. There is nothing to keep running at home.

```
GitHub Actions (every 15 min)          Cloudflare Worker (free)            Kindle 4
 pull Google Calendar + Open-Meteo  ──▶  stores dash.png in KV      ◀── plain HTTP ── wget every 15 min
 draw 600×800 grayscale PNG              answers /status: ALARM/OK  ◀── every 1 min
```

**Why the Cloudflare Worker?** The Kindle 4's downloader only speaks plain HTTP and old TLS. GitHub, Google and most hosts now require modern HTTPS, so the Kindle can't reach them directly. The Worker serves the finished image over `http://`.

**Privacy:** the GitHub repo can be public because it contains only code. Your calendar link and keys live in GitHub *Secrets*. The rendered image is only reachable at a URL containing your own secret KEY.

---

## Part A: Cloud setup (≈20 minutes, done on your computer)

### A1. Get your Google Calendar's private iCal link
1. Open Google Calendar on the web. Click ⚙ → **Settings**, then pick your calendar on the left under *Settings for my calendars*.
2. Scroll to **Integrate calendar** and copy **Secret address in iCal format** (ends in `basic.ics`).
3. To show several calendars, collect each link and join them with commas later.

### A2. Create the Cloudflare Worker (free account at dash.cloudflare.com)
1. **Storage & Databases → KV → Create namespace**, named `kindle-dash`. Copy its **Namespace ID**.
2. **Workers & Pages → Create → Worker**, named `kindle-dash`, then **Deploy**. Click **Edit code**, replace everything with `worker/worker.js` from this kit, and **Deploy** again.
3. In the Worker's **Settings**:
   - **Bindings → Add → KV namespace:** variable name `DASH`, namespace `kindle-dash`.
   - **Variables and Secrets:**
     - `KEY` (type *Secret*): a random string you invent, like `k7Qp2xR9mZ`. This is your password-in-the-URL.
     - `TZ_NAME` = `America/Los_Angeles`
     - `ALARM_MINUTES` = `5`
4. Note your Worker URL, e.g. `kindle-dash.yourname.workers.dev`.
   Visit `http://kindle-dash.yourname.workers.dev/YOURKEY/status`. It should say `OK 16:45` (the image will say "not rendered yet" until A4).

   *(If you prefer the CLI instead: edit `worker/wrangler.toml`, then run `npx wrangler deploy` and `npx wrangler secret put KEY`.)*

5. **Create an API token** (My Profile → API Tokens → Create Token → *Custom*):
   - permission: Account → **Workers KV Storage → Edit**
   - Copy the token. Also copy your **Account ID** from the right side of the Workers overview page.

### A3. Put this kit on GitHub
1. Create a new **public** repository (public repos get unlimited free Actions minutes) and upload this whole folder, including `.github/workflows/render.yml`.
2. In the repo, go to **Settings → Secrets and variables → Actions**.

   **Secrets:**

   | name | value |
   |---|---|
   | `ICAL_URL` | the Google link(s) from A1, comma-separated |
   | `CF_API_TOKEN` | token from A2.5 |
   | `CF_ACCOUNT_ID` | account ID from A2.5 |
   | `CF_KV_NAMESPACE_ID` | namespace ID from A2.1 |

   **Variables:**

   | name | example | meaning |
   |---|---|---|
   | `ALARMS` | `06:45@1-5,08:30@6-7` | see *Alarm format* below |
   | `LAT` / `LON` | `37.3688` / `-122.0363` | weather location (default Sunnyvale) |
   | `UNITS` | `imperial` | or `metric` |

### A4. First run
1. Go to the **Actions** tab, choose **Render Kindle dashboard**, and click **Run workflow**. It should finish green in about a minute.
2. Open `http://kindle-dash.yourname.workers.dev/YOURKEY/dash.png` in your browser. You should see your dashboard. ✅

After this it re-renders by itself every 15 minutes.

### Alarm format
`HH:MM@days` entries, comma-separated, using 24-hour time. Days are numbered 1 = Monday through 7 = Sunday. Use ranges with `-` and separate pieces with `;`.
- `06:45@1-5`: weekdays at 6:45
- `08:30@6-7`: weekends at 8:30
- `07:00`: every day
- `06:00@1;3;5`: Mon, Wed and Fri

To change alarms, edit the `ALARMS` variable. The change takes effect at the next render, within about 15 minutes.

---

## Part B: Kindle setup (≈30 minutes)

> **Before you start:** connect the Kindle to Wi-Fi in its normal UI, and copy off any personal documents. The jailbreak doesn't erase books, but backups are cheap. The device should be at least 50% charged.

### B1. Jailbreak (Kindle 4 non-touch, works on 4.1.2)
1. Download the **Kindle 4 NT jailbreak** (`kindle-jailbreak-k4-*.zip`, by Yifan Lu and NiLuJe). It is linked from the *Jailbreak* section of the MobileRead wiki page **Kindle4NTHacking** (wiki.mobileread.com/wiki/Kindle4NTHacking).
2. Plug the Kindle in via USB. Copy these from the zip to the **root** of the Kindle drive:
   - `data.tar.gz` (keep the `.gz`; some systems hide extensions)
   - `ENABLE_DIAGS`
   - the whole `diagnostic_logs` folder (including `device_info.xml`, which is needed to exit diagnostics mode later)
3. Eject, unplug, then restart: **Menu → Settings → Menu → Restart**.
4. It boots into a text menu called *Diagnostics*. Use the 5-way pad to pick **D) Exit, Reboot or Disable Diags**, then **R) Reboot System**, then **Q) To continue**.
5. After about 20 seconds you'll see a jailbreak screen. Then it reboots into the normal UI with a new book: **"You are Jailbroken"**. ✅

   *If it boots back into Diagnostics:* choose **D) Exit, Reboot or Disable Diags → D) Disable Diagnostics → Q**.

### B2. Install USBNetwork, which gives you SSH over Wi-Fi
This lets you start and stop the dashboard from your computer's terminal.
1. From the same MobileRead *Kindle4NTHacking* page (or NiLuJe's "Kindle Hacks" thread), get **USBNetwork for the K4** and copy its `Update_usbnetwork_*_k4_install.bin` to the Kindle root.
2. Run **Menu → Settings → Menu → Update Your Kindle**.
3. On the Kindle drive, a new `usbnet/` folder appears:
   - In `usbnet/etc/config`, set `USE_WIFI="true"` so SSH works over Wi-Fi.
   - Put your computer's SSH public key (`~/.ssh/id_ed25519.pub`) into `usbnet/etc/authorized_keys`.
   - Check the README inside that package for the exact option names in your version.
4. Turn it on: on the Kindle home screen, press the keyboard key and type `;debugOn` and press Enter. Then type `~usbNetwork` and Enter, then `;debugOff` and Enter.
5. Find the Kindle's IP in your router's device list, then run `ssh root@<kindle-ip>`.

### B3. Install the dashboard
1. Copy the `kindle/dashboard` folder from this kit to the **root** of the Kindle drive, so you have `/mnt/us/dashboard/`.
2. In that folder, copy `config.example.sh` to `config.sh`. Edit `config.sh` and set `BASE` to your Worker URL **with `http://`** plus your KEY:
   ```
   BASE="http://kindle-dash.yourname.workers.dev/k7Qp2xR9mZ"
   ```
3. *(Optional)* If you have installed KUAL (Kindle Unified Application Launcher), also copy `kindle/extensions/dashboard` to `/mnt/us/extensions/` to get a **Start dashboard** button.

### B4. Start it
```sh
ssh root@<kindle-ip> 'sh /mnt/us/dashboard/start.sh'
```
The reading UI disappears and the dashboard appears within about a minute. Leave the Kindle **plugged into USB power**: Wi-Fi stays on and sleep is disabled, so the battery lasts only about a day on its own. A low-battery warning appears below 15%.

### Getting your Kindle back
- `ssh root@<kindle-ip> 'sh /mnt/us/dashboard/stop.sh'`, **or**
- hold the power button about 20 seconds until it restarts. The dashboard does not auto-start, so it comes back as a normal Kindle.

---

## Customising
- **Layout:** `render/render.py` draws everything with Pillow. To preview locally without calendar or network access:
  `pip install -r render/requirements.txt && SAMPLE_ICS=my.ics WX_FIXTURE=wx.json python render/render.py`.
  Without `WX_FIXTURE` it calls Open-Meteo, which is free and needs no key.
- **Refresh rate:** `REFRESH_MIN` in `kindle/dashboard/config.sh`, and the cron line in the workflow.
- **Flash length:** `ALARM_MINUTES` on the Worker.

## Troubleshooting
| symptom | fix |
|---|---|
| Workflow fails at *Upload* | Check that the token has *Workers KV Storage: Edit* and that the account and namespace IDs are correct. |
| Dashboard shows `! calendar: …` in the footer | The iCal link is wrong or was reset. Copy it again from Google. |
| Kindle shows "No connection" | `ssh` in and run `wget -O - $BASE/status` (run `. /mnt/us/dashboard/config.sh` first). Make sure BASE starts with `http://`. Check `/tmp/dash/dash.log`. |
| `http://…workers.dev` redirects to https | Cloudflare changed policy. Attach a cheap custom domain to the Worker and turn **Always Use HTTPS** *off* for it. |
| Wi-Fi drops after start | Run `lipc-set-prop com.lab126.wifid enable 1` over SSH. The loop also retries this every failed refresh. |
| Ghosting or faint leftovers | Normal on e-ink. Every refresh uses a full flash (`eips -f`), which clears most of it. |
| GitHub schedule stopped | GitHub pauses idle repos after 60 days. The workflow makes a monthly keep-alive commit, and you can re-enable the workflow in the Actions tab. |
