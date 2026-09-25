### Static Model Routing Fundamentals

Think of static routing as a **pre-defined traffic controller** for your Generative AI application. Instead of asking an AI to decide which model should answer a request at runtime, you define the rules upfront: "If the request is X, always send it to Model Y."

In Amazon Bedrock terms, you are creating a fixed mapping between an **input characteristic** - like API endpoint, task type, or user persona - and a specific **Foundation Model (FM) endpoint**.

This is different from **Dynamic Routing**, where a classifier model or an LLM analyzes the content of the prompt in real-time to decide where to route it. Static routing is deterministic, faster, and cheaper because there is no extra inference step for routing.

**How it works in practice:**

1.  User sends a request to your application layer (e.g., via API Gateway)
2.  Your routing layer [a lightweight AWS Lambda function] inspects metadata, not the prompt semantics. e.g., `task_type` header, `/support` vs `/developer` API path
3.  The request is forwarded to the pre-assigned Bedrock Model ID
4.  Response is returned with predictable latency and cost

#### Key Characteristics - Refined

**1. Predetermined Model Assignment:** The routing logic is rule-based and configured at deployment time. No ML model is needed to make the routing decision.

**2. Immutable at Runtime:** Routing rules don't change during inference. To change them, you update your config or IaC [CDK / CloudFormation], not the model's behavior.

**3. Deterministic & Observable:** For the same input category, you will always hit the same FM. This gives you consistent performance, cost, and makes debugging with Amazon CloudWatch much simpler.

**4. Low Latency Overhead:** Since it's just an `if/else` or switch-case lookup, you add ~5-10ms of latency, versus 200-500ms if you used another FM as a router.

### Technical Example: E-commerce Platform on AWS

Let's say you're building a GenAI assistant for an e-commerce company with three distinct use cases.

You don't want to use one large, expensive model for everything. You optimize:

*   Customer Q&A needs to be fast, cheap, and empathetic
*   Product description generation needs to be creative and brand-aligned
*   Code assistance for your internal sellers needs strong reasoning

**Architecture:**
`[Client App] -> [Amazon API Gateway: /chat, /generate, /code] -> [AWS Lambda - Router] -> [Amazon Bedrock]`

**Step 1: Define your static routing table as config**

This lives in AWS Systems Manager Parameter Store or AppConfig:

```json
{
  "customer_support": {
    "model_id": "anthropic.claude-3-haiku-20240307-v1:0",
    "reason": "Lowest latency and cost for high-volume conversational tasks"
  },
  "marketing_content": {
    "model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "reason": "Best balance of creativity and instruction following"
  },
  "code_generation": {
    "model_id": "meta.llama3-70b-instruct-v1:0",
    "reason": "Strong reasoning for Python/SQL generation, cost-effective"
  }
}
```

**Step 2: Implement the Router in Lambda - No AI needed**

```python
import boto3

bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')

ROUTING_MAP = {
    "customer_support": "anthropic.claude-3-haiku-20240307-v1:0",
    "marketing_content": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "code_generation": "meta.llama3-70b-instruct-v1:0"
}

def lambda_handler(event, context):
    # Input characteristic comes from API path or frontend, not from analyzing the prompt
    task_type = event['headers'].get('x-task-type') # e.g., 'customer_support'
    user_prompt = event['body']['prompt']

    model_id = ROUTING_MAP.get(task_type)
    
    if not model_id:
        raise ValueError(f"No static route defined for {task_type}")

    # Invoke the pre-assigned FM
    response = bedrock_runtime.invoke_model(
        modelId=model_id,
        body=f'{{"prompt": "{user_prompt}", "max_tokens": 1024}}'
    )
    return response
```

If `x-task-type: customer_support` -> Request always goes to Claude 3 Haiku. If it's `code_generation` -> Always goes to Llama 3 70B.

**Why this is powerful for you:**

*   **Cost Optimization:** You avoid using Claude 3.5 Sonnet ($3 / 1M input tokens) for simple FAQs that Haiku can handle for $0.25 / 1M tokens.
*   **Performance SLAs:** You can guarantee <1s latency for customer chat because you know Haiku's p95 latency.
*   **Governance:** You can easily track spend and quality per use case in CloudWatch by Model ID.

#### When to Use Static Routing vs. Dynamic Routing?

**Use Static Routing when:**
Your task categories are clearly separable upfront. You have distinct APIs, user roles, or workflows.

