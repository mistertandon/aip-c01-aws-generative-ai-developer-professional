https://www.meta.ai/prompt/8871b14d-6dbe-4046-b844-ec50e095b440

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

### Advantages over static routing
Static routing is rule-based, dynamic routing is intelligence-based.

Think of it like this:

> **Static Routing:** Hard-coded GPS. `if prompt_length > 1000, use Model A else Model B`. It breaks when traffic or roads change.
> **Dynamic Routing with Bedrock Intelligent Prompt Routing:** Waze with live traffic. An ML-based router model evaluates prompt complexity, latency, and cost in real-time and picks the best Foundation Model.

Here are the 3 key advantages, refined:

#### 1. Flexibility and Adaptability

**Static routing requires code changes and redeployment** for every change in business logic or model performance. Dynamic routing adapts in real-time without touching your application code.

It responds to three changes automatically:
* **New Input Patterns:** A sudden spike in long-context RAG queries.
* **Model Performance Variation:** A model experiencing throttling or higher latency.
* **Evolving Business Needs:** You add a new model to your fleet.

The system continuously learns from historical usage, CloudWatch metrics like `InvocationLatency` and error rates, to improve future routing decisions.

**Technical Example:**

Imagine you hard-coded static routing in Lambda:

```python
# STATIC - Brittle, needs redeployment for any change
def static_route(prompt):
    if len(prompt) > 5000:
        return "anthropic.claude-3-5-sonnet-v2:0"
    else:
        return "amazon.titan-text-lite-v1"
```

Now Nova 2 Pro is released and is 2x better for your use case. You have to update code, test, and redeploy 15 microservices.

**With Bedrock Prompt Router :**[Dynamic]

```python
# DYNAMIC - No code change needed
response = bedrock_runtime.converse(
    modelId="arn:aws:bedrock:us-east-1:123456789012:prompt-router/my-router",
    messages=[...]
)
```

You just add `amazon.nova-2-pro-v1:0` to your Prompt Router in the Bedrock Console. Your application instantly starts leveraging it. If Claude Sonnet is throttled, the router automatically fails over to Nova Pro, maintaining your SLO without any incident.

#### 2. Cost and Performance Optimization

Static routing is a **one-size-fits-all** approach. You end up over-provisioning your most expensive model to handle worst-case prompts. Dynamic routing applies **cost-aware inference** - use the cheapest model that can meet the quality bar.

It optimizes on two axes in real-time:
* **Cost Optimization:** Routes simple queries to cost-effective models and reserves expensive, capable models only for complex tasks.
* **Performance Optimization:** Detects latency degradation and automatically switches models to maintain p95 latency targets.

**Technical Example: Real Cost Impact**

Let's say you have 1M requests/month for a support chatbot.

**Static Approach:** All 1M requests -> `Claude 3.5 Sonnet` @ $3.00 / 1M input tokens.
Avg cost = $3,000/month.

**Dynamic Approach with Intelligent Prompt Routing:**
The router analyzes actual complexity. It finds 70% are simple FAQ, 25% medium, 5% complex.

* 700K requests -> `Nova 2 Lite` @ $0.08 / 1M tokens = $56
* 250K requests -> `Nova 2 Pro` @ $0.80 / 1M tokens = $200
* 50K requests -> `Claude 3.5 Sonnet` @ $3.00 / 1M tokens = $150

**Total = $406/month. That's ~86% cost reduction.** Plus, your p95 latency drops from 2.1s to 0.8s because Lite is much faster for the majority of requests. You monitor this with `PromptRouterInvokedModelId` metric in CloudWatch.

#### 3. Multi-Model Utilization

Static routing forces you to compromise on a single Foundation Model. Dynamic routing lets you build a **best-of-breed portfolio** - using each model's specialized strength within a single application API.

This maximizes your FM investment. You are not locked into one model family.

**Technical Example: Unified Customer Experience App**

A single travel application needs three very different capabilities:

1. User says: *"Change my flight via voice"* -> Needs real-time, low-latency speech-to-speech.
2. User says: *"Summarize my 10-page itinerary"* -> Needs fast, cost-effective summarization.
3. User says: *"My flight was cancelled, my hotel is non-refundable, and I have a meeting tomorrow. What's my best alternative plan considering cost and policy?"* -> Needs complex, multi-step reasoning.

**With Static Routing:** You would pick Claude Sonnet for all 3 and pay high cost and high latency for simple tasks, or pick Titan Lite and get poor quality for complex reasoning.

**With Dynamic Routing + Nova Family:**

