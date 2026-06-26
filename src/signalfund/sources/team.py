"""Team enrichment — the founder signal (highest predictive value; the fix for the
relationship-sourced blind spot the backtest exposed).

TWO TIERS, both feeding scoring.team_bonus via candidate.raw:

  FREE (GitHub, only GITHUB_TOKEN) — `enrich_team_github()` fills the subset GitHub can
  know: team_size, a technical_ceo PROXY (the owner is committing code), and
  frontier_lab_alum (a top contributor publicly belongs to a notable org).

  PREMIUM (Harmonic, HARMONIC_API_KEY) — augments with what GitHub can't see: prior_exit,
  exit_size_usd, repeat_founder_count, same_domain (and augments the GitHub-derived fields).

enrich() runs the FREE path always, then the PREMIUM path if the key is present. Networked;
the orchestrator runs it in LIVE mode only. No-op (no raise) on missing repo/key/handle or
any failure. Pre-baked raw fields are left untouched (setdefault / augment, never clobber).

NOTE: like sources/harmonic.py, confirm the exact Harmonic endpoint + response shape for
your account — parsing is defensive on purpose.

Optional TeamSource.fetch() discovers stealth founders from a Harmonic *people*
saved-search (HARMONIC_PEOPLE_SEARCH_ID); returns [] when unconfigured.
"""
from __future__ import annotations

import os
import re

from .base import Source
from .github_velocity import _client as _gh_client, _owner_repo
from ..models import Candidate

HARMONIC_API = "https://api.harmonic.ai"

# Frontier-lab pedigree — verifiable prior employment, not a self-asserted title.
_FRONTIER_LABS = ("openai", "anthropic", "deepmind", "google brain", "meta ai",
                  "fair", "mistral", "xai", "microsoft research")
_TECHNICAL_TITLES = ("cto", "chief technology", "founding engineer", "phd", "co-founder & cto")
_EXIT_WORDS = ("acqui", "ipo", "exit", "m&a", "merger")

# Public GitHub orgs we treat as notable pedigree (frontier labs + top crypto). Editable;
# LOW recall by design — only PUBLIC org memberships are visible via the API. That's fine.
_NOTABLE_ORGS = {"openai", "anthropics", "google-deepmind", "ethereum", "paradigmxyz",
                 "a16z", "solana-labs", "base-org", "optimism", "eigenlayer"}
_MAX_TEAM_SIZE = 50      # cap so a huge OSS repo doesn't imply a 500-person "team"
_TOP_CONTRIBUTORS = 3    # only inspect the top few contributors (caps extra API calls)


# ---- FREE path: GitHub --------------------------------------------------------

def _gh_repo(candidate) -> str | None:
    """'owner/repo' from raw public_handles/github_repo, else the candidate url/name."""
    raw = candidate.raw or {}
    handles = raw.get("public_handles") or {}
    repo = handles.get("github_repo") or raw.get("github_repo")
    if isinstance(repo, str) and "/" in repo:
        return repo.strip("/")
    return _owner_repo(candidate)


def enrich_team_github(candidate) -> None:
    """FREE team signal from GitHub (no Harmonic): fills team_size, a technical_ceo PROXY,
    and frontier_lab_alum onto candidate.raw. Leaves the exit/talent fields (prior_exit,
    exit_size_usd, repeat_founder_count) to Harmonic. No-op on missing/private repo or rate
    limit; GITHUB_TOKEN is optional (only lifts rate limits)."""
    repo = _gh_repo(candidate)
    if not repo or "/" not in repo:
        return
    owner = repo.split("/")[0].lower()
    try:
        with _gh_client() as cx:
            rc = cx.get(f"/repos/{repo}/contributors", params={"per_page": 100})
            if rc.status_code != 200:
                return
            contributors = rc.json()
            if not isinstance(contributors, list) or not contributors:
                return
            logins = [str(c.get("login") or "").lower() for c in contributors if c.get("login")]

            # team_size = contributor count, capped (a 500-contributor OSS repo isn't a team of 500)
            candidate.raw.setdefault("team_size", min(len(logins), _MAX_TEAM_SIZE))

            # technical_ceo PROXY: the repo/org owner is themselves a contributor — i.e. a
            # founder is actually committing code. A heuristic, NOT a verified title.
            if owner in logins:
                candidate.raw.setdefault("technical_ceo", True)

            # frontier_lab_alum: a top-~3 contributor is a PUBLIC member of a notable org.
            for login in [c.get("login") for c in contributors[:_TOP_CONTRIBUTORS] if c.get("login")]:
                ro = cx.get(f"/users/{login}/orgs")
                if ro.status_code != 200:
                    continue
                orgs = {str(o.get("login") or "").lower() for o in ro.json()}
                if orgs & _NOTABLE_ORGS:
                    candidate.raw.setdefault("frontier_lab_alum", True)
                    break
    except Exception:
        return


# ---- PREMIUM path: Harmonic ---------------------------------------------------