**Use Dynamic Routing when:**
A single API endpoint like `/general-assistant` can receive anything, and you need an LLM classifier to detect intent first.

> **Architect's Best Practice:** Start with Static Routing. It's simpler, cheaper, and more reliable. Only move to dynamic routing when your rule-based logic can no longer classify inputs accurately. You can also hybridize - use static routing at the API Gateway level, and dynamic routing only inside your complex `/general-assistant` endpoint.

---
---

### Advantages and Disadvantages of Static Model Routing

Static routing is when you hard-code the rule: **"For Task X, always use Model Y"**. It's like having dedicated lanes on a highway.

#### Advantages: Why we often start here

**1. Straightforward Implementation**
You don't need a separate classifier model or vector search. It's just conditional logic in your application layer. Any developer can build and maintain it.

**2. Predictable Performance & Latency**
Because the route is fixed, you know the exact latency profile. You can set accurate SLAs. A request for `customer_support` will *always* go to the same model and return in a predictable p95 latency.

**3. Lower Computational Overhead**
Dynamic routing requires an extra inference call just to decide *where* to route. Static routing removes that. Your routing decision is a simple dictionary lookup in AWS Lambda - ~5ms, vs 300ms+ for an LLM-based router.

**4. Cost Predictability and Governance**
This is critical for FinOps. When routes are fixed, you can forecast Bedrock costs per use case. You can also apply different throttling, guardrails, and logging per route in Amazon CloudWatch.

#### Disadvantages: Where it starts to hurt

**1. Limited Flexibility**
Routing logic is coupled to your code/config. To add a new FM or change a rule, you need a code deployment. It cannot adapt on the fly to a new business requirement.

**2. Potential for Suboptimal Model Selection**
Static rules look at metadata [like API endpoint or `task_type`], not the nuance inside the prompt. It will miss context that a smarter router would catch.

**3. Manual Maintenance Overhead**
When AWS releases a better model in Amazon Bedrock, or you want to A/B test, you have to manually update your routing table, update your CDK, and redeploy.

**4. No Self-Optimization**
The system doesn't learn. It can't automatically learn from user feedback, latency metrics, or quality scores to improve routing over time.

### Technical Example: Where Advantages and Disadvantages Show Up

Let's take the same e-commerce assistant on **API Gateway + Lambda + Amazon Bedrock**.

**Your Static Routing Table in Parameter Store:**

```python
ROUTING_TABLE = {
  "support_chat": "anthropic.claude-3-haiku-20240307-v1:0", # $0.25 / 1M tokens, fast
  "product_description": "anthropic.claude-3-5-sonnet-20241022-v2:0", # Creative, higher cost
  "seller_code_assist": "meta.llama3-70b-instruct-v1:0"
}
```

**The Advantage in action:**
A request comes to `POST /support_chat` with prompt: "Where is my order?"
Lambda does: `model_id = ROUTING_TABLE["support_chat"]`
Result: You get a fast, cheap, predictable response from Haiku. You saved cost and met your <1 sec SLA. Perfect.

**The Disadvantage in action:**
A request comes to the *same* `POST /support_chat` endpoint but the prompt is:
> "Where is my order? Also, write me a Python script to bulk check all my order statuses using your Seller API."

Your static router still sends it to Haiku because the rule is based on the endpoint, not the content. Haiku will struggle with the code part. A dynamic router would have detected "code generation intent" inside the prompt and routed the second part to Llama 3 70B or Claude 3.5 Sonnet.

Now you have a suboptimal selection, and to fix it, you have to manually rewrite your Lambda logic to handle mixed-intent prompts.

**Architect's Mitigation Pattern:**

Don't hard-code the map in Lambda code. Externalize it to make disadvantages manageable:

1.  Store `ROUTING_TABLE` in **AWS AppConfig or Systems Manager Parameter Store** with feature flags.
2.  This lets you change routes without redeploying code.
3.  Add **observability**: Log `task_type`, `model_id`, latency, and token usage to CloudWatch. When you see quality drops for certain prompts, that's your signal that you have outgrown static routing and should consider a hybrid or dynamic approach for that specific route.

---
---

### Static model routing use cases

**Use static routing when you can answer the routing question *before* you read the prompt.** If the destination is obvious from the API, metadata, or user journey, static routing is the most cost-effective and reliable pattern.

Here are the 4 use cases where it shines:

#### 1. Well-Defined Input Types with Stable Categories

**When to use:** Your inputs fall into consistent, predictable buckets that don't change often and can be identified by metadata, not by deep semantic analysis.

