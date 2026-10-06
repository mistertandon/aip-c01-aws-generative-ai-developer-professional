https://www.meta.ai/prompt/ab47664a-3e1f-49b3-aa51-51c163199432

### Circuit Breaker for GenAI

Think of a Circuit Breaker as an electrical breaker for your AI calls. Instead of continuously hammering a failing service, it detects failure, trips, and routes traffic to a safe fallback until the service recovers.

In Generative AI, failures are common: `ThrottlingException` from Amazon Bedrock, model latency > 5s, embedding store timeout, or content filter blocks. Without a breaker, one slow model can bring down your entire app.

#### The 3 States

- **CLOSED - Normal:** All requests go to the LLM. Failure count is tracked.
- **OPEN - Tripped:** After threshold breach, calls are blocked immediately. Fallback is served.
- **HALF-OPEN - Probing:** After a cool-down, it allows 1-2 test requests to check if the LLM has recovered.

### Benefits for GenAI Applications

#### 1. Failure Isolation: Stop one failure from causing a cascade

- **What it means:** Prevents a failing downstream AI component from taking down upstream services like API Gateway, Lambda concurrency, or UI threads.
- **Why it matters for GenAI:** LLM inference is much slower and more failure-prone than normal microservices.
- **Example:** Your RAG chatbot calls Bedrock, OpenSearch Serverless, and a translation API. If Bedrock Claude is throttling, the breaker isolates Bedrock calls only. Your OpenSearch retrieval and user session management continue to work.

#### 2. Resource Protection: Stop paying for requests that will fail

- **What it means:** Avoids wasting expensive resources - GPU time, Lambda execution time, and token costs - on doomed calls.
- **Why it matters for GenAI:** Every LLM call costs tokens and 3-10 seconds of Lambda time. Retrying in a loop is expensive.
- **Example:** If Bedrock returns 5 consecutive `ModelTimeoutException`, the breaker opens. Instead of invoking the model for the next 1,000 users and burning cost and Lambda concurrency, you immediately return a cached response from ElastiCache Serverless.

#### 3. Automatic Recovery: Self-heal without manual intervention

- **What it means:** The system automatically tests recovery and resumes normal operation.
- **Why it matters for GenAI:** Bedrock throttling is often transient. You do not want an engineer to manually flip a switch.
- **Example:** Breaker is `OPEN` for 60 seconds. After that, it enters `HALF-OPEN` and allows 1 test request. If that request succeeds with latency < 2s, it transitions back to `CLOSED`. This is fully automated using DynamoDB TTL or ElastiCache to store breaker state across Lambda invocations.

#### 4. Graceful Degradation: Maintain partial functionality

- **What it means:** Your app continues to deliver value, even if at reduced quality, instead of showing a hard 500 error.
- **Why it matters for GenAI:** A degraded answer is better than no answer for user experience.
- **Example:** When breaker is `OPEN`, you fallback to:
  - a) **Semantic cache** - return similar previous answer from ElastiCache
  - b) **Smaller/faster model** - fallback from Anthropic Claude 3.5 Sonnet to Amazon Titan Text Lite on Bedrock
  - c) **Static response** - "I'm experiencing high demand, here's a summary from our knowledge base without AI generation."

### Technical Example - End to End on AWS

**Use Case:** Customer Support Assistant built with API Gateway -> Lambda -> Bedrock + Bedrock Knowledge Base.

**Scenario Without Breaker:** Bedrock starts throttling at peak. Each Lambda retries 3 times. 500 concurrent users = 1500 failing Bedrock calls. Lambda throttles, API Gateway 504s, entire support portal goes down, CloudWatch costs spike.

**Scenario With Breaker on AWS:**

**Architecture:** 
`API Gateway -> Lambda (with pybreaker + Lambda Powertools) -> Breaker State in DynamoDB -> Primary: Bedrock Claude -> Fallback: ElastiCache Semantic Cache / Bedrock Titan Lite`

**Implementation Pattern:**

```python
import pybreaker
import boto3
from aws_lambda_powertools import Tracer

# Shared state across Lambdas - use DynamoDB or Redis
breaker = pybreaker.CircuitBreaker(
    fail_max=5,              # Trip after 5 failures
    reset_timeout=60,        # Try Half-Open after 60s
    listeners=[]
)

bedrock = boto3.client('bedrock-runtime')

@breaker
def invoke_primary_llm(prompt):
    return bedrock.invoke_model(
        modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
        body=prompt
    )

def lambda_handler(event, context):
    try:
        response = invoke_primary_llm(event['prompt'])
        return {"answer": response, "source": "primary-llm"}
    
    except pybreaker.CircuitBreakerError:
        # OPEN state - Graceful Degradation
        # Fallback 1: Check semantic cache
        # Fallback 2: Invoke smaller model
        return {
            "answer": get_from_cache_or_titan_lite(event['prompt']),
            "source": "fallback-cache",
            "note": "Primary model is recovering, serving degraded response"
        }
```

