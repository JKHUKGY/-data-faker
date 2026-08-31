# Ember Realms Saga Player Economy and Third-Party Top-Up Channel Health Analysis: Business Context

## 1. The Company: Pinnacle Peak Games

Pinnacle Peak Games is a fictional mobile game studio headquartered in Seattle, Washington. It was
founded in 2019 by a handful of artists and systems designers who came out of traditional console
game studios, and it now has roughly 90 employees. The company does exactly one thing: it operates
a F2P (Free-to-Play) gacha collection RPG called *Ember Realms Saga*. The game launched globally on
January 6, 2025, and in the 18 months since launch it has racked up more than 8 million downloads and
roughly 900,000 monthly active users. It is the company's sole source of revenue.

The org chart is deliberately flat. The CEO also serves as creative director and sets the game's
direction; at the same level sit a CFO and a Head of Game Design. Monetization is owned end-to-end by
a VP of Monetization & Publishing, under whom sit three groups: Live Ops (the team that continuously
ships events, gacha pools, and pricing changes, with a Live Ops Program Manager scheduling the event
calendar), Trust & Safety (fraud and account-risk, split internally into a Lead and Analyst tier), and
a small Player Support team led by a Player Support Manager. You have just joined the Live Ops team as
a Game Economy Analyst, reporting directly to the Director of Live Operations, who in turn reports to
the VP of Monetization & Publishing. Aside from these functions, the rest of the 90-person company is
product, engineering, and art — the game development side — which is out of scope for this dataset.

## 2. Business Model: Free to Download, Carried by the Top 1% of Players

Downloading *Ember Realms Saga* and most of its content is free. Nearly all company revenue comes
from voluntary in-app purchases of a premium currency called Aether Shards ("Shards" for short) — a
currency that can only be bought with real money, as distinct from free resources earned by defeating
enemies. Players spend real money on Shards, then spend Shards either pulling from gacha pools
(a randomized, lottery-style mechanic for acquiring characters and items) or buying bundles directly.

The defining feature of this business is extreme revenue concentration: the vast majority of players
never pay a cent, while a small group of "heavy spenders" accounts for nearly all revenue. The industry
calls these tiers "whale" (extremely high-spending players), "dolphin" (mid-tier spenders), and
"minnow" (small spenders). In this dataset, the top 1% of players (50 people) account for roughly 65%
of IAP revenue, the top 4% (dolphins plus whales combined) account for roughly 94%, and the remaining
96% of players (including everyone who has never paid) account for only about 6%. This isn't a quirk of
this particular dataset — it's the norm across nearly every F2P mobile game — but it also means the
company's revenue is extremely fragile: if a handful of those 50 whales churn, the impact shows up
directly in the financials, and that's exactly what keeps the VP of Monetization up at night.

IAP products range from a $0.99 starter Shard pack up to the $199.99 "Ultimate Shard Vault," and the
higher the price point, the more of it whales tend to buy. Beyond Shard packs, the company also sells a
Monthly VIP Pass, a Battle Pass Premium, and time-limited crossover bundles.

## 3. Project Background: An Economy Health Review Triggered by a Trust & Safety Escalation

In June 2026, the Trust & Safety team, during routine chargeback monitoring (a chargeback is when a
cardholder disputes a charge with their card issuer as "I didn't authorize this," forcing the bank to
refund the merchant), noticed that a cluster of accounts had chargeback rates far above normal over the
past several months. These accounts were also heavily clustered on device fingerprints (the same
phone or emulator registering multiple accounts leaves a matching fingerprint), and following that
thread turned up a batch of transactions where players had bought Shards through unauthorized
third-party "top-up agents" — third parties who sell game currency outside official channels, typically
profiting off regional price differences.

As a result, the VP of Monetization moved up the normally quarterly "player economy health" review and
asked the Live Ops team to deliver a complete analysis within two weeks, in time for the July board
deck. The analysis needs to cover whale dependency, whether gacha odds are being honestly disclosed,
whether the event cadence is burning through player retention, and just how large a financial and
reputational risk this top-up/fraud incident actually is. The material the analyst delivers for this
review is exactly what this dataset is built to support.

