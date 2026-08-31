# Credit Card Analytics Primer for Complete Beginners

> This is the fifth document in the `fintech_credit_card_lifecycle_high` dataset, **a long-form tutorial for outsiders**. The first three documents (business context 01, ER document 02, SQL queries 03) constantly reference eight analyses: underwriting model calibration, channel adverse selection, transactor profitability, promo cliff, CLI adverse selection, bonus churner, vintage deterioration, and product P&L. If you have zero credit card industry background, those names sound like gibberish.
>
> This primer assumes you only bring three things to the table: basic math (you can compute percentages and averages), a rough sense of data and SQL (you know what tables, rows, columns, and group-by aggregation are), and curiosity. No finance background required. By the end, you'll be able to explain each of the eight analyses clearly: what it does, why it matters, how the formula works, and what it looks like in our data.
>
> We recommend reading the business context (01) first. Each analysis maps to a specific query in the SQL document (03), and we'll call out the query number.

---

## 1. How to Read This Primer

Credit card analytics sounds fancy, but strip away the jargon and it's all answering the same plain question: **where does the money come from in this business, and where does it leak out?** The eight analyses are just eight different angles on that one question about money.

Here's how we suggest reading this. Spend ten minutes on Section 2 first (laying the foundation) — it explains how a card issuer actually makes money and introduces a handful of terms that show up again and again (transactor, revolver, interchange, rewards, charge-off). These terms are the shared vocabulary for every analysis that follows; if the foundation isn't solid, everything after it gets confusing fast. The eight sections that follow (Sections 3 through 10) each cover one analysis, in any order you like — feel free to jump to whichever interests you most. Every section follows the same structure.

- **One sentence to explain what it is** (a quick mental hook).
- **A real-life scenario** (a non-financial analogy so it clicks instantly).
- **Why the company cares** (the business motivation, whose money is on the line).
- **What happens if you don't do it** (the cost, so you know this isn't an academic exercise).
- **How the formula works** (step by step, with a worked numeric example).
- **What it looks like in the Keystone data** (which tables and columns, what numbers to expect, how to read the result).
- **Common pitfalls** (the mistakes beginners tend to make).

Section 11 ties all eight analyses together into one complete story — you'll see they're actually a single chain.

---

## 2. Laying the Foundation: How Does a Card Issuer Actually Make Money

Before we discuss any single analysis, you need to understand one thing first: **how do you figure out whether a single credit card account makes or loses money for the company?** This is what's called the single-account P&L (profit and loss). Once you understand this equation, five of the eight analyses become immediately obvious.

### Where the Revenue Comes From

For an issuer like Keystone, an account generates revenue from three sources.

The first is **interest**. Say you spend $1,000 this month but only pay $200 by the due date — the remaining $800 is called a "revolving balance." That $800 accrues interest at the APR (annual percentage rate). If the APR is 24%, that's roughly $800 times 24% divided by 12, or about $16 in interest per month. This is the fattest piece of meat for the issuer.

The second is **interchange** (the swipe fee). Every time you swipe, the merchant who's collecting your payment pays roughly 1.8% of the transaction amount to the issuer (the exact rate depends on the merchant category). You swipe $1,000, and the issuer collects about $18 from the merchant. Note that this money has nothing to do with whether you pay your bill — it flows in the moment you swipe, and the issuer bears no default risk on it.

The third is **fees**. Mainly annual fees (a premium card might charge you $95 to $395 a year), plus things like late fees ($35 if you miss a payment).

### Where the Cost Leaks Out

The same account is also spending the company's money.

The most direct cost is **rewards** (cashback or points). To entice you to spend more, many cards promise "spend X, get Y back," say 2% cashback. You swipe $1,000, and the company has to hand you $20 back. That's pure cash cost.

The most dangerous cost is **charge-off** (write-off loss). If you owe $3,000 and eventually stop paying entirely, the company waits about six months to confirm it's unrecoverable, then writes off the entire $3,000 as a loss. A single charge-off like that can wipe out an entire year's profit from dozens of normal accounts.

There's also **acquisition cost**: to get you to open the account in the first place, the company spent on marketing, and may have handed you a signup bonus (say, $200).

### Turning It Into an Equation

