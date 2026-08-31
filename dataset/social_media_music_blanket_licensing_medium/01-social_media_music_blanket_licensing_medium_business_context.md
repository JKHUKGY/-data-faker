# Social Media — Short-Video Platform Music Blanket Licensing & Compliance Audit Business Context

> This document is the business context for the `social_media_music_blanket_licensing_medium` dataset. It answers the question "what kind of company is this, what business is it in, and what problem are we solving?" For the data structure, see `02-social_media_music_blanket_licensing_medium_er_document.md`; for the SQL queries, see `03-social_media_music_blanket_licensing_medium_sql_queries.md`.
>
> Intended reader: you're a smart new hire who just joined the project. You don't need to know anything about music rights or social media products going in. After reading this document, you should be able to explain this company's business, its industry, and the questions this analysis is meant to answer at your first stand-up.

---

## 1. Company Profile

**ReelWave, Inc.** is a fictional North American short-video social platform headquartered in San Francisco, California, founded in 2018. Its product is the familiar "vertical scroll" social video app. Users scroll and socialize for free; the company monetizes through advertising — users are the product, and advertisers are the customers.

Company profile (order-of-magnitude figures, not exact):

- **User base:** roughly 85 million monthly active users (MAU) across the US and Canada.
- **Revenue:** roughly $1.9 billion in annual ad revenue.
- **Headcount:** roughly 3,200 employees.
- **The business line this dataset focuses on:** an internal music team called **"Sounds,"** which sits under the Content Partnerships / Label Relations organization. This team does two things: first, it signs **blanket license** deals with record labels, buying legal usage rights to a label's entire music catalog on the platform; second, it runs the **Creator Fund**, which shares a portion of revenue with everyday creators whose videos go viral on the strength of original "sounds" (user-made remixes).
- **Geography:** the platform serves users in the US and Canada, and the record labels and aggregators it signs are likewise headquartered mainly in North America.

Roles at the company relevant to this analysis (the SQL queries reference these people by title):

| Title | What they care about |
|------|----------|
| General Counsel | The overall legal risk exposure of blanket license contracts, especially contract breaches that could be subject to retroactive claims |
| Head of Label Relations | Overall negotiation strategy and renewal prioritization across the portfolio of 20 blanket license deals |
| Director of Rights Compliance | Setting audit policy, escalating compliance risk, and reporting exposure to Legal and Finance |
| Rights & Licensing Compliance Officer | The **primary persona** for this dataset — auditing each contract, each UGC sampling flag, and each week's Creator Fund payout for compliance |
| Creator Fund Program Manager | The Creator Fund payout formula, creator experience, and retention of top creators |
| VP of Finance (FP&A) | Total blanket license spend and the potential retroactive payout amounts tied to compliance risk exposure |

---

## 2. Business Model

ReelWave makes money from advertising, but its "Sounds" music team doesn't generate revenue directly — it manages a **necessary compliance cost that also doubles as a product moat**: most viral videos on the platform have background music or sound, and if that music isn't properly licensed, the company is exposed to copyright infringement lawsuits at any time.

Here's how this "business" actually works:

1. ReelWave signs a **blanket license agreement** with a record label (or with a **label aggregator** representing several independent labels) — instead of negotiating song by song, the company pays a **fixed annual license fee** in exchange for legal rights to use that label's **entire catalog of master recordings** on the platform: whether a track is played in full, or dropped **unaltered** into a user's video, both are covered by this master-recording blanket license.
2. That annual fee is negotiated at signing based on a **usage share assumption** — an estimate of "roughly what percentage of the platform's total music-video views we expect this label's catalog to represent." The higher the assumed share, the higher the fee typically is.
3. The problem: once signed, these contracts are usually locked in for 2 to 3 years, and the fee barely changes over that term — but a catalog's **actual usage share drifts over time**. A label's songs might suddenly go viral through a TikTok-style challenge, pushing actual usage share well above the assumption made at signing; or the buzz could fade, leaving actual share well below the assumption. Either way, the fee never gets renegotiated.
4. But the blanket license only covers "using the master recording unaltered." The moment a user's own **remix** **samples** a clip from an official track and changes it — speed, pitch, slicing, remixing — it creates a **derivative work**, which touches two categories of rights the master-recording blanket license **typically doesn't cover**: the right to make derivative/adapted works, and the **publishing** (composition) side of rights. The sampled material may also **fall entirely outside any current contract's coverage** (the artist has left the label, the track predates the contract window, or it comes from a label with no blanket deal at all). So any remix that hasn't cleared the internal sampling-approval process is a potential **unauthorized sample** and a rights conflict that needs to be flagged, verified, and resolved in a human review queue. This is exactly why a label can have a fully signed blanket license and ReelWave can still face copyright exposure from a single remix.
5. For creators whose videos go viral on the strength of an original sound (a melody or vocal they made themselves, not based on any official track), the company runs the **Creator Fund**: it calculates each sound's share of weekly views and distributes a fixed weekly pool of money proportionally.

