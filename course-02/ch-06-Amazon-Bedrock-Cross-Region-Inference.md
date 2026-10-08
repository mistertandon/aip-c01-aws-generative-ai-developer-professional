https://www.meta.ai/prompt/2c899231-4d52-4c3e-a21b-13f47dab9d4c

### Understanding Cross-Region Inference in Amazon Bedrock

#### 1. The Production Problem We All Hit

When you go live with GenAI, two things will break your application:

**Problem A: Model Availability Gap.** Not every Foundation Model [FM] is available in every AWS Region. If your app runs in `ap-south-1 [Mumbai]` for data residency, you might find that Claude 3.5 Sonnet v2 or Llama 3.3 70B is not offered there.

**Problem B: Regional Resilience.** Bedrock is regional. If that Region has a service disruption, or you get throttled with `TooManyRequestsException` during a traffic spike, your app goes down. For a production workload with a 99.9% availability target, that's not acceptable.

We used to solve this by building custom routing logic with Route 53, health checks, and retries. Cross-Region Inference replaces all of that.

#### 2. What is Cross-Region Inference? - Simple Explanation

Think of it as **Multi-AZ for Foundation Models**.

Instead of calling a specific model in a specific Region, you call an **Inference Profile**. An Inference Profile is a logical ID that represents the *same* FM in multiple Regions within a geography set.

You still make ONE API call from your primary Region. Bedrock's managed router then transparently routes that request to the healthiest Region where the model is available and has quota.

It is 100% transparent to your application. Your API interface - `Converse`, `InvokeModel`, `ConverseStream` - and your request/response JSON schema remain exactly the same.

**Geography Boundary is Key:** AWS groups Regions into geographies - `us`, `eu`, `apac`, `global`. A profile with `us.` prefix will ONLY route within US Regions `us-east-1, us-west-2, etc.`. Your prompt data never leaves that geography unless you use a `global.` profile.

#### 3. Production Real-World Example

**Customer:** A FinTech unicorn in Gurugram building an AI Loan Underwriting Copilot.

**Workload:** The app stack [EKS + Bedrock Agent + Knowledge Bases for KYC docs] runs in `ap-south-1` to meet RBI data residency. The core model is `anthropic.claude-3-5-sonnet-20241022-v2:0` because of its reasoning on financial documents.

**Production Incident Without Cross-Region:**
During month-end, loan applications spike 5x. Bedrock in `ap-south-1` throttles. Their customer-facing copilot returns 429 errors. Loan officers can't process loans. Business impact.

**Architecture With Cross-Region Inference:**

`[User -> EKS in ap-south-1] -> [Bedrock Runtime Client in ap-south-1] -> calls Inference Profile ID: apac.anthropic.claude-3-5-sonnet-20241022-v2:0`

What happens behind the scenes:
1. Bedrock tries to serve from `ap-south-1`.
2. On throttling, it automatically fails over to `ap-southeast-1 [Singapore]` or `ap-northeast-1 [Tokyo]` where quota is available.
3. Response returns to your app in `ap-south-1` as if nothing happened.

No custom failover code, no second endpoint to manage.

**Production Implementation - It's just one ID change:**

```python
import boto3

# You are still calling from your primary region
bedrock_runtime = boto3.client('bedrock-runtime', region_name='ap-south-1')

# BEFORE: Brittle - Direct Model ID
# model_id = 'anthropic.claude-3-5-sonnet-20241022-v2:0'

# AFTER: Resilient - APAC Cross-Region System Inference Profile
model_id = 'apac.anthropic.claude-3-5-sonnet-20241022-v2:0'

response = bedrock_runtime.converse(
    modelId=model_id, # Same parameter, now using a Profile
    messages=[{"role": "user", "content": [{"text": "Analyze this KYC doc for risk"}]}],
    inferenceConfig={"temperature": 0.2, "maxTokens": 1024}
)
```
You don't create this profile - AWS provides System-Defined Profiles like `us.*`, `eu.*`, `apac.*`. You just need to enable model access in all destination Regions.

#### 4. Key Benefits - Refined for Production