**Observability:** Emit custom metrics to Amazon CloudWatch: `CircuitBreakerState`, `FallbackInvocations`, `BedrockThrottles`. Create a CloudWatch Alarm when state is `OPEN` > 5 minutes. Trace with AWS X-Ray to see time saved.

**Best Practice from AWS Well-Architected:** Combine circuit breaker with Timeout + Retry with exponential backoff + jitter. Breaker is the outer protection. Retries happen inside `CLOSED` state only.

---
---

### Step Functions for Circuit Breaker Implementation:

AWS Step Functions is the most robust way to implement circuit breaker for GenAI on AWS. Instead of writing breaker logic inside your Lambda code, you build a durable, visual state machine that controls the flow, tracks health, and decides whether to call the LLM or serve a fallback.

This prevents a failing AI provider like Amazon Bedrock from causing cascading failures across your entire architecture.

Here are the 4 pillars of this implementation, simplified:

#### 1. State Machine Design - The Foundation

**What it means:** Step Functions provides native states to model the circuit breaker lifecycle. You don't just call Bedrock, you orchestrate the call.

**Refined Implementation:** Design your state machine with explicit states:

*   **CheckCircuitState [Task State]:** Reads current breaker status from DynamoDB.
*   **ClosedState [Choice + Task State]:** Normal path. Calls Amazon Bedrock via Lambda / Bedrock SDK integration.
*   **OpenState [Choice + Pass State]:** Circuit is tripped. Skips the LLM call and routes directly to fallback.
*   **HalfOpenState [Task + Wait State]:** Probing path. Allows one test request to check if the LLM has recovered.

**Best Practice:** Keep your business logic (prompt building) separate from your resiliency logic (breaker states). Use a `Choice` state after every Bedrock call to evaluate the result and update the circuit.

#### 2. Error Detection and Thresholds - When to Trip

**What it means:** Don't trip on a single failure. Define intelligent thresholds based on real GenAI failure types.

**Refined Implementation:** Your error detection Lambda should classify errors:

*   **Retriable:** `ThrottlingException`, `ModelTimeoutException`, `ServiceUnavailable` (HTTP 429, 500, 504)
*   **Non-Retriable:** `ValidationException`, `AccessDeniedException` (should not trip the breaker)

Track these in a sliding window, for example: 5 failures in last 2 minutes OR 50% failure rate in last 20 calls.

**Best Practice:** Implement a sliding window in DynamoDB, not just a simple counter. This avoids false positives from a single bad request. Use Step Functions `Retry` with exponential backoff for transient errors before you count it as a breaker failure.

> **Technical Example:** For a RAG chatbot, your state machine calls `Bedrock InvokeModel`. If it fails 5 times consecutively within 60 seconds, you write to DynamoDB: `circuit_status = OPEN`, `opened_at = timestamp`, `failure_count = 5`. The next execution will see OPEN and will not call Bedrock.

#### 3. Timeout and Recovery Logic - How to Heal Safely

**What it means:** How long you stay OPEN and how you test recovery is critical. If you test too aggressively, you will overwhelm a recovering LLM.

**Refined Implementation:** Use `Wait` state and exponential backoff.

*   First trip: Stay OPEN for 60 seconds
*   Second consecutive trip: Stay OPEN for 120 seconds
*   Third trip: Stay OPEN for 240 seconds

In HALF-OPEN, Step Functions sends only ONE probe request via a `Task` state. If it succeeds with latency < 2s, transition to CLOSED. If it fails, go back to OPEN.

**Best Practice:** Use exponential backoff for timeouts for repeatedly failing services, but use a faster recovery for intermittent 429 throttling. Step Functions makes this easy with `Wait` state using `SecondsPath` from your DynamoDB record.

#### 4. State Persistence - Making the Breaker Distributed

**What it means:** Lambda is stateless. Step Functions executions are independent. You need a central store for breaker state so all invocations know the circuit is OPEN.

**Refined Implementation:** Use Amazon DynamoDB as your single source of truth.

**Table: `genai-circuit-breaker-state`**
*   `PK: service_name` (e.g., `bedrock-claude-sonnet`)
*   `circuit_state: CLOSED | OPEN | HALF_OPEN`
*   `failure_count, success_count, last_failure_time, opened_at, timeout_seconds`
*   `TTL` enabled to auto-reset stuck OPEN circuits.

Every Step Functions execution starts with a `DynamoDB GetItem` Task, and ends with a `DynamoDB PutItem` Task to update the state.

**Best Practice:** Use DynamoDB conditional writes for atomic updates and enable Point-in-Time Recovery. Emit metrics to Amazon CloudWatch: `CircuitOpenCount`, `FallbackInvocationCount` for dashboards and alarms.

**End-to-End Flow Example:**