So the core tension in this business line is: **the assumption locked into the contract vs. the constantly shifting reality.** Once a fee assumption is written into a contract, it's hard for it to keep reflecting reality — whether that's a label's catalog heating up or cooling off, whether UGC sampling crossed a rights line, or how the Creator Fund's payout window is sliced. In every case there's a structural gap where the contract or rule lags behind actual usage — and it's exactly the kind of problem a Rights & Licensing Compliance Officer needs to surface proactively through data, rather than waiting for a label or creator to complain.

---

## 3. Industry Primer: Music Blanket Licensing on Short-Video Platforms

If you're coming from a different industry, this section will get you up to speed quickly.

**What value does this industry create?** Music is core to short-video content — a video with the right background music gets watched to completion and shared far more than a silent one. But a platform can't realistically negotiate and pay for every single song used across billions of user videos, one at a time. **Blanket licensing** solves this scale problem: the platform buys rights to a label's entire catalog in one deal, the label gets predictable fixed income, and users can pick any song when creating a video without worrying about rights clearance.

**Main player categories (no real companies named).**

- **Record label:** a company that owns the recording rights to songs, ranging from major multinational labels to mid-size regional labels.
- **Label aggregator:** a middleman that licenses on behalf of a group of independent musicians or small labels, categorized in this dataset as **indie_aggregator**.
- **Short-video platform:** a product like ReelWave, which is both the consumer of the catalog and the payer of both the blanket license fees and the Creator Fund.
- **Creator:** an everyday user who posts videos on the platform, some of whom drive significant views with self-made original sounds or remixes and may be eligible for a Creator Fund payout.

**Regulatory and compliance framework (North America).** Music rights in the US are governed mainly by the Copyright Act and the case-law boundaries of "fair use." There's no single federal regulator dedicated to short-video platforms, but a few frameworks still set the floor for compliance:

- **Copyright infringement liability:** using copyrighted recordings or compositions without authorization constitutes infringement, and rights holders can sue for damages — this is the fundamental reason blanket licensing exists.
- **DMCA (Digital Millennium Copyright Act):** provides safe-harbor protection for platforms hosting user-uploaded content, along with the accompanying notice-and-takedown obligations.
- **Most-Favored-Nation (MFN) clauses under contract law:** many blanket license agreements include an MFN clause — if the platform later gives a better deal to another label, this contract's terms have to adjust accordingly. This is the contractual basis for one of this dataset's traps.
- **Industry norms around platform creator revenue sharing:** while not legally mandated, transparency in creator fund-style programs has become an issue that both public opinion and regulators are watching closely.

**Current macro forces.** Short-video-driven viral hits make catalog popularity shift extremely fast — a song can go from obscure to platform-wide ubiquity in two weeks, and fade just as quickly. Platforms competing for exclusive or preferred catalog access are offering increasingly aggressive rates to up-and-coming aggregators, which directly raises the question of whether the MFN protections that legacy labels negotiated at signing are actually being honored. Meanwhile, the explosive growth of UGC remixes has made "who is legally using whose rights" harder to track than ever before.

---

## 4. Project Framing: What You're Doing

You're a newly hired analyst on ReelWave's **Rights & Licensing Compliance** team, working as a **Rights & Licensing Compliance Officer** (the primary persona for this dataset, per the table in Section 1). You report directly to the **Director of Rights Compliance**, and your output will be shared with both the **General Counsel** and the **VP of Finance (FP&A)**.

Before you arrived, the "Sounds" team relied on the personal judgment of label relations managers and scattered spreadsheets to decide whether contracts were worth it, whether UGC was compliant, and whether the Creator Fund was fair — nobody had systematically cross-checked blanket license contract terms, monthly catalog usage data, UGC sampling flags, and Creator Fund payout records against each other. The Director has tasked you with pulling these pieces of data together in SQL ahead of the next round of label renewal negotiations, producing a **Quarterly Blanket License Compliance & Risk Report** that directly supports renewal negotiation strategy, UGC compliance remediation priorities, and Creator Fund payout rule adjustments.

All analysis is anchored to a fixed reference date, **REFERENCE_DATE = 2026-06-30** (see Section 6 for details).

---

## 5. Business Questions This Project Answers