**Why static routing fits:** You don't need an LLM to decide the category. The source system already tells you.

**Technical Example: Intelligent Document Processing**
An application processes documents uploaded to Amazon S3. The S3 object metadata or file prefix already tells you the type.

Architecture: `S3 Upload (s3://invoices/...) -> S3 Event -> AWS Lambda Router -> Amazon Bedrock`

The Router logic is simple:

```python
# No AI needed for routing, just S3 key/metadata
if s3_key.startswith("invoices/"):
    model_id = "anthropic.claude-3-haiku-20240307-v1:0" # Fast, cheap for extraction
elif s3_key.startswith("contracts/"):
    model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0" # Strong reasoning for legal clauses
elif s3_key.startswith("reports/"):
    model_id = "amazon.titan-text-express-v1" # Good for summarization
```

You get predictable latency and cost per document type, without paying for an extra classification model.

#### 2. Task-Specific Model Optimization

**When to use:** You have evaluated your FMs and you know Model A is clearly better and cheaper for Task A, and Model B for Task B.

**Why static routing fits:** You are optimizing for quality, cost, and latency per task. You want to enforce that optimization.

**Technical Example: Financial Services Platform**
Same user, two very different tasks in your app.

*   Task A: `/api/analyze-earnings` -> Needs numerical reasoning and factual accuracy
*   Task B: `/api/write-blog` -> Needs creativity and brand tone

You statically route:

*   `analyze-earnings` -> `meta.llama3-70b-instruct-v1:0` or a finance-tuned model on SageMaker JumpStart - optimized for structured data reasoning
*   `write-blog` -> `anthropic.claude-3-5-sonnet-20241022-v2:0` - optimized for long-form creative generation

If you routed both to Sonnet, you'd overpay for the earnings task. If you routed both to Llama 3 70B, you'd lose quality on the blog. Static routing gives you the best price-performance per task.

#### 3. FAQ Chatbot with Tiered Complexity

**When to use:** This is the classic cost-saving pattern for customer service.

**Why static routing fits:** 70% of queries are simple and can be handled by a small, fast model. 30% are complex and need a large model. The API path or intent button already separates them.

**Technical Example: Customer Support on Amazon Lex + Bedrock**

Architecture: `Amazon Lex [Intent Detection] -> Lambda Router -> Bedrock`

*   Lex intent = `BusinessHours`, `ReturnPolicy`, `ContactUs` -> Route to `amazon.titan-text-lite-v1` or `anthropic.claude-3-haiku`. Lightweight FM, <500ms response, $0.0003 per query.
*   Lex intent = `TechnicalTroubleshooting`, `Escalation` -> Route to `anthropic.claude-3-5-sonnet` with access to Knowledge Base via Bedrock Knowledge Bases. More expensive, but can do multi-step reasoning and tool use.

Result: You reduce your total Bedrock bill by 60-70% because you are not using your most powerful FM for "What are your business hours?"

#### 4. Content Type Segregation - Multimodal Routing

**When to use:** Your application accepts multiple modalities - text, image, video, audio.

**Why static routing fits:** A text-only model will fail on an image. The content-type header tells you exactly which capability you need. No AI analysis required.

**Technical Example: E-commerce Product Support**

User can upload text OR an image of a damaged product.

Your API Gateway receives `Content-Type` header.

```python
if content_type == "text/plain":
    model_id = "anthropic.claude-3-haiku-20240307-v1:0" # Text-only, cheap
elif content_type == "image/jpeg":
    model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0" # Vision-capable FM
    # Or: "amazon.titan-image-generator-v1" if task is generation
```

If it's an image, you *must* route to a vision-capable FM. If it's text, routing it to a vision model is wasteful - you pay for image tokens you don't need. Static routing based on `Content-Type` prevents both failure and waste.

**Architect's Rule of Thumb:**
If you can determine the route with an `if/else` on metadata, API path, or file type, use static routing and store the mapping in **AWS Systems Manager Parameter Store**. Move to dynamic routing only when you need to read the *meaning* inside the prompt to make the decision.

---
---

### Implementation examples

This is how I guide teams to implement static routing. Don't hardcode model IDs everywhere. Start simple, then externalize the config for production.

Here are 3 patterns we use on AWS, from MVP to production-grade. All use **Amazon Bedrock** with boto3.

#### Pattern 1: Simple Conditional Logic - For Prototyping

**When to use:** You have 2-3 models and you are building an MVP. Fastest to implement.