## 4. Industry Overview: F2P Mobile Gaming and Gacha Monetization

Mobile gaming moved long ago from "sell a copy" to "download for free, monetize through IAP." Within
that model, gacha (a randomized draw mechanic that originated in Japanese mobile games and is now a
worldwide-standard monetization design) is the dominant revenue driver for collection RPGs: players
spend Shards to pull from a pool, and the odds of pulling a rare character or item are typically kept
between 1% and 5% (in this game, the disclosed probability for the top rarity tier, Legendary, falls
between 2% and 5%). The rarer the tier, the more it drives players to keep paying in hopes of landing it.

This industry faces several persistent regulatory and reputational pressures:

1. **Probability disclosure compliance**: A number of countries and regions (including China, Japan,
   Belgium, and some U.S. states) require or recommend that game companies publish their gacha odds.
   What players and regulators worry about most is "actual odds lower than the disclosed odds" — if
   that ever comes to light, it can range from a collapse of community trust to a full consumer-protection
   investigation.
2. **Minor and consumer protection**: Regulation is tightening in many jurisdictions, requiring game
   companies to identify and limit spending by minors and to provide clearer spending disclosures.
3. **Payment fraud and the gray-market top-up ecosystem**: In some regions — especially markets with
   volatile local currency exchange rates or where official store pricing runs low, such as Turkey or
   Argentina — professional "top-up agents" buy currency cheap and resell it at a markup. These
   transactions bypass official payment channels entirely, so the platform both loses its cut of the
   payment processing fee and takes on a much higher risk of downstream chargebacks and refunds.
4. **Player retention and "event fatigue"**: Live Ops teams drive spending by continuously shipping
   time-limited events, but events scheduled too close together ("stacked") tend to wear players out.
   A short-term revenue bump can amount to borrowing against future retention — a pattern the industry
   sometimes calls "growth that eats its own future."

## 5. The 5 Business Questions You Need to Answer

As the Game Economy Analyst, you have two weeks to produce findings that support the VP of
Monetization's presentation to the July board meeting. Each of the following five questions maps to
one deliverable conclusion:

- **Q1 Whale dependency**: Is IAP revenue overly concentrated in a very small number of players? If
  several of these whales were to churn, how large would the revenue impact be? Should the company
  build a dedicated customer-success (VIP retention) program for this group?
- **Q2 Disclosed-probability deviation**: Across the 8 gacha pools, is there evidence that the actual
  Legendary (the top rarity tier) drop rate is materially below the officially disclosed probability?
  If so, which pools are affected, how large is the gap, and does it warrant urgent remediation and
  proactive player compensation?
- **Q3 Live Ops false prosperity**: Do high-frequency, stacked time-limited events genuinely lift
  average spend and engagement in the short run, while quietly burning through those same players'
  future retention? Is this kind of "borrowed growth" worth continuing?
- **Q4 Top-up/discount channel arbitrage**: Compared with normal channels and normal code redemption,
  what do actual paid prices and refund/chargeback risk look like for unauthorized third-party top-up
  agents, and for region-exclusive discount codes that leak and get abused outside their intended
  region? How much revenue and trust do these two arbitrage channels quietly erode each year, combined?
- **Q5 Refund fraud rings**: Are there clusters of accounts sharing the same device (suspected
  sock-puppet accounts registered in bulk by the same person or ring) that show abnormally high
  refund/chargeback rates? Which account clusters should Trust & Safety prioritize for banning?

## 6. Data Scope at a Glance

To keep the analysis tractable and internally consistent, this dataset is scoped to: the roughly 18
months of operating data for *Ember Realms Saga* from its global launch (2025-01-06) through the
analysis reference date REFERENCE_DATE = 2026-06-30, for a random sample of 5,000 players (including
players who have never paid, so metrics like "share of paying players" can be computed correctly).
These 5,000 players are just a manageable analytical sample drawn from the 8 million cumulative global
downloads — they do not represent the company's full player base or its overall financial scale.