`API Gateway -> Step Functions (CheckCircuit from DynamoDB) -> Choice: If OPEN -> Pass to Fallback (Return cached answer from ElastiCache Serverless or call Titan Lite) | If CLOSED -> Call Bedrock -> On Success -> Update DynamoDB (reset failure_count) -> On Throttling Failure -> Update DynamoDB (increment failure_count, set OPEN if threshold breached) -> Return fallback.`

This pattern is far more resilient than in-code `pybreaker` because it is visual, durable, survives Lambda timeouts, and provides full audit trail in Step Functions execution history.

---
---

### Step Function Configuration for AI Circuit Breaker

In GenAI, your model call to Amazon Bedrock is your most fragile dependency. It can throttle, time out, or degrade in quality. A systematic Step Functions configuration gives you a durable, serverless circuit breaker that protects your entire workflow.

Think of Step Functions as the control plane for your AI resilience.

#### 1. Define Service Health Checks

**What it means in simple terms:** Before you send a costly, full-prompt request to the LLM, quickly check if the service is actually healthy.

**Technical Implementation:**
Create a dedicated `Task` state called `HealthCheck`. This should be a lightweight probe, not a full generation.

*   **Availability Check:** Does Bedrock respond at all? Handle `ThrottlingException`, `ServiceUnavailable`.
*   **Quality Check:** Is it responding slowly? If p95 latency > 3 seconds, treat it as degraded.

**Example:** A Lambda function that does a cheap health check:
```python
# health_check_lambda
bedrock.invoke_model(
  modelId='anthropic.claude-3-haiku-20240307-v1:0',
  body='{"max_tokens": 1, "messages": [{"role":"user","content":"ping"}]}'
)
```
This costs < 10 tokens but tells you if the model endpoint is alive. Store result in DynamoDB.

**Best Practice:** Use Amazon Bedrock `Converse` API with `max_tokens: 1` and a 2-second timeout. This validates both connectivity and performance without burning tokens.

#### 2. Implement Error Tracking

**What it means:** You need memory. Lambda is stateless, so you must track failures centrally to decide when to trip.

**Technical Implementation:**
Design two states:

*   `RecordFailure [Task - DynamoDB PutItem]`: After every failed Bedrock call, update a central table.
*   `RecordSuccess [Task - DynamoDB PutItem]`: On success, reset counters.

**DynamoDB Table `ai-circuit-state` design:**
`PK: bedrock-claude-sonnet`
`Attributes: failure_count, success_count, total_requests, last_5_minute_window, last_failure_type, avg_latency`

Use Step Functions built-in `Catch` and `Retry` to categorize failures:
*   `Catch: States.ALL` with `ResultPath: $.error` -> Go to `CategorizeError` Choice state
*   If error is `ThrottlingException` -> Count as retriable failure
*   If error is `ValidationException` -> Do NOT count, it's a client bug

**Best Practice:** Don't just count absolute failures. Track sliding window. Store a list of last 20 request outcomes in DynamoDB as a JSON array for trend analysis.

#### 3. Configure Threshold Logic

**What it means:** This is the brain that decides when to OPEN the circuit. It must be smart enough to avoid tripping during low traffic.

**Technical Implementation:**
Use a `Choice` state called `EvaluateThreshold`.

Logic inside a Lambda or with JSONata in Step Functions:

```
IF failure_count >= 5 in 2 minutes 
   OR failure_rate > 50% AND total_requests > 10
THEN -> Go to OpenCircuit
ELSE -> Go to ClosedState
```

This handles two scenarios: Absolute count for sudden outages, and percentage-based for degraded quality.

**Example:** 
At 3 AM you have 2 requests, both fail. Failure rate is 100% but absolute count is only 2. You should NOT trip. So your rule says `total_requests > 10` is required for percentage logic. This avoids premature circuit activation during low-traffic periods.

**Best Practice:** Implement dual thresholds in your `Choice` state. Always check request volume before evaluating percentage.

#### 4. Set Up State Transitions

**What it means:** Define how you move between CLOSED -> OPEN -> HALF-OPEN -> CLOSED with proper delays and validation.

**Technical Implementation in ASL:**

*   **CLOSED to OPEN:** `Choice` state detects threshold breach -> `Task: UpdateDynamoDB to OPEN, set opened_at = timestamp, timeout = 60s` -> `Pass: ServeFallback`
*   **OPEN to HALF-OPEN:** Next execution starts with `Task: GetCircuitState`. If `state == OPEN AND current_time - opened_at > timeout`, then go to `Wait: 1 second` + `Task: ProbeBedrock` (one test call). This is HALF-OPEN.
*   **HALF-OPEN to CLOSED / OPEN:** `Choice` state: If probe succeeds -> `Task: Set state to CLOSED, reset counters`. If probe fails -> `Task: Set state to OPEN, double timeout with exponential backoff: 60s -> 120s -> 240s`.

**End-to-End Technical Example:**

User asks a question to your Support Bot.

**Flow 1 - Healthy:** Step Functions -> `GetState (CLOSED)` -> `Invoke Bedrock Claude` -> Success -> `Reset Counters in DynamoDB` -> Return Answer.

