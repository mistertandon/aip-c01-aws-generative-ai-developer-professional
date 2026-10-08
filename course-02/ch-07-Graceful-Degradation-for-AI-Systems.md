### Understanding Graceful Degradation for GenAI

**In simple terms:** Don't let your app show "AI is unavailable, try later". Instead, design it to automatically switch to a simpler, cheaper, but still useful mode. Like Google Maps - if live traffic fails, it shows you the route without traffic, not a blank screen.

In Bedrock terms: Your primary FM `Claude 3.5 Sonnet` is throttled even after cross-region failover. Instead of failing the loan application, you degrade to a smaller model, then to a cached answer, then to a rule-based response.

#### How to Design It - The Core vs Optional Rule

Before writing code, classify your AI features:

**Must-have :** The user cannot complete the task without it. Must have a fallback that works with zero AI dependency if needed.
**Nice-to-have :** Enhances experience but can be skipped during disruption.[Core][Optional]

If you don't do this, everything looks critical and you will fail completely when Bedrock has issues.

#### Prod Real-World Example: BharatFin Loan Copilot

This is a live design in `ap-south-1` that handles 15,000 loan applications per day.

**Normal Mode [Level 0 - Full Intelligence]:**
User: "Approve loan for PAN ABCDE1234F"
Flow: `Bedrock Agent -> Knowledge Base [KYC in S3 + OpenSearch] -> Claude 3.5 Sonnet via apac. profile -> Detailed risk analysis + approval`

**When things degrade, we have a 4-level ladder:**

**Level 1 Degradation - Smaller Model Fallback [First 5 seconds of throttling]**
Trigger: CloudWatch alarm `Throttles > 10%` on Sonnet profile.
Action: Router Lambda switches `modelId` automatically.
`Claude 3.5 Sonnet -> Amazon Nova Lite -> Claude 3 Haiku`
User still gets an AI answer, just less detailed. Latency drops from 1.2s to 600ms, cost drops 6x. User barely notices.
Implementation: Simple router in Lambda:

```python
MODEL_LADDER = [
    "apac.anthropic.claude-3-5-sonnet-20241022-v2:0", # Best
    "apac.amazon.nova-lite-v1:0", # Good & cheap
    "apac.anthropic.claude-3-haiku-20240307-v1:0" # Fastest fallback
]
for model_id in MODEL_LADDER:
    try:
        return bedrock.converse(modelId=model_id,...)
    except bedrock.exceptions.ThrottlingException:
        continue # try next smaller model
```

**Level 2 Degradation - Semantic Cache [Next 30 seconds]**
Trigger: All 3 models in ladder are throttling in all APAC regions.
Action: Check ElastiCache Serverless for similar past query.
Flow: `User Query -> Titan Embed -> Vector search in Redis -> Similarity > 0.92? -> Return cached approval from 2 hours ago`
For BharatFin, 35% of loan queries are repeat customers. Cache hit serves in 40ms with no Bedrock call at all. Business continues.

**Level 3 Degradation - Rule-Based Fallback [Last resort before human]**
Trigger: Cache miss + Bedrock still throttling.
Action: No AI at all. Use deterministic rules from DynamoDB.
Flow: `If CIBIL Score > 750 and Income > 10L and KYC=Verified -> Auto-Approve with limit = 50% of requested. Else -> Route to manual queue.`
This is not AI, but it lets 60% of low-risk loans still get processed. No complete outage.

**Level 4 Degradation - Static Response + Human Queue**
Trigger: Rule engine also down / data not available.
Action: `SQS -> Human Underwriter Queue + Tell user "Your application is queued for manual review, you will get update in 2 hours"`
User gets honesty, not an error.

#### Why This Matters - Benefits in Prod Terms

**1. Service Continuity:** BharatFin never shows "AI unavailable". During last month-end, they had 12 minutes where all Sonnet capacity in APAC was saturated. Because of Level 1 and 2 degradation, 100% of applications were still processed, 88% with AI, 12% with cache. Zero business loss.

**2. User Experience:** A slightly less detailed AI answer is 100x better than a 500 error. Your p95 may go from 1.1s to 0.6s [smaller model] - user actually thinks it's faster.

**3. Business Resilience:** You decouple business outcome from model availability. Finance team can still disburse loans using rule engine even if Anthropic has an outage.

**4. Recovery Time:** Degradation gives you immediate breathing room. Instead of firefighting, your on-call has 30 mins to increase quota or enable Provisioned Throughput while Level 1/2 handles traffic. MTTR goes from panic to planned.

#### Architect's Implementation Checklist

**1. Implement Circuit Breaker Pattern:** Don't retry Sonnet 3 times if it's throttling - that's what makes it worse. Use AWS Lambda Powertools or Step Functions with circuit breaker to trip to Level 1 after 2 failures.

