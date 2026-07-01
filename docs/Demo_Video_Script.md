# Signal — demo video talking points (aim ~4 min; anywhere 3–5 is fine)

Not a word-for-word script — just the points to hit in each section. Say them **in your own words**;
that's what makes it sound like you, not read. Numbers in **bold** are the facts to get right.
Timings are rough — at a natural pace this lands around 4 minutes.

**Setup:** web UI on the Run tab, Demo mode (instant on camera). Have three tabs ready — the web UI, the
GitHub repo, and `config/thesis.yaml`. Record 1280×720. Do one practice run so the clicks are smooth.

---

### Open — ~20s
**Show:** the web UI.
- The job comes down to two things: find good companies early, and make up your mind fast.
- Most people would show you a pile of demos. I built one tool that actually helps with both.
- It's called Signal. Let me show you it running.

### Finding companies — ~60s
**Show:** click **Run sourcing** → list fills → click the top company to open its score → flash `thesis.yaml`.
- It looks where founders show up before they're obvious — GitHub, on-chain activity, research, hackathons, crypto Twitter.
- It scores each one against what the fund actually cares about — I wrote that out in plain language, right here (and I can change it and re-run in seconds).
- It's not one number. It asks: is the team real? Is anyone using it? Are credible people paying attention early?
- Pick one and show the breakdown — you see *why* it scored that way, so you can push back. It's not a black box.
- And it quietly screens out the obvious junk — meme coins, pump-and-dumps — so you're not wading through noise.

### The write-up — ~50s
**Show:** click a company → **Write memo** → point at a source link and the Risks part.
- One click and it drafts a memo — what they do, what's interesting, what's risky, and the questions I'd still want answered.
- Every claim links back to a source. If it can't back something up, it drops it instead of guessing. I'd rather it say less than make things up.
- Point at the risks — it's honest: "early, no recent commits," that kind of thing. It's a first draft to react to, not a verdict.
- The value: it does the hour of gathering, so you spend your time actually deciding.

### The honest part — ~60s (this is the one — slow down)
**Show:** the Backtest tab → the yellow result and the little table.
- Here's the part I'm proudest of, and it's not a feature — it's a gut check.
- It's easy to make a demo look smart. I wanted to know if this is actually reliable. So I asked: if I'd been running it a while back, would it really have caught good deals early? And I tested it against real past ones.
- The answer was: partly. For companies with some public trail, it flagged **about two-thirds** of them, roughly **six weeks early**. The ones that came through a warm intro, with nothing public yet — it caught **none**.
- I think that's worth saying out loud. It's honest about where it helps — stuff out in the open — and where it doesn't — relationships.
- That actually shaped how I built it: use it to widen the top of the funnel and to prep for calls, not to replace the network. Knowing the difference is the whole idea.

### Under the hood — ~30s
**Show:** the tests running / the green cloud run, then the on-off signal switches.
- It's built like real software, not a demo. I only use the AI where you genuinely need judgment — everything else is plain, boring code, because that's cheaper and more reliable.
- Every time I change how it scores, there's a test that checks I didn't quietly make it worse.
- It runs three ways — on your machine, in a browser, or in the cloud — and you can try it with no keys at all.

### Close — ~25s
**Show:** the GitHub repo.
- It's all open source. What I'd add next: more signals that have to agree with each other, and letting it learn from a simple thumbs up or down as you review.
- Honestly, I built this because it's what I'd want to be using on day one — and I tried to be straight about what it can and can't do. Thanks for watching.

---

**To land near 5 min:** walk through a *second* company in "finding companies," or explain one signal in
a bit more depth (e.g. why "credible people following early" is hard to fake). **To keep it at 3:** cut
"under the hood" to one line and trim the second half of "finding companies." Protect the honest part
either way.

**Delivery:** glance at a bullet, look at the screen, talk — don't read. Pauses and a stray "um" are
fine; a real take beats a perfect one. End on the repo link.