**Flow 2 - Bedrock Throttling:** Step Functions -> `GetState (CLOSED)` -> `Invoke Bedrock` fails 5 times. On 5th failure -> `UpdateState to OPEN` -> Return Fallback answer from ElastiCache semantic cache + emit CloudWatch Metric `CircuitBreakerOpen=1`.

**Flow 3 - Recovery:** 60 seconds later, new user request -> `GetState (OPEN but timeout expired)` -> Enters HALF-OPEN -> Sends 1 probe request to Bedrock. If 200 OK and latency < 1.5s -> `UpdateState to CLOSED` -> Normal operation resumes.

This gives you a fully resilient, observable, and self-healing GenAI workflow without any custom daemon or sidecar to manage.

---
---

### Implementing Fallback Paths

A circuit breaker without a fallback is just a failure detector. True resilience means when you OPEN the circuit for your primary LLM, you have a well-defined alternate path that keeps the business running.

I design fallback in 3 tiers for all production GenAI workloads.

#### 1. Alternate Model Routing - Same Capability, Different Model

**What it means in simple terms:** If your premium model fails, automatically route to a cheaper, faster model that can still do the job.

**Technical Implementation:**
Don't hardcode fallbacks. Configure a model mapping table in DynamoDB or AppConfig.

This mapping considers capability, context window, and cost.

**Model Mapping Example Table `genai-fallback-map`:**
*   `Primary: anthropic.claude-3-5-sonnet-20240620-v1:0` -> `Fallback Tier 1: anthropic.claude-3-haiku-20240307-v1:0` -> `Fallback Tier 2: amazon.titan-text-lite-v1`

**Refined Best Practice:**
In your Step Functions `OpenState`, add a `Task` state `RouteToFallbackModel`. Before routing, implement a quality check. For example, if the original task was complex reasoning, Haiku may not be suitable, so you should skip to degraded functionality. If it was summarization, Haiku is perfectly acceptable.

**Technical Example:**
Your customer support bot uses Claude Sonnet for complex troubleshooting. Bedrock returns `ThrottlingException`. The circuit opens. The state machine reads the mapping and invokes Haiku with the same prompt. You add a system prompt: `You are a fallback model. Provide a concise answer. If unsure, say you will escalate.` 
This maintains continuity with 10x lower latency and cost.

You can implement this with a `Choice` state in Step Functions:
`If $.error = ThrottlingException AND $.task_type = SUMMARIZATION -> Invoke Haiku`
`If $.error = ThrottlingException AND $.task_type = COMPLEX_REASONING -> Go to Degraded Functionality`

#### 2. Degraded Functionality - Reduced Capability, Core Business Intact

**What it means:** When even fallback models are failing, don't return a 500 error. Return a reduced but useful response.

**Technical Implementation:**
Build 3 types of degraded paths:

**a) Semantic Cache:** Use Amazon ElastiCache Serverless or OpenSearch Serverless k-NN. Before calling Bedrock, check if a semantically similar question was answered in last 24 hours. If circuit is OPEN, serve directly from cache. Hit rate for support bots is typically 30-40%.

**b) Rule-Based / Retrieval-Only:** Skip the LLM entirely. Return raw results from Bedrock Knowledge Bases. For example: "AI generation is temporarily under high load. Here are the top 3 relevant documents from our knowledge base."

**c) Static Response with Transparency:** Maintain trust by communicating status.

**Technical Example:**
State machine enters `DegradedState`:
```json
{
  "answer": "We found relevant information in our docs: [Doc 1, Doc 2]",
  "mode": "degraded-retrieval-only",
  "user_message": "AI summarization is temporarily unavailable, showing search results only."
}
```
In the frontend, you show a yellow banner. The user still gets value, and you avoid a complete outage. Log this event to CloudWatch with metric `DegradedFallbackCount`.

**Best Practice:** Always tell the user you are in degraded mode. Never silently serve a low-quality answer as if it came from your premium model.

#### 3. Cross-Region Failover - Protection Against Regional Outage

**What it means:** What if Bedrock in `us-east-1` is down completely? Your fallback models in the same Region will also fail. You need geographic redundancy.

**Technical Implementation:**
Use **Amazon Bedrock Cross-Region Inference**. Instead of calling a model directly, you call an Inference Profile.

An inference profile like `us.anthropic.claude-3-5-sonnet-20240620-v1:0` automatically routes your request to a healthy Region among `us-east-1`, `us-west-2`, etc., managed by AWS.

For more control, implement custom logic in Step Functions:

**Step 1:** Try `us-east-1` Bedrock
**Step 2:** On `ServiceUnavailable`, `Task: Update Region to us-west-2` and retry with a `Wait` state of 2 seconds.
**Step 3:** Store region health in DynamoDB to avoid repeated calls to a bad Region.

