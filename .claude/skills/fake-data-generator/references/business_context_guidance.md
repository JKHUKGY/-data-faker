# Business Context Guide

This guide describes the business context file, the document that frames every other artifact in the dataset.

The skill produces the Chinese variant `01-{dataset_name}_business_context-cn.md` during the authoring pass. The English variant `01-{dataset_name}_business_context.md` comes later from the `translate-to-en` skill. Do not author the English file by hand.

The `01-` prefix marks this file as the first artifact in the dataset bundle. ER document is `02-`, SQL queries is `03-`, Python generator is `04-`.

The market is always North America. The fictional company is based in the United States or Canada. The currency is USD. Regulatory references are American or Canadian. The Chinese narrative voice is only a language choice; the business is still North American.

---

## 1. Why this file exists

The business context file frames everything else in the dataset. The schema, the SQL queries, and the deliberately embedded distribution traps all serve the company and the project described here. Without the business context, a dataset is just a schema with example rows. With it, the dataset becomes the data layer of a believable project.

The audience is a smart layperson, not a domain expert. Think of a new intern who just joined the project and needs to come up to speed before the first stand-up. The file should explain the company, the industry, the project, the problems, and the jargon clearly enough that the intern can talk shop within a few hours of reading.

If the file reads like a press release for a real public company, the tone is wrong. Aim for the voice of an experienced colleague briefing a new hire over coffee.

---

## 2. Required content beats

The order of sections is flexible. Use whatever headings flow best for the specific dataset. The following beats must all appear somewhere in the file.

### Beat 1. The company

State the fictional company's name (always invented, never a real company), a North American city or region, rough scale (employees, revenue, customer count, all order of magnitude), and a one-sentence origin story when it informs the dataset. Mention the relevant org structure (CEO, CFO, CRO, VP titles) when the dataset's queries will reference those roles by title.

### Beat 2. The business model

Explain what they sell, who buys it, and how they make money. Be specific about the pricing mechanic (subscription, transactional, per-case, take-rate, advertising spend, professional services). Note the rough unit economics when they shape the metrics that show up later (gross margin band, payback period band, average revenue per customer).

### Beat 3. Industry overview

Walk a reader from a different industry through what this market actually does. Cover what value the industry creates, who the main player categories are (without naming real companies), the relevant regulators or compliance frameworks (HIPAA, FDA, SOX, KYC, OCC, PCI DSS, CCPA), and the macro forces shaping the space right now (consolidation, AI disruption, regulatory tightening). The reader should leave this section able to discuss the industry at a high level.

### Beat 4. The project context

Name the role the user is playing inside the company. The choice between intern, full-time analyst, BI engineer, consultant, or founding data hire affects the tone of the SQL queries and the project deliverables. State what they are working toward (a board deck, a quarterly review, an automated dashboard, a recommendation memo, an ML model) and who the deliverable goes to (CEO, CFO, VP Sales, board, regulator). Add a timeline if it matters.

### Beat 5. The business problems being solved

List three to five concrete business questions or decisions the project addresses. Each is stated in one or two sentences. Be specific. "Are we pricing Grade C loans correctly?" beats "Improve loan portfolio quality." These problems become the lattice for both the ER document and the SQL queries. Every SQL query should map back to one of them.

### Beat 6. Data scope at a glance

Briefly describe the time horizon (such as "22 months of applications anchored at REFERENCE_DATE = 2026-06-03"), the rough data volume in plain language ("a few thousand customers, tens of thousands of payments"), and any deliberate scope decisions (single state, single product line, single channel) with the reason behind them. Do not enumerate tables here. Tables live in the ER document.

### Beat 7. Industry knowledge primer

The thirty to sixty minutes of context an outsider needs before the data makes sense. The exact content depends on the industry. In SaaS this covers funnel mechanics, ARR versus MRR, gross retention versus net retention. In lending this covers credit grades, DPD, default versus charge-off, recovery, vintage. In medical devices this covers UDI, distributor versus hospital channels, consignment versus purchase, surgeon-driven adoption. Use numbered flows or short tables where they help. Skip what the layperson already knows.

### Beat 8. Glossary of key terms