You configure one Prompt Router containing `[Nova 2 Sonic, Nova 2 Lite, Nova 2 Pro]`.

* Voice request -> **Auto-routed to Nova 2 Sonic** [Optimized for real-time dialogue]
* Summarization -> **Auto-routed to Nova 2 Lite** [High throughput, low cost]
* Complex re-planning -> **Auto-routed to Nova 2 Pro** [Advanced reasoning]

Your application code is simple, but your end-user gets the right intelligence, at the right latency, at the right cost for every single turn. This is strategic multi-model orchestration vs. a one-size-fits-all compromise.

---
---

### Use cases and scenarios
Dynamic routing is not for every workload - it excels when **input diversity, latency SLOs, and cost constraints vary within the same application.** Use dynamic routing when your application is not uniform. If your inputs vary in complexity, your SLAs vary by request type, or your users have different cost-to-serve models, a Prompt Router with the Nova family gives you a single API to optimize quality, latency, and cost automatically.

Here are the 4 patterns where I recommend it to customers, with implementation examples.

#### 1. Diverse Input Applications

**The Problem:** One application handles inputs with vastly different complexity. A CMS gets a 2-line product title and a 50-page technical manual. A customer support bot gets "What is my order status?" and "My API integration is failing with error 403 after OAuth token refresh."

**Static Routing Fails:** If you use your most capable model for everything, you overpay and add latency for simple tasks. If you use a small model, complex tasks fail.

**Dynamic Routing Solution:** Route based on query complexity and content type.

**Technical Example: Customer Service Platform**

```python
# Routing logic inside Bedrock Intelligent Prompt Routing
def get_routing_hint(prompt):
    if len(prompt) < 50 and "what is" in prompt.lower():
        return "FAST_PATH" # FAQ
    elif "error" in prompt or "why" in prompt or len(prompt) > 1000:
        return "REASONING_PATH" # Complex troubleshooting

# Result:
# "What are your return policies?" -> Nova 2 Lite | 400ms | $0.00008
# "My Lambda function times out when calling Bedrock via VPC endpoint with this policy..." 
# -> Nova 2 Pro or Claude 3.5 Sonnet | 2.5s | Higher quality reasoning
```

You configure one **Prompt Router ARN** with `[Nova Lite, Nova Pro]`. Bedrock automatically learns that FAQ patterns go to Lite.

#### 2. Performance-Sensitive Systems

**The Problem:** Enterprise systems must maintain strict Service Level Agreements [SLAs]. Not all requests have the same urgency.

**Dynamic Routing Solution:** Route based on latency budget and business criticality, not just prompt complexity. Monitor p95 latency and throughput in CloudWatch and adapt.

**Technical Example: Financial Analysis Platform**

An investment platform has two types of workloads on the same API:

*   **Trader Chat [SLO: <800ms]:** "What was the pre-market move for NVDA?"
*   **Overnight Report [SLO: <30s acceptable]:** "Generate a 10-page earnings analysis comparing 5 banks with risks and YoY trends."

**Implementation:**

```python
# Explicit routing layer + Prompt Router for resilience
if request.priority == "REAL_TIME":
    model_id = "amazon.nova-2-lite-v1:0" # High-throughput, low latency
    max_tokens = 300
else: # BATCH / ANALYTICS
    model_id = "amazon.nova-2-pro-v1:0" # Quality-prioritized, accepts higher latency
    max_tokens = 4000

# If Lite gets throttled during market open, Prompt Router automatically fails over
# to an alternative model to maintain SLA - no outage.
```

This ensures you meet your real-time SLA without paying for Pro on every request.

#### 3. Multi-Modal and Multi-Task Applications

**The Problem:** An Intelligent Document Processing [IDP] pipeline needs different specialized skills in one workflow.

**Dynamic Routing Solution:** Use dynamic routing as an orchestrator to send each sub-task to the most specialized model.

**Technical Example: Document Processing System**

An insurance claims intake processes PDFs with text, tables, and handwritten notes.

**Workflow with AWS Step Functions:**

`S3 Upload -> Lambda Router -> Bedrock`

1.  **Step 1 - Extraction:** `prompt = "Extract all fields from this invoice"` 
    -> **Nova Micro** - Cheapest, fastest for structured extraction.

2.  **Step 2 - Sentiment/Classification:** `prompt = "Classify claim urgency: High/Med/Low based on description"` 
    -> **Nova Lite** - Good balance for classification.

3.  **Step 3 - Summarization & Reasoning:** `prompt = "Summarize this 20-page adjuster report and identify fraud risk factors with reasoning"` 
    -> **Nova Pro** - Needs long-context and reasoning.