**Technical Example:**
Your primary Region is Mumbai `ap-south-1`. You have enabled cross-region inference profile `apac.anthropic.claude-3-5-sonnet-20240620-v1:0` which can failover to `ap-northeast-1` Tokyo.

Step Functions logic:
```
Invoke in ap-south-1 -> Fails with 500 -> Choice: If error is regional -> Lambda: Invoke Bedrock client in ap-northeast-1 with same prompt -> Success -> Update DynamoDB: ap-south-1 health = degraded -> Return answer with metadata: failover_region: ap-northeast-1
```

**Best Practice for Region Selection:** Don't just failover blindly. Your selection logic in Lambda should consider:
*   **Latency:** Failover to the nearest Region for your users.
*   **Model Availability:** Not all models are available in all Regions. Check via Bedrock `ListFoundationModels`.
*   **Cost:** Cross-region inference has slightly higher cost. Use it as Tier 3 fallback, not Tier 1.

**Final Architect View:** Your resilience ladder should be:
**CLOSED:** Primary Model in Primary Region -> **OPEN Tier 1:** Fallback Model in Same Region -> **OPEN Tier 2:** Semantic Cache / Retrieval-Only -> **OPEN Tier 3:** Cross-Region Inference Profile.

This ensures 99.9% availability for your GenAI application even when a foundation model provider is degraded.

---
---

### Monitoring and Optimizing Circuit Breaker Performance

In production, a circuit breaker you cannot see is as risky as no circuit breaker. Comprehensive monitoring is what lets you tune thresholds and prove that your fallback actually works. We do this natively with Amazon CloudWatch.

#### Why Monitor?

Your thresholds on Day 1 will be wrong. You might trip too early during low traffic, or too late when Bedrock is already throttling. Monitoring gives you the data to optimize `fail_max`, `reset_timeout`, and your fallback strategy.

We track 4 golden metrics for every GenAI circuit breaker.

#### The 4 Key Metrics to Monitor

**1. Circuit State Transitions - When and how often does it trip?**
*What it means:* Count every CLOSED -> OPEN, OPEN -> HALF-OPEN, HALF-OPEN -> CLOSED transition.
*Why it matters:* If your circuit opens 20 times a day, your threshold is too sensitive or your primary model is unstable. If it never opens but users see timeouts, your threshold is too lenient.

*Implementation:* In your Step Functions or Lambda, emit a custom metric via CloudWatch Embedded Metric Format [EMF]:
`PutMetric: CircuitState=OPEN, Service=bedrock-claude-sonnet, Count=1`
Create a CloudWatch dashboard widget showing state over time. Set an Alarm: `IF CircuitState=OPEN for >10 mins -> Notify on-call via SNS`.

**2. Error Rates and Types - Why did it trip?**
*What it means:* Not all failures are equal. Track retriable vs non-retriable errors separately.
*Why it matters:* `ThrottlingException [429]` should trip the breaker. `ValidationException [400]` should NOT. If you mix them, you will trip on a bad prompt.

*Implementation:* In your `Catch` state, categorize:
`ErrorType=Throttling, ErrorType=ModelTimeout, ErrorType=ServiceUnavailable`
Use CloudWatch Logs Insights to query: 
`filter @message like /CircuitBreaker/ | stats count() by ErrorType`

**3. Response Times - Detect degradation BEFORE failure**
*What it means:* Don't wait for a 504 timeout. If p95 latency goes from 1.2s to 4s, your user experience is already degraded.
*Why it matters:* GenAI quality degrades before it fails. Slow responses should trigger early fallback.

*Implementation:* Emit `BedrockLatency` as a histogram metric from Lambda. Set two thresholds:
*   Hard threshold: `latency > 5000ms = failure`
*   Soft threshold: `p95 latency > 2500ms for 5 mins = Alarm, start using fallback model Haiku`

Use AWS X-Ray to trace end-to-end latency: API Gateway -> Step Functions -> Bedrock.

**4. Fallback Usage and Effectiveness - Is your fallback actually helping?**
*What it means:* Measure how often you used the fallback and whether the user was satisfied.
*Why it matters:* A fallback that no one uses or that has 90% user thumbs-down is not resilience, it is a different failure.

*Implementation:* Emit two metrics:
`FallbackInvoked: FallbackTier=Cache / FallbackTier=SmallModel / FallbackTier=CrossRegion`
`FallbackSuccess: Did fallback return a valid answer? Did user give positive feedback?`

If `FallbackInvoked` is 30% of traffic, your primary model capacity is under-provisioned.

#### Prod-Level Real World Example

**Use Case: FinTech Loan Assistant at 10K requests/day**
Architecture: `API Gateway -> Step Functions -> Lambda -> Primary: Bedrock Claude 3.5 Sonnet in ap-south-1 [Mumbai] -> Fallbacks -> DynamoDB for circuit state -> CloudWatch Dashboard`

