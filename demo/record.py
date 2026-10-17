"""Drive the real app with Playwright as the demo user and record the screen.

Run (app running locally or the Cloud Run URL):
    python demo/record.py --url http://localhost:8080
    python demo/record.py --url https://policy-vault-240640518337.asia-south1.run.app --show

Needs demo/out/audio/durations.json from demo/voice.py (narration timing drives the pacing).
Writes demo/out/video/*.webm and demo/out/timeline.json for demo/assemble.py.

Every result on screen comes from the live app: real Gemini calls, real comparisons.
Only idle waiting time (no narration playing) is marked for trimming, and the video says so.
"""
import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from script import CAPTION, KEYS  # noqa: E402

OUT = HERE / "out"
W, H = 1280, 720

OVERLAY = r"""
window.__demo = (() => {
  const css = `
    #demo-cap{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);max-width:1040px;z-index:99999;
      background:rgba(10,16,30,.86);color:#fff;font:600 19px/1.4 Inter,system-ui,sans-serif;padding:10px 20px;
      border-radius:10px;text-align:center;box-shadow:0 6px 24px rgba(0,0,0,.25);transition:opacity .3s}
    #demo-badge{position:fixed;top:14px;right:16px;z-index:99999;background:#fff;color:#101a2e;border-radius:99px;
      font:600 13px Inter,system-ui,sans-serif;padding:6px 14px;box-shadow:0 2px 10px rgba(0,0,0,.25)}
    #demo-badge i{display:inline-block;width:8px;height:8px;border-radius:50%;background:#1d7a46;margin-right:7px}
    #demo-toast{position:fixed;top:62px;left:50%;transform:translateX(-50%);z-index:99999;background:#fdf3e1;
      color:#7a4a00;border:1px solid #f0b429;font:600 14px Inter,system-ui,sans-serif;padding:7px 16px;border-radius:8px}
    #demo-card{position:fixed;inset:0;z-index:100000;background:#101a2e;color:#fff;display:flex;flex-direction:column;
      align-items:center;justify-content:center;text-align:center;font-family:Inter,system-ui,sans-serif;padding:40px}
    #demo-card h1{font-size:54px;margin:0 0 14px;letter-spacing:-1px}
    #demo-card p{font-size:21px;color:#b9c4d6;margin:6px 0;max-width:900px}
    #demo-card .tag{margin-top:26px;font-size:15px;color:#f0b429;font-weight:600}
    .demo-ring{outline:3px solid #f0b429 !important;outline-offset:4px;border-radius:8px;transition:outline-color .3s}`;
  const el = (id, tag='div') => {
    let e = document.getElementById(id);
    if (!e) {
      if (!document.getElementById('demo-css')) {
        const s = document.createElement('style'); s.id = 'demo-css'; s.textContent = css; document.head.appendChild(s);
      }
      e = document.createElement(tag); e.id = id; document.body.appendChild(e);
    }
    return e;
  };
  return {
    caption(t) { const e = el('demo-cap'); e.textContent = t; e.style.opacity = t ? 1 : 0; },
    badge(t) { el('demo-badge').innerHTML = '<i></i>' + t; },
    toast(t) { const e = el('demo-toast'); e.textContent = t || ''; e.style.display = t ? 'block' : 'none'; },
    card(title, lines, tag) {
      el('demo-card').innerHTML = `<h1>${title}</h1>${lines.map(l => `<p>${l}</p>`).join('')}<div class="tag">${tag || ''}</div>`;
      el('demo-card').style.display = 'flex';
    },
    uncard() { const e = document.getElementById('demo-card'); if (e) e.style.display = 'none'; },
    ring(sel, ms) {
      const e = typeof sel === 'string' ? document.querySelector(sel) : sel; if (!e) return;
      e.classList.add('demo-ring'); setTimeout(() => e.classList.remove('demo-ring'), ms || 2600);
    },
  };
})();
"""

USER = "Demo user: Priya · new system admin"
WAIT_NOTE = "Live Gemini call in progress · waiting time shortened in this video"


class Director:
    """Keeps narration and screen in step, and records where idle waiting can be trimmed."""

    def __init__(self, page, durations):
        self.page, self.dur = page, durations
        self.t0 = time.monotonic()
        self.events, self.cuts = [], []
        self.busy_until = 0.0

    def now(self):
        return time.monotonic() - self.t0

    def say(self, key, wait=False):
        self.finish()
        self.page.evaluate("t => __demo.caption(t)", CAPTION[key])
        start = self.now()
        self.events.append({"key": key, "start": round(start, 2)})
        self.busy_until = start + self.dur[key] + 0.35
        if wait:
            self.finish()

    def finish(self):
        left = self.busy_until - self.now()
        if left > 0:
            self.page.wait_for_timeout(left * 1000)

    def pause(self, s):
        self.page.wait_for_timeout(s * 1000)

    def wait_app(self, js, what, timeout_s=240):
        """Wait for the live app. Silent waiting beyond narration is marked for trimming."""
        start = self.now()
        self.page.evaluate("t => __demo.toast(t)", WAIT_NOTE)
        try:
            self.page.wait_for_function(js, timeout=timeout_s * 1000, polling=250)
        except Exception as e:
            print(f"  ! timed out waiting for {what}: {e}")
        self.page.evaluate("() => __demo.toast('')")
        end = self.now()
        idle_from = max(start, self.busy_until)
        if end - idle_from > 3.5:  # keep 1.2 s either side so the cut is visible, not hidden
            self.cuts.append([round(idle_from + 1.2, 2), round(end - 1.2, 2)])
        print(f"  {what}: {end - start:.1f}s")

    def show(self, selector, ring=True):
        loc = self.page.locator(selector).first
        loc.evaluate("e => e.scrollIntoView({behavior: 'smooth', block: 'center'})")
        self.pause(0.9)
        if ring:
            loc.evaluate("e => __demo.ring(e)")
        return loc

    def click(self, selector):
        loc = self.show(selector)
        self.pause(0.5)
        loc.click()


