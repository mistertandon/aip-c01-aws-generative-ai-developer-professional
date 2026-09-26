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