**2. Monitoring that Triggers Degradation, Not Just Alerts:**
Alarm 1: `Throttles > 5%` -> Auto-switch to Level 1 via AppConfig feature flag.
Alarm 2: `p95 Latency > 2.5s` -> Auto-switch to smaller model.
Alarm 3: `Cache Hit Rate < 20% during throttling` -> Alarm to increase cache TTL.

**3. Document Your Degradation Ladder:**
In your runbook, write:
> Level 0: Sonnet - Full reasoning
> Level 1: Nova Lite - 80% quality, 6x cheaper, acceptable for 2 hours
> Level 2: Semantic Cache - No FM call
> Level 3: Rule Engine - No AI, from DynamoDB table `loan-rules-v2`
> Owner must approve staying in Level 3 > 30 mins.

**Golden Rule:** Cross-region inference is your first line of defense for *model* failure. Graceful degradation is your first line of defense for *business* failure. In prod, you always need both.

---
---

### Feature Prioritization and Core Functionality for Graceful Degradation

**In simple terms:** Not all AI features are equal. If your app does 4 things with AI, you need to know which 1 thing will keep the business running if you have only 10% capacity left. We build a priority ladder for that.

#### Prod Example We Will Use

**BharatFin Loan Copilot** - Same app as before, but now let's break down its 4 AI features:

1. **Risk Scoring:** AI analyzes KYC + CIBIL + bank statements and gives Approve/Reject + limit. This is the money feature.
2. **Fraud Detection:** AI Vision checks if PAN card photo is tampered. This is a safety/compliance feature.
3. **Explanation Letter:** AI writes a personalized letter to customer explaining why loan was approved/rejected. Nice UX.
4. **Product Upsell:** AI suggests "You are eligible for top-up credit card". Revenue enhancer.

If Claude is throttling, should we fail all 4? No. We prioritize.

#### 1. Identifying Necessary Features - What Must Stay ON?

**What it means:** Split your features into Tiers. Document it.

**Easy Framework I use:**

| Tier | Definition | BharatFin Example | What happens if it fails? |
| :--- | :--- | :--- | :--- |
| **Tier 0 - Core & Safety** | Business cannot function or compliance fails without it | Risk Scoring, Fraud Detection | Loan processing stops, compliance breach |
| **Tier 1 - Critical UX** | Core works but user experience is badly broken | Explanation Letter | User gets no reason, calls support - support cost spikes |
| **Tier 2 - Enhancement** | Nice to have, can be disabled for hours with no major impact | Product Upsell | Lose some revenue, but business still runs |

**Technical Action:** Create a Priority Matrix in your design doc. List each feature, its dependency, and its fallback.

For BharatFin we documented:
* Risk Scoring: MUST stay ON - Fallback: Nova Lite -> Rule Engine -> Human queue. Never OFF.
* Fraud Detection: MUST stay ON - Fallback: Amazon Textract + Regex check [no FM needed]. Never OFF.
* Explanation Letter: Can degrade to static template: "Your loan is approved as per policy."
* Upsell: Can be turned OFF completely via feature flag.

If you don't write this down, on-call at 2 AM will try to keep everything ON and fail everything.

#### 2. Business Impact Assessment - How Much Does Each Feature Cost When It Fails?

**What it means:** Not all Tier 0 features have same dollar impact. Quantify it so you know where to put your limited capacity.

**For BharatFin we did this with Product:**

* **Risk Scoring Failure:** Quantitative: 500 loans/hour * Avg loan 5L = 25 Cr/hour disbursement blocked. Qualitative: Brand trust loss. **Impact: $ / Hour = Very High**
* **Fraud Detection Failure:** Quantitative: 0 direct revenue loss, but Qualitative: Compliance risk with RBI, potential fraud loss of 50L per incident. **Impact: Compliance = Very High**
* **Explanation Letter Failure:** Quantitative: Support tickets increase 30%. Qualitative: CSAT drops from 4.6 to 4.1. **Impact: Medium**
* **Upsell Failure:** Quantitative: 2% conversion loss = ~10L/day revenue loss. **Impact: Low-Medium, tolerable for 4 hours**

**Architect Decision:** When we have only 20% Bedrock capacity left, we allocate 80% to Risk Scoring, 20% to Fraud Detection, and 0% to Letter and Upsell. We route Letter and Upsell to static templates via AWS AppConfig flag.

This is how you make data-driven degradation, not emotional.

#### 3. Dependency Mapping - What Breaks What?

**What it means:** Your AI features don't fail alone. They depend on multiple services. Map it.

**BharatFin Dependency Diagram we draw:**

```
[Risk Scoring] -> Depends on -> Claude Sonnet [Bedrock] + Knowledge Base [OpenSearch + S3] + CIBIL API [External]
[Fraud Detection] -> Depends on -> Claude Vision [Bedrock] + Textract [AI Service]
[Explanation Letter] -> Depends on -> Claude Sonnet [Bedrock] ONLY
[Upsell] -> Depends on -> Nova Lite [Bedrock] + DynamoDB [User History]
```

