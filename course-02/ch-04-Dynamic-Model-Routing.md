### Amazon Bedrock Intelligent Prompt Routing

Amazon Bedrock Intelligent Prompt Routing is a fully managed capability that automatically routes each prompt to the most optimal foundation model in your prompt router. Instead of you hard-coding which model to use, a specialized router model analyzes your request in real-time based on complexity, content type, and quality/latency requirements.

You get the right balance of **quality, latency, and cost** without writing custom routing logic.

> **How it works:** Application -> **Bedrock Prompt Router ARN** -> Router Model evaluates prompt -> Routes to best-fit FM [Claude, Titan, Llama, etc.] -> Unified response back to application.

To understand how it optimizes your AI workloads, explore the 3 core concepts below.

---

#### 1. Decision Factors: How the Router Chooses a Model

The router doesn't guess. It uses a multi-dimensional evaluation at inference time:

* **Input Characteristics:** Prompt length, token count, reasoning complexity, and content type - e.g., code, summarization, open Q&A, RAG.
* **Performance Metrics:** Your defined SLOs for latency, accuracy, and throughput.
* **Business Constraints:** Cost budget per request, quality threshold, and routing policies you configure.

**Technical Example:**

Imagine an e-commerce support bot using one Prompt Router containing `Claude 3 Haiku` and `Claude 3.5 Sonnet`.

**Prompt A:** `Summarize this in one line: "Product arrived late but quality is good."`
> Router Analysis: Length= 10 tokens, Complexity= Low, Task= Simple Summarization.
> **Routing Decision:** `Claude 3 Haiku` - Low latency ~300ms, cost $0.00025 per 1K tokens. Perfect for this.

**Prompt B:** `Analyze these 20 customer complaints and identify root cause trends, sentiment shift, and propose 3 operational improvements.`
> Router Analysis: Length= 1500+ tokens, Complexity= High, Task= Complex Reasoning & Analysis.
> **Routing Decision:** `Claude 3.5 Sonnet` - Higher reasoning capability needed, even if cost is 10x higher.

You define this once in the router configuration, not in application code.

#### 2. Model Specialization: The Right Tool for the Right Job

Intelligent Prompt Routing leverages the inherent strengths of each Foundation Model. It creates a tiered model portfolio.

| Model Family | Strength & Ideal Use Case | Routing Trigger |
| :--- | :--- | :--- |
| **Anthropic Claude 3.5 Sonnet / Opus** | Complex reasoning, nuanced analysis, long-form content generation, agentic workflows | High complexity, multi-step logic |
| **Anthropic Claude 3 Haiku** | Fast, balanced intelligence for general chat, summarization | Medium complexity, latency-sensitive |
| **Amazon Titan Text Lite / Express** | Highly cost-effective, low-latency for classification, simple extraction, FAQ | Low complexity, high-throughput, cost-sensitive |

The service has a continuous learning loop. It uses CloudWatch metrics and feedback data like latency, error rate, and response quality to refine future routing decisions automatically.

**Technical Example - Cost Optimization:**
Without routing, if you send 100,000 requests/day all to Claude Sonnet at $3.00 / 1M input tokens, your cost is high.

With Intelligent Prompt Routing configured as `70% Haiku / 30% Sonnet` based on actual complexity distribution:
- 70,000 simple queries go to Haiku at $0.25 / 1M tokens
- 30,000 complex queries go to Sonnet

**Result: Up to 60-70% cost reduction with no drop in perceived quality**, because simple queries don't need a large model.

#### 3. Integration: One API, Zero Model-Switching Code

You don't need to manage multiple `InvokeModel` clients. You interact with a single **Prompt Router ARN** using the standard Bedrock Converse or Invoke API. The response schema remains consistent regardless of which underlying FM was used.

This is a minimal-code change. Just replace your `modelId` with your `promptRouterArn`.

**Technical Example - Python with Boto3:**

```python
import boto3

bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')

# Your Prompt Router ARN - created in Bedrock Console
# It contains your model pool: e.g., [Claude 3 Haiku, Claude 3.5 Sonnet]
PROMPT_ROUTER_ARN = "arn:aws:bedrock:us-east-1:123456789012:prompt-router/my-ecommerce-router"

response = bedrock_runtime.converse(
    modelId=PROMPT_ROUTER_ARN,
    messages=[
        {
            "role": "user",
            "content": [{"text": "Classify this ticket: My order #123 is stuck, urgent!"}]
        }
    ]
)

# Response format is identical whether Haiku or Sonnet was used
print(response['output']['message']['content'][0]['text'])
print(f"Actually routed to: {response['trace']['promptRouter']['invokedModelId']}")
```