**What we observed in Week 1:**
CloudWatch dashboard showed Circuit opened 18 times. Metric breakdown:
*   Circuit State Transitions: 18 OPEN events, all between 3 PM - 5 PM IST
*   Error Rates: 95% were `ThrottlingException`, 5% `ModelTimeout`
*   Response Times: p95 went from 1.3s to 4.8s just before tripping
*   Fallback Usage: 22% of traffic went to `Fallback Tier 1: Claude Haiku`, 8% went to `Tier 2: ElastiCache Semantic Cache`

**Optimization we did based on data:**

1.  We changed threshold from `fail_max=5 in 2 mins` to `fail_max=3 in 1 min AND p95 > 3s`. This made the breaker trip 1 minute earlier, avoiding the slow 4.8s responses.
2.  We saw Haiku fallback had 92% user acceptance, but Cache fallback had only 60%. We improved cache embedding model from Titan to Cohere Embed v3, raising cache acceptance to 85%.
3.  We enabled Bedrock Cross-Region Inference Profile `ap.anthropic.claude-3-5-sonnet...` as Tier 3. After that, OPEN events dropped from 18 to 2 per week because traffic automatically spilled to `ap-northeast-1` during Mumbai throttling.

**Result:** User-facing error rate went from 4.2% to 0.15%, average latency in fallback mode went from 4.8s to 0.9s [from cache], and we saved ~35% on Bedrock costs by not retrying failing calls.

**Best Practice Checklist:**
1. Create a single CloudWatch Dashboard named `GenAI-CircuitBreaker-Health`
2. Emit all 4 metrics using EMF from Lambda - zero extra API calls
3. Set Alarms on `Circuit OPEN > 5 mins` and `Fallback Usage > 20%`
4. Review dashboard weekly to tune thresholds - this is a continuous optimization loop, not a one-time setup.

---
---

### Implementation Best Practices - Monitoring for Circuit Breaker

A circuit breaker is not a set-and-forget pattern. In production GenAI, you need monitoring that tells you *when* it opened, *why* it opened, *what was the impact to the user*, and *how to tune it next week*. These 4 best practices are what we implement for enterprise workloads.

#### 1. Configure CloudWatch Alarms for Proactive Alerting

**What it means:** Don't let your users tell you the circuit is OPEN. Let CloudWatch tell your on-call team first.

**Technical Implementation:**
Create actionable alarms, not noisy alarms.

*   **Critical Alarm - Circuit OPEN too long:**
    Metric: `CircuitState = OPEN`
    Condition: `OPEN > 10 minutes`
    Action: SNS -> PagerDuty / Slack. This means recovery logic failed.

*   **Warning Alarm - Pre-failure Degradation:**
    Metric: `BedrockErrorRate = ThrottlingException`
    Condition: `> 30% for 3 consecutive minutes`
    Action: SNS -> Auto Scaling action or email to SRE. This fires *before* the circuit opens.

*   **Quality Alarm - Slow degradation:**
    Metric: `p95 BedrockLatency`
    Condition: `> 3000ms for 5 minutes`
    Action: Trigger Lambda to pre-warm fallback cache.

**Best Practice:** Use composite alarms. `IF ErrorRate > 50% AND CircuitState = CLOSED` then alarm. This avoids alerting when circuit is already OPEN and protecting the system - that's expected behavior.

#### 2. Use Custom Metrics for Business Impact, Not Just Infra Metrics

**What it means:** Infra metrics tell you *what* failed. Business metrics tell you *if the user cared*.

**Technical Implementation:**
Emit custom business metrics using CloudWatch Embedded Metric Format [EMF] from your Lambda, at zero extra cost.

Don't just track `BedrockFailures`. Track:

*   `UserExperienceImpact`: Did user retry? Did user abandon chat?
*   `TaskCompletionRate`: In fallback mode, did user still complete the loan application / booking?
*   `FallbackQualityScore`: Thumbs up/down on fallback answers vs primary model answers.
*   `CostSaved`: How much token cost you saved by failing fast instead of retrying 3 times.

**Example Code:**
```python
# Inside your fallback path
metrics.put_metric("FallbackInvoked", 1, "Count")
metrics.put_metric("FallbackTier", "Haiku") # dimension
metrics.put_metric("TaskCompletionInFallback", 1 if user_completed else 0)
```

Now your dashboard shows not just "Circuit OPEN 5 times" but "Circuit OPEN 5 times, but 92% of users still completed their task using Haiku fallback."

#### 3. Implement Unified Dashboards for Real-Time Visibility

**What it means:** You run models in Mumbai, fallback in Singapore, cache in us-east-1. You need a single pane of glass.

**Technical Implementation:**
Build one CloudWatch Dashboard: `GenAI-CircuitBreaker-Global-Health`

Add 4 widgets:

*   **Widget 1 - State Map:** Single-value widget per service/region: `bedrock-claude-sonnet [ap-south-1] = CLOSED [Green]`, `bedrock-claude-sonnet [ap-northeast-1] = CLOSED`
*   **Widget 2 - Transitions Over Time:** Line graph of `CLOSED -> OPEN` events per hour.
*   **Widget 3 - Error Breakdown:** Pie chart of `ErrorType`: Throttling vs Timeout vs ModelError.
*   **Widget 4 - Fallback Effectiveness:** Stacked bar of `Primary vs Fallback Tier 1 vs Tier 2` traffic.