def _harmonic_client(key: str):
    import httpx
    return httpx.Client(base_url=HARMONIC_API,
                        headers={"apikey": key, "accept": "application/json"}, timeout=30)


def _domain_root(url: str) -> str:
    m = re.search(r"https?://([^/]+)", url or "")
    host = m.group(1).replace("www.", "").lower() if m else ""
    return host.split(".")[0] if host else ""


def _founder_fields(company: dict, domain_root: str) -> dict:
    """Extract the team signal from a Harmonic company payload (defensive)."""
    people = company.get("people") or company.get("founders") or company.get("team") or []
    founders = [p for p in people
                if "found" in str(p.get("role") or p.get("title") or "").lower()] or people
    prior_exit = technical = frontier = same_domain = False
    exit_size = 0.0
    repeat = 0
    for p in founders:
        roles = " ".join(str(p.get(k) or "") for k in ("role", "title", "headline")).lower()
        if any(t in roles for t in _TECHNICAL_TITLES):
            technical = True
        founded_before = 0
        for e in (p.get("experience") or p.get("prior_companies") or []):
            emp = str(e.get("company") or e.get("name") or "").lower()
            if any(lab in emp for lab in _FRONTIER_LABS):
                frontier = True
            if e.get("founder") or "found" in str(e.get("role") or "").lower():
                founded_before += 1
                if domain_root and domain_root in emp:
                    same_domain = True
            outcome = str(e.get("exit_type") or e.get("outcome") or "").lower()
            if e.get("exit_size_usd") or any(x in outcome for x in _EXIT_WORDS):
                prior_exit = True
                try:
                    exit_size = max(exit_size, float(e.get("exit_size_usd") or 0))
                except (TypeError, ValueError):
                    pass
        repeat = max(repeat, founded_before)
    return {"team_size": len(founders), "prior_exit": prior_exit,
            "exit_size_usd": exit_size or None, "repeat_founder_count": repeat,
            "same_domain": same_domain, "technical_ceo": technical,
            "frontier_lab_alum": frontier}


def enrich_team_harmonic(candidate) -> None:
    """PREMIUM augmentation via Harmonic (needs HARMONIC_API_KEY): adds the exit/talent-flow
    fields GitHub can't know, and augments the GitHub-derived ones (OR for booleans, max for
    team_size). No-op without the key / on any failure."""
    key = os.getenv("HARMONIC_API_KEY")
    if not key or not candidate.url:
        return
    try:
        with _harmonic_client(key) as cx:
            r = cx.post("/companies", params={"website_url": candidate.url})
            if r.status_code not in (200, 201):
                return
            f = _founder_fields(r.json(), _domain_root(candidate.url))
    except Exception:
        return
    raw = candidate.raw
    # Exits / talent-flow — Harmonic's exclusive domain.
    for k in ("prior_exit", "exit_size_usd", "repeat_founder_count", "same_domain"):
        if f.get(k) is not None:
            raw[k] = f[k]
    # GitHub-derivable fields — AUGMENT, don't destroy a free True / smaller estimate.
    if f.get("team_size"):
        raw["team_size"] = max(raw.get("team_size") or 0, f["team_size"])
    for k in ("technical_ceo", "frontier_lab_alum"):
        if f.get(k):
            raw[k] = True


def enrich(candidate) -> None:
    """Run the FREE GitHub team signal always, then the PREMIUM Harmonic augmentation if
    HARMONIC_API_KEY is set. Either path no-ops gracefully when its prerequisites are absent."""
    enrich_team_github(candidate)
    enrich_team_harmonic(candidate)


class TeamSource(Source):
    """Optional discovery: surface stealth founders from a Harmonic people saved-search.
    Returns [] unless HARMONIC_API_KEY + HARMONIC_PEOPLE_SEARCH_ID are both set."""
    name = "team"

    def __init__(self, people_search_id: str = None):
        self.people_search_id = people_search_id or os.getenv("HARMONIC_PEOPLE_SEARCH_ID")

    def fetch(self, limit: int = 25, store=None) -> list:
        key = os.getenv("HARMONIC_API_KEY")
        if not key or not self.people_search_id:
            return []
        try:
            with _harmonic_client(key) as cx:
                r = cx.get(f"/saved_searches/{self.people_search_id}/results",
                           params={"size": limit})
                r.raise_for_status()
                payload = r.json()
        except Exception as e:
            print(f"[signal][warn] team discovery failed: {e}")
            return []

        out = []
        for person in (payload.get("results") or payload.get("people") or [])[:limit]:
            co = person.get("current_company") or person.get("company") or {}
            name = co.get("name") or person.get("full_name") or "stealth founder"
            website = co.get("website")
            url = (website.get("url") if isinstance(website, dict) else website) or ""
            cand = Candidate(name=name, source="team", url=url,
                             summary=co.get("description") or person.get("headline") or "",
                             signal_metric="stealth — surfaced via founder graph (Harmonic)",
                             tags=co.get("tags") or [], raw={})
            enrich(cand)
            out.append(cand)
        return out
