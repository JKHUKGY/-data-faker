# Kestrel Compute Power Procurement and Demand Response Business Context

This document is the business foundation for this dataset. For what the data tables look like, see `02-utilities_datacenter_power_procurement_demand_response_high_er_document.md`; for how to query them, see `03-utilities_datacenter_power_procurement_demand_response_high_sql_queries.md`.

---

## 1. Who this company is

Kestrel Compute, Inc. is an AI compute operator headquartered in Columbus, Ohio. When the company was founded in 2019, it started out hosting traditional high-performance computing (HPC) workloads for a handful of engineering firms doing fluid simulation and seismic data processing. In early 2023, management made a decisive pivot: they redirected all capital spending toward AI training compute and gradually phased out the legacy HPC tenants. In three years, the company grew from 40 MW to 420 MW of contracted capacity.

By the end of FY2026, the company operates 6 campuses across four US states, with a combined 420 MW of contracted power capacity, roughly 180,000 deployed GPUs, about 640 full-time employees, and annual revenue of roughly $2.4 billion. These six campuses weren't chosen at random — they sit in three electrically isolated power markets, and that geographic spread is itself a deliberate part of the company's power strategy, as we'll get into below.

Organizationally, the CEO is Marguerite Vance, the COO is Rafael Duarte, and the CFO is Helen Okafor. Power sits under the COO, and the team actually running it is a 12-person group called Energy and Grid Strategy, led by VP of Energy Strategy Dana Whitfield. The team includes Power Procurement Manager Marcus Ellery, who handles long-term contracts and hedging; Demand Response Manager Priya Raghavan, who runs the demand response programs; and Grid Operations Specialist Luis Ferrer, who watches real-time grid conditions and makes curtailment calls. On the campus side, the counterpart is Director of Data Center Operations Tom Brennan.

---

## 2. How the money comes in, and where it goes

Kestrel sells GPU hours. Customers buy access to a batch of GPUs and get billed hourly under three main tiers: RESERVED is a one-to-three-year commitment at the lowest unit price, but customers must commit to a minimum spend; ON_DEMAND is pay-as-you-go at the highest unit price; and SPOT is cheap, preemptible capacity, with the contract explicitly stating Kestrel can reclaim those GPUs at any time. Customers include several foundation-model labs, a few pharma companies doing protein-structure prediction, two autonomous-driving companies, and teams doing film rendering and materials simulation.

The cost structure is highly concentrated. GPU depreciation and electricity together make up roughly 80% of the cost base. Depreciation is locked in the moment the purchase order is signed and can't be changed afterward. Electricity is different — it's the single largest cost this company can actually still do something about. In FY2026, the company spent $204.9 million on electricity, consuming 2.548 million MWh, for a blended rate of $0.0804 per kWh.

That $0.0804 figure is a company-wide average, and it papers over something pretty glaring: the Columbus campus has a blended rate of $0.1387 per kWh, while the Abilene campus comes in at $0.0484 per kWh — nearly a threefold difference. Put the same GPU in Texas versus Ohio, and the electricity savings alone are enough to buy nearly half of another GPU. That gap is the entire reason the Energy and Grid Strategy team exists.

---

## 3. The power market basics you need first

In North America, you don't just buy electricity from a single company. Most regions are dispatched by an entity called an Independent System Operator (ISO), which manages the entire grid, matches generation to load, and clears prices every few minutes. Kestrel's campuses sit in three different ISOs, and the rules across these three ISOs differ so much they might as well be three different countries.

**ERCOT** runs the Texas grid. Its most distinctive feature is that it has no capacity market. Other markets pay generators extra just to be "on standby even if they never generate"; ERCOT doesn't pay that premium, and instead relies on letting prices spike to extreme levels during shortages to attract investment. The result is that ERCOT's real-time prices are the most volatile in North America: on a windy night, prices can go negative (generators pay you to consume power), while a heat-wave afternoon can send prices to several thousand dollars per MWh. Kestrel's Abilene campus sits in West Texas, an area extremely dense with wind generation, and roughly one-fifth of all hours in the year see negative prices there.

**PJM** covers thirteen states in the East. It has a full capacity market, with complex rules and prices that are stable but on the pricier side. Kestrel's two Ohio campuses are here — price swings are small, but the bill carries a heavy load of capacity charges, transmission charges, and demand charges on top of the energy charge.

**MISO** covers fifteen Midwestern states. Wind generation is a large share of the mix, negative overnight prices are common, and overall it sits somewhere between the other two markets.