Use CloudWatch Cross-Region dashboards to pull metrics from `ap-south-1` and `us-east-1` into one view.

**Best Practice:** Add a `Service Map` using AWS X-Ray so you can click from dashboard directly into the failing Step Functions execution.

#### 4. Include Trend Analysis to Optimize Configuration Over Time

**What it means:** Your Day 1 thresholds are guesses. Week 4 thresholds should be data-driven.

**Technical Implementation:**
Use CloudWatch Logs Insights and S3 + Athena for long-term trends.

*   **Weekly Review Query in Logs Insights:**
    `filter @message like /CircuitBreaker/ | stats count() as trip_count, avg(latency) by bin(1h), model_id | sort trip_count desc`
    This shows you which model trips most and at what hour.

*   **Trend Analysis:** Export EMF metrics to S3 via Kinesis Firehose and query with Athena. Look for seasonality.

#### Prod-Level Real World Example

**Customer: Large E-commerce in India - 25K GenAI requests/day for Product Q&A**

**Architecture:** `API Gateway -> Step Functions -> Primary: Bedrock Claude Sonnet in ap-south-1 -> Fallbacks: Haiku, ElastiCache Serverless, Cross-Region to ap-southeast-1 -> State in DynamoDB -> Monitoring in CloudWatch`

**What Monitoring Showed:**

*   Dashboard showed OPEN events spiked every day at 7-9 PM IST during Big Billion Days sale.
*   Alarms: `ThrottlingException` alarm fired at 7:05 PM, but `Circuit OPEN` alarm fired at 7:12 PM - 7 minutes late. Users saw slow responses for 7 mins.
*   Custom Metric `TaskCompletionInFallback` showed Haiku fallback had 88% completion vs 94% for Sonnet, but cache fallback had only 55%.
*   Trend analysis in Logs Insights showed `p95 latency` crossed 2.5s *before* throttling started. Latency was a leading indicator.

**Optimizations We Did:**

1.  Changed alarm to trigger on `p95 latency > 2500ms` instead of waiting for error rate. Circuit now opens 5 minutes earlier, saving user experience.
2.  Changed threshold from `5 failures in 2 mins` to `3 failures in 1 min during peak hours (6-10 PM)` using EventBridge Scheduler to update AppConfig.
3.  Improved cache embeddings, raising cache task completion from 55% to 81%.

**Business Outcome:** After optimization, user-facing timeouts dropped from 3.8% to 0.2%, MTTR [Mean Time To Recovery] went from 18 mins to 2 mins auto-recovery, and the SRE team gets only 1 actionable alarm per day instead of 15 noisy ones.

---
---

### AWS Security Hub Integration for AI Resilience

For Prod GenAI workloads, resilience is not just about handling `ThrottlingException`. It is also about security. What if your Bedrock model starts getting anomalous access, or your fallback model in another Region does not meet PCI-DSS controls? 

AWS Security Hub acts as the security brain that talks to your circuit breaker.

Think of it like this: Circuit Breaker protects you from *performance failures*. Security Hub protects you from *security failures*, and it can tell your circuit breaker to trip when there is a security risk.

#### 1. Near-Real-Time Risk Analytics - Security Can Trip Your Circuit

**What it means in simple terms:** Security Hub continuously analyzes your AI stack and can automatically open your circuit if it detects a threat.

**Technical Implementation:**
Security Hub ingests findings from GuardDuty, Inspector, CloudTrail, and Config in ASFF format in near-real-time.

How it connects to circuit breaker:

*   **Anomalous Access:** GuardDuty detects `Anomalous API call - Bedrock InvokeModel from unusual IP`. Security Hub creates a Critical finding. An EventBridge rule `Security Hub Findings - Imported, Severity = CRITICAL, Resource = Bedrock` triggers a Lambda that writes to your DynamoDB circuit table: `circuit_state = OPEN, reason = SECURITY_RISK, opened_by = SecurityHub`.

*   **Real-Time Risk Scoring:** Security Hub aggregates risk score. If risk score for your GenAI workload goes above 80/100, your Step Functions `CheckCircuit` state treats it as OPEN, even if Bedrock itself is healthy.

**Best Practice:** Don't treat all security findings as circuit breaker triggers. Filter only for findings related to your AI resources: `ResourceType = AwsBedrockCustomModel, AwsBedrockFoundationModel, AwsIamRole` associated with your GenAI app.

#### 2. Improved Prioritization for AI Workloads - Focus on What Matters

**What it means:** Security Hub has hundreds of findings. Which one should wake up your SRE at 2 AM? The one affecting your PII-heavy GenAI workload.

**Technical Implementation:**
Security Hub does risk-based prioritization by correlating findings.