Every piece of jargon used in the ER document or SQL queries gets one glossary entry. Each entry has the term in English (always English, even in the Chinese file), a one-sentence layman explanation, and a one-sentence "why this matters here." Acronyms get their full form on first use. The bar is "would a smart college freshman understand this after one read." If the glossary is short, jargon is missing.

### Beat 9. Key metrics with formulas

For every metric that appears in the SQL queries document or that the reader is expected to know:

- Give the formula in plain notation. SQL-flavored pseudocode is fine.
- Note what inputs it uses and any conventions (window length, exclusions, weighting).
- When two definitions are common (activation rate by accounts versus by users), pick one and say so. Inconsistent definitions cause downstream SQL disagreement.

Sample formulas:

```
DSO = (Accounts Receivable / Revenue) * Days In Period
Net Revenue Retention = (Starting ARR - Churn + Expansion) / Starting ARR
Cost Per Lead = Total Spend / Marketing Qualified Leads
```

---

## 3. Tone and length

A workable length sits between two thousand and five thousand words. Med-device and regulated-finance datasets can run longer because their jargon and regulatory shape demand more primer. Simple ecommerce business models can run shorter. The glossary is allowed to be long when the industry uses many specialized terms.

Good tone reads like an experienced colleague explaining the company at coffee:

> Pacific Bridge Lending makes money by collecting interest spread. The gap between what they charge borrowers and what they pay their warehouse line.

Bad tone reads like a careers page:

> Pacific Bridge Lending leverages cutting-edge data analytics to optimize lending operations across diverse customer segments.

The first sentence tells a layperson something specific. The second is generic LinkedIn voice that fits any company in any industry.

---

## 4. The Chinese narrative voice

Chinese is the language of narration, not the locale of the business. Three rules keep the voice consistent:

1. The fictional company is North American. The narrator just happens to be telling the story in Chinese.
2. Business terminology stays in English. Write `ARR`, not 年度经常性收入. The glossary explains it once.
3. Cultural references resolve to North American defaults. State names are American or Canadian provinces. Currency is USD. Holidays are Thanksgiving (US or Canadian), not 春节. Regulators are SEC, OCC, FDA, CFPB, FINRA, Health Canada, OSC.

---

## 5. The English version

The English variant of this file is produced by the `translate-to-en` skill after the Chinese file is finalized. It mirrors the same structure and the same business decisions. English jargon stays unchanged across the two files. Sample numbers and entity names stay unchanged. Only the narrative voice is rewritten for an English-reading audience.

Do not write the English file by hand during the authoring pass. Wait for the translation pass.

---

## 6. Mini example opening

The opening paragraph of a finished business context file looks like this:

```
Pacific Bridge Lending 是一家总部位于加州 Walnut Creek 的中型金融科技公司,专注于
中小企业 (SMB) 贷款. 客户主要是年营收 200K 到 10M 美元的本地餐饮, 零售, 技术服务
等企业. 2024 年公司全年放款约 4 亿美元, 拥有 3000 个活跃借款人, 50 名员工.

商业模式很直接: Pacific Bridge 用自己的资本与一条仓储融资额度 (warehouse line)
给小企业放贷, 赚"借出利率 减去 资金成本"的利差. SMB 贷款的利率通常 5.5% 到 16%
(按风险等级), 资金成本约 4%, 因此每笔贷款的毛利空间在 1.5pp 到 12pp 之间, 违约则
吞掉这些毛利. 利润最终取决于两件事: 风险定价是否准确, 以及对违约的早期识别能否
减少损失.

你正在 Pacific Bridge 做暑期数据分析实习, 直接向 VP Risk 汇报. 任务是用过去 22
个月的贷款数据回答五个具体问题 ...
```

These three paragraphs name the company, place it, size it, explain the revenue model in plain language, frame the project, and are about to enumerate the business problems. They mention no table, no column. Tables come later in the ER document.

---

## 7. Anti-patterns to avoid

The file is doing it wrong when any of these are true.

- The opening reads like a marketing one-pager.
- The company name is a thinly veiled real public company.
- The business model is described in terms that fit any industry.
- The problems are stated as goals ("improve sales") rather than questions ("which segment is bleeding margin").
- A piece of jargon is used in the ER doc or queries but never explained here.
- Two queries imply two different formulas for the same metric, and this file does not pick one.
- The company is in Shenzhen, the currency is RMB, or the regulators are Chinese. The market is North America.