This is direct `if/else` based on a metadata field you already have, like an API path or a header. You are not analyzing the prompt content.

```python
import boto3
import json

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def get_response(task_type, prompt):
    # task_type comes from your frontend, e.g., "support" or "code"
    if task_type == "support":
        model_id = "anthropic.claude-3-haiku-20240307-v1:0" # Fast, cheap for FAQs
    elif task_type == "code":
        model_id = "meta.llama3-70b-instruct-v1:0" # Strong reasoning
    else:
        model_id = "amazon.titan-text-express-v1" # Default fallback

    body = json.dumps({"inputText": prompt, "textGenerationConfig": {"maxTokenCount": 1024}})

    response = bedrock.invoke_model(modelId=model_id, body=body)
    return json.loads(response['body'].read())['results'][0]['outputText']
```

**Pros:** Very easy to understand.
**Cons:** To add a new model, you need to change code and redeploy your Lambda.

#### Pattern 2: Dictionary-Based Routing Table - Recommended for Most Apps

**When to use:** You have 3+ use cases and want clean, maintainable code. This is the pattern I recommend for 80% of customers.

You separate the routing decision from the invocation logic.

```python
# Central routing table - easy to read and audit
ROUTING_TABLE = {
    "customer_faq": {
        "model_id": "anthropic.claude-3-haiku-20240307-v1:0",
        "max_tokens": 512,
        "description": "High volume, low latency"
    },
    "product_copy": {
        "model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "max_tokens": 2048,
        "description": "High creativity needed"
    },
    "sql_generation": {
        "model_id": "meta.llama3-70b-instruct-v1:0",
        "max_tokens": 1024,
        "description": "Optimized for code"
    }
}

def invoke_bedrock(task_type: str, prompt: str):
    config = ROUTING_TABLE.get(task_type)
    if not config:
        raise ValueError(f"No static route defined for task: {task_type}")

    # Standardized invocation
    response = bedrock.invoke_model(
        modelId=config["model_id"],
        body=json.dumps({
            "prompt": prompt,
            "max_gen_len": config["max_tokens"]
        })
    )
    return response
```

You now have one place to manage cost and performance per task.

#### Pattern 3: Configuration-Driven Routing - Production Standard on AWS

**When to use:** Production workloads where you need to change models without code deployment, do canary testing, or let non-developers manage routes.

In production, we never keep the table in code. We externalize it to **AWS Systems Manager Parameter Store / AWS AppConfig**. This gives you versioning, audit, and no-downtime updates.

**Architecture:**
`[Client] -> [API Gateway] -> [Lambda Router] -> [AppConfig: routing.json] -> [Amazon Bedrock] -> [CloudWatch Metrics]`

**Step 1: Config file stored in AppConfig `routing.json`:**
```json
{
  "invoice_processing": "anthropic.claude-3-haiku-20240307-v1:0",
  "contract_review": "anthropic.claude-3-5-sonnet-20241022-v2:0",
  "image_qa": "anthropic.claude-3-5-sonnet-20241022-v2:0"
}
```

**Step 2: Lambda fetches config at runtime:**

```python
import boto3

appconfig_client = boto3.client('appconfigdata')
bedrock_client = boto3.client('bedrock-runtime')

# Fetch routing config at cold start - cached for the execution environment
def get_routing_config():
    # In production, use AppConfig extension for Lambda to cache this
    response = appconfig_client.get_latest_configuration(
        ConfigurationToken="your-token"
    )
    return json.loads(response['Configuration'].read())

ROUTING_CONFIG = get_routing_config()

def lambda_handler(event, context):
    # Example: S3 key gives us the input type
    s3_key = event['Records'][0]['s3']['object']['key'] # e.g., "invoices/inv_123.pdf"
    doc_type = s3_key.split('/')[0] # "invoices"

    # Map business category to task
    task_map = {"invoices": "invoice_processing", "contracts": "contract_review"}
    task_type = task_map.get(doc_type, "invoice_processing")

    model_id = ROUTING_CONFIG[task_type]

    # Invoke with observability
    print(f"Routing doc_type={doc_type} to task={task_type} model={model_id}")
    #... invoke_model call...

    # This log allows you to build CloudWatch dashboards for cost per task_type
```

**Why this is production-grade:**

1. **No code deploy to change models:** When `Claude 4` launches, you just update AppConfig from `claude-3-haiku` to `claude-4-haiku`. Lambda picks it up instantly.
2. **Governance:** You can add Bedrock Guardrails, IAM permissions, and throttling per route.
3. **Fallback & Observability:** You can add a `default` model and log `task_type`, `model_id`, `latency`, `input_tokens` to CloudWatch for FinOps.