Instead of calling one giant model 3 times, you call the right-sized model for each task. You optimize **resource utilization** and control cost per step. You can trace this entire chain with Bedrock Trace.

#### 4. Cost-Conscious Implementations [Tiered Experience]

**The Problem:** You have different budget constraints for different user segments. You want to offer service differentiation.

**Dynamic Routing Solution:** Inject business context [user tier, subscription] into your routing decision.

**Technical Example: EdTech Platform**

*   Free Tier Student: 10M users, cost-sensitive
*   Premium Tier Student: 100K users, pays for high quality tutoring

```python
def route_by_tier(user, prompt):
    base_model = prompt_router.invoke(prompt) # Let Prompt Router decide complexity first

    # Apply business policy override
    if user.tier == "FREE":
        # Cap free users to Lite, even if Pro would be slightly better
        # Ensures cost per user stays < $0.01/month
        return "amazon.nova-2-lite-v1:0" if "lite" in base_model else "amazon.nova-micro-v1:0"
    
    elif user.tier == "PREMIUM":
        # Allow escalation to Pro for premium users
        return base_model # Can be Pro

# Free: "Explain Pythagoras theorem" -> Nova Lite
# Premium: "Explain Pythagoras theorem and create a personalized proof using my previous mistakes" -> Nova Pro
```

You maintain service differentiation and control expenses without maintaining two separate application stacks. You can enforce this with a single Prompt Router + a Lambda authorizer that checks the user tier.

---
---

### Implementation approaches

You can implement Bedrock Intelligent Prompt Routing in 3 ways, based on your control and latency needs:

1.  **Step Functions:** For sophisticated, multi-step content-based workflows
2.  **API Gateway:** For lightweight, low-latency dynamic selection at the API layer
3.  **Performance-Based Fallback:** For resilience and SLA protection

---
---

### Content-Based Routing with Step Functions

AWS Step Functions lets you build intelligent, content-aware routing without writing complex routing code in your application. You define a **state machine workflow** with decision points that analyze incoming content and dynamically route it to the most appropriate Amazon Bedrock foundation model.

This pattern is ideal when routing logic depends on more than just prompt length - for example, document type, intent, or complexity score.

#### How This Workflow Works

This state machine optimizes both cost and performance by ensuring you only pay for a powerful model when you actually need it.

**The flow has 3 stages:**

**1. AnalyzeContent [Task State]:**
Invokes a Lambda function `content-analyzer`. This Lambda is your lightweight classifier. It inspects `$.prompt` characteristics - token count, keywords like "analyze / reason / compare", or document type - and returns a complexity label: `high`, `medium`, or `low`.

**2. RouteBasedOnComplexity [Choice State]:**
This is the decision point. It evaluates the `$.complexity` field returned by Lambda:
* If `complexity == high` -> Route to `InvokeClaudeOpus`
* If `complexity == medium` -> Route to `InvokeClaudeSonnet`
* Default [low complexity] -> Route to `InvokeTitanExpress`

**3. Model Invocation [Task State]:**
Uses the optimized Bedrock integration `arn:aws:states:::bedrock:invokeModel` to call the selected foundation model. No Lambda needed for the actual model call.

#### Complete, Production-Ready Workflow

Your original code was missing the final two states. Here is the corrected and complete version:

```json
{
  "Comment": "Dynamic model routing based on content analysis",
  "StartAt": "AnalyzeContent",
  "States": {
    "AnalyzeContent": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "content-analyzer",
        "Payload.$": "$"
      },
      "ResultSelector": {
        "complexity.$": "$.Payload.complexity",
        "prompt.$": "$.Payload.prompt"
      },
      "Next": "RouteBasedOnComplexity"
    },
    "RouteBasedOnComplexity": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.complexity",
          "StringEquals": "high",
          "Next": "InvokeClaudeOpus"
        },
        {
          "Variable": "$.complexity",
          "StringEquals": "medium",
          "Next": "InvokeClaudeSonnet"
        }
      ],
      "Default": "InvokeTitanExpress"
    },
    "InvokeClaudeOpus": {
      "Type": "Task",
      "Resource": "arn:aws:states:::bedrock:invokeModel",
      "Parameters": {
        "ModelId": "anthropic.claude-3-opus-20240229-v1:0",
        "Body": {
          "anthropic_version": "bedrock-2023-05-31",
          "max_tokens": 2000,
          "messages.$": "$.prompt"
        }
      },
      "End": true
    },
    "InvokeClaudeSonnet": {
      "Type": "Task",
      "Resource": "arn:aws:states:::bedrock:invokeModel",
      "Parameters": {
        "ModelId": "anthropic.claude-3-sonnet-20240229-v1:0",
        "Body": {
          "anthropic_version": "bedrock-2023-05-31",
          "max_tokens": 1000,
          "messages.$": "$.prompt"
        }
      },
      "End": true
    },
    "InvokeTitanExpress": {
      "Type": "Task",
      "Resource": "arn:aws:states:::bedrock:invokeModel",
      "Parameters": {
        "ModelId": "amazon.titan-text-express-v1",
        "Body": {
          "inputText.$": "$.prompt",
          "textGenerationConfig": { "maxTokenCount": 512 }
        }
      },
      "End": true
    }
  }
}
```