The three markets also bill transmission costs in completely different ways, and this comes up repeatedly later. PJM bills based on your Peak Load Contribution (PLC); MISO bills based on coincident peak demand — different terminology, but a similar underlying logic: roughly, "how much power you were using when the system as a whole was busiest." ERCOT uses 4CP, or Four Coincident Peak: it looks only at the single highest 15-minute interval of statewide demand in each of the four months from June through September, and your average usage during those four intervals sets your transmission charges for the entire following year. Avoiding those four 15-minute windows can save seven figures a year. This is the single most important lesson for industrial customers in Texas, and it's also the source of the most expensive mistake in this dataset.

On the regulatory side, the federal-level body is the Federal Energy Regulatory Commission (FERC), which approves ISO market rules and transmission rates; reliability standards are set by the North American Electric Reliability Corporation (NERC). At the state level, Texas is regulated by the Public Utility Commission of Texas, and Ohio by the Public Utilities Commission of Ohio. Data center power contracts don't require separate regulatory approval, but participating in demand response programs requires registering with the ISO, and settlement data is subject to after-the-fact audit by the ISO.

---

## 4. Your role here

You're a newly hired Energy Data Analyst on the Energy and Grid Strategy team, reporting directly to Dana Whitfield.

Kestrel's fiscal year runs from July through the following June. FY2026 ends on June 30, 2026, which is also the `REFERENCE_DATE` for this dataset. You joined right as something important was happening: the board is set to review the FY2027 energy budget at its September meeting, and CFO Helen Okafor asked Dana a hard-to-answer question during the last budget discussion. She pointed out that for the past two years, every team update has emphasized how much money demand response earned and how much the PPAs saved by locking in prices — yet the company's per-unit power cost keeps climbing. Either one of those two claims is wrong, or something is being left out of the math.

Dana handed this problem to you. Your deliverable is a board-facing FY2027 energy budget review memo, due before the September meeting. The memo needs to answer five specific questions, and every conclusion needs to be directly backed by data, because Helen will push back line by line on methodology.

---

## 5. The five questions to answer

**Q1. Is demand response actually making money or losing money?** On the team's scorecard, FY2026 demand response settlement revenue came in at just over $3 million, and it's always been reported as a profit center. But what gets curtailed is never just idle capacity — it's GPU workloads actively running. Once you factor in the opportunity cost of the interrupted jobs, is this business still net positive? If not, where are the losses concentrated, and which programs should the company exit?

**Q2. Is the curtailment volume we're reporting to the ISO actually real?** Demand response curtailment isn't measured directly — it's calculated as a "baseline" minus actual metered load. The most commonly used baseline algorithm looks at load during the same time window on the ten business days before the event. If someone deliberately inflates load in the days before an event, the baseline rises with it, and the reported curtailment grows out of thin air. Does our data show any trace of this? If the ISO were to audit us, how much settlement revenue wouldn't hold up?

**Q3. Is the Longhorn Ridge wind PPA an asset or a liability?** This 150 MW wind contract locks in a price of $28.50 per MWh, versus an annual average price of $35.47 at the West Texas settlement node. On that comparison, the contract appears to save the company over $2 million a year, and that's how Marcus has always reported it. But does wind output actually line up with market prices? If wind output happens to peak exactly when prices are lowest, that comparison falls apart. Should this contract be renewed for FY2027?

**Q4. Which part of the power bill can actually be reduced?** The blended rate smashes every charge into a single number and hides the underlying structure. How much of the bill is demand charges? How is billing demand actually set? If it's determined by a single 15-minute interval, how much would shaving down that one spike save?

**Q5. How many times did we miss on 4CP avoidance, and at what cost?** The 2025 4CP season spanned four months, and each month required predicting the single highest 15-minute statewide demand interval in Texas and proactively curtailing the two Texas campuses ahead of it. How many times did we predict correctly? For each miss, how much extra does the company pay in transmission charges the following year?

---

## 6. What the data covers

The data window spans the full 365 days of FY2026, from July 1, 2025 through June 30, 2026. Prices and campus metering are both recorded at 15-minute granularity — that's 35,040 intervals per node, and per campus. The reason for insisting on 15-minute granularity instead of hourly is that both demand charges and 4CP are determined at the 15-minute-interval level; roll that up to hourly and both of those mechanics disappear entirely.