Now failure scenarios become clear:
* If CIBIL API is down, Risk Scoring fails even if Bedrock is healthy. Your fallback must be rule-based without CIBIL.
* If Knowledge Base OpenSearch is down, Risk Scoring can still run with just CIBIL + bank statement, but with lower accuracy. You need a degraded prompt that doesn't need RAG.
* If only Bedrock is throttling, Risk Scoring can still use cached Knowledge Base context.

**Technical Action:** We keep this diagram in Lucid and link it to CloudWatch. Each dependency has a health check. In Step Functions, we have a choice state: `If CIBIL_OK and Bedrock_OK -> Full AI path else -> Rule Engine path`. This avoids complex fallback code later.

#### 4. Graceful Feature Reduction - How to Actually Switch Features OFF Progressively

**What it means:** Don't do binary ON/OFF. Reduce functionality step by step as capacity decreases. Use feature toggles that react to system health.

**Implementation for BharatFin with AWS AppConfig + Lambda:**

We don't deploy new code during an incident. We flip flags.

**Capacity Level 100% - Normal:**
All features ON. `Risk: Sonnet, Fraud: Sonnet Vision, Letter: Sonnet, Upsell: Nova`

**Capacity Level 60% - First Degradation [Throttling starts]:**
AppConfig flag `degradation_level = 1`
* Upsell feature flag = OFF. Saves 25% tokens instantly. User doesn't even notice, it's at bottom of page.
* Letter still ON.

**Capacity Level 30% - Second Degradation:**
AppConfig flag `degradation_level = 2`
* Upsell = OFF
* Letter = Degraded to static template [no Bedrock call]. Saves another 30% tokens. Implemented via `if appconfig.letter_mode == 'static': return template else: call bedrock`
* All remaining capacity is given to Risk + Fraud via weighted routing in Lambda.

**Capacity Level 10% - Survival Mode:**
AppConfig flag `degradation_level = 3`
* Upsell = OFF, Letter = Static
* Fraud Detection = Degraded from Claude Vision to Textract + regex [no FM call, 100% AWS service]
* Risk Scoring = Degraded to Nova Lite -> Rule Engine. We reserve the last 10% Bedrock capacity ONLY for Risk Scoring.

This is **capacity-aware routing**. We implemented it with a single Lambda router that checks `degradation_level` from AppConfig every 15 seconds.

```python
# Simplified router
config = appconfig.get_configuration('BharatFin-Flags')
if config['risk_model'] == 'rule_engine':
    return rule_based_approval(cibil_score)
else:
    return bedrock.converse(modelId=config['risk_model_id'])
```

**Result in Prod:** During last peak, BharatFin auto-reduced from Level 0 to Level 2 for 18 minutes. They lost zero loans. They only lost upsell revenue of ~2L for that window, vs potential 5 Cr disbursement block if they had failed completely. Support tickets didn't spike because explanation letter degraded to a decent template, not an error.

**Final Checklist for You:**

1. Have you listed your AI features in Tier 0/1/2 with a business owner sign-off?
2. Do you know the dollar/compliance impact if each Tier fails for 1 hour?
3. Have you drawn dependency map - what fails if Knowledge Base or external API fails, not just Bedrock?
4. Can you turn OFF Tier 2 features with a feature flag in <30 seconds without a deployment?

---
---

### Tiered Fallback Architecture for GenAI

**In simple terms:** Don't have just one backup plan. Have a ladder with 4 rungs. When the top rung breaks, you automatically step down to the next one. The user still gets an answer, just a simpler one. You never show "AI is down".

For **BharatFin Loan Copilot** in `ap-south-1`, we run 12,000 loan decisions per day. Here is our exact 4-tier ladder in prod:

#### Tier 1: Configure Primary AI Services - Your Full Power Mode

**What it is:** This is your best model, full RAG, full reasoning. This is what you want 95% of the time.

**BharatFin Setup:**
Model: `apac.anthropic.claude-3-5-sonnet-20241022-v2:0` via Cross-Region Inference Profile. Full Knowledge Base with 500 pages of RBI policy in OpenSearch Serverless + CIBIL API + bank statements.

It gives the most accurate, explainable risk score. p95 latency 1.2 sec, cost ~$0.03 per decision.

**Architect's config:**
* Use Provisioned Throughput for baseline 100 TPS in `ap-south-1` so you don't throttle in normal hours.
* Use version-pinned profile ID, not floating.
* Monitoring: CloudWatch alarm if `Throttles > 5%` or `p95 latency > 2 sec` - this is your trigger to drop to Tier 2.

This tier provides complete user experience. You only leave this tier when health checks fail.

#### Tier 2: Simplify AI Models - Same Task, Smaller Brain