The lifetime profit or loss of an account is revenue minus cost:

```
Account contribution = (interest + interchange + fees) - (rewards + net charge-off loss + signup bonus)
```

In our data, the first three items (monthly interest, interchange, fees, rewards) all live in the `statement` table (one row per account per month); charge-off loss lives in the `charge_off` table; the signup bonus lives in `account.signup_bonus_usd`. Sum up all of an account's monthly statements, then subtract its charge-off loss and signup bonus, and you get exactly how much that account made or lost for the company. This is precisely what SQL queries Q11 and Q12 do.

### Two Kinds of Customers: Transactor and Revolver (Remember This, You'll Use It Constantly)

Now for a counterintuitive but critically important fact. Customers come in two types.

The first is the **transactor**: pays the statement in full every month, never carries a balance overnight. This person **never pays interest**. Their only contribution to the company is interchange (the swipe fee), minus rewards. If they swipe $1,000, the company collects $18 in interchange but has to pay out $20 in rewards — a net loss of $2 on that transaction. It sounds absurd, but that's the real economics of a transactor on a high-rewards card.

The second is the **revolver**: pays only part of the balance each month, letting the rest revolve and accrue interest. This person **pays interest**, and that interest is often several times larger than interchange. The revolver is the issuer's true profit engine.

Burn this into your memory: **revolvers make money through interest; transactors may actually be losing the company money.** This single distinction directly underlies analysis #3 (transactor profitability) and analysis #8 (product P&L), and it lurks beneath several of the others too.

Alright, the foundation is laid. The next eight sections each cover one analysis.

---

## 3. Analysis One: Underwriting Model Calibration (the core question for Data Scientists)

**One sentence.** At underwriting, we assign every applicant a risk score using a model; this analysis checks whether that score is actually accurate — especially whether it quietly breaks down for certain groups.

**A real-life scenario.** Imagine a weather forecaster who reports a "chance of rain" every day. To check whether he's accurate, you can't just look at whether he was right on any single day — you have to pull out every day he said "90% chance of rain" and check whether it actually rained about nine times out of ten. If his stated probability matches the actual rain frequency, he's a good forecaster. The underwriting model is exactly this kind of "default forecaster": it gives every applicant a score (`underwriting_score`, 0 to 999, higher meaning less likely to default). What we need to check is: do people with higher scores actually default less?

**Why the company cares.** This score determines who gets approved, how much credit line they get, and what interest rate they're charged. If the score is accurate, the company can confidently treat good and bad customers differently, making the money it should make and avoiding the losses it should avoid. If the score breaks down for a particular segment (say, it's essentially guessing randomly for subprime customers), the company is lending to that group blind, and trouble is only a matter of time. This question is specifically designed for the Data Scientist role, because it uses the fundamentals of ML model evaluation: ROC curves, AUC, confusion matrices.

**What happens if you don't do it.** A broken underwriting model is one of the most expensive mistakes an issuer can make. You think you're lending precisely, but you're actually issuing cards to a bunch of people who will default. By the time the charge-off numbers surface, a year has already passed, and a cohort of bad debt is already unrecoverable. Worse, because the overall numbers still look fine, nobody thinks to check by segment, and the problem keeps quietly compounding.

**How the formula works.** The core technique is called "bucket and check the actual rate." Three steps.

Step one: sort all accounts by underwriting score from lowest to highest, and split them into 10 equal-sized groups (this is called a decile). Group 1 is the bottom 10% of scores; group 10 is the top 10%.

Step two: compute the actual charge-off rate within each group:

```
Charge-off rate for a group = number of charged-off accounts in the group / total accounts in the group
```

Step three: look at the trend across these 10 charge-off rates. If the model is good, the charge-off rate should **decrease monotonically** with score: the higher the score, the lower the charge-off rate.

Here's a concrete example. Say the lowest-scoring group has 100 accounts with 9 charged off (a 9% charge-off rate), and the highest-scoring group has 100 accounts with only 3 charged off (3%), with a smooth transition in between. This downward curve from 9% to 3% shows the model has discriminative power. That's good news.