The entire dataset is designed to answer the four core business questions below. Each question maps to a corresponding data trap in the ER document and a corresponding query in the SQL queries document.

1. **Q1 Usage-Share Drift:** Which labels' **actual usage share** has drifted significantly from the **usage share assumption** written into their contract at signing, leaving the annual fee badly mismatched with real usage value? And is the drift in the platform's favor, or is the label being shortchanged?
2. **Q2 Unauthorized-Sample Compliance:** How many flagged UGC remix sampling conflicts have gone unresolved past the company's internal service-level target (SLA)? How much ad revenue exposure sits behind these unresolved tracks?
3. **Q3 Weekly Snapshot Misalignment:** Does the Creator Fund's calendar-week payout logic systematically underpay sounds whose "viral window" straddles two calendar weeks?
4. **Q4 MFN Clause Compliance:** Are there any labels protected by a Most-Favored-Nation (MFN) clause that are actually receiving a lower "annual fee per usage-share point" than a label signed later without MFN protection? If so, the company may be in breach of contract and exposed to retroactive claims.

Beyond these four marquee questions, the dataset also supports a range of operational analyses — label portfolio composition, catalog release cadence, creator composition, seasonal trends, and the like — for day-to-day operations and portfolio management questions.

---

## 6. Data Scope Overview

- **Time span:** monthly catalog usage data covers 18 months (2025-01 through 2026-06); Creator Fund weekly payout data covers roughly the last 12 months. Usage-share drift, UGC compliance flags, and MFN clause compliance are all snapshot analyses run against this historical data at a fixed reference date. Every "today / current snapshot" reference in this project is anchored to the fixed reference date **REFERENCE_DATE = 2026-06-30**.
- **Data volume (order of magnitude, plain terms):** 20 signed labels (3 major, 7 mid_size, 10 indie_aggregator), roughly 600 tracked "Sounds" (400 official tracks + 200 creator-made remixes/original sounds), roughly 150 Creator Fund-eligible creators, roughly 9,700 rows of monthly catalog usage records, roughly 8,800 rows of Creator Fund weekly payout records, and roughly 5,400 rows of daily fine-grained usage records for 120 "trending-candidate sounds" — about 25,000 rows total.
- **Deliberate scope decisions:**
  - **Blanket-licensed catalogs only, not single-track sync licensing:** ReelWave has a separate team handling single-track sync licensing for ads and film/TV; this dataset doesn't touch that, so as to avoid mixing two entirely different licensing logics.
  - **Only the currently active contract per label is modeled:** expired historical contracts aren't tracked; the focus is on whether the "currently active portfolio" is compliant, which is the real decision context.
  - **Creator Fund covers only UGC remixes/original sounds, not official tracks:** revenue from official tracks is already covered by the blanket license fee and isn't double-counted in the Creator Fund.

(This section doesn't list specific tables; see the ER document for the table structure.)

---

## 7. Industry Knowledge Primer

About half an hour's worth of background you'll need before this data will make sense. It helps to think of it as "the life cycle of a blanket license contract."

**1) The three key terms of a blanket license contract.**

```
usage share assumption → annual license fee → MFN clause (optional)
```

- **Usage share assumption:** at signing, both parties estimate roughly what percentage of the platform's total music-video views this label's catalog is expected to represent going forward, usually based on the label's historical popularity and reach.
- **Annual license fee:** the fixed fee negotiated based on the usage share assumption, which stays essentially unchanged for the contract term (typically 2-3 years). You can back into an **effective rate** from this: annual fee ÷ share assumption in percentage points, i.e., "how much the platform is willing to pay for each percentage point of catalog usage share."
- **MFN clause:** some contracts (usually ones major labels have the leverage to negotiate) state that if the platform later agrees to a higher effective rate with any other label, this contract's rate must be raised to match. It's how major labels protect themselves from being undercut by "a newcomer getting a better deal."

**2) How usage share is calculated.** Each month, video views from all official tracks — plus views from UGC remixes that sample an official track — get attributed to the corresponding label. A label's usage share for a given month = views attributed to that label ÷ total views across all attributable labels × 100%. This share fluctuates over time — a song goes viral, and the share rises; the buzz fades, and the share falls. **The usage share assumption from signing is just a static snapshot — it never auto-updates to reflect actual usage.**

**3) UGC remixes and sampling.** Users can create derivative work based on an official track (clipping, speeding up, or blending in other sounds) — this is called a **remix**, and the act of clipping/using a piece of the original track is called **sampling**. The platform has an internal approval process to determine whether a given instance of sampling went through proper rights clearance. Sampling that skipped this process, or that clearly overstepped, gets flagged as an **unauthorized sample** — a type of **rights conflict** — and must be resolved within an internally agreed time limit (SLA), whether through clarification, retroactive licensing, or takedown.