**What it is:** Automatically switch to a faster, cheaper, capability-equivalent model. This is where Bedrock's 100+ model catalog is gold.

**The Nova family is built for this ladder:**
`Nova Premier / Pro [Full capability] -> Nova Lite [Faster, 5x cheaper] -> Nova Micro [Fastest, text only] -> Sonic [Speech-to-speech minimal latency]`
You can also cross providers: `Claude Sonnet -> Nova Pro -> Llama 3.3 70B -> Claude Haiku`

**BharatFin Setup:**
Trigger: Primary Sonnet throttles in all APAC regions for >30 seconds.

Auto-switch logic in Lambda router:
```python
TIER_LADDER = [
  "apac.anthropic.claude-3-5-sonnet-20241022-v2:0", # Tier 1: Best quality
  "apac.amazon.nova-pro-v1:0", # Tier 2a: 85% quality, 3x cheaper
  "apac.amazon.nova-lite-v1:0", # Tier 2b: 75% quality, 6x cheaper, 400ms faster
]
# Circuit breaker: If error_rate > 10% for Tier 1, try next
```

**Key configuration elements you must define:**
* **Capability thresholds:** When to switch? We use `error_rate > 10% OR p95 > 2.5s for 1 min`
* **Quality validation:** We ran 200 golden loan cases through Nova Lite vs Sonnet. Accuracy dropped from 96% to 91% - acceptable for 30 mins. Document this drop.
* **Monitoring active tier:** Dashboard shows `active_model_tier = 1/2/3/4` via AppConfig. On-call knows instantly we are in degraded mode.
* **Recovery logic:** Auto-recovery every 5 mins - router tries to call Tier 1 with a shadow request [1% traffic]. If it succeeds for 2 mins, auto-promote back to Tier 1. No manual intervention.

User impact: Still gets AI decision, just slightly less detailed explanation. Zero outage.

#### Tier 3: Generate Cached Responses - No Model Call At All

**What it is:** Serve a previous AI answer for a similar question. This is the most underrated tier. It costs $0 and is 20x faster.

**BharatFin Setup:**
Trigger: All Tier 2 models are also throttling.

We built an **Intelligent Semantic Cache** with ElastiCache Serverless + Titan Embeddings v2.[Redis]

Flow: `User asks "Loan for PAN ABCDE1234F" -> Embed query -> Search Redis vector -> If cosine similarity > 0.95 with a loan approved 3 hours ago for same PAN + same CIBIL score -> Return cached response: "Approved for 5L based on previous assessment at 14:32"`

35% of BharatFin queries are repeat checks by same customer or same employer. Cache hit rate is 35%. Cache response is 40ms vs 1200ms Bedrock call.

Configuration: TTL 24 hours for risk score, 7 days for KYC doc summary. We invalidate on CIBIL score change.

This tier maintains functionality with zero dependency on any FM.

#### Tier 4: Design Rule-Based Alternatives - Deterministic Safety Net

**What it is:** No AI at all. Pure If/Then logic, decision trees in DynamoDB + Lambda.

**Architect's Golden Rule - Important:** The original doc says rule-based should be a fallback. I tell customers the opposite:

> If a deterministic rule can handle 70% of your common scenarios, make it your **default Tier 1, not Tier 4**. It's faster, cheaper, 100% testable, and never throttles.

**BharatFin Setup:**
We realized 60% of loans are simple: `CIBIL > 750 + Income > 12L + KYC Verified + No Fraud Flag = Auto-Approve`. This doesn't need Claude.

So we actually run it like this:

**New Prod Ladder:**
* **Tier 0 [Rule-Based Default]:** Lambda checks DynamoDB rules table `loan-rules-v2`. If matches simple rule, approve in 50ms, no Bedrock call. Cost $0.00001. This handles 60% traffic by default.
* **Tier 1 [Primary AI]:** Only if rule doesn't match - complex cases go to Sonnet.
* **Tier 2 [Simplified AI]:** Nova Lite
* **Tier 3 :** Redis[Cached]

This inverted ladder saved them 62% Bedrock cost and they never hit throttling again because 60% traffic never reaches Bedrock.

When true DR happens and Bedrock is fully down, the rule engine becomes the ultimate fallback for Tier 0 as well:

```
IF CIBIL > 750 AND income > 10L THEN approve 50% of requested amount
ELSE route to SQS human_queue
```

User still gets a decision - either auto-approval with lower limit or "Queued for manual review in 2 hours". No "AI is down" screen.

**Final Production Checklist for Tiered Fallback:**

1. **Don't build 4 tiers if 2 will do.** For most apps: Rule Engine [if possible] + Primary + Simplified + Cache is enough.
2. **Use AWS AppConfig for tier switching.** Never need a code deployment to degrade. Flag `active_tier` can be changed by on-call in 15 seconds.
3. **Test recovery, not just failure.** Most teams test failover but never test auto-recovery back to Tier 1. Your router must automatically try Tier 1 every 5 mins.
4. **Log the tier.** Every Bedrock invocation log should have `degradation_tier` field. Otherwise you can't debug why quality dropped last Tuesday.