**1. Model Availability:** Access best-in-class models even if they don't exist in your primary Region. Build in Mumbai, infer from Singapore.

**2. Resilience: Automatic Failover:** Handles both regional outages and throttling. This is how you meet business continuity and RTO requirements for GenAI apps.

**3. Simplified Architecture:** One endpoint to manage. You eliminate custom routing, retry, and health-check Lambdas. Less code, less to operate.

**4. Consistent Interface:** No payload change. Your Guardrails, Prompt Management, Agents all work the same way regardless of which Region actually runs the inference.

#### 5. Architect's Checklist Before You Go Live

If you use this in prod, do this:

**a) Quotas:** Increase `On-demand model invocation` quota for that FM in *all* Regions in your geography set, not just primary. Failover will fail if destination has no quota.

**b) Latency & Cost:** Failover to a farther Region adds 100-250ms latency. Cost is based on the Region that *serves* the request, not the Region you call from. There is no extra charge for routing itself.

**c) Data Residency:** If regulation says data cannot leave India, you cannot use `apac.` profile. You must stay with a single-region profile in `ap-south-1`. Use `eu.` profiles for GDPR workloads.

**d) Observability:** Enable Bedrock Invocation Logging and CloudWatch metric `Invocations` filtered by `InferenceProfileId` to see which underlying Region served the request and track failover rate.

**Bottom Line:** For any pilot, use direct model IDs. For any production workload where availability matters, use a Cross-Region Inference Profile. It's the difference between a demo and a service.

---
---

### Assessing Amazon Bedrock Regional Model Availability

**In simple terms:** Bedrock is not the same everywhere. A model you use in `us-east-1` may not exist in `ap-south-1`, may have different quota, different version, or may not be allowed to process your data due to compliance. You need to assess this *before* you go live.

I use a 4-pillar framework to assess this for every prod workload.

#### Prod-Level Example We Will Use

**Company: ShopGlobal** - A retail platform. Primary region is `ap-south-1 [Mumbai]` for India customers to meet DPDP Act. DR region is `ap-southeast-1 [Singapore]`. They also serve EU customers from `eu-west-1 [Ireland]`.

**Use Case:** GenAI Contact Center - `Anthropic Claude 3.5 Sonnet` for reasoning + `Amazon Titan Embeddings v2` for RAG on product manuals.

#### Pillar 1: Regional Capacity Considerations

**What it means:** Same model, same Region, different capacity. `us-east-1` and `ap-south-1` are high-demand regions. During peak events like Diwali Sale, you will hit `TooManyRequestsException` or higher latency even if the model is available.

On-Demand is shared capacity. Provisioned Throughput is reserved capacity.

**Prod Reality:**
ShopGlobal's contact center handled 200 TPS normally in Mumbai. On Diwali, it spiked to 1500 TPS. Bedrock in `ap-south-1` throttled, even though Claude was available. Chatbot went down.

**Architect Action:**
1.  Never design for just availability, design for capacity. Check Service Quotas > Amazon Bedrock in each target Region.
2.  Use **Cross-Region Inference Profile** - e.g., `apac.anthropic.claude-3-5-sonnet-20241022-v2:0`. If Mumbai is throttled, Bedrock automatically fails over to Singapore or Tokyo within the `apac` geography.
3.  For predictable peak, buy **Provisioned Throughput** in primary and at least one secondary Region.

> Tool: CloudWatch metric `Throttles` for Bedrock + console `aws bedrock list-foundation-models --region ap-south-1`

#### Pillar 2: Model Distribution Patterns

**What it means:** Bedrock has ~100 serverless models from 7+ providers - Amazon Nova, Anthropic Claude, Meta Llama, Mistral, Cohere, AI21, Stability. But distribution is not uniform due to provider commercial agreements, GPU infrastructure, and regulations.

You cannot assume your favorite model is everywhere.

**Prod Reality:**
ShopGlobal found Claude 3.5 Sonnet is not in `ap-south-1` on launch week. Titan Embeddings v2 is in `ap-south-1`, but Cohere Embed v3 is not.

If you hardcode `anthropic.claude-3-5-sonnet`, your Mumbai deployment fails at deploy time.