Here's a key point that's easy to overlook: the blanket license buys the right to "**play/embed the master recording unaltered**" — a remix that alters the sample creates a derivative work, which falls into a gray zone the master-recording license doesn't cover. So even if the original track comes from a label under contract, the sample itself still needs separate rights clearance. It's also worth noting that the vast majority of audio matching on the platform happens automatically at upload time via **audio fingerprinting**. The `rights_conflict_flag` table in this dataset only records the residual set of disputed cases that automated fingerprinting couldn't confidently resolve and that required **human-escalated review** — which is why its record count (in the dozens) is so much smaller than the platform's total video volume.

**4) The Creator Fund's weekly payout logic.** The Creator Fund is a pool with a fixed weekly budget, distributed among participating sounds based on each sound's share of that week's views — the higher a sound's view share, the more it earns that week. The implicit assumption behind this mechanism is that "a song's viral run happens entirely within a single calendar week." In reality, though, a video might start gaining traction on Thursday, peak on Saturday, and keep spreading through Sunday into the following Monday — **the viral window straddles two calendar weeks** — which means that sound never looks like "the biggest hit of the week" in either week taken individually, and it ends up earning less than it should.

**5) The math behind effective rate and MFN auditing.** Checking whether an MFN clause has been violated comes down to calculating every contract's **effective rate** (annual fee ÷ share assumption), then checking: does any MFN-protected contract have an effective rate lower than the highest effective rate among contracts **without** MFN protection? If so, the platform should have raised that MFN contract's rate to match the highest rate, and hasn't — that's a contract breach, and the longer it goes uncorrected, the larger the retroactive claim exposure grows.

---

## 8. Glossary

Every piece of jargon that shows up in the ER document or SQL queries gets a plain-language explanation here, plus a note on why it matters for this project. All terms are kept in their original English form.

| Term | Plain-language explanation | Why it matters here |
|------|----------|----------------------|
| Blanket license | A one-time buyout of a label's entire catalog usage rights, instead of negotiating song by song | The core business object of the `label_blanket_license` table |
| Usage share assumption | The estimate, made at signing, of a catalog's expected future share of usage | A shared input variable for Trap 1 and Trap 4 |
| Effective rate | Annual fee divided by the share assumption — how much is paid per usage-share point | The core calculation behind Trap 4 (MFN compliance) |
| MFN (Most-Favored-Nation) clause | A clause guaranteeing terms no worse than what any other party gets | The contractual basis for Trap 4 |
| Label aggregator | A middleman licensing on behalf of multiple independent musicians/small labels | The indie_aggregator category in the `label` table |
| Sound | ReelWave's umbrella term for any piece of music usable in a video, covering both official tracks and user remixes | The core entity in the `sound` table |
| Official track | A full song owned and copyrighted by a label, covered by blanket licensing | `sound.sound_type = official_track` |
| UGC remix | A derivative sound made by a user (a remix), which may sample an official track or be entirely original | `sound.sound_type = ugc_remix`; the core object for Trap 2/3 |
| Sampling | The act of clipping or using a piece of an official track within a UGC remix | Determines whether rights approval is required |
| Rights conflict | A remix sampling something the master-recording blanket license doesn't cover (derivative rights, the publishing side, or a track outside any contract) that requires human-escalated review | The `rights_conflict_flag` table; the core of Trap 2 |
| SLA (Service-Level Agreement) | Here, the internal deadline for resolving a rights conflict from the moment it's flagged | The baseline for determining whether Trap 2 is "overdue" |
| Revenue at risk | Estimated ad revenue tied to a remix with a rights conflict | Measures the financial consequences of Trap 2 (a conservative ad-revenue proxy, not a statutory-damages figure) |
| Creator Fund | The platform's fixed weekly budget pool paid out to creators of popular original sounds | The `creator_fund_weekly_payout` table |
| Trending snapshot / snapshot week | The calendar-week (Monday-Sunday) time granularity the Creator Fund uses to calculate payouts | Defines the payout period for Trap 3 |
| Viral spike window | The consecutive days during which a sound's views spike sharply | The "real" heat window compared against the snapshot week in Trap 3 |
| Spike week alignment | Whether a spike window falls entirely within one week (aligned) or straddles two weeks (split_across_weeks) | A field on the `sound` table that directly drives the payout gap in Trap 3 |
| MAU (Monthly Active Users) | Monthly active user count | A common metric describing platform scale |

---

## 9. Key Metrics and Formulas