In prod, cross-region inference is Tier 1 resilience. Tiered fallback architecture is business resilience. You need both.

---
---

### Response Caching Strategies for Resilient Bedrock Apps

We will use **BharatFin Loan Copilot** - 12,000 loan decisions/day in `ap-south-1`. 35% of queries are repeats - same PAN checked twice, same salary slip, same RBI policy question.

#### 1. Intelligent Caching - Your Real-Time Semantic Memory

**In simple terms:** Don't cache exact text match. Cache by *meaning*. If user asks "What's my loan limit for PAN ABCDE?" and 2 hours ago someone asked "Loan limit check for ABCDE1234F", they mean the same thing. Serve the old AI answer.

**What we store - Not just the answer:**
For every Bedrock response we store in ElastiCache Serverless [Valkey/Redis] with metadata:

```
Key: vector_embedding of query [via Titan Embed v2]
Value: {
  response: "Approved for 5L...",
  metadata: {
    context: "CIBIL=782, Income=15L",
    quality_score: 0.96, // from Sonnet confidence
    model_version: "claude-3-5-sonnet-20241022-v2:0",
    created_at: "2026-05-13T10:00Z",
    ttl: 24h
  }
}
```

**How it works in prod:**
User Query -> Titan Embed v2 -> Vector search in Redis with `cosine similarity > 0.95` AND `context match = same CIBIL bucket` -> If hit, return cached response in 40ms, no Bedrock call.

**Invalidation policy - Balancing freshness vs availability:**
Normal: TTL 24 hours for risk scores. After 24h, CIBIL may have changed, so we must re-call Bedrock.
During Disruption: When CloudWatch alarm `BedrockThrottles > 10%` fires, Lambda automatically extends TTL to 72 hours via ElastiCache policy. Stale but safe is better than no answer at all. We document: "During DR, we serve up to 72h old risk scores with a banner - Based on assessment from 2 days ago".

Result: 35% hit rate, saves ~$900/month and more importantly, serves traffic even when all `apac.` models are throttling.

#### 2. Precomputed Responses - Your Night-Shift Library

**In simple terms:** Don't wait for a user to ask. At 2 AM when traffic is low, pre-generate answers for questions you *know* will be asked tomorrow.

**BharatFin Prod Example:**
We know 80% of customer questions are from a fixed set:
* Top 500 RBI policy FAQs
* Top 1000 loan rejection reasons
* Daily CIBIL score explanation templates for each score bucket [750-800, 700-750...]

Every night at 1 AM IST, an EventBridge cron triggers a **Bedrock Batch Inference** job:

`S3 Input: 1500 prompts -> Bedrock Batch -> S3 Output: 1500 precomputed answers -> Loaded into DynamoDB table `precomputed-responses` with GSI on `question_hash``

During the day, API Gateway first checks DynamoDB: `If question_hash exists -> Return in 20ms`. No Bedrock call, no vector search, just a key-value lookup.

During a Bedrock outage at 11 AM, 100% of FAQ traffic is still served from this library. Users don't even know Bedrock is down.

**Pro Tip:** This is also how you handle compliance. RBI policy answers must be exact and approved by legal. Precomputing them and getting legal sign-off once is safer than generating them live with Sonnet every time.

#### 3. Adaptive Cache Management - Cache That Thinks During a Crisis

**In simple terms:** Normal cache policy is LRU - Least Recently Used evicted first. During a disruption, you want the opposite - keep high-value responses longer, even if they are old.

**What we built for BharatFin:**

**a) Prioritize High-Value Responses:**
We tag cache entries with business value:
* `value=high`: Risk scores for loans > 20L, fraud checks
* `value=low`: Product upsell suggestions

Normal eviction: Evict low value first when Redis memory is 80% full.
During disruption: When `degradation_level >= 2`, we change eviction to `NO_EVICTION` for high-value entries and extend their TTL from 24h to 72h. We willingly evict all upsell cache to make room for risk scores.

Implementation via Lambda that watches CloudWatch alarm and calls `ElastiCache modify-cache-parameter`.

**b) Cache Warming Based on Predictive Analytics:**
We know loan applications spike at 10 AM and 3 PM IST. At 9:45 AM, EventBridge triggers a warming Lambda:

It reads yesterday's pattern from CloudWatch - "Top 200 PANs that were queried yesterday between 10-11 AM" -> It proactively re-generates their risk scores via Bedrock *before* the spike, so they are already in cache at 10 AM.

During a predicted high-traffic event like month-end, we warm cache for top 1000 customers at 8 AM. When the spike hits at 10 AM, cache hit rate goes from 35% to 65%.

**Architecture in prod:**