**Architect Action: Build a Capability Map, not a Model Map.**

| Capability Needed | Preferred Model | Region-Aware Alternative [Same Job] | When to Use |
| :--- | :--- | :--- | :--- |
| Complex Reasoning | Claude 3.5 Sonnet | Amazon Nova Premier, Llama 3.3 70B | If Claude not available in `ap-south-1` |
| Embeddings for RAG | Titan Embed v2 | Cohere Embed English v3 | If you need multilingual |
| Fast Summarization | Nova Lite | Mistral Small | Cost/latency sensitive |

We always document this in our IaC. And we automate the check:

```python
import boto3
for region in ['ap-south-1', 'ap-southeast-1', 'eu-west-1']:
    bedrock = boto3.client('bedrock', region_name=region)
    models = [m['modelId'] for m in bedrock.list_foundation_models()['modelSummaries']]
    print(f"{region} has Claude Sonnet: {'anthropic.claude-3-5-sonnet' in str(models)}")
```

Review this mapping quarterly - AWS adds models to new Regions every month.

#### Pillar 3: Compliance and Data Residency

**What it means:** Cross-region routing is powerful, but it means your prompt - which may contain PII, KYC data - leaves your primary Region.

Some data *cannot* leave.

**Prod Reality:**
ShopGlobal's India loan data cannot leave India per compliance. EU customer chat data cannot leave `eu-*` per GDPR.

If they used a `global.anthropic.claude...` profile from `ap-south-1`, that PII could be processed in `us-east-1`. That's a compliance violation.

**Architect Action:**
1.  Classify your data: Public / Internal / Restricted / PII.
2.  Align profile to compliance:
    *   India PII -> Use ONLY single-region model ID in `ap-south-1` OR an `apac.` profile only after legal sign-off that `ap-southeast-1` is allowed.
    *   EU PII -> Use ONLY `eu.anthropic.claude...` profile. It guarantees routing stays inside `eu-west-1, eu-central-1, eu-north-1`.
3.  Document restrictions: "No cross-region for KYC RAG. OK for public product Q&A."

#### Pillar 4: Model Version Consistency

**What it means:** `Claude 3.5 Sonnet` is not one version. There is `20240620-v1` and `20241022-v2`. Different Regions can be on different versions for a few days/weeks during rollout. Responses will differ slightly.

Cross-region inference *tries* to route to equivalent versions, but it's not guaranteed during rollout.

**Prod Reality:**
ShopGlobal's prompt that was tuned for Sonnet v2 in `us-east-1` gave different JSON formatting in `ap-southeast-1` which was still on v1. Their downstream parser broke.

**Architect Action:**
1.  Always pin to full versioned ID: `anthropic.claude-3-5-sonnet-20241022-v2:0`, not `anthropic.claude-3-5-sonnet`.
2.  When using cross-region profiles, pin to versioned profile: `apac.anthropic.claude-3-5-sonnet-20241022-v2:0`
3.  Add Model Evaluation in your CI/CD - run the same 50 golden prompts across primary and secondary Regions and compare for drift using Bedrock Model Evaluation.

**Final Checklist for Production:**

Before you ship, answer this:
1.  Have I listed my models in all 3 Regions I care about?
2.  Have I mapped an equivalent alternative for each?
3.  Have I checked quotas and throttling in *all* failover Regions?
4.  Does my cross-region profile geography align with data residency?
5.  Am I pinned to a full versioned model ID?

If yes, you are resilient. If not, your first regional outage will be your lesson.

---
---

### Setting up Cross-Region Inference - The Right Way

**Core Idea in simple terms:** You still call Bedrock from your primary Region like `ap-south-1`. Instead of calling a Model ID like `anthropic.claude-3-5-sonnet`, you call an **Inference Profile ID** like `apac.anthropic.claude-3-5-sonnet-20241022-v2:0`. That `apac.` prefix is the magic - it tells Bedrock "if Mumbai is throttled or down, automatically try Singapore and Tokyo". Same API, same code.

#### Prod-Level Example We Will Use