Below are the metrics used in the SQL queries, or that the reader should know about. Formulas are written as plain SQL-style pseudocode, with notes on inputs and conventions.

**Usage-Share Drift (Trap 1)**

```
label_month_videos(label, month) = SUM(sound_monthly_usage.video_count)
    WHERE sound.primary_label_id = label OR sound.source_sound_id IN (official tracks under this label)
      AND sound_monthly_usage.usage_month = month
labeled_total_videos(month) = SUM(label_month_videos) across all 20 labels
usage_share_pct(label, month) = label_month_videos(label, month) / labeled_total_videos(month) * 100
usage_share_drift_pp(label) = average usage_share_pct over the most recent 3 months − label_blanket_license.usage_share_assumption_pct
```

**Effective Rate and MFN Compliance (Trap 4)**

```
effective_rate_per_point(label) = label_blanket_license.annual_license_fee_usd / label_blanket_license.usage_share_assumption_pct
max_non_mfn_rate = MAX(effective_rate_per_point) WHERE has_mfn_clause = FALSE
mfn_breach(label) = has_mfn_clause = TRUE AND effective_rate_per_point(label) < max_non_mfn_rate
mfn_breach_exposure_usd(label) = (max_non_mfn_rate − effective_rate_per_point(label)) × usage_share_assumption_pct   -- calculated only for labels where mfn_breach = TRUE
```

**Unauthorized-Sample Compliance Audit (Trap 2)**

```
is_overdue(flag) =
    (resolution_status IN ('open', 'under_review') AND (REFERENCE_DATE − flagged_date) > sla_days_target)
    OR (resolved_date IS NOT NULL AND (resolved_date − flagged_date) > sla_days_target)
open_revenue_at_risk_usd = SUM(revenue_at_risk_usd) WHERE resolution_status IN ('open', 'under_review')
```

**Creator Fund Weekly Snapshot Misalignment (Trap 3)**

```
payout_rate_per_1000_views(group) = SUM(payout_usd) / SUM(weekly_view_count) × 1000
    grouped by sound.spike_week_alignment (aligned vs split_across_weeks)
underpayment_gap_pct = (payout_rate_per_1000_views(aligned) − payout_rate_per_1000_views(split_across_weeks))
    / payout_rate_per_1000_views(aligned) × 100
```

> **Conventions worth noting (so downstream SQL doesn't contradict itself):**
> - The denominator of `usage_share_pct`, `labeled_total_videos`, only counts views that **can be attributed to a label** (official tracks plus remixes that sample an official track). Fully original UGC sounds that don't sample any official track are excluded from this denominator, because they aren't covered by any blanket license contract.
> - `effective_rate_per_point` uses the **share assumption from signing**, not the current actual share, because the contract's annual fee was negotiated based on that assumption at the time — this is exactly why Trap 1 and Trap 4 look at two different angles: "assumption vs. actual usage" versus "assumption vs. contract-rate fairness."
> - `is_overdue` uses a different elapsed-time calculation for resolved records versus still-open (open/under_review) records — the two can't be handled with a single `resolved_date` field, because unresolved records have a null `resolved_date`.
> - **Don't conflate the two "revenue exposure" cuts.** `open_revenue_at_risk_usd` (the formula above) only totals flags that are **still unresolved** (`open` / `under_review`), on the order of $140K, answering "how much exposure is currently outstanding and could be subject to a claim at any moment." SQL Query 6, by contrast, aggregates `revenue_at_risk_usd` across the **overdue set** (unresolved-and-overdue plus resolved-but-late, combined), on the order of $210K, answering "how much exposure has historically been mishandled past the deadline and exposed the company to legal risk." Both numbers are correct, but they're cut differently (one by resolution status, one by whether the SLA was missed) — when citing either in a report, be explicit about which cut you mean so readers don't assume they're the same figure.
> - **`revenue_at_risk_usd` is a conservative lower-bound proxy — it is not the real legal exposure.** It only estimates the ad revenue earned by the videos tied to the remix in question (and it correlates with that remix's popularity — the more viral, the higher the estimate). But under US copyright law, the real driver of legal risk is **statutory damages (17 U.S.C. §504)** — up to $150,000 per willful infringement — plus injunction and litigation risk, which is what actually keeps the General Counsel up at night. So when citing the $210K/$140K figures in a report, be clear that they measure "ad revenue exposure," not "potential damages owed." The real exposure lives in the long tail of statutory damages and is typically far higher than this proxy.
> - `spike_week_alignment` is only meaningful for the 120 trending-candidate sounds where `sound.is_trending_monitored = TRUE`; other sounds don't have daily fine-grained tracking, so there's no way to tell whether their spike window straddled a week boundary.