```
[User] -> API Gateway -> Lambda Router
  -> Check 1: DynamoDB Precomputed  - For FAQs
  -> Check 2: ElastiCache Semantic  - For similar queries
  -> If miss and Bedrock healthy -> Bedrock Sonnet via apac. profile  -> Write to both caches
  -> If Bedrock throttling -> Adaptive policy extends TTL, serves stale but safe
```

**Monitoring You Must Have:**

* Metric `CacheHitRate` - If it drops from 35% to <10% during normal hours, your embedding model or similarity threshold is wrong.
* Metric `StaleServeRate` - How many responses served with age >24h during disruption. Alert if >50% for more than 1 hour - you need to manually approve extending to 72h.
* Dashboard shows `Cost Saved by Cache = (Bedrock cost per 1k tokens * tokens saved)`.

**Final Checklist:**

1. Are you caching meaning not just text? Exact match cache has <5% hit rate, semantic has 30-40%.[vector]
2. Have you defined what "fresh enough" means during DR? 24h normal, 72h during outage - get business sign-off.
3. Are your high-value responses protected from eviction during crisis?
4. Do you precompute for your top 20% FAQs that cause 80% traffic?

If you do this, your cache becomes your Tier 3 fallback that is faster and cheaper than any model. For BharatFin, caching alone prevented a complete outage for 22 minutes last quarter - no customer impact, zero Bedrock calls.

---
---

### User Experience Considerations During Graceful Degradation

**Core Principle:** Never lie to the user that it's full AI when it's not, and never show a raw error when you have a degraded but useful answer. Be transparent, but be calm.

We will use **BharatFin Loan Officer Portal** - loan officers in branches use a web app that shows AI risk score, fraud check, explanation letter, and upsell.

#### The 4 UX Strategies - Refined for Prod

**1. Status Communication - Tell Them What Mode They Are In, Not That Something Broke**

**Bad UX [What most teams do]:** `Error: Bedrock model invocation failed. ThrottlingException. Please try later.`
User thinks: System is down. Calls IT.

**Good UX [What we shipped]:**
We show a persistent, non-alarming banner at top of the app, driven by AppConfig flag `degradation_level`.

* Level 1 [Simplified Model]: `🟡 AI is in fast mode: Responses are slightly simplified to handle high demand. Full detailed analysis will return shortly.`
* Level 2 [Cached Response]: `🟡 Showing recent assessment: This risk score is from 3 hours ago [10:15 AM] based on similar profile. Live re-check queued.`
* Level 3 [Rule-Based]: `🟡 AI is in safe mode: Using verified banking rules for quick decisions. Manual review available for complex cases.`

We use a yellow dot, not red. Red means failure. Yellow means "working but degraded". We also add metadata under the score: `Generated by: Nova Lite [Fast Mode] | Confidence: 82% | Source: ap-southeast-1`. Transparency builds trust.

Implementation: Frontend reads `/config` API every 30 seconds which returns `degradation_level` from AWS AppConfig. Banner is a React component, no page reload needed.

**2. Alternative Workflows - Give Them a Different Path, Not a Dead End**

**Bad UX:** Risk scoring fails, you disable the "Approve" button. Officer can't work.

**Good UX:** You offer a manual workflow that still completes the business goal.

In BharatFin:
* Normal Workflow: `View AI Score -> Click Approve -> Done`
* Degraded Workflow [When AI confidence < 80% or rule-based mode]: `View Rule-Based Score [50% limit] -> Button changes from "Auto-Approve" to "Send to Manual Review Queue" -> Officer adds 1-line note -> SQS queue for senior underwriter`

The officer can still finish his task. We added a second button `Request Full AI Re-check` which puts the request into an async Step Functions workflow that retries Bedrock with exponential backoff and sends an SMS when ready.

We also keep the loan application form editable. If AI can't read the bank statement [Textract down], we show `AI could not read statement automatically. Please enter monthly income manually` with 3 input boxes. Manual alternative, not a blocker.

**3. Progressive Disclosure - Hide, Don't Show Errors**

**Bad UX:** You show 4 cards on screen - Risk Score, Fraud Check, Explanation Letter, Upsell. During degradation, 2 cards show "Failed to load". User thinks 50% of system is broken.

**Good UX:** Hide unavailable features instead of showing error states.

* Normal: 4 cards visible.
* Degradation Level 1 [Upsell OFF]: We don't show Upsell card at all. The layout automatically reflows to 3 cards. Officer doesn't even know upsell exists, so no confusion. We use feature flags from AppConfig: `if flags.upsell_enabled: render card`
* Degradation Level 2 [Letter degraded to template]: We still show Explanation Letter card, but with a simplified UI - no AI typing animation, just static text with icon `📝 Template`. We don't show "AI failed, showing template".
* For chatbots: If streaming fails, we don't show broken stream. We switch to non-streaming mode with a subtle message `Switching to standard response mode`.