**BharatFin - A Lending FinTech in Gurugram.**
Primary workload in `ap-south-1` for DPDP Act compliance. They run a Loan Underwriting Copilot using Bedrock Agents + Claude 3.5 Sonnet + Knowledge Bases.
SLO: 99.95% availability, p95 latency < 2 seconds. During month-end, traffic is 10x.

Here is how we set it up for them in 4 steps:

**Step 1: Enable Model Access Everywhere [What the doc calls "Turn on cross-region"]**

There is no global toggle. You need to do two things:

a) Enable model access in **ALL Regions** you want to failover to. Bedrock console > Model access > Enable Claude Sonnet in `ap-south-1`, `ap-southeast-1`, `ap-northeast-1`.

b) Start using the System-Defined Cross-Region Profile. You don't create it, AWS already created it.

```bash
# List all cross-region profiles available to you
aws bedrock list-inference-profiles --region ap-south-1 --query "inferenceProfileSummaries[?contains(inferenceProfileId, 'apac')]"
# You will see: apac.anthropic.claude-3-5-sonnet-20241022-v2:0
```

For BharatFin, we chose `apac.*` because it keeps data within APAC geography. For EU workloads we would choose `eu.*` to stay GDPR compliant.

**Step 2: Configure Region Preferences - Choose Your Geography**

This is the most important architect decision. You are not picking primary/secondary manually. You are picking a geography set by the prefix.

| Prefix | Where it can route | When to use |
| :--- | :--- | :--- |
| `ap-south-1` model ID | Only that Region | Strict data must not leave India |
| `apac.` profile | `ap-south-1, ap-southeast-1/2, ap-northeast-1/2/3` | BharatFin - India + APAC resilience |
| `eu.` profile | `eu-west-1/3, eu-central-1/2, eu-north-1` | GDPR workloads |
| `us.` profile | `us-east-1/2, us-west-2` | US workloads |
| `global.` profile | Anywhere | Non-sensitive, max resilience |

**BharatFin Decision:** We used `apac.` profile. Primary is Mumbai for latency, failover is Singapore because it's closest to users [~70ms extra vs 250ms to Tokyo]. We documented that PII can be processed in Singapore after legal sign-off.

If you need a custom list of Regions [e.g., only Mumbai and Singapore, not Tokyo], you create an **Application Inference Profile** via console or CDK.

**Step 3: Implement Request Routing - Zero Custom Logic**

This is the beauty - you do NOT build routing logic. You use the standard Bedrock Runtime API.

BharatFin's code before :[brittle]
```python
client = boto3.client('bedrock-runtime', region_name='ap-south-1')
client.converse(modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',...) # Fails on throttling
```

After [resilient - prod ready]:
```python
import boto3
from botocore.config import Config

# Add retries - Bedrock will handle cross-region retry automatically
config = Config(retries={'max_attempts': 3, 'mode': 'adaptive'})
client = boto3.client('bedrock-runtime', region_name='ap-south-1', config=config)

# Just change the modelId to the Inference Profile ID
PROFILE_ID = 'apac.anthropic.claude-3-5-sonnet-20241022-v2:0'

response = client.converse(
    modelId=PROFILE_ID, # Same param
    messages=[{"role": "user", "content": [{"text": "Assess loan risk for PAN: ABCDE1234F"}]}]
)
```

Test it like prod: We injected throttling in `ap-south-1` using fault injection and saw requests automatically succeed from `ap-southeast-1` with no code change. Latency increased from 1.2s to 1.35s, which was within SLO.

IAM permission needed is same: `bedrock:InvokeModel` and `bedrock:Converse` on the profile ARN, not just model ARN.

**Step 4: Configure Monitoring and Alerting - You Must Know When Failover Happens**

Failover is silent by default. You must make it visible.

BharatFin setup:

1. **Enable Model Invocation Logging:** Bedrock > Settings > Model invocation logging > S3. The log contains `inferenceProfileId` and `invokedRegion` - which tells you where it actually ran.

2. **CloudWatch Metrics:**
    Metric: ` AWS/Bedrock -> ModelInvocationThrottles` and `ModelInvocationLatency` filtered by `inferenceProfileId`.