def run(url, show):
    durations = json.loads((OUT / "audio" / "durations.json").read_text())
    missing = [k for k in KEYS if k not in durations]
    if missing:
        sys.exit(f"Missing narration clips {missing}: run python demo/voice.py first")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not show)
        ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(OUT / "video"),
                                  record_video_size={"width": W, "height": H})
        ctx.add_init_script(OVERLAY)
        for pack in ("expense", "inventory"):  # fresh demo: no Decision Records yet
            ctx.request.delete(f"{url}/api/records?pack={pack}")
        page = ctx.new_page()
        d = Director(page, durations)
        page.goto(f"{url}/?pack=expense", wait_until="networkidle")
        page.evaluate("t => __demo.badge(t)", USER)

        # ---- Scene 1: the pain ----
        page.evaluate("""() => __demo.card('Policy Vault',
            ['Captures the reasons behind enterprise system configuration before experts leave,',
             'and detects where written policy and live configuration disagree.'],
            'Gemini · Vertex AI Search · Firestore · Cloud Run')""")
        d.pause(0.5)
        lead_in = d.now()  # everything before the title card (blank page loading) is trimmed
        d.say("intro", wait=True)
        page.evaluate("() => __demo.uncard()")
        d.show(".handover")
        d.say("meet", wait=True)

        # ---- Scene 2: drift detection ----
        d.show("#scanBtn")
        d.say("scan")
        page.locator("#scanBtn").click()
        d.show("#scanSteps", ring=False)
        d.wait_app("() => !document.getElementById('scanBtn').disabled && document.getElementById('scanOut').children.length",
                    "expense scan")
        d.finish()
        d.show("#scanOut .tiles")
        d.say("results", wait=True)
        d.click("tr.drift:has-text('R-001')")
        d.pause(0.6)
        d.show("#ev-R-001", ring=False)
        d.say("evidence", wait=True)
        d.show("tr.drift:has-text('R-003')")
        d.say("rootcauses", wait=True)

        # ---- Scene 3: ask before, gap finder, interview ----
        d.show("#q")
        d.say("ask_before")
        q = page.locator("#q")
        question = q.input_value()
        q.fill("")
        q.press_sequentially(question, delay=22)
        d.click("#askBtn")
        d.wait_app("() => !document.getElementById('askBtn').disabled && document.getElementById('askOut').innerText.trim()",
                    "ask before")
        d.finish()
        d.show("#askOut .answer")
        d.say("ask_before_result", wait=True)

        d.show("#gapsOut")
        d.say("gaps")
        d.pause(2.5)
        d.show("#coverageOut")
        d.finish()
        d.click("#gapsOut .gap:has-text('R-014') button")
        d.say("interview")
        d.wait_app("() => document.querySelector('#interviewOut .vault-says, #interviewOut .err')", "interview question")
        d.show("#interviewOut .vault-says")
        d.finish()
        d.click("#interviewOut button.secondary")  # play the expert's recorded answer
        d.say("expert", wait=True)
        d.click("#draftBtn")
        d.say("record")
        d.wait_app("() => document.querySelector('#draftOut .record, #draftOut .err')", "draft record")
        d.show("#draftOut .record")
        d.finish()
        d.click("#draftOut button")  # Verify & save
        d.wait_app("() => document.querySelector('#interviewOut .record .chip.green')", "save record")
        d.pause(1.5)
        d.show("#coverageOut")
        d.say("saved", wait=True)

        # ---- Scene 4: ask after ----
        page.evaluate("() => { document.getElementById('askOut').innerHTML = ''; }")
        d.show("#q")
        d.say("ask_after")
        d.click("#askBtn")
        d.wait_app("() => !document.getElementById('askBtn').disabled && document.getElementById('askOut').innerText.trim()",
                    "ask after")
        d.finish()
        d.show("#askOut .answer")
        d.say("ask_after_result", wait=True)

        # ---- Scene 5: same engine, inventory ----
        page.goto(f"{url}/?pack=inventory", wait_until="networkidle")
        page.evaluate("t => __demo.badge(t)", USER)
        d.show(".packs a.on")
        d.say("inventory")
        d.click("#scanBtn")
        d.wait_app("() => !document.getElementById('scanBtn').disabled && document.getElementById('scanOut').children.length",
                    "inventory scan")
        d.show("tr.drift:has-text('INV-001')")
        d.finish()
        d.pause(1.0)

        # ---- Close ----
        page.evaluate("""() => __demo.card('Policy Vault',
            ['Other tools search what was written down.',
             'Policy Vault captures what was never written, and checks policy against reality.'],
            'github.com/PadmajaG-ai/policy_vault')""")
        page.evaluate("() => __demo.caption('')")
        d.say("close", wait=True)
        d.pause(1.5)
        end = d.now()

        video = page.video.path()
        ctx.close()
        browser.close()

    timeline = {"events": d.events, "cuts": [[0.0, round(lead_in, 2)]] + d.cuts, "end": round(end, 2),
                "video": str(video)}
    (OUT / "timeline.json").write_text(json.dumps(timeline, indent=1))
    trimmed = sum(b - a for a, b in d.cuts)
    print(f"Recorded {end:.0f}s ({trimmed:.0f}s of idle waiting marked for trimming) -> {video}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8080")
    ap.add_argument("--show", action="store_true", help="show the browser while recording")
    a = ap.parse_args()
    run(a.url.rstrip("/"), a.show)