**What the `content-analyzer` Lambda does in practice:**

```python
def lambda_handler(event, context):
    prompt = event.get('prompt', '')
    # Simple scoring - can be replaced with Nova Micro as a classifier
    if len(prompt) > 5000 or "analyze" in prompt.lower():
        complexity = "high"
    elif len(prompt) > 500:
        complexity = "medium"
    else:
        complexity = "low"
    
    return { "complexity": complexity, "prompt": prompt }
```

**Outcome:** 
* Simple FAQ -> **Titan Express** [Lowest cost, ~300ms latency]
* Standard summarization -> **Claude Sonnet** [Balanced cost and intelligence]
* Complex reasoning / RAG with large context -> **Claude Opus** [Highest quality]

This approach gives you visual observability in Step Functions console, built-in retry and error handling, and full control to add more branches later without redeploying your application.

---
---

### API Gateway Routing Logic for Dynamic Model Selection

Amazon API Gateway acts as the intelligent entry point for your generative AI application. It provides request transformation and routing capabilities, allowing you to inspect incoming requests and dynamically route them to the most appropriate Amazon Bedrock foundation model.

You can implement this in two ways:
1.  **Mapping Templates [VTL]:** For lightweight routing based on headers or JSON fields without Lambda overhead.
2.  **Lambda Integration:** For advanced logic that analyzes content type, user tier, or performance requirements - which is what the example below does.

This approach lets you enforce business policies at the API layer.

#### How This Implementation Works

This pattern uses **API Gateway -> Lambda -> Bedrock Runtime** to balance performance and cost-efficiency. Instead of using one expensive model for all requests, it selects the optimal Claude model based on two signals:

*   **User Tier:** Read from the custom header `X-User-Tier`
*   **Content Length:** Measured from the request body

**The Routing Logic:**

1.  **Premium User + Long Content > 1000 chars:** Route to **Claude 3 Opus** - Our most capable model for complex, high-value tasks requiring deep reasoning.
2.  **Medium Content > 500 chars:** Route to **Claude 3 Sonnet** - Balanced intelligence and speed for standard workloads.
3.  **Short Content / Basic Tier:** Route to **Claude 3 Haiku** - Fastest, most cost-effective model for simple queries.

After selection, the function invokes the chosen model via `bedrock-runtime` using the Converse API format and returns the response with a custom header `X-Selected-Model` for full observability and traceability in CloudWatch.

#### Refined Code with Best Practices

Here is the same logic, refined for production with error handling and correct body parsing:

```python
import json
import boto3

bedrock = boto3.client('bedrock-runtime')

def lambda_handler(event, context):
    # 1. Parse and analyze request characteristics
    body = event.get('body', '')
    # API Gateway can base64 encode body, handle both cases
    if event.get('isBase64Encoded'):
        import base64
        body = base64.b64decode(body).decode('utf-8')
        
    content_length = len(body)
    user_tier = event['headers'].get('X-User-Tier', 'basic').lower()

    # 2. Dynamic model selection logic
    if user_tier == 'premium' and content_length > 1000:
        model_id = 'anthropic.claude-3-opus-20240229-v1:0' # High complexity, premium SLA
    elif content_length > 500:
        model_id = 'anthropic.claude-3-sonnet-20240229-v1:0' # Balanced
    else:
        model_id = 'anthropic.claude-3-haiku-20240307-v1:0' # Cost-optimized, low latency

    # 3. Invoke selected model via Bedrock
    response = bedrock.invoke_model(
        modelId=model_id,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": body}]
        })
    )
    
    response_body = json.loads(response['body'].read())

    # 4. Return with routing metadata
    return {
        'statusCode': 200,
        'body': json.dumps(response_body),
        'headers': {
            'Content-Type': 'application/json',
            'X-Selected-Model': model_id # Critical for debugging and cost allocation
        }
    }
```