3. **Alert:** We created an alarm: If more than 15% of invocations in 5 mins have `invokedRegion!= ap-south-1`, trigger PagerDuty. This means Mumbai is constantly throttling and we need to increase Provisioned Throughput quota.

Sample CloudWatch Logs Insights query:
```
fields @timestamp, modelId, @message
| filter inferenceProfileId like /apac/
| stats count() by invokedRegion
```

**Final Production Checklist:**
1. Model access enabled in ALL regions in the geography?
2. Service Quota for On-Demand invocations increased in ALL failover regions?
3. Are you using version-pinned profile ID e.g. `...20241022-v2:0` not floating?
4. Does your geography `us/eu/apac/global` align with your compliance doc?
5. Do you have an alarm for continuous failover?

If you do this, your GenAI app will survive a regional outage like any other well-architected workload.

---
---

### Performance and Cost Considerations for Cross-Region Inference

**The core trade-off:** Resilience vs. Latency vs. Cost. You get resilience out of the box with a cross-region profile like `apac.anthropic.claude-3-5-sonnet`. What you need to architect is how to keep latency and cost flat.

> **Important correction:** There is **no extra fee** for cross-region routing itself. You don't pay for "data transfer" for the routing. You simply pay the standard Bedrock model price in the Region where the request *actually ran*. And there is no CDN/Edge that can cache a Bedrock LLM call - you need to cache at the application layer.

#### 1. Performance - Where Does Latency Come From?

**What happens:** Normal path: `App in ap-south-1 -> Model in ap-south-1` = ~800ms p95.
Failover path: `App in ap-south-1 -> Bedrock internal routing -> Model in ap-southeast-1 [Singapore]` = ~800ms + network hop of 70-120ms + cold start = ~950-1100ms p95. If it fails over to Tokyo, add 180-250ms.

It's not huge, but for a streaming chatbot, user will feel it.

**Prod Example: BharatFin's Underwriting Copilot**
We measured this in prod for 10M requests. 95% served from Mumbai: p95 1.1 sec. 5% that failed over to Singapore during month-end peak: p95 1.35 sec. Their SLA was 2 sec, so it was still within SLO, but their UX team noticed the streaming felt slower.

**How we optimized performance:**

**a) Region Selection is Latency Selection:** Don't pick secondary randomly. For `ap-south-1` primary, pick `ap-southeast-1` as secondary, not `ap-northeast-1`. It's 3x closer. For EU, pair `eu-west-1 [Ireland]` with `eu-central-1 [Frankfurt]` - 20ms apart, not with `eu-north-1`.

**b) Request Optimization - This is where you save the most:**
* **Prompt Caching [Bedrock feature]:** For RAG, your system prompt + KYC docs are same for every request. Enable `prompt caching` - Bedrock caches it in the region that serves it. Saves 60-80% latency on cached tokens.
* **Semantic Caching:** 40% of support questions are repeated - "What is my loan status?". We added an ElastiCache Serverless semantic cache. If embedding similarity >0.95, return cached answer without calling Bedrock at all. Failover = 0 for those requests.[Redis]
* **Batch Embeddings:** Don't call Titan Embed for 1 doc at a time. Batch 20 docs for Knowledge Base ingestion. Fewer cross-region calls.

#### 2. Cost - Where Does Money Actually Go?

You don't pay extra for failover, but you do pay for these 4 cost leaks:

**Prod Example: Same BharatFin - 20M tokens/day**

| Cost Leak | What Happened | Architect Fix |
| :--- | :--- | :--- |
| **1. No caching** | Same 5-page loan policy sent in every request. 3,000 tokens wasted per call. | Prompt caching + semantic cache saved ~$1,200/month |
| **2. No capacity planning** | Primary quota was 100 TPS. They hit 300 TPS, 66% requests failed over. They paid Singapore price + primary still idle. | Increased quota + 100 TPS Provisioned Throughput in `ap-south-1`. Failover dropped from 66% to 3%. |
| **3. Wrong model for job** | Using Claude Sonnet for simple classification that Haiku could do. | Router pattern: Classifier Lambda -> If simple -> `apac.anthropic.claude-3-haiku`, If complex -> Sonnet. 70% traffic moved to Haiku - 5x cheaper. |
| **4. No monitoring** | Team didn't know 30% traffic was going to secondary for a week. | Added monitoring - see below. |