Roughly in scale: 6 campuses, 6 pricing nodes, 11 supply contracts, 6 demand response programs, 58 demand response events, 137 actual curtailment actions, 2,600 GPU jobs, and 70 monthly power bills. Time-series data accounts for the large majority of rows, with about 504,000 rows across the whole database.

A few deliberate scope decisions are worth flagging up front. First, the New Albany East campus didn't come online until September 15, 2025, so it only has about nine and a half months of data — any metric averaged over 12 months will understate it. Second, the coincident peak for the June interval of the 2025 4CP season occurred before the data window begins, so only the ISO settlement record for it is retained, with no corresponding detailed metering. Third, this dataset covers only the power side of the business and the compute jobs affected by power decisions — it does not include the full compute business dataset, because this memo doesn't need it.

---

## 7. Industry primer

### How prices are set

Every few minutes, the ISO runs an economic dispatch: it ranks all generators willing to produce power from lowest bid to highest, and stacks them up until supply just meets system demand. The bid of the last generator selected becomes the price for that moment. This is called the Locational Marginal Price (LMP), and it differs by node, because transmission lines have limited capacity — where cheap power can't physically reach, prices run higher.

LMP is made up of three components: the energy component is the systemwide baseline price of power, the congestion component reflects the price gap caused by transmission bottlenecks, and the loss component accounts for line losses. Add all three together and you get the price you're actually settled at. When wind generation is high but the transmission lines can't carry it all out, congestion can turn sharply negative, and the nodal price can drop below zero — meaning whoever is consuming power at that moment gets paid to do so.

### What actually makes up an industrial power bill

Many people assume a power bill is just "usage times unit price." For industrial customers, it's nothing like that. A bill typically breaks down as follows:

| Charge Category | Billing Basis | Description |
| :--- | :--- | :--- |
| ENERGY | Energy consumed (MWh) | Actual energy consumed, settled at wholesale index or contract fixed price |
| DEMAND | Billing demand (kW) | Billed on the single highest power draw of the month, regardless of duration |
| TRANSMISSION | Billing demand (kW) | Cost of using the transmission grid; allocation method varies by market |
| CAPACITY | Billing demand (kW) | Capacity market charge; ERCOT has no such charge |
| ANCILLARY | Energy consumed (MWh) | Allocated share of ancillary services such as frequency regulation and reserves |
| RIDER | Energy consumed (kWh) | Regulatory riders — policy-driven charges like efficiency-fund surcharges |
| TAX | Sum of all above | State and local utility taxes |

DEMAND is the line item most often underestimated. It doesn't care how much energy you used — it only cares about the single highest 15-minute power draw during the month. A 30-minute full-load stress test and a full month of continuous full-load operation get billed identically on this line.

Even nastier is the demand ratchet clause. Many industrial rate schedules stipulate that a given month's billing demand can't fall below some percentage — typically 75% to 85% — of the trailing 11-month peak demand. In other words, the peak you set in August becomes a floor that inflates your bill for the next 11 months, even in months when you genuinely used far less power.

### How demand response gets settled

ISOs need a pool of customers who can rapidly cut consumption in an emergency, as a backstop alongside generation. Participants get paid based on the capacity they've committed to curtail — this is called capacity compensation, priced per MW per month, and it's paid regardless of whether an actual event ever occurs. When an event does occur, some programs also pay an additional energy compensation based on the actual curtailed volume.

The crux of the matter is how curtailment volume gets calculated. You can never directly measure "how much I would have used if the event hadn't happened" — you can only estimate a baseline, then subtract actual metered load from it. There are three common baseline algorithms:

**AVG_10_BUSINESS_DAYS** takes the average load during the same time window across the ten business days before the event. This is the most widely used algorithm in North America, and also the easiest to game: deliberately using more power in the days leading up to an event pushes the baseline up, and the reported curtailment inflates out of nowhere. The industry calls this baseline inflation.

**METER_BEFORE_AFTER** uses actual metered load from one hour before and one hour after the event as the baseline. It's insensitive to gaming in the days before the event, but it's inaccurate for customers whose load naturally swings a lot.

**FIRM_SERVICE_LEVEL** uses a fixed load level written into the contract as the baseline, entirely independent of recent behavior. It's the hardest to game, but also the least favorable to the customer, since there's no upside captured when load naturally drops.

### Why demand response is especially awkward for AI data centers

For a traditional industrial load, an hour of downtime costs an hour of lost output. For a GPU cluster, an hour of downtime can cost far more than an hour.