The dataset consists of 12 tables and roughly 70,000 rows, covering player install attribution, 10
payment channels (2 official app stores, 1 official direct web purchase channel, 2 officially
authorized regional billing partners, and 5 unauthorized top-up agents), pricing coefficients for 10
billing regions, 12 IAP products, 8 gacha pools, 45 discount codes, 30 Live Ops events, roughly 17,700
IAP transactions, roughly 40,000 gacha pull records, roughly 7,000 event participation records, 500
refund/chargeback/risk events, and 720 support tickets.

## 7. Crash Course: What You Need to Know to Read This Data

**How gacha pulls work.** Players spend Shards to do a "single pull" or a "10-pull" (pulling 10 times
at once, usually with a better guaranteed floor result). Each pull randomly produces a rarity result
according to the pool's preset probabilities. This dataset uses four rarity tiers — Common, Rare, Epic,
and Legendary — where Legendary is the top tier and the one players want most.

**Standard pools vs. rate-up pools.** The `gacha_pool` table has two types: `standard` (a permanent
pool, open long-term, with relatively stable odds) and `limited_rateup` (a limited-time "rate-up" pool,
usually tied to a new character's release, open for about 2 weeks, and advertised as having "boosted
odds" for that new character). To land the limited character, players tend to concentrate heavy
spending and pulling into that 2-week window, which is also one of the biggest revenue spikes of the
year.

**Why regional pricing gets arbitraged.** Mobile game publishers typically set different official list
prices per country based on purchasing power and local currency exchange rates (`region_price_tier.price_index`
is exactly this conversion coefficient). For example, the same bundle might list at $9.99 in the U.S.
but only the local-currency equivalent of $5.49 in Turkey. That price gap is what fuels the "top-up
agent" business: someone buys in bulk in the cheap region and resells at a markup to players in the
expensive region. Both sides feel like they're getting a deal — meanwhile the platform is quietly
losing its revenue cut and absorbing higher fraud risk.

**Live Ops event cadence.** Game companies rely on a steady stream of time-limited events (login
rewards, drop-rate doublers, flash sales, new-character tie-ins, anniversary celebrations, and so on)
to keep players engaged and spending. A well-known industry risk is that if events are scheduled too
tightly ("stacked," with less than a week between the end of one and the start of the next), players'
willingness to spend gets squeezed dry in the short term — and that tends to accelerate churn for a
subset of those players not long after. This is the pattern known as "borrowed growth."

**Refunds vs. chargebacks.** `refund_requested` is when a player proactively contacts support to ask
for their money back, which the company can choose to approve or deny. `chargeback_filed` is when a
player skips support entirely and goes straight to their card-issuing bank to dispute the charge — the
bank then forces the merchant to refund the money and typically also charges an extra chargeback fee.
For the merchant, a chargeback is more disruptive and more costly than an ordinary refund.

## 8. Glossary

| Term | Explanation | Why It Matters |
|------|------|------------|
| F2P (Free-to-Play) | A game model that is free to download and monetizes through in-app purchases | Establishes that revenue comes entirely from voluntary spending, not an upfront price |
| IAP (In-App Purchase) | Items players pay for directly inside the game | This dataset's `iap_transaction` table records every single IAP |
| gacha | A randomized, lottery-style acquisition mechanic | The core spending driver in this game |
| whale / dolphin / minnow | Industry shorthand for tiering players by how much they spend | The unit of analysis for Q1 (whale dependency) |
| rate-up banner (limited pool) | A time-limited gacha pool tied to a new character's release, typically open about 2 weeks | The main place where the Q2 disclosure-deviation problem shows up |
| disclosed probability | The gacha odds the game company publishes publicly | The gap versus actual odds is the core metric Q2 measures |
| chargeback | When a cardholder forces a transaction reversal directly through their card issuer | Costlier than an ordinary refund; a core risk signal for Q4/Q5 |
| device fingerprint | A unique identifier derived from device/environment characteristics, used to detect multiple accounts registered on the same device | The key field for identifying "sock-puppet fraud rings" in Q5 |
| third-party agent | A third-party channel that tops up players' in-game currency without official authorization from the game company | The subject of the Q4 analysis |
| region price arbitrage | Profiting by buying at a low official price in one country and reselling at a higher price in another | The economic foundation that makes the top-up agent business possible |
| ARPPU (Average Revenue Per Paying User) | Standard definition: average revenue contributed per paying player. In this dataset, when comparing two time windows of very different lengths, we additionally normalize by calendar days into "ARPPU per Active Day" (see Section 9), to avoid conclusions being skewed by differing window lengths | Measures the quality of paying players; Query 7 confirms that the day-normalized "ARPPU per Active Day" is significantly higher inside stacked-event windows |
| stacked event | A high-frequency event that starts less than 7 days after the previous one ends | The core grouping variable for the Q3 analysis |
| churn / retention | Players going inactive vs. staying continuously active | Q3 measures retention as "still active 30 days after the event" |
| SKU (Stock Keeping Unit) | The smallest sellable unit of a product; here, each individually purchasable IAP item | Each row in the `iap_product` table is one SKU |

## 9. Key Metrics and Formulas

```
Whale Revenue Share
  = SUM(iap_transaction.paid_price_usd WHERE player_segment = 'whale')
    / SUM(iap_transaction.paid_price_usd)
  Grouping by player_segment gives the share for each of whale / dolphin / minnow / non_payer.

Probability Gap (units: percentage points, pp)
  = 100 * COUNT(gacha_pull_log WHERE result_rarity='Legendary' AND gacha_pool_id = X)
        / COUNT(gacha_pull_log WHERE gacha_pool_id = X)
    - gacha_pool.disclosed_legendary_prob_pct (for pool X)
  The more negative the gap, the further the actual drop rate falls below the disclosed probability.

Post-Event Retention Gap
  Among players who participated in at least 1 stacked event, compare:
  - players with stacked_count >= 2 (meets the fatigue condition)
  - players with stacked_count == 1 (control group)
  (The control group is defined as "participated in exactly 1 stacked event" rather than "never
  participated in any stacked event," so that both groups satisfy the same precondition of "having
  stuck around long enough to even encounter a stacked event." This removes survivorship bias —
  otherwise the "never encountered a stacked event" group would be full of short-lived players who
  churned early, which would completely distort the conclusion. Query 8 walks through this in detail.)
  For each group, compute the share of players whose player.last_active_date is still no earlier than
  30 days after their last stacked event ended; the difference between the two shares is the retention
  gap. To avoid right-censoring (false-looking churn caused by the observation window not being long
  enough), only players whose "last stacked event end date + 45 days" still falls before REFERENCE_DATE
  are included.

Agent Discount Rate
  = 1 - AVG(iap_transaction.paid_price_usd / iap_transaction.list_price_usd
            WHERE channel_partner.is_authorized = false)

Channel Risk Rate
  = COUNT(DISTINCT refund_chargeback_risk_event.id WHERE transaction is on that channel)
    / COUNT(DISTINCT iap_transaction.id WHERE on that channel)
  Compare by grouping on channel_partner.channel_type / is_authorized.

Code Out-of-Scope Redemption Rate
  = COUNT(iap_transaction WHERE this code was redeemed AND player's region != discount_code.intended_region_scope)
    / COUNT(iap_transaction WHERE this code was redeemed)
  This covers the "discount channel arbitrage" half of Q4, and together with the agent discount rate/
  risk rate above forms the full evidence chain for Q4: top-up agents are arbitrage via an "unauthorized
  channel," while leaked discount codes are arbitrage via an "authorized channel being abused" — different
  in mechanism, but both fall under the broader category of "circumventing the normal pricing system."

ARPPU per Active Day
  = SUM(iap_transaction.paid_price_usd, within a given time window)
    / COUNT(DISTINCT iap_transaction.player_id, within that window)
    / number of calendar days in that window
  Used to compare a "stacked-event window" against a "non-event window" when the two spans are very
  different lengths: without day-normalization, directly comparing raw revenue/paying-player counts
  between the two windows is misleading, because the non-event window's much longer cumulative span
  makes its raw ARPPU look higher. Only after normalizing does it become clear that players' "spending
  efficiency" is actually significantly higher inside stacked-event windows.

Lifetime Spend (player.lifetime_spend_usd)
  = SUM(iap_transaction.paid_price_usd) WHERE player_id = this player, precomputed at data-generation
    time and stored directly in the player table — no re-aggregation needed to use it.
```