**Region Selection for Cost:** Model price is not identical everywhere. `us-east-1` and `us-west-2` are cheapest. `ap-south-1` is typically 5-10% higher. If you use `global.` profile and it fails over from US to Asia, your per-token cost goes up slightly. For cost-sensitive workloads, stick to `us.` or `apac.` only, not `global.`.

#### 3. How We Monitor Both Together - Production Dashboard

We build one dashboard for ShopGlobal that tracks resilience, performance, and cost together:

**CloudWatch + Invocation Logs:**
Enable Bedrock Model Invocation Logging to S3. Each log has `invokedRegion` and `inferenceProfileId`.

Query in CloudWatch Logs Insights:
```
fields @timestamp, modelId, invokedRegion, inputTokens, outputTokens
| filter inferenceProfileId like /apac/
| stats avg(latency) as p95_latency, sum(inputTokens+outputTokens)/1000 as kTokens, count() by invokedRegion
```

**Alarms we set:**
1. **Performance:** Alarm if p95 latency > 1.8s for 5 mins
2. **Resilience:** Alarm if `invokedRegion!= ap-south-1` > 10% for 10 mins - means primary is under-provisioned
3. **Cost:** Daily Cost Anomaly in Cost Explorer for Bedrock service, grouped by Region. If Singapore cost spikes 50% day-over-day, we know failover is high.

**My Architect Checklist to Balance All Three:**

1. **Right-size primary:** Buy Provisioned Throughput in primary for your baseline TPS. Use on-demand + cross-region only for burst. This reduces failover frequency to <5% - best for latency and cost.
2. **Cache first, call second:** Always implement semantic cache + Bedrock prompt caching before you worry about region selection. It saves both latency and cost instantly.[Redis]
3. **Choose secondary by latency, not just availability:** For `ap-south-1`, `ap-southeast-1` > `ap-northeast-1`. Document the extra p95 you will accept during failover.
4. **Don't use Global Accelerator or CloudFront to "fix" Bedrock latency.** It doesn't. Global Accelerator helps your app layer if you are Active-Active. For model layer, your optimization is prompt caching and staying in-region.

In short: Use cross-region profiles for availability - it's free resilience. Use caching and capacity planning to keep latency and cost from creeping up.

---
---

### Implementation Best Practices for Cross-Region Inference

We will use the same prod example: **BharatFin** - Loan Copilot running in `ap-south-1` primary with failover to `ap-southeast-1`, SLO 99.95%, p95 < 2 sec.

#### 1. Testing Strategy - Don't Assume Failover Works, Prove It

**In simple terms:** Bedrock will failover automatically on throttling and 5xx, but you have never seen it happen until you force it to happen. Test it like you test AZ failure for RDS.

**What we do for BharatFin - 3 levels of testing:**

**Level 1: Planned Failover Test**
We intentionally exhaust the quota in primary to force routing.
How: We have a test script that fires 500 TPS to `ap-south-1` for 2 minutes using a low quota IAM role. We verify all requests still succeed but `invokedRegion` in logs changes to `ap-southeast-1`. We measure latency impact - from 1.1s to 1.4s - and confirm it's within SLO.[Monthly]

**Level 2: Chaos Engineering with AWS FIS [Quarterly GameDay]**
We use AWS Fault Injection Simulator to inject throttling on the Bedrock data plane.
FIS Experiment: `aws:fis:inject-api-throttle` on `bedrock-runtime:Converse` in `ap-south-1` with 100% throttling for 10 minutes.
Expected behavior: App stays green, no customer impact. CloudWatch alarm `CrossRegionFailover-High` fires, on-call gets notified that failover is active, but no page for outage.

**Level 3: Model Capability Test**
Failover to another Region can mean a slightly different model version. We run 50 golden prompts - loan risk assessments with known good outputs - through primary and secondary. We use Bedrock Model Evaluation to compare for drift. If JSON schema breaks, we fix the prompt before prod does.