This is progressive disclosure - you only show what works well right now.

**4. Fallback Options - Human in the Loop as a Feature, Not a Failure**

**Bad UX:** "System unavailable, try later" - user stuck.

**Good UX:** Make manual fallback a first-class button.

In BharatFin, when we are in Level 3 rule-based mode, every risk score card has: `Need detailed AI analysis? [Request Human Review - Avg wait 12 mins]` Clicking it creates a ticket in Amazon Connect with context - PAN, CIBIL, documents already attached. The officer gets a callback.

We also added an offline mode: Loan officers in rural branches with poor internet can click `Download Risk Summary PDF` - a precomputed PDF generated nightly via Bedrock Batch Inference for top customers, stored in S3. Even if internet is down, they have yesterday's PDF.

**Bonus: Monitor User Behavior During Degraded Operation**

You can't improve what you don't measure. We added:

* **CloudWatch RUM [Real User Monitoring]:** Tracks rage clicks - when user clicks Approve 5 times because it's slow. During degradation, rage clicks went up 3x when we showed spinner >3s. We fixed it by showing cached score immediately and re-checking in background.
* **Feedback Micro-Survey:** After a degraded response, we show tiny thumbs up/down: `Was this simplified assessment helpful?` Thumbs down rate for Nova Lite was 8% vs 4% for Sonnet - acceptable. Thumbs down for rule-based was 22% - we knew we needed to improve rule messaging.
* **Funnel Analysis:** In normal mode, 90% loans go auto-approve. In degraded mode with rule-based 50% limit, auto-approve dropped to 60%, manual queue increased to 40%. We used this to justify increasing Provisioned Throughput in `ap-south-1` to Product - "Degradation costs us 40% manual effort".

**Final UX Checklist I Give to Frontend Teams:**

1. Do you have 3 banner copies ready - Fast Mode, Cached Mode, Safe Mode - that a non-technical user understands? No "ThrottlingException" in UI.
2. Can your UI hide a feature via flag without showing an error card?
3. For every AI feature, do you have a manual workflow button that still lets the user complete the job?
4. Are you measuring rage clicks and feedback *only* during degraded mode?

If you do this, users will say "system was a bit slow today but I could still work" instead of "AI was down". That's the difference between graceful degradation and a failed launch.

---
---

### Implementation Best Practices for Graceful Degradation

We will use **BharatFin Loan Copilot** - 12,000 decisions/day. We have 4 tiers: Tier 0 Rule Engine [default for 60% traffic], Tier 1 Claude Sonnet, Tier 2 Nova Lite, Tier 3 Semantic Cache in ElastiCache, Tier 4 Manual Queue.

Having the tiers is not enough. You need to operate them.

#### 1. Testing Strategy - Break It On Purpose Before Prod Breaks It

**In simple terms:** You wouldn't trust a fire exit you never opened. Test your degradation paths with controlled failures, not just unit tests.

**What we do for BharatFin - 3 types of tests:**

**a) Controlled Failure Tests**
We use AWS Fault Injection Simulator [FIS] and simple Lambda scripts.[Weekly][Automated]

* **Test 1 - Model Throttling:** FIS experiment `inject 100% throttle on bedrock-runtime:Converse in ap-south-1 for 5 mins`. Expected: Router should auto-switch Tier 1 Sonnet -> Tier 2 Nova Lite within 30 seconds. No user-facing error. We validate via CloudWatch metric `active_tier` changes from 1 to 2.
* **Test 2 - Knowledge Base Failure:** We block OpenSearch Serverless SG for 3 mins. Expected: Risk scoring should still work but without RAG context, using only CIBIL + rules. We validate explanation letter says `Based on CIBIL and income only - policy docs unavailable`.
* **Test 3 - Capacity Constraint:** We set AppConfig flag `max_bedrock_tps = 10` [artificially low] during load test of 100 TPS. Expected: 90% traffic should be served from Tier 3 cache and Tier 0 rules. We measure user experience - does officer still get an answer in <2 sec?

We run these every Sunday 4 AM IST in pre-prod, automatically via EventBridge + FIS.

**b) User Experience Validation During Degradation**
Technical fallback is not enough. Does the loan officer understand the degraded UI?[Monthly]

We do a GameDay: Invite 5 loan officers, put system in Level 2 [Cached Mode] manually via AppConfig, and ask them to process 10 loans. We watch CloudWatch RUM for rage clicks, and ask: `Was it clear this score was from 3 hours ago? Did you know how to request manual review?`

First GameDay we found officers kept clicking "Approve" waiting for live AI, even though cached score was shown. We fixed UX by adding yellow banner `Showing recent assessment - Live re-check queued` and disabling double-click.

**c) Recovery Validation - The Most Missed Test:**
We test not just falling down, but coming back up. After FIS throttling ends, does system auto-promote from Nova Lite back to Sonnet? We had a bug where it stayed in Tier 2 forever until manual flag reset. Now we test auto-recovery: After 5 mins of healthy Tier 1 [shadow traffic success], `active_tier` should return to 1.