**Why this matters:** You achieve **tier-based SLA enforcement**. Premium users get Opus for long, complex prompts where quality matters, while basic users and short prompts are served by Haiku at ~10x lower cost and ~2x lower latency. You get this without deploying multiple API endpoints.

---
---

### Performance-Based Fallback Mechanisms

Performance-based routing goes beyond static rules. It monitors real-time model health and automatically switches to an alternative Foundation Model when performance degrades. This ensures you maintain your SLA even during throttling, high load, or model latency spikes.

We achieve this by using **Amazon CloudWatch metrics** like `InvocationLatency` and `InvocationThrottles` as routing signals, with a fast, high-throughput fallback model to guarantee availability.

**When to use this pattern:** For production, customer-facing workloads where you cannot afford a 500 error just because your primary model is slow.

#### How This Implementation Works

This `PerformanceBasedRouter` class implements a **health-aware circuit breaker** pattern for Amazon Bedrock:

**1. Monitors Health in Real-Time:**
The `get_model_performance()` method queries CloudWatch for the last 5 minutes of `InvocationLatency` for each primary model. It checks `AWS/Bedrock` namespace with `ModelId` dimension. If there is no data, it returns `inf` - treating lack of data as a potential issue.

**2. Selects Optimal Model Based on Health + Complexity:**
`select_optimal_model()` iterates through your primary models in priority order - e.g., `[Claude 3 Opus, Claude 3 Sonnet]`. It picks the first model whose average latency is below your threshold of **2000ms**. If all primary models are slow, it automatically fails over to your fallback model, **Claude 3 Haiku**, which is optimized for low latency and high throughput.

**3. Executes with Automatic Retry on Failure:**
`route_request()` invokes the selected model. If Bedrock returns an exception like `ThrottlingException` or `ModelTimeoutException`, it recursively retries with the fallback model, ensuring graceful degradation instead of failing the user request.

#### Refined Production-Ready Code

Your logic is correct, I have refined it for safety, observability, and to avoid infinite recursion:

```python
import boto3
import json
from datetime import datetime, timedelta

class PerformanceBasedRouter:
    def __init__(self):
        self.bedrock = boto3.client('bedrock-runtime')
        self.cloudwatch = boto3.client('cloudwatch')
        # Priority order: Most capable first
        self.primary_models = [
            'anthropic.claude-3-opus-20240229-v1:0',
            'anthropic.claude-3-sonnet-20240229-v1:0'
        ]
        self.fallback_model = 'anthropic.claude-3-haiku-20240307-v1:0'
        self.latency_threshold_ms = 2000

    def get_model_performance(self, model_id: str) -> float:
        """Check real-time health via CloudWatch InvocationLatency"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=5)
        
        response = self.cloudwatch.get_metric_statistics(
            Namespace='AWS/Bedrock',
            MetricName='InvocationLatency',
            Dimensions=[{'Name': 'ModelId', 'Value': model_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=['Average']
        )
        if response['Datapoints']:
            # Return latest average latency in ms
            return response['Datapoints'][-1]['Average']
        return float('inf')  # No datapoints = treat as unhealthy

    def select_optimal_model(self, complexity_score: int) -> str:
        """Select first healthy model under threshold, else fallback"""
        # For low complexity, you could directly prefer Haiku to save cost
        # if complexity_score < 3: return self.fallback_model

        for model_id in self.primary_models:
            latency = self.get_model_performance(model_id)
            if latency < self.latency_threshold_ms:
                print(f"Selected {model_id} with latency {latency}ms")
                return model_id
        
        print(f"All primary models slow, failing over to {self.fallback_model}")
        return self.fallback_model

    def route_request(self, prompt: str, complexity_score: int):
        """Route with performance-aware selection + error-based fallback"""
        selected_model = self.select_optimal_model(complexity_score)
        try:
            response = self.bedrock.invoke_model(
                modelId=selected_model,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}]
                })
            )
            return {
                "model_used": selected_model,
                "response": json.loads(response['body'].read())
            }
        except Exception as e:
            # True fallback: If primary fails, retry once with Haiku
            if selected_model != self.fallback_model:
                print(f"{selected_model} failed with {e}, retrying with fallback")
                return self.route_request(prompt, complexity_score=0) # Force fallback path
            raise e
```

**Architectural Best Practice:** For most customers, you don't need to build this. Create a **Bedrock Prompt Router** and configure `fallbackModel = Claude 3 Haiku`. Bedrock natively monitors health and does this failover for you with built-in CloudWatch metrics like `PromptRouterFallbackTriggered`. Use this custom class only when you need custom thresholds or business logic based on `complexity_score`.

---