**Prod Test Checklist:**
* [ ] Can you prove 100% of requests succeed when primary is at 0 TPS quota?
* [ ] Do you know your p95 latency during failover? Is it documented in your SLO?
* [ ] Does your app handle streaming `ConverseStream` correctly during a mid-stream failover retry?

#### 2. Monitoring Setup - Make Failover Visible

**In simple terms:** Failover is silent by default. If you don't monitor it, you will be paying for secondary Region for weeks without knowing primary is under-provisioned.

**What BharatFin monitors - 3 dashboards in one:**

**Dashboard 1: Routing Observability - Where did it run?**
Enable Bedrock Model Invocation Logging to S3. Each log line has `inferenceProfileId` and `invokedRegion`.

CloudWatch Logs Insights query we use in prod:
```
fields @timestamp, modelId, invokedRegion, latency
| filter inferenceProfileId like /apac.anthropic/
| stats count(*) as requests, avg(latency) as avg_lat, pct(latency, 95) as p95 by invokedRegion
```

Visual: Pie chart - 92% ap-south-1, 8% ap-southeast-1. If that 8% becomes 40%, something is wrong.

**Dashboard 2: Performance & Errors**
Metrics: ` AWS/Bedrock -> Invocations, InvocationLatency, InvocationThrottles, InvocationClientErrors` filtered by `InferenceProfileId`.

Alarms:
* `Critical`: `Throttles > 5%` in primary for 5 mins -> Auto-scale Provisioned Throughput or increase quota.
* `Warning`: `p95 Latency > 2 sec` for 10 mins -> Check if traffic is failing over to far Region like Tokyo instead of Singapore.

**Dashboard 3: Cost & Usage**
In Cost Explorer, group by Region and filter Service = Bedrock. BharatFin had a surprise $2k spike in Singapore last month - because their primary quota was still at 100 TPS while traffic grew to 300 TPS. Failover was happening daily.

Alarm: CloudWatch Anomaly Detection on daily Bedrock cost per Region.

#### 3. Documentation - What the 2 AM On-Call Needs

**In simple terms:** If your runbook just says "Bedrock cross-region is enabled", your on-call will have no idea what to do when latency spikes.

**BharatFin's Runbook - 1 Page we maintain in Confluence:**

**a) Region Preferences Documented:**
> Primary: `ap-south-1` - for DPDP compliance, lowest latency for Indian users.
> Secondary: `ap-southeast-1` - 80ms RTT, legally approved for DR only. Tertiary: `ap-northeast-1` - last resort.
> Profile Used: `apac.anthropic.claude-3-5-sonnet-20241022-v2:0` [Version-pinned]
> Data Classification: PII allowed to failover to Singapore for max 24 hours, after that need manual approval.[Mumbai][Singapore][Tokyo]

**b) Failover Procedures:**
> Scenario 1: Alarm `CrossRegionFailover-High` fires but app is green -> Action: Check Service Quotas in `ap-south-1`. If throttling, request quota increase. No customer notification needed. This is expected behavior.
> Scenario 2: Alarm `LatencyHighDuringFailover` fires -> Action: Check if Singapore is also throttled and traffic went to Tokyo. If yes, temporarily shift 20% traffic to smaller model `apac.anthropic.claude-3-haiku` using weighted router to reduce load.

**c) Performance Baselines Documented:**
> Normal: p95 1.1 sec from Mumbai, 0% failover
> Failover to Singapore: p95 1.4 sec, acceptable
> Failover to Tokyo: p95 1.9 sec, borderline - page architect if sustained

**d) Architecture Diagram + IaC:**
Link to CDK code where profile ID is defined, so on-call knows where to change it if they need to pin to `ap-south-1` only for compliance emergency.

**Final Architect Advice:**

Day 0 - Before launch: Enable logs, create 2 alarms, write 1-page runbook.
Day 1 - After launch: Run your first planned failover test. Document the latency numbers.
Day 2 - Ongoing: Monthly check of quotas and quarterly GameDay with FIS.

If you do these three, cross-region inference goes from a checkbox feature to a real production safety net.

---
---