**Key Benefits for Developers:**

1. **Simplified Operations:** No if-else logic to choose models. Observability is built-in via CloudWatch metrics for `InvokedModelId`.
2. **Consistent Schema:** You parse one response format.
3. **Fallback Handling:** If one model is throttled, the router can automatically failover to another model in the pool.

---
---

### Dynamic Routing with Nova Models

The Amazon Nova family is purpose-built for dynamic routing. Unlike using a single large model for everything, Nova offers distinct tiers with different trade-offs in intelligence, latency, and cost. This lets you build a routing layer that automatically sends each request to the most efficient Nova model.

Think of it as: **One router, multiple Nova specialists.**

> **Architecture:** User Request -> **Custom Router [AWS Lambda / Bedrock Prompt Router]** -> Complexity Scoring -> Nova Model Selection -> Unified Response

#### 1. Complexity-Based Routing: The Core Strategy

Instead of hard-coding a model, you route based on a **Complexity Score**. We evaluate every prompt on four dimensions:

* **Instruction Complexity:** Is it a simple command or a multi-step instruction with constraints?
* **Reasoning Depth:** Does it need factual recall vs. multi-step reasoning, analysis, and planning?
* **Context Requirements:** Short prompt vs. long-context RAG with 50K+ tokens?
* **Time Expectations:** Do you need real-time <300ms response or is quality more important than latency?

Here is how the Nova portfolio maps naturally to these tiers:

| Nova Model | Role in Routing Tier | When to Route to It | Trade-off |
| :--- | :--- | :--- | :--- |
| **Nova 2 Pro** | The Brain - High Intelligence | Multi-step reasoning, complex analysis, financial report synthesis, code generation | Highest quality, higher latency & cost |
| **Nova 2 Lite** | The Workhorse - Balanced | Standard generation, summarization, classification, RAG Q&A, email drafting | Best balance of cost, latency, quality. Handles 70-80% of workloads. |
| **Nova 2 Sonic** | The Conversationalist - Real-time | Voice-to-voice, real-time dialogue, low-latency chat, contact center streaming | Ultra-low latency speech-to-speech, optimized for conversational flow |
| **Nova Micro** | The Sprinter - Ultra Efficient | Simple classification, entity extraction, routing itself, high-throughput tasks | Lowest cost & latency |

---

### 2. Cost-Optimized Routing: The Cascade Pattern

Don't start with your most powerful and expensive model. Follow a progressive escalation approach - **Try cheap, validate, then escalate only if needed.** This is also called Cascade Routing.

**The Workflow:**

1.  **Start with Nova 2 Lite:** Route 100% of requests to Lite first. It handles 70-80% of enterprise tasks well at ~75% lower cost than Pro.
2.  **Validate Quality:** Automatically score the response against your quality threshold using confidence scoring or an LLM-as-a-Judge.
3.  **Escalate Conditionally:** Only if the score is low, escalate the *same* prompt to Nova 2 Pro.
4.  **Cache Everything:** Use semantic caching to avoid paying for the same question twice.

**Technical Example:**

This pattern is ideal for high-volume applications like customer support or internal knowledge search.

```python
# 1. Check Semantic Cache first - DynamoDB / ElastiCache Serverless
cached_answer = semantic_cache.search(prompt_embedding)
if cached_answer:
    return cached_answer # Cost: $0

# 2. Try with economical model
response_lite = bedrock.converse(modelId="amazon.nova-2-lite-v1:0", messages=[...])

# 3. Validate quality - Use Nova Micro as a Judge [fast & cheap]
judge_prompt = f"Rate this answer quality from 0-1 for prompt: {original_prompt}. Answer: {response_lite}. Return only score."
judge_score = float(bedrock.converse(modelId="amazon.nova-micro-v1:0", ...))

if judge_score < 0.75: # Quality Threshold failed
    # 4. Escalate to Pro only when necessary
    response_pro = bedrock.converse(modelId="amazon.nova-2-pro-v1:0", messages=[...])
    final_response = response_pro
    semantic_cache.save(prompt, final_response)
else:
    final_response = response_lite

# Result: You pay for Pro only for the 15-20% of requests that truly need it.
```