**Architect's Recommendation:** Start with Pattern 2 for development, and move to Pattern 3 before you go to production. It saves you from redeploying your application every time you want to optimize cost or quality.

---

### Python Implementation: Conditional Routing with Amazon Bedrock

This is the **Dictionary-Based Static Routing** pattern. It's the most common pattern I recommend for teams starting out. The core idea is simple: the routing decision is made from a predefined metadata field `request_type`, not by analyzing the prompt itself.

Think of it as a deterministic switchboard.

#### How This Code Works - Simplified

The `StaticModelRouter` class acts as a central controller that maps a business task to a specific Foundation Model [FM] endpoint in Amazon Bedrock.

**1. Initialization `__init__`: The Control Plane**
```python
self.bedrock = boto3.client('bedrock-runtime')
self.model_mappings = {... }
```
You create two things:
* A **Bedrock Runtime client**: The low-level client that will perform `invoke_model` API calls.
* A **Routing Table**: A Python dictionary that is your static rulebook. Key = `request_type` [your business category], Value = `modelId` [the Bedrock FM ID]. This table is fixed at deployment time.

We choose models based on price-performance:
* `faq` -> `claude-3-haiku`: Fastest and cheapest, perfect for high-volume, low-complexity queries.
* `technical_support` -> `claude-3-sonnet`: Balanced reasoning for troubleshooting.
* `creative_writing` -> `claude-3-opus`: Highest quality for creative tasks.
* `data_analysis` -> `amazon.titan-text-express-v1`: Cost-effective for summarization/extraction.

**2. Routing `route_request()`: The Data Plane**
```python
model_id = self.model_mappings.get(request_type)
```
This is where static routing happens. It does a simple O(1) dictionary lookup. There is no LLM classifier, no embedding search. If `request_type` is `faq`, it will *always* resolve to Haiku. This gives you predictable latency and cost. If the key doesn't exist, we fail fast with a `ValueError` to avoid silent misrouting.

**3. Invocation `invoke_model()`: The Execution**
This method standardizes the Bedrock API call. It formats the payload to the Anthropic Messages API format `anthropic_version`, `messages`, and calls `bedrock.invoke_model()`. The response is then parsed from the StreamingBody.

#### Production-Ready Refined Version

Your original code has a small bug `init` vs `__init__` and uses different payload formats for Claude vs Titan. Here is the corrected, production-ready version I use with customers:

```python
import boto3
import json
import logging

logger = logging.getLogger(__name__)

class StaticModelRouter:
    def __init__(self, region_name="us-east-1"):
        self.bedrock = boto3.client('bedrock-runtime', region_name=region_name)
        # In production, move this to AWS AppConfig / Parameter Store
        self.model_mappings = {
            'faq': 'anthropic.claude-3-haiku-20240307-v1:0',
            'technical_support': 'anthropic.claude-3-sonnet-20240229-v1:0',
            'creative_writing': 'anthropic.claude-3-opus-20240229-v1:0',
            'data_analysis': 'amazon.titan-text-express-v1'
        }

    def route_request(self, input_text: str, request_type: str):
        model_id = self.model_mappings.get(request_type)
        if not model_id:
            raise ValueError(f"Unknown request type: {request_type}. Valid types: {list(self.model_mappings.keys())}")

        logger.info(f"Static routing: request_type={request_type} -> model_id={model_id}")
        return self.invoke_model(model_id, input_text)

    def invoke_model(self, model_id: str, input_text: str):
        # Note: Titan and Claude have different request bodies. In production, handle this with a model-specific formatter.
        # This example is for Claude 3 models
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": input_text}]
        })

        response = self.bedrock.invoke_model(
            body=body,
            modelId=model_id,
            accept='application/json',
            contentType='application/json'
        )
        return json.loads(response.get('body').read())

# Usage example
router = StaticModelRouter()
# The request_type comes from your API Gateway path or frontend, e.g., x-task-type header
result = router.route_request("What are your business hours?", "faq")
print(result['content'][0]['text'])
```

**Why this is static routing:** The model selection is predetermined in `model_mappings`. Even if the user asks a complex technical question inside the `faq` task, it will still go to Haiku. The decision logic doesn't change at runtime based on the content of `input_text`.

---

### Configuration-Based Routing