Long-running pretraining jobs periodically write model weights and optimizer state to storage — this is called a checkpoint. Because the data volume involved is enormous, checkpoint intervals tend to be stretched quite long; in this dataset, pretraining jobs checkpoint every 300 minutes. When a job is interrupted, all the computation done since the last checkpoint but not yet saved is wasted, and on average half of the interval has to be rolled back. That means a two-hour demand response event on a pretraining job actually costs two hours plus an average of two hours of rollback — effectively double.

Online inference jobs are completely different. There's no checkpointing involved — you just pull traffic off and put it back — so downtime costs exactly as much time as the downtime itself. Batch inference and small-scale fine-tuning fall somewhere in between.

This creates an asymmetry: curtailing the same 1 MW can cost several times more at a campus running pretraining than at a campus running online inference. But demand response compensation is paid strictly by the MW, with no regard for what kind of workload got curtailed. This asymmetry is the physical basis behind Q1.

### PPAs and shape risk

A Power Purchase Agreement (PPA) is a long-term contract signed with a specific generation project at a fixed price. Wind and solar PPAs are typically settled as generated: whatever the plant produces, you buy at the agreed price; when it produces nothing, you get nothing from the contract and have to buy on the open market instead.

There's a trap here, known in the industry as shape risk. The intuitive way to judge whether a PPA is a good deal is to compare the contract price against the average market price. But the power you actually receive isn't spread evenly across every hour of the year — it's concentrated in the hours when the plant happens to generate the most. If those hours happen to be when market prices are lowest, then a comparison against the annual average price is simply the wrong comparison.

West Texas wind is a textbook case of this. Wind is strongest overnight and in spring, which are exactly the hours when Texas demand — and prices — are lowest, sometimes even negative. Conversely, during summer afternoon price spikes, the wind is nearly still, so the PPA delivers almost nothing, forcing you to buy at peak prices on the open market instead. The correct comparison is against the generation-weighted market price — the hourly market price weighted by that hour's generation output.

Solar has the opposite shape. Peak sun hours are usually also peak demand hours, so solar PPAs tend to have positive shape value. This dataset includes three variable-generation PPAs — one wind, two solar — which makes for a useful side-by-side comparison.

---

## 8. Glossary

| Term | One-line explanation | Why it matters here |
| :--- | :--- | :--- |
| ISO | Independent System Operator — dispatches the entire grid and clears prices | The three ISOs' differing rules drive three entirely different power strategies |
| LMP | Locational Marginal Price — the marginal price at a given node at a given moment | The basis for all wholesale settlement and economic curtailment decisions |
| ERCOT | Texas grid; no capacity market; the most volatile prices in North America | The market where the Abilene and Temple campuses sit |
| PJM | Thirteen-state Eastern grid; has a capacity market; stable but pricier | The market where the Columbus and New Albany campuses sit |
| MISO | Fifteen-state Midwestern grid; high wind share | The market where the Cedar Rapids and Fargo campuses sit |
| Settlement Point | The pricing node against which your power usage is settled | One per campus; part of the primary key for pricing data |
| Demand Charge | Billed on the month's single highest power draw, independent of duration | 27.0% of the Columbus campus bill; the core of Q4 |
| Billing Demand | The kW figure actually multiplied by the demand rate | May come from the month's actual peak, or be inflated by a ratchet clause |
| Ratchet | A clause preventing billing demand from falling below a set percentage of the trailing 11-month peak | A single spike can drag down bills for nearly a year afterward |
| 4CP | Four Coincident Peak — Texas transmission charges based on usage during the system's peak interval in each of four summer months | The entire subject of Q5; one bad prediction costs $2 million |
| PLC | Peak Load Contribution — how PJM allocates transmission and capacity costs; MISO uses a similar concept, coincident peak demand (recorded in the data as `PEAK_DEMAND`) | Determines fixed costs for the Ohio and Midwest campuses |
| PPA | Power Purchase Agreement — a fixed-price long-term contract with a specific generation project | The subject of Q3; the company holds three variable-generation PPAs |
| Strike Price | The fixed settlement price agreed in a PPA | The benchmark for judging whether a PPA is a good deal |
| As Generated | A PPA settlement structure based on the plant's actual output | Means you can't choose when you receive power — this is the root of shape risk |
| Shape Risk | The hidden loss from a mismatch between generation timing and high-price timing | The answer to Q3; comparing against the annual average price gets it backwards |
| Capacity Factor | The share of rated capacity actually generated | About 30% for wind, 21%–27% for solar |
| Demand Response | ISO payments to customers for cutting usage during emergencies | The subject of Q1 and Q2 |
| Baseline | The estimate of "how much power would have been used absent the event" | Curtailment volume is entirely determined by this, which is also why it can be gamed |
| Curtailment | The act of proactively reducing power draw | Falls into three types: DR-event-triggered, 4CP avoidance, and purely economic |
| Economic Curtailment | Proactively shutting down because prices are too high to justify running the job | Unrelated to any DR program; generates no settlement revenue |
| Scarcity Pricing | The mechanism where prices spike sharply when the system is tight | ERCOT relies entirely on this to attract investment, since it has no capacity market |
| Checkpoint | The act of writing a training job's intermediate state to storage | The longer the interval, the greater the rollback loss when interrupted |
| GPU Hour | One GPU running for one hour | The unit of pricing for compute, and for opportunity cost |
| Goodput | The share of output that represents genuinely useful computation | Work lost to curtailment and rollback doesn't count as goodput |
| SLA Credit | A refund paid to a customer for violating an availability commitment | Triggered when RESERVED-tier customers are interrupted; counted as part of the true cost of curtailment |
| Wet Bulb Temperature | A combined temperature-and-humidity metric | The real driver of cooling system efficiency, more relevant than dry-bulb temperature |