> **Pro Tip:** Enable **Bedrock Prompt Caching** for RAG use cases. If you are sending the same 20K token knowledge base with every request, caching reduces input cost by up to 90%.

---

### 3. Latency-Optimized Routing: Route by SLO

Not all applications have the same latency Service Level Objective [SLO]. Route based on your application's time budget.

*   **Nova 2 Sonic: < 500ms [Real-Time]** - For voice-to-voice, live agents, and streaming. It's a speech-to-speech model, so it removes the STT -> LLM -> TTS hops.
*   **Nova 2 Lite: < 1.5s p95 [Near-Real-Time]** - For chatbots, search, and high-throughput APIs where user is waiting.
*   **Nova 2 Pro: 2-5s+ [Quality-Prioritized]** - For asynchronous jobs like report generation, deep analysis, or batch processing where quality > speed.

Continuously monitor p95 latency and error rate in Amazon CloudWatch and adjust routing.

**Technical Example: Contact Center Application**

```python
def route_by_sla(application_type, prompt):
    if application_type == "VOICE_BOT":
        return "amazon.nova-2-sonic-v1:0"  # Must meet real-time voice SLO
    
    elif application_type == "CHAT_WIDGET":
        # User is waiting, prioritize throughput
        return "amazon.nova-2-lite-v1:0"
    
    elif application_type == "POST_CALL_ANALYTICS":
        # Background job, no user waiting
        return "amazon.nova-2-pro-v1:0"

# You can then set different thresholds in CloudWatch:
# Alarm if p95 latency for CHAT_WIDGET > 1.2s -> Auto-shift 10% more traffic to Lite
```

---

### 4. Integration with Intelligent Prompt Routing: Managed + Custom

You don't have to build all this logic yourself. Combine your explicit routing logic with **Amazon Bedrock Intelligent Prompt Routing [Prompt Routers]** for comprehensive optimization.

A Prompt Router is a single endpoint ARN that contains multiple models. Bedrock's own router model decides the best model based on the criteria you define.

**Configure it with 4 key parameters:**

**a) Quality Thresholds:** `e.g., min_quality_score: 0.8`
**b) Cost Constraints:** `e.g., prioritize_cost_savings: true`
**c) Latency Requirements:** `e.g., max_latency_ms: 1000`
**d) Automatic Failover:** If Nova Lite is throttled, automatically failover to Nova Micro.

**Technical Example: Creating a Prompt Router with Nova Family**

You create this once in Bedrock Console or via API. Your app code never changes again.

```python
import boto3
bedrock_control = boto3.client('bedrock', region_name='us-east-1')

bedrock_control.create_prompt_router(
    promptRouterName="nova-cost-latency-router",
    models=[
        {"modelId": "amazon.nova-2-lite-v1:0"},
        {"modelId": "amazon.nova-2-pro-v1:0"},
        {"modelId": "amazon.nova-2-sonic-v1:0"}
    ],
    routingCriteria={
        "responseQualityDifference": 0.20 # Allow Lite if quality is within 20% of Pro
    },
    fallbackModel={"modelId": "amazon.nova-2-lite-v1:0"},
    description="Routes between Nova tiers based on complexity, cost and latency"
)

# Your application code becomes simple:
bedrock_runtime = boto3.client('bedrock-runtime')
response = bedrock_runtime.converse(
    modelId="arn:aws:bedrock:us-east-1:123456789012:prompt-router/nova-cost-latency-router",
    messages=[{"role": "user", "content": [{"text": prompt}]}]
)
# Bedrock automatically logs which model was invoked: response['trace']['promptRouter']['invokedModelId']
```

**Best Practice Architecture I recommend:**

**Explicit Pre-Filter + Managed Router**

`Application -> [Your Lightweight Logic: is it voice? is it cached?] -> Bedrock Prompt Router ARN [Nova Lite, Pro, Sonic] -> Model`

This way, you handle deterministic rules like caching and voice detection, and let Bedrock Intelligent Prompt Routing handle the non-deterministic complexity-based routing. You get full control, with minimal code to manage.

---
---