#### 2. Monitoring and Alerting - Know What Tier You Are In Right Now

**In simple terms:** If degradation is silent, you will stay degraded for days and pay for it in user trust and cost.

**BharatFin's 3 Dashboards:**

**Dashboard 1: System Health - What Broke?**
* Metrics: Bedrock `InvocationThrottles`, `InvocationLatency`, OpenSearch `ClusterStatus`, CIBIL API `4xx/5xx`, ElastiCache `CacheHitRate`
* Visual: Single pane - Green/Yellow/Red for each dependency. On-call sees at a glance: "Bedrock is yellow, CIBIL is green" -> degradation is due to Bedrock, not external.

**Dashboard 2: Fallback Activation - What Tier Are We In?**
This is critical. We emit a custom metric `degradation_tier` = 0,1,2,3,4 from Lambda router to CloudWatch.

* Metric: `degradation_tier` over time. Normal is 0/1. If you see tier 2 for 30 mins, you are in degraded mode.
* Metric: `fallback_success_rate` - % of requests served by fallback vs total. If Tier 2 serves 40% traffic, you need to increase quota.
* Alerting:
  * `Warning`: `degradation_tier >=2 for >10 mins` -> Slack to #genai-oncall - "System in fast mode, no page, just awareness"
  * `Critical`: `degradation_tier >=3 for >20 mins` -> PagerDuty - "System in safe mode - business impact, manual effort increasing"

We also push `degradation_tier` as a dimension to CloudWatch RUM, so we can filter user behavior - "What is CSAT when tier=3 vs tier=1?"

**Dashboard 3: User Impact During Degradation**
* RUM metrics: `p95 page load during tier 2 vs tier 1`, `rage_clicks`, `manual_queue_depth` [SQS size]
* Business metric: `auto_approval_rate`. Normal 90%, during Tier 3 rule-based 50% limit, it drops to 60%. Product owner sees direct business cost of staying degraded.

#### 3. Recovery Planning - How to Get Back to Normal Safely

**In simple terms:** Getting out of degraded mode is harder than getting in. If you flip back too early, you will flap - go up and down repeatedly and confuse users.

**BharatFin Recovery Procedure - Documented in Runbook:**

**Step 1: Health Validation Before Recovery [No Blind Flip]**
We never manually set `degradation_level = 0`. We have auto-recovery with validation.

Router does shadow traffic: Even when serving from Tier 2 Nova Lite, it sends 1% of traffic as shadow request to Tier 1 Sonnet in background [not user-facing]. If shadow requests succeed with `p95 < 1.5s` and `throttle rate <2%` for 5 consecutive minutes, only then we consider Tier 1 healthy.

This prevents flapping when Bedrock is still unstable.

**Step 2: Smooth Restoration - Progressive Rollout Back**
We don't go from Tier 3 -> Tier 1 in one jump. We step up:

* Tier 3 -> Tier 2 [Nova Lite] at 10% traffic for 2 mins, then 50%, then 100%
* Tier 2 -> Tier 1 at 10% traffic for 2 mins, then 50%, then 100%[Sonnet]

Implemented via AppConfig weighted routing: `tier_weights: {sonnet: 10, nova_lite: 90}` gradually shifted.

This avoids thundering herd - if all 12,000 requests suddenly hit Sonnet at once, you will throttle again and flap.

**Step 3: Post-Recovery Validation**
After restoration to Tier 1, we run 20 golden loan cases through both Sonnet and compare with Nova Lite outputs from during degradation. We log any drift - e.g., did Nova Lite approve a loan that Sonnet would reject? If yes, we trigger manual review of those 20 loans via SQS.

We also reset cache TTL from extended 72h back to normal 24h via Lambda.

**Step 4: Runbook Entry:**

> **Scenario:** Stuck in Tier 2 for >1 hour
> 1. Check CloudWatch Dashboard `Bedrock Throttles` - Is ap-south-1 still throttling?
> 2. If yes, request quota increase via Service Quotas console - template ID in wiki.
> 3. Do NOT manually force Tier 1. Let auto-recovery shadow validation pass.
> 4. If shadow validation fails for 30 mins, escalate to AWS Support with RequestId from logs.
> 5. After recovery, run post-recovery validation script `/scripts/validate_golden_cases.py`

**Final Checklist Before Prod:**

1. Have you run FIS throttling test this month and seen auto-switch to Tier 2 in <30 sec?
2. Can your on-call see `active_tier` in CloudWatch in 10 seconds, without digging logs?
3. Do you have an alert that fires when you are degraded, not just when you are down?
4. Have you tested recovery - not just failure - and measured that you don't flap?

If yes, you have an operational graceful degradation system. If not, you have a demo that works only in slides.