---

## 9. Key metrics and definitions

The following metrics recur throughout the SQL query document. Each metric has exactly one definition, and this is the authoritative version.

**Blended Rate**

```
blended_rate_usd_per_kwh = total_amount_usd / (total_energy_mwh * 1000)
```

Total bill amount divided by total energy consumed. This smears energy charges, demand charges, transmission charges, and taxes all into a single per-kWh figure. It's convenient for comparing campuses side by side, but it completely hides the underlying bill structure — which is exactly what Q4 needs to unpack.

**DR Net Benefit**

```
dr_net_benefit_usd = SUM(total_settlement_usd)
- SUM(opportunity_cost_usd + sla_credit_usd)
```

Settlement revenue minus the opportunity cost of the interrupted compute and any SLA credits. Note that opportunity cost is only tallied for curtailment actions where `curtailment_type = 'DR_EVENT'` — 4CP avoidance and economic curtailment each have their own calculations and must not be mixed in.

**Opportunity Cost**

```
lost_gpu_hours      = gpus_released * (interruption_minutes + checkpoint_rollback_minutes) / 60
opportunity_cost_usd = lost_gpu_hours * internal_cost_usd_per_gpu_hour
```

The key term here is `checkpoint_rollback_minutes`. Counting only the interruption duration will systematically understate the loss on pretraining jobs.

**Baseline Inflation Ratio**

```
inflation_ratio = pre_event_3day_avg_mw / pre_event_30day_avg_mw
```

The average load in the three days before the event, divided by the average load in the thirty days before the event. Under normal operation, this ratio should sit close to 1.0; a value noticeably above 1 suggests load was artificially inflated ahead of the event. This dataset uses 1.06 as the flagging threshold.

**Generation Weighted Market Price**

```
gen_weighted_price = SUM(generation_mwh * hourly_lmp) / SUM(generation_mwh)
```

This is the correct methodology for judging whether a PPA is a good deal. The incorrect comparison, by contrast, is `AVG(hourly_lmp)` — a simple, unweighted average.

**PPA Net Cost**

```
ppa_net_cost_usd = SUM(generation_mwh) * strike_price_usd_per_mwh
- SUM(generation_mwh * hourly_lmp)
```

A positive value means the PPA cost more than buying the equivalent power on the open market; a negative value means it genuinely saved money.

**4CP Transmission Cost**

```
four_cp_transmission_usd = AVG(kestrel_coincident_demand_mw) * 1000 * 58.0
```

The average of usage across the four coincident peak intervals, converted from MW to kW, multiplied by a rate of $58 per kW per year. This rate is stored in the `ERCOT_4CP_RATE_USD_PER_KW_YEAR` constant.

**Ratchet Floor**

```
ratchet_floor_kw = MAX(metered_peak_demand_kw over trailing 11 months) * demand_ratchet_pct / 100
billing_demand_kw = MAX(current month metered_peak_demand_kw, ratchet_floor_kw)
```

When `is_ratchet_binding = 1`, it means that month's bill was inflated by a historical peak, rather than driven by that month's actual usage.