We call it **Configuration-Driven Static Routing**.

Think of your previous `if/else` router as hard-wiring. This pattern is like using a switchboard - you can change the wiring by updating a JSON file, without touching or redeploying your application code.

You still have static routing principles - the decision is deterministic and rule-based - but your rules are externalized.

This approach decouples your routing logic from your business logic by storing your routing rules in an external configuration file.

**How it works in 3 steps:**

**1. Load Rules at Startup:** The `ConfigurableStaticRouter` loads a JSON configuration that contains an ordered list of `routing_rules` and a `default_model`. On AWS, we don't load this from local disk in production, we load it from **AWS AppConfig or Systems Manager Parameter Store** for versioning and dynamic updates.

**2. Evaluate Metadata with `matches_criteria`:** Instead of routing on a single `request_type`, you route on rich metadata. The method checks if ALL key-value pairs in a rule's `criteria` match the incoming `input_data`. For example, does `department == technical` AND `priority == high`?

**3. Route and Invoke with Fallback:** The `route_by_metadata` method iterates through the rules in priority order. The first rule that matches wins. If no rules match, it safely falls back to `default_model`. This guarantees every request gets a model. Then `invoke_selected_model` calls Amazon Bedrock.

This is still **static routing** because there is no AI model making the routing decision - it's a deterministic dictionary comparison.

#### Corrected and Production-Ready Implementation

Your original code has two small issues - `init` should be `__init__` and indentation. Here is the refined version we use:

**routing_config.json - Your External Rulebook**
```json
{
  "routing_rules": [
    {
      "criteria": {"department": "technical", "priority": "high"},
      "model_id": "anthropic.claude-3-opus-20240229-v1:0",
      "reason": "Highest reasoning for critical tech issues"
    },
    {
      "criteria": {"department": "sales"},
      "model_id": "anthropic.claude-3-sonnet-20240229-v1:0",
      "reason": "Balanced for sales conversations"
    }
  ],
  "default_model": "anthropic.claude-3-haiku-20240307-v1:0"
}
```

**Python Router**

```python
import json
import boto3
from typing import Dict, Any

class ConfigurableStaticRouter:
    def __init__(self, config_path: str, region_name="us-east-1"):
        # In production, replace file open with AppConfig call
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        self.bedrock = boto3.client('bedrock-runtime', region_name=region_name)

    def route_by_metadata(self, input_data: Dict[str, Any]) -> str:
        """Iterates rules in order and returns first matching model_id"""
        for rule in self.config['routing_rules']:
            if self.matches_criteria(input_data, rule['criteria']):
                return rule['model_id']
        # Fallback - ensures 100% availability
        return self.config['default_model']

    def matches_criteria(self, input_data: Dict[str, Any], criteria: Dict[str, Any]) -> bool:
        """True only if ALL criteria key-values match input_data"""
        for key, expected_value in criteria.items():
            if input_data.get(key) != expected_value:
                return False
        return True

    def invoke_selected_model(self, model_id: str, prompt: str) -> Dict[str, Any]:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}]
        })
        response = self.bedrock.invoke_model(
            body=body,
            modelId=model_id,
            accept='application/json',
            contentType='application/json'
        )
        return json.loads(response.get('body').read())

# --- Usage Example ---
router = ConfigurableStaticRouter(config_path="routing_config.json")

# This metadata could come from API Gateway headers or a CRM system
request_metadata = {"department": "technical", "priority": "high", "user_id": "123"}
prompt = "Production database is down, need RCA steps"

model_to_use = router.route_by_metadata(request_metadata)
# Returns: anthropic.claude-3-opus-20240229-v1:0 because it matches first rule

request_metadata_2 = {"department": "support", "priority": "low"}
model_to_use_2 = router.route_by_metadata(request_metadata_2)
# Returns: anthropic.claude-3-haiku-20240307-v1:0 -> fallback to default_model

result = router.invoke_selected_model(model_to_use, prompt)
```

**Why this is better for enterprise:**

1.  **No Code Deploy for Model Changes:** To swap `claude-3-sonnet` to `claude-3.5-sonnet`, you just update `routing_config.json` in AppConfig. Lambda picks it up instantly.
2.  **Business-Friendly Rules:** Your product team can manage the JSON based on business logic like `department` and `priority`, without needing to understand Python.
3.  **Deterministic and Auditable:** Rules are evaluated top-to-bottom. You always know why a request went to a specific FM, which is critical for governance and CloudWatch cost allocation.

---