It considers:
*   **Data Sensitivity:** Is this Bedrock Knowledge Base connected to S3 bucket with PII? Security Hub tags it as `DataClassification: PII`.
*   **Business Criticality:** Is this loan approval assistant Tier 1? You tag it in Config: `BusinessCriticality: High`.
*   **Scope of Impact:** One IAM role compromised affecting 3 Regions vs one model.

So instead of 100 low-severity findings, SRE sees: `Critical - Compromised IAM Role used for Bedrock Inference affecting High-criticality loan assistant handling PII data`.

**Prod Example:** Security Hub correlates 3 findings: GuardDuty `CredentialExfiltration`, CloudTrail `Bedrock InvokeModel without MFA`, and Config `S3 bucket public`. Alone they are Medium. Correlated, it becomes Critical and triggers immediate circuit open + auto-remediation.

#### 3. Security-Aware Fallback Strategies - Don't Failover to an Insecure Region

**What it means:** Your fallback must be as secure as your primary. You cannot failover from a compliant Region to a non-compliant one.

**Technical Implementation:**
Integrate Security Hub compliance checks into your fallback logic.

Before routing to a fallback model/Region, your Lambda does:

1.  **Check Security Posture:** Call Security Hub `BatchGetSecurityControls` - Is fallback Region passing your custom standard `AI-Security-Standard`? Does it have GuardDuty enabled, KMS encryption, VPC endpoints?
2.  **Verify Authentication:** During failover, ensure IAM role assumption still enforces MFA and that Bedrock VPC endpoint policy is intact.
3.  **Maintain Logging:** Ensure CloudTrail, CloudWatch Logs, and Bedrock model invocation logging remain enabled in fallback path for audit. If fallback Region has logging disabled, Security Hub marks it non-compliant, and you should skip it.

**Example:** Primary is `ap-south-1` with PCI-DSS enabled. Your circuit breaker wants to failover to `us-east-1`. But Security Hub shows `us-east-1` Bedrock is not using CMK KMS key as required by your standard. Your fallback logic then skips `us-east-1` and goes to `ap-northeast-1` which IS compliant, or serves from ElastiCache cache instead.

#### 4. Implementation Considerations - How to Wire It

**Step 1: Enable Foundational Logging**
Enable CloudTrail for all Bedrock data events: `managementEvents + dataEvents for bedrock.amazonaws.com`. Enable GuardDuty, Config, and send all to Security Hub in your central security account.

**Step 2: Create Custom AI Security Standard**
In Security Hub, create a custom standard `GenAI-Resilience-Standard` with controls like:
*   `Bedrock models must use KMS CMK`
*   `Bedrock Knowledge Base S3 must not be public`
*   `IAM Roles for Bedrock must require MFA`

**Step 3: Automated Response with Circuit Breaker**
`Security Hub Finding [CRITICAL] -> EventBridge Rule -> Lambda: OpenCircuitBreaker -> Updates DynamoDB: state=OPEN, reason=SecurityFindingId -> SNS -> SRE Team`

Your Step Functions state machine's first state `CheckCircuit` now checks both performance state AND security state from DynamoDB.

**Step 4: Unified Dashboard**
Build a CloudWatch Dashboard that overlays two metrics:
*   Line 1: `Circuit Breaker State Transitions`
*   Line 2: `Security Hub Critical Findings Count for GenAI Workload`
This correlation shows you if a performance failure was actually caused by a security event.

#### Prod-Level Real World Example - FinTech in India

**Customer:** A bank running a GenAI Loan Underwriting Assistant on Bedrock Claude, processing PII, PCI data. Primary Region `ap-south-1`.

**Incident:** At 2:30 PM, GuardDuty detected an IAM role `Bedrock-Inference-Role` being used from an unusual Tor IP to call `InvokeModel`. GuardDuty -> Security Hub -> Finding `UnauthorizedAccess: IAMUser/AnomalousBehavior`, Severity Critical, Risk Score 85.

**Automated Flow:**
1. EventBridge triggered Lambda `SecurityAwareCircuitBreaker`.
2. Lambda immediately set DynamoDB `circuit_state=OPEN, reason=SECURITY_GUARD_DUTY_AnomalousAccess`.
3. Step Functions for all new loan requests started serving fallback: `Retrieval-only from Knowledge Base, no LLM generation` to avoid data exfiltration via LLM.
4. Simultaneously, Lambda revoked temporary credentials for that IAM role via IAM.
5. Security Hub dashboard showed circuit OPEN correlated with security finding. SRE investigated, confirmed compromise, rotated keys.
6. After Security Hub finding was resolved and risk score dropped to 10, a manual approval via Slack + EventBridge set circuit back to HALF-OPEN for testing.

**Outcome:** Instead of just retrying a compromised endpoint, the system automatically contained a potential data exfiltration. The fallback maintained audit logging and compliance, and the bank could prove to auditors that failover did not bypass security controls.

---
---