But the real test comes with a second cut. Pull out the highest-risk segment (Subprime, band D) on its own, and bucket it by score again to look at charge-off rates within that segment. If the charge-off rates for the high-scoring and low-scoring buckets within this subgroup are roughly the same (say, both bouncing around 11% with no downward trend), that tells you: **the model works overall, but it's essentially guessing randomly for Subprime.**

In terms of AUC: the overall AUC might be 0.70 (clearly better than the 0.50 you'd get from random guessing), but the Subprime subgroup's AUC is close to 0.50 (a coin flip). The good overall number is masking a local failure.

**What it looks like in the Keystone data.** This maps to SQL Q3 (overall) and Q4 (Subprime segment). The table is `account`, and the two key columns are `underwriting_score` (the score) and `account_status` (whether it's CHARGED_OFF, i.e., the actual outcome). Q3 gives you a nice smooth curve declining from about 9.7% to about 3.2%, making everything look fine. Q4 isolates band D and shows the charge-off rate bouncing between 10% and 17% with no discernible downward trend at all. Comparing the two tables side by side is damning: the model has failed for the subprime segment.

**Common pitfalls.** The biggest pitfall is "concluding from the overall picture alone." A good overall AUC creates a false sense of safety. The real risk usually hides in some subgroup (a particular FICO band, a particular channel, a particular product). Building the habit of "always check by segment too" is the most important lesson this question teaches. A second pitfall is forgetting to filter before bucketing: to see stratification within band D, you must first filter down to band D and then bucket, not bucket across everyone and then look at D afterward — otherwise your bucket boundaries reflect the whole population, not band D specifically.

---

## 4. Analysis Two: Channel Adverse Selection (the "cheap" channel might be the most expensive)

**One sentence.** We acquire customers through several marketing channels; this analysis exposes which channel looks cheap but actually brings in the worst customers.

**A real-life scenario.** You're opening a restaurant and hiring servers. You have two hiring channels: a recruiter (expensive, $500 per hire) and a flyer on the street corner (cheap, almost free). You go cheap and use only flyers — the people you hire quit after two days, and all the training cost goes to waste. Do the full math, and that "cheap" channel turns out to be the most expensive one. Marketing channels work the same way: a channel with a low cost per contact (CPA) can bring in customers whose quality is far worse.

**Why the company cares.** Marketing budgets are finite, and the CMO (Chief Marketing Officer) has to decide where the money goes. If you only look at the surface metric of "acquisition cost" (CPA, cost per acquisition), you'll pour money into the cheapest channel. But if that channel's customers charge off at an alarming rate, the few dollars you saved on acquisition will get devoured many times over by hundreds of dollars in bad debt. This is "adverse selection": cheap things are often cheap precisely because they're low quality.

**What happens if you don't do it.** You'll keep pouring budget, year after year, into a channel that's actually generating bad debt for you, all while thinking you're being frugal. The acquisition volume KPI looks great, but portfolio quality is quietly rotting until the charge-off numbers can no longer be hidden.

**How the formula works.** Two layers. First layer: charge-off rate by channel.

```
Channel charge-off rate = number of charged-off accounts from this channel / total accounts from this channel
```

Placing this side by side with the channel's acquisition cost reveals the "cheap but bad debt" contradiction.

The second layer goes further and computes a "loss-adjusted true cost" — the average net charge-off loss generated per customer booked:

```
Net loss per booked account for a channel = sum of net charge-off losses across all accounts from this channel / number of accounts from this channel
```

Here's a concrete example. The affiliate channel costs $2 per contact, cheaper than digital channels ($3 to $4.5), and has a higher approval rate too, so the team keeps wanting to give it more budget. But its accounts charge off at 12.6%, averaging about $597 in net loss per account. Meanwhile prescreen mail (costing $1.1 per contact, one of the cheapest channels) has a charge-off rate of only 3.9%, averaging about $169 in net loss per account. The few-dollar difference in contact cost is negligible next to a several-hundred-dollar difference in loss. The conclusion is obvious: affiliate's cheap acquisition cost is an illusion — once you account for bad debt, it's actually the most expensive channel.

**What it looks like in the Keystone data.** This maps to SQL Q6 (charge-off rate vs. acquisition cost) and Q7 (loss-adjusted true cost). Join `account` to `marketing_channel` (for channel name and cost), then to `charge_off` (to compute net loss). You'll see affiliate_partner topping the charge-off rate chart at about 12.6% despite a low contact cost, while prescreen_mail and branch_referral have the lowest charge-off rates. Net loss per booked account ranges from about $597 for affiliate down to about $169 for prescreen — more than a threefold difference.

**Common pitfalls.** The biggest pitfall is "making decisions off the wrong metric." CPA (acquisition cost) is a vanity metric — it only captures half the cost (the acquisition half), not the risk half. Always ask: what's the back-end bad debt cost of this cheap thing? Another pitfall is using the wrong join type: going from channel to loss requires a LEFT JOIN — otherwise channels that happen to have zero charge-offs will disappear entirely, making you think they don't exist.

---

## 5. Analysis Three: Transactor Profitability (customers gaming the rewards are losing the company money)

**One sentence.** Transactors who pay in full every month are actually money-losers on high-cashback cards; this analysis proves it with numbers.

**A real-life scenario.** Imagine a gym running a "cash back for every workout" promotion. There are two kinds of members. One shows up every day, collects cashback every time, but never buys personal training or supplements — pure cashback farming. The other comes occasionally but signs up for memberships and personal training, contributing plenty. The gym actually loses money on the first type (the cashback paid out exceeds the revenue they bring in) and makes its money from the second type. The credit card transactor is that "pure cashback farmer" member.

**Why the company cares.** As we covered in the foundation section: transactors don't pay interest, and their only contribution is interchange (about 1.8%), while they still collect rewards. If a card pays 2% or even 2.5% cashback, the company loses money on every swipe a transactor makes. Product managers and the CFO need to know: which of our products are being propped up by revolver interest while transactors drag them down? Only with that knowledge can they adjust rewards rates, adjust annual fees, or stop marketing to segments that are obviously transactors.

**What happens if you don't do it.** You'll keep launching increasingly generous rewards to win customers, attracting a pile of transactors. Acquisition numbers look great on paper, but every one of those customers is quietly losing money. The premium card looks impressive but is actually a loss-making black hole (the product P&L in a later section confirms this).

**How the formula works.** Take the "account contribution" formula from the foundation section and group it by product and behavior (transactor/revolver), then average:

```
Average contribution by product and behavior = AVG(account contribution)   -- account contribution = margin - signup bonus - net loss
where margin = SUM(interest + interchange + fees - rewards)   -- transactors accrue zero interest in a normal full-payment month
```

Here's a concrete example. A transactor on a Cashback card (1.5% rewards) spends $12,000 a year and pays in full every month. They contribute interchange of about $12,000 times 1.8%, or $216, but collect rewards of about $12,000 times 1.5%, or $180, with zero net interest. Surface margin comes out to about $36. But if they also received a $200 signup bonus when they opened the account, this account is a lifetime net loss of about $164. Meanwhile a revolver on the same card, carrying a $2,000-$3,000 balance year-round at 22.99% interest, contributes several hundred dollars in interest alone in a year — solidly positive.

**What it looks like in the Keystone data.** This maps to SQL Q12 (transactor vs. revolver by product) and Q19 (rewards eating into interchange). Use the `statement` table to compute margin, `account.behavior_segment` to distinguish transactor/revolver, and join `card_product` to see the product. You'll see that on every card with a rewards rate of 1.5% or higher, transactor average contribution is negative (about -270 for Cashback, -405 for Cashback Plus, -207 for Travel, and even about -40 for the premium Venture Premium transactors), while revolvers on the same products are all positive. Q19 makes it even more stark: once the rewards rate hits 2% or above (Cashback Plus, Travel, Venture Premium), interchange minus rewards goes straight negative.

**Common pitfalls.** Beginners tend to assume "a customer who spends a lot is a good customer." Wrong. A customer who spends heavily, pays in full, and collects high rewards may be one of your biggest money losers. To judge whether a customer is good, you need the full contribution picture (interest, interchange, rewards, losses), not just spend volume. Another pitfall is leaving out rewards cost when computing margin, which makes transactors look more profitable than they actually are.

---

## 6. Analysis Four: Promo APR Cliff (mass delinquency when the 0% offer expires)

**One sentence.** Customers acquired through a "0% APR for 12 months" promotion tend to delinquent in a wave the moment the promo expires; this analysis maps out that "cliff."

**A real-life scenario.** A gym runs a "no membership fee for the first 12 months" promotion, and a flood of people sign up. For the first 12 months, everyone's happy. But starting month 13, the fee kicks in, and a big batch of these people suddenly realize they never intended to work out long-term — they cancel or fall behind en masse. The promotion created an "expiration cliff." A credit card's 0% balance transfer promotion works exactly the same way: for the first 12 months, no interest accrues, and everything looks calm; in month 13, the rate jumps to 22%, the payment due suddenly spikes, and a batch of people can't keep up and fall delinquent.

**Why the company cares.** The risk in these accounts isn't randomly distributed — it's **concentrated at a predictable point in time** (one to three months after the promo expires). If the risk team can identify this cliff in advance, they can intervene proactively before expiration (remind customers, offer installment plans) and smooth out the cliff. This also makes a great question for Data Scientists: "months until promo expiration" is a feature that meaningfully improves a risk model.

**What happens if you don't do it.** You'll get blindsided by a sudden wave of delinquency right after the promo expires, only realizing after the fact that the promotion caused it. Customers who could have been caught with a month or two of lead time instead roll straight into deep delinquency or even charge-off.

**How the formula works.** The key is to look at delinquency by **months on book, not calendar time**, comparing promo accounts against non-promo accounts:

```
DPD30+ rate for promo group at a given tenure = number of statements with 30+ days past due for promo accounts at this tenure / total statements for promo accounts at this tenure
```

Compute the same thing for non-promo accounts as a control. Because every account's promo expires "12 months after account opening," aligning on account age (cycle_month) means months 12 through 14 line up exactly with the expiration window across all promo accounts, so the cliff stacks up and becomes visible.

Here's a concrete example. The promo group's DPD30+ rate sits at only about 2% to 5% during cycle_month 6 through 11 (still within the promo period) — well-behaved. Then at cycle_month 12 through 14 (right after the promo expires), it jumps to about 13%, before receding afterward. The non-promo group, meanwhile, declines smoothly to under 1% with no spike at all. Comparing the two curves draws the cliff clearly.

**What it looks like in the Keystone data.** This maps to SQL Q13. Join `statement` to `account`, split into two groups using `account.is_promo_apr`, group by `cycle_month`, and compute the share with `days_past_due >= 30`. You'll see that spike at months 12 through 14 for the promo group, in sharp contrast to the smooth curve for the non-promo group.

**Common pitfalls.** The biggest pitfall is **looking at calendar month instead of account age**. Different accounts open at different times, so their promo expiration dates land in different calendar months — if you group by calendar month, the cliffs for different accounts scatter across different months and cancel each other out, and you'll see nothing. Only by aligning on account age (cycle_month) does the cliff stack up and become visible. This is a classic teaching point in time-series analysis: "event time vs. calendar time."

---

## 7. Analysis Five: CLI Adverse Selection (adding leverage to people who are already about to break)

**One sentence.** Our strategy of increasing credit lines for "high utilization customers" may be pouring fuel on the people most at risk; this analysis tests that.

**A real-life scenario.** Suppose you lend money to a friend. One friend always maxes out his credit card and asks to borrow from you every month to get by. You think, "he uses money so freely, he'll be thrilled if I lend him more," so you raise his limit. He borrows even more, and eventually he can't pay any of it back, and you lose even more. "He uses it a lot" doesn't mean "he can pay it back" — it might mean the opposite. Credit line increases (CLI) on credit cards have exactly this trap.

**Why the company cares.** CLI is a common tool issuers use to stimulate spend and boost interest income. The conventional logic is "increase the line for active, good customers." But is "high utilization" (close to maxing out the line) a signal of "an active customer who loves using their card," or a signal of "someone who's about to break"? If it's the latter, a credit line increase is piling more fuel onto a ticking time bomb. The Chief Credit Officer needs to get this right in order to set correct CLI policy.

**What happens if you don't do it.** You'll systematically hand more leverage to the riskiest customers, turning someone who owed $3,000 into someone who owes $5,000 before charging off. The short-term interest income from the CLI comes nowhere close to covering the amplified bad debt.

**How the formula works.** The key field is "pre-change utilization" (utilization rate before the credit line change). Split accounts that received a CLI into two groups by this field, and compare charge-off rates:

```
Charge-off rate for high-utilization CLI group = (charged-off accounts among those with pre-change utilization > 70%) / (total accounts with pre-change utilization > 70%)
Charge-off rate for low-utilization CLI group = (charged-off accounts among those with pre-change utilization <= 70%) / (total accounts with pre-change utilization <= 70%)
```

Here's a concrete example. Say accounts that already had utilization above 70% before the increase later charge off at about 10%, while accounts with lower pre-change utilization charge off at only about 3.4% — roughly a threefold difference. This shows that giving credit line increases to people who have already maxed out their limit is adverse selection: you're picking out precisely the people most likely to default.

**What it looks like in the Keystone data.** This maps to SQL Q9. Use the `credit_line_change` table (which stores the `pre_change_utilization_pct` field specifically for this purpose), filter to increase events (change_type='CLI'), join back to `account` to see the charge-off outcome, and group by whether pre-change utilization exceeded 70%. You'll see a stark contrast: about 10% for the high-utilization group versus about 3.4% for the low-utilization group.

**Common pitfalls.** The trap is equating "activity" with "creditworthiness." High utilization is a double-edged signal — it could mean a good customer who loves using their card, or a bad customer about to collapse. Utilization alone can't tell you which; you need to combine it with payment behavior. This question teaches you: the targeting logic behind a business action (a credit line increase) may unintentionally select the worst possible customers.

---

## 8. Analysis Six: Bonus Churner (rewards hunters who take the money and run)

**One sentence.** A large signup bonus attracts a segment of "take the money and run" bonus hunters; this analysis calculates the negative value they leave behind.

**A real-life scenario.** A mall runs a "sign up for a membership card, get a $200 voucher" promotion. A batch of people show up purely for the $200 voucher, redeem it, buy just enough to meet the minimum spend, and never come back — a few months later they cancel the card. The mall spent $200 to acquire this "customer" but earned almost nothing from them. This kind of person is called a churner. A large credit card signup bonus attracts exactly this crowd.

**Why the company cares.** Marketing teams love using large bonuses to pump up new-account volume, because account openings is a KPI that looks great. But if a large chunk of those accounts are bonus hunters who collect a $200-$300 bonus, hit the minimum spend, then close the account within a few months, those accounts have negative lifetime value (LTV): the company pays out more in bonuses than it earns from them. The VP of Acquisitions needs to identify this segment to judge whether a given bonus campaign is actually profitable or just burning money.

**What happens if you don't do it.** You'll think a big bonus campaign was a success (account openings surged), when in reality it attracted a pile of negative-value customers and the campaign's ROI is negative. Worse, you'll keep escalating bonuses in future campaigns, digging the hole deeper.

**How the formula works.** A simplified LTV measure = lifetime operating margin earned by the account, minus the signup bonus paid out to it:

```
Account LTV = SUM(interest + interchange + fees - rewards) - signup bonus
```

Then group by "close reason" (close_reason) and compute average LTV. The bonus hunter group (close_reason = 'bonus_churn') should be significantly negative.

Here's a concrete example. A bonus hunter collects a $250 bonus, spends $2,000 to hit the minimum spend threshold (contributing about $36 in interchange), then stops using the card and closes it 8 months later. Their lifetime margin might come to only $30 to $50; subtract the $250 bonus, and LTV comes out to about -$200. Compare that to a customer who closed their account normally (say, after two years, switching to another card) — they contributed several hundred dollars in interest and interchange over that time, for a positive LTV.

**What it looks like in the Keystone data.** This maps to SQL Q15. Use the `attrition_event` table (which only contains closed accounts, including close_reason), join to `account` to get the bonus, then compute margin. You'll see the `bonus_churn` group with an average LTV of about -$280, the only negative value among all close reasons; every other reason (rate_shopping, inactivity, product_upgrade, etc.) sits above +$330.

**Common pitfalls.** The trap is fixating on account openings, a vanity metric. Rising account openings don't mean rising profit — you need to look at what those accounts actually contributed afterward. Another pitfall is evaluating a bonus campaign by only counting the bonus cost, without asking "how much would these accounts have earned without the bonus?" A proper evaluation looks at net incremental value.

---

## 9. Analysis Seven: Vintage Deterioration (underwriting standards quietly loosening)

**One sentence.** Our underwriting standards may be quietly loosening, causing recently opened cards to go bad faster than older ones; this analysis uses vintage curves to catch it.

**A real-life scenario.** A bakery hires a new batch of apprentices every month. You want to know whether the recent hiring bar has dropped (maybe the head baker is cutting corners to keep up with demand). You can't just compare "apprentices who've been here a year" to "apprentices hired last month" (the newcomers obviously haven't had time to make as many mistakes yet). The fair comparison is: look at each batch's error rate "at the three-month mark since hiring." If recent batches have a noticeably higher three-month error rate, hiring standards have slipped. Credit card vintage analysis follows the exact same logic.

**Why the company cares.** Credit card risk's worst fear is "quietly loosening underwriting during good times without realizing it." To chase growth, underwriting criteria can drift looser bit by bit (approval rates creep up, approved customers' FICO scores drift down). In the short term this looks great, since account openings rise, but the resulting bad debt doesn't surface for a year or two. The Chief Risk Officer must catch this drift early, because under CECL accounting standards, expected losses must be reserved for prospectively, directly affecting the financial statements. This is also a core portfolio quality metric that has to be explained to investors.

**What happens if you don't do it.** In the euphoria of growth, portfolio quality gets a little worse every quarter until the bad debt erupts all at once. By the time the financials look bad, you discover underwriting had already loosened a year earlier — but that batch of accounts is already out the door and can't be undone.

**How the formula works.** The core concept is vintage (a cohort grouped by account opening quarter) combined with "fixed-tenure comparison." Group accounts by opening quarter, and for each group compute "the share that charged off within 6 months on book":

```
mob6 charge-off rate for a vintage = (accounts opened in this quarter that charged off within 6 months) / (total accounts opened in this quarter)
```

The key: you must **fix the tenure** (always looking at month_on_book <= 6), otherwise recent cohorts, simply by virtue of having less time on the books, will show fewer absolute charge-offs and falsely appear healthier. You should also exclude the most recent one or two quarters, since most of those accounts haven't reached the 6-month mark yet, making the denominator not yet comparable.

Here's a concrete example. Cards opened in Q3 2024 have a 6-month charge-off rate of about 1.2%; by Q4 2025, that's risen to about 3.5%. At the same six-month tenure, recent cohorts are going bad nearly three times as fast. Pair that with another table: the approval rate has risen from about 55% to about 60%, and approved customers' average FICO has slid from about 722 to about 694. Put those three pieces of evidence together, and the story of loosening underwriting is confirmed.

**What it looks like in the Keystone data.** This maps to SQL Q16 (vintage loss curve) and Q17 (underwriting drift). Q16 uses `account.open_vintage` (account opening quarter) and `months_on_book` to compute the fixed-tenure charge-off rate. Q17 uses `application.application_date` to look at trends in approval rate and booked FICO over time. You'll see the vintage curve trending upward, the approval rate rising, and FICO sliding — a clear causal chain.

**Common pitfalls.** The biggest pitfall is **comparing different cohorts without fixing tenure**. Directly comparing "total charge-off rate for an old cohort" to "total charge-off rate for a new cohort" is wrong, because the new cohort hasn't completed its default cycle yet and will always look better. You must compare at the same tenure (mob6). A second pitfall is including the most recent, still-immature vintages in the comparison — their denominators aren't mature yet and will mislead the trend.

---

## 10. Analysis Eight: Product Ladder P&L (which card actually makes money — the counterintuitive answer)

**One sentence.** Work out the complete profit and loss for all six cards, and you'll find that the least flashy card is the most profitable, while the flashiest card is losing money.

**A real-life scenario.** A restaurant has six dishes, ranging from cheap comfort food to an expensive signature entree. The owner instinctively assumes the signature entree is the most profitable (it's priced the highest, after all). But once you actually account for ingredients, labor, and waste for every dish, you might find the signature entree uses such expensive ingredients that it barely breaks even, while that unassuming comfort-food dish, with low cost and high repeat orders, is actually the profit engine. Credit card product lines work the same way — intuition is often wrong.

**Why the company cares.** Keystone has six cards, ranging from the entry-level Secured card to the premium Venture Premium travel card. The CFO needs to know exactly which ones are profitable in order to decide which to push, which to cut, and how to adjust rewards and annual fees. Intuition (premium cards are the most profitable) is often unreliable, because premium cards tend to have both higher rewards costs and a higher share of transactors. This question rolls up several earlier analyses (transactor losses, rewards erosion) into a single product-level ledger.

**What happens if you don't do it.** You'll keep pouring resources into a product that looks premium but is actually losing money, while neglecting the product that's quietly profitable. The profitability of the entire product portfolio gets dragged down without anyone noticing.

**How the formula works.** Take the "account contribution" formula from the foundation section and roll it up by product:

```
Product P&L = SUM over all accounts of this product of (interest + interchange + fees - rewards - net charge-off loss - signup bonus)
```

Compute the revenue side (interest, interchange, fees) and the cost side (rewards, charge-offs, bonuses) separately for each product, then subtract.

Here's a concrete example (in order of magnitude). Keystone Secured (no rewards, an APR as high as 26.99%, mostly interest-paying revolvers) nets about +$1.05 million overall, the most profitable. Student and Venture Premium each come in at roughly +$250,000 to +$270,000. Meanwhile, the two cashback-focused cards, Cashback Plus (about -$250,000) and Travel (about -$160,000), are overall **loss-making**, and Cashback is slightly negative too (about -$14,000). Venture Premium, the premium card, only stays positive thanks to its $395 annual fee acting as a backstop — without it, its transactors would drag it into a loss.

**What it looks like in the Keystone data.** This maps to SQL Q11 (full product P&L) and Q19 (rewards erosion). Use `statement` to compute revenue and cost line items, joining to `card_product` and `charge_off`. You'll see that counterintuitive ranking: Secured on top, the premium cashback cards at the bottom. This table ties transactor profitability (Analysis Three) directly to product strategy.

**Common pitfalls.** Pitfall one is the intuition that "a more expensive product is always more profitable." Higher revenue doesn't mean higher profit — costs (rewards, acquisition, charge-offs) can be higher too. Pitfall two is using an INNER JOIN to bring in the charge-off table when computing P&L, which leaves only charged-off accounts and makes every product look wildly unprofitable. You must use a LEFT JOIN to also include the normal accounts that never charged off. Pitfall three is forgetting to include the signup bonus as part of acquisition cost.

---

## 11. How the Eight Analyses Weave Into One Story

You've now gone through all eight analyses. Step back, and you'll see they're not eight isolated exercises — they're one complete "money chain" that follows the credit card lifecycle from start to finish.

The story starts with **acquisition**. Analysis Two (channel adverse selection) tells you: don't be fooled by a cheap channel — look at the back-end bad debt of the customers it brings in. Analysis Six (bonus churner) tells you: don't get swept up by a large signup bonus — a segment of people will take the money and run.

Next comes **underwriting**. Analysis One (underwriting model calibration) tells you: the model you rely on to decide approvals may have already broken down for a particular segment. Analysis Seven (vintage deterioration) tells you: your underwriting standards may be quietly loosening, and recent cohorts are getting worse.

Then comes **account management**. Analysis Five (CLI adverse selection) tells you: increasing credit lines for high-utilization customers may be adding leverage to the very people most at risk. Analysis Four (promo cliff) tells you: accounts acquired through a promotion will delinquent in a wave at a predictable point in time.

Finally, **profit attribution**. Analysis Three (transactor profitability) and Analysis Eight (product P&L) tell you: the premium cashback card you thought was profitable may actually be losing money because of transactors and rewards; the products quietly making money are the ones full of interest-paying revolvers.

Follow this chain all the way through, and you understand the core anxiety of a data-driven card issuer: **from acquisition to underwriting to account management to profitability, every single stage hides a trap that looks right but is actually wrong — and the value of data analysis is shining a light on each of these traps, one by one.** This is exactly why a company like Keystone hires Business Analysts and Data Scientists, and it's exactly what this dataset wants you to practice.

Now, open the SQL query document (03) and go hunt down these traps for yourself, one query at a time.
