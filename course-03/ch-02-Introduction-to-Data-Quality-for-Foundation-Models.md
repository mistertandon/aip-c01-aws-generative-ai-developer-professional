https://www.meta.ai/prompt/85d4b02f-fffc-42cd-8825-748c47a3a1f1

---
---

### 1. Why Data Quality is Non-Negotiable for Foundation Models

Foundation Models are only as good as the data you feed them. High-quality input is essential for generating outputs that are accurate, relevant, and reliable. In a production system on AWS, poor data quality is the #1 cause of hallucinations, bias, and unpredictable behavior.

On **Amazon Bedrock**, we see input data in three distinct forms. You need a quality strategy for all three:

**A. Prompts - The Direct Instructions**
What the user asks or the system instruction you send to the model.
> *Quality means:* Clear, specific, well-structured, and free of ambiguity, PII leakage, or prompt injection.

**B. Retrieved Information - The External Context**
This is the data you pull from outside the model to ground its answer, typically in a **RAG - Retrieval-Augmented Generation - workflow**. This comes from your **Vector Database** like **Amazon OpenSearch Serverless, Aurora PostgreSQL with pgvector, or S3 Vectors**.

> *Quality means:* Fresh, accurate, relevant, properly chunked, and with rich metadata. A 2022 price list retrieved for a 2026 question is technically data, but it's poor quality data.

**C. Fine-tuning Datasets - The Domain Knowledge**
The curated datasets you use to adapt a base model to your specific domain using **Amazon Bedrock Custom Model fine-tuning / import**.

> *Quality means:* Labeled accurately, diverse, de-biased, and representative of real production scenarios. 100 high-quality examples beat 10,000 noisy ones.

During **inference**, if your prompt is vague or your retrieved context is irrelevant, the model will either hallucinate, misunderstand intent, or fail safely. Garbage In, Garbage Out is amplified in generative AI.

### 2. Production-Level Example on AWS: How We Architect for Quality

Let's take a real-world customer I work with: **A large Insurance company building an Intelligent Claims Assistant on Bedrock.**

**Architecture:**
`User -> API Gateway -> Lambda -> Bedrock Guardrails -> Knowledge Bases for Bedrock [OpenSearch Serverless] -> Bedrock Model [Anthropic Claude 3.5 Sonnet / Amazon Nova Pro] -> Response`

Here's how data quality shows up at each layer:

**Scenario 1: Poor Retrieval Quality -> Wrong Answer**
User asks: *"Is my Honda City 2023 claim covered under flood?"*
If the Knowledge Base ingested old policy PDFs without metadata filtering and retrieves a 2019 policy document, Claude will generate a confident but incorrect answer. The model was fine, the retrieval quality was poor.

**Architected Solution on AWS:** We implement a quality pipeline:
1.  Ingest with **Bedrock Data Automation** to intelligently parse, chunk, and extract metadata (policy_year, product_type) from unstructured PDFs in S3.
2.  Use **Knowledge Bases for Bedrock** with metadata filtering to only retrieve `policy_year=2023 AND product_type=Auto`.
3.  Apply **Bedrock Guardrails** to validate prompt quality - block PII, detect toxic prompts, and ensure the question is in-domain before it hits the model.

**Scenario 2: Poor Fine-Tuning Data -> Biased Model**
Same insurer fine-tunes **Meta Llama 3 on Bedrock** for claim summarization using historical adjuster notes that contain inconsistent language and bias. The fine-tuned model learns and replicates that bias.

**Architected Solution on AWS:** We use **Amazon Bedrock Model Evaluation** to run automated evaluation jobs comparing the base model vs. fine-tuned model on accuracy, helpfulness, and bias metrics using a curated golden dataset stored in S3. We also use **AWS Glue DataBrew + Deequ** to profile and clean the fine-tuning dataset before training.

### 3. Business Impact of Data Quality

From an architect's perspective, this is how I map data quality to business KPIs:

*   **Response Accuracy:** High-quality, relevant context reduces hallucinations and grounds the answer in truth. This is directly measured by RAG evaluation metrics like faithfulness and answer relevance.
*   **Model Reliability & Predictability:** Consistent data quality means consistent model behavior. In production, this means fewer escalations and fewer Guardrail interventions.
*   **User Experience & Trust:** Trustworthy AI applications drive adoption. Users abandon an assistant after 2-3 bad answers.
*   **System Performance & Cost:** Clean, well-chunked data means fewer tokens retrieved, lower latency, and lower **Bedrock** inference cost. Poor data leads to larger context windows and retry loops.

### 4. Architect's Recommendation: Model Selection Matters

**Amazon Bedrock offers 100+ fully managed and serverless models from Amazon Nova, Anthropic Claude, Meta Llama, Mistral, Cohere, and AI21 Labs**, including open-weight models you can customize.

This choice is a data quality lever. Different models have different tolerance levels:

*   For noisy, user-generated prompts, choose a model with strong instruction-following and reasoning like **Claude 3.5 Sonnet** and front it with **Bedrock Guardrails**.
*   For RAG where retrieval might be imperfect, choose **Amazon Nova Pro or Mistral Large**, which are highly resilient to imperfect context.
*   For domain-specific tasks where you have very high-quality fine-tuning data, a smaller, fine-tuned model like **Llama 3 8B** can outperform a larger general-purpose model at 1/10th the cost and latency.

**Architect's Rule:** Don't just fix the model. Fix the data pipeline first, then select the model whose sensitivity to data quality matches your use case. Build your validation pipeline with Bedrock Guardrails for prompts and Knowledge Bases data source sync validation for retrieval.

> Good data quality isn't a one-time cleanup task. On AWS, we architect it as a continuous evaluation loop: Ingest -> Validate -> Retrieve -> Generate -> Evaluate.

---
---

### Common Data Quality Challenges in Production

In production on **Amazon Bedrock**, we see 6 recurring data quality patterns that directly degrade Foundation Model performance. If you don't architect for them, they will show up as hallucinations, high cost, and poor user trust.

Think of it as: **Inference Quality = Model Capability x Data Quality**. If data quality is 0, your output is 0.

Let me break down each one with a real production fix.

#### 1. Incomplete Data
**What it is:** Missing values, partial records, or fields that were never captured. When context is missing, the FM is forced to assume or hallucinate.

**Prod Example:** We built a **RAG-based Customer Support Agent for a leading Indian E-commerce company on Bedrock**. Their Knowledge Base had product specs from S3. For 30% of products, the `warranty_period` field was null because the legacy PIM system didn't enforce it. When users asked "What is warranty for OnePlus Nord?", the model retrieved incomplete records and guessed "1 year".

**How we fix it on AWS:**
*   At ingestion, use **Bedrock Data Automation** to automatically parse and extract missing attributes from unstructured manuals and images.
*   In your ETL pipeline, use **AWS Glue DataBrew** to profile and flag null rates before embedding.
*   At retrieval, use **Knowledge Bases for Bedrock** with metadata filtering + **Bedrock Guardrails** to block responses when critical fields are missing, instead of hallucinating.

#### 2. Inconsistent Data Formats
**What it is:** Same entity, different representation across sources. FMs are pattern matchers - inconsistent schemas confuse the attention mechanism.

> Examples: `12/05/2026` vs `2026-05-12T00:00:00Z`, `weight: 50 lbs` vs `weight: 22.6 kg`, `cust_name` vs `customerName`.

**Prod Example:** For a **BFSI client building an Investment Research Assistant** using **Claude 3.5 Sonnet on Bedrock**, we ingested SEC filings, Bloomberg feeds, and internal Excel sheets. Date and currency formats were all different. The vector embeddings for "Revenue $10M" and "Revenue 10,000,000 USD" were far apart, so retrieval failed.

**How we fix it on AWS:** Standardize BEFORE you embed.
*   Create a normalization Lambda in your ingestion pipeline: Convert all dates to ISO-8601, all currencies to a base unit.
*   Use **Bedrock Data Automation's custom blueprint** to define a single schema for extraction.

#### 3. Outdated Information
**What it is:** Stale data that was accurate once but is now wrong. This is the #1 cause of irrelevant RAG answers in production.

**Prod Example:** An Airline's **Bedrock Agent** for flight policies. Their baggage policy was updated in Jan 2026 from 15kg to 20kg, but the S3 data source for Knowledge Bases was last synced in Nov 2025. The agent was confidently giving the old policy.

**How we fix it on AWS:**
*   Architect for freshness. Use **Knowledge Bases for Bedrock - S3 Sync with automatic refresh** - schedule it hourly/daily based on your SLA.
*   Add `last_updated_date` as metadata and use metadata filtering in retrieval to boost recent documents.
*   Implement a TTL logic: `If document_age > 90 days, add system prompt: "Verify this information may be outdated"`.

#### 4. Data Duplication
**What it is:** Exact duplicates, near-duplicates, or semantically similar records. Duplicates skew embeddings and cause the model to over-weight that information.

> Exact: Same PDF uploaded twice.
> Semantic: "How to reset password?" and "Procedure for password reset" - two different docs with same intent.

**Prod Example:** Same e-commerce client had the same return policy in 5 places - website, PDF, FAQ doc, Confluence. After chunking, we had 120 vector chunks saying the same thing. The **OpenSearch Serverless vector search** returned 5 identical chunks in top-5 results, wasting context window and cost.

**How we fix it on AWS:**
*   **Exact dedup:** Use S3 object hash + Glue.
*   **Semantic dedup:** This is critical. During ingestion, generate embeddings using **Amazon Titan Embeddings V2** and run a cosine similarity check. If similarity > 0.95, drop the duplicate chunk. We automate this in a Lambda step before writing to OpenSearch.

#### 5. Encoding and Character Issues
**What it is:** Incorrect character encoding - UTF-8 vs Latin-1, broken emojis, HTML artifacts `&nbsp;`, OCR errors. This breaks tokenization.

**Prod Example:** A UAE-based customer had support tickets in Arabic, English, and Hindi mixed with emojis. Data was ingested as `ISO-8859-1` instead of `UTF-8`. `مرحبا` became `Ù…Ø±Ø­Ø¨Ø§`. **Nova and Llama** models failed to understand it, increasing token count by 3x.

**How we fix it on AWS:**
*   Enforce UTF-8 at source. In your Glue / Lambda parser, add `chardet` library to detect and convert.
*   Clean HTML artifacts and add a text cleaning step in **Bedrock Data Automation**.
*   Test with multilingual evaluation using **Bedrock Model Evaluation** with multilingual datasets.

#### 6. Data Bias
**What it is:** Historical bias, sampling bias, or under-representation in data that FMs amplify. This is a reliability and Responsible AI risk.

**Prod Example:** A tech hiring assistant fine-tuned on historical resumes. 80% of resumes were male engineers. When asked to "summarize a good candidate", the fine-tuned model consistently used "he/him" pronouns and prioritized male-coded language.

**How we fix it on AWS:**
*   Before fine-tuning on **Bedrock Custom Models**, profile your dataset with **SageMaker Clarify** to detect bias on attributes like gender, location.
*   Curate a balanced golden dataset for evaluation.
*   At inference, use **Bedrock Guardrails** - Enable bias and fairness filters, and use **Bedrock Model Evaluation** to measure bias metrics across demographics.
*   Implement Human-in-the-loop with **Bedrock Human Evaluation**.

### Architect's Checklist for Your Bedrock Pipeline

For any production workload, I mandate this:

| Challenge | AWS Control to Implement |
| :--- | :--- |
| Incomplete | DataBrew profiling + Guardrails - block on missing critical context |
| Inconsistent | Bedrock Data Automation blueprint + Normalization Lambda |
| Outdated | Knowledge Bases auto-sync + metadata `last_updated_date` filtering |
| Duplication | Titan Embeddings semantic dedup with threshold |
| Encoding | UTF-8 enforcement + HTML cleaning |
| Bias | SageMaker Clarify + Bedrock Evaluation + Guardrails |

**Final Architect Insight:** Don't try to solve all 6 after you build the RAG app. Solve them in the ingestion pipeline, before the vector is created. On Bedrock, 80% of production issues I see are not model issues, they are data quality issues in the Knowledge Base.

---
---

### Key Quality Dimensions: The 4-D Validation Framework

For a Foundation Model on **Amazon Bedrock**, data quality is not a feeling, it's a measurable framework. In production, we validate every dataset that feeds the model on 4 dimensions: **Completeness, Accuracy, Consistency, and Timeliness.** If one fails, your outputs fail.

I tell my customers: Build this validation gate *before* you create embeddings, not after.

Let me break down each dimension with how we implement it on AWS.

#### 1. Assess Completeness - "Do we have everything the model needs?"

**In plain English:** Is all the required information present? We check two things.

*   **Structural Completeness:** Are all expected fields/columns present? e.g., does every product record have `price, specs, warranty`?
*   **Value Completeness:** Are the values inside those fields not null or empty? e.g., `warranty` field exists but is blank for 40% records.

You must define thresholds. A chatbot can tolerate 5% missing warranty info, but a claims processing agent cannot tolerate 5% missing `policy_number`.

**Prod Example on Bedrock:**
A customer built a **Loan Underwriting Assistant using Knowledge Bases for Bedrock + Claude 3.5 Sonnet**. Their S3 data had 100k loan applications. 22% were missing `credit_score`. The model started hallucinating scores to complete the analysis.

**How we fix it on AWS:**
*   Use **AWS Glue DataBrew + Deequ** to profile the dataset and generate a completeness scorecard: `completeness(credit_score) = 0.78`. Set a rule: If < 0.95, fail the ingestion pipeline.
*   Use **Bedrock Data Automation** to intelligently extract missing fields from scanned documents to fill gaps before embedding.
*   In **Knowledge Bases for Bedrock**, configure a metadata filter to not retrieve documents where `completeness_score < threshold`.

#### 2. Verify Accuracy - "Is the data correct in the real world?"

**In plain English:** Does the data represent reality? Is it true?

> Technical checks: Is the email in valid format? Is `order_date` not in the future? Is `pincode` a real pincode? Is `price = -500` an impossible outlier?

We validate against known standards, authoritative sources, and anomaly detection.

**Prod Example on Bedrock:**
For a **Retail Product Search Assistant on Bedrock using Amazon Nova Pro**, the catalog had prices like `iPhone 15 - Rs. 1,200` due to manual entry error. The vector search retrieved it, and Nova confidently recommended a flagship phone for Rs. 1,200, creating a business incident.

**How we fix it on AWS:**
*   Implement validation rules in your ingestion Lambda: Regex for emails, range checks `0 < price < 500000`, date logic.
*   Cross-reference with an authoritative source - e.g., master product catalog in **Aurora PostgreSQL**.
*   Use **Bedrock Guardrails** with Contextual Grounding Check to detect if the model's answer is not supported by the retrieved accurate data, and block it.

#### 3. Confirm Consistency - "Is the data speaking the same language?"

**In plain English:** Does data from different sources follow the same standards, formats, and conventions? FMs get confused by inconsistent patterns.

> This includes format standardization `MM/DD/YYYY -> YYYY-MM-DD`, unit normalization `lbs -> kg`, and schema alignment `cust_id vs customer_id`.

**Prod Example on Bedrock:**
For a **Global Airline's Bedrock Agent** handling baggage, US sources sent weight as `50 lbs`, India sources sent `23 kg`, and the website said `23Kgs`. The embeddings were different, so the agent couldn't answer "What is my baggage limit?" consistently.

**How we fix it on AWS:**
*   Establish a **Golden Schema** in **AWS Glue Data Catalog**.
*   Build a normalization step using Lambda: `standardize_date()`, `convert_to_kg()`, `lowercase_and_trim()`.
*   Use **Bedrock Data Automation Blueprints** to force all unstructured PDFs, images, and docs into that single, consistent JSON schema before they go to **OpenSearch Serverless**.

#### 4. Evaluate Timeliness - "Is the data fresh enough for this use case?"

**In plain English:** Is the data current enough? Freshness requirements depend on your use case.

> Real-time trading assistant = needs data in seconds.
> HR policy assistant = can tolerate data that is 30 days old.

Define a freshness SLA and alert when data becomes stale.

**Prod Example on Bedrock:**
An **Investment Research Assistant for a BFSI firm using Bedrock Knowledge Bases** was answering questions about Q2 earnings using Q1 reports because the S3 sync was manual and last ran 2 months ago.

**How we fix it on AWS:**
*   Define freshness: e.g., `earnings_reports freshness SLA = 24 hours`.
*   Implement it: Enable **automatic sync for Knowledge Bases for Bedrock S3 data source** with EventBridge trigger on new S3 upload.
*   Add metadata `ingestion_timestamp` to every vector. At query time, boost recency in OpenSearch or filter `ingestion_timestamp > now() - 24h`.
*   Monitor staleness with **CloudWatch Metrics + Alarms**: If `time_since_last_sync > SLA`, trigger an alert and show a disclaimer in the UI: "Data last updated 45 days ago".

### Architect's Production Blueprint on Bedrock

In production, I never let raw data go straight to the vector DB. We build a **Data Quality Gate**:

**S3 Raw Data -> [Glue DataBrew + Deequ: Check Completeness, Accuracy, Consistency] -> Bedrock Data Automation [Standardize + Extract] -> Lambda [Semantic Dedup + Freshness Tag] -> OpenSearch Serverless / S3 Vectors -> Bedrock Knowledge Bases -> Bedrock Guardrails -> FM**

And we continuously measure it with **Bedrock Model Evaluation** to track if quality drops over time cause accuracy drops.

**Bottom line:** Completeness asks *Do we have it?*, Accuracy asks *Is it true?*, Consistency asks *Is it uniform?*, Timeliness asks *Is it fresh?* - If you can answer YES to all four with metrics in CloudWatch, your Bedrock application will be reliable in production.

---
---

### Impact on Foundation Model Performance

On **Amazon Bedrock**, data quality directly determines 3 things your business cares about: **What the model says, How the model behaves, and Whether your system stays up.** All three directly impact user trust and operational cost.

Think of it as a chain reaction: **Bad Data -> Bad Response -> Unpredictable Behavior -> System Failure.**

Let's break down each tab with a production view.

#### 1. Response Quality - "What the user actually sees"

**In plain English:** If you feed the model inaccurate, incomplete, or inconsistent data, it will generate unreliable, misleading answers. This is where hallucinations come from.

High-quality data = relevant, accurate, and useful answers. Low-quality data = confident but wrong answers.

**Technical impact:** Poor retrieval in RAG lowers **faithfulness and answer relevance scores**. Poor prompts lower intent understanding.

**Prod Example on AWS:**
We deployed a **Claims Policy Assistant for an Insurance company using Knowledge Bases for Bedrock + Claude 3.5 Sonnet on OpenSearch Serverless.**

**Before Quality Fix:** Their Knowledge Base had two conflicting documents: `policy_v1.pdf` saying "flood damage not covered" and `policy_v3.pdf` saying "flood damage covered with add-on". No metadata, no versioning. When user asked "Is flood covered?", retrieval returned the old v1 chunk. Claude answered confidently: "No, not covered." - Wrong answer, customer escalated.

**After Quality Fix:** We implemented:
*   **Bedrock Data Automation** to extract `policy_version` and `effective_date` as metadata.
*   Knowledge Base retrieval with **metadata filtering + reranking** to always prefer latest version.
*   **Bedrock Guardrails - Contextual Grounding Check** to block answers not grounded in retrieved data.

**Result:** Response relevance went from 68% to 94% in **Bedrock Model Evaluation**.

#### 2. Model Behavior - "How predictable is your AI?"

**In plain English:** Inconsistent data causes the same question to get different answers, random errors, or unexpected formatting. Users can't trust it for important decisions.

Quality data gives you stable, predictable behavior. Poor data gives you a model that works on Monday and fails on Tuesday.

**Technical impact:** This shows up as high variance in latency, increased **Bedrock Guardrail interventions**, parsing errors in **Bedrock Agents** function calling, and inconsistent output format breaking downstream apps.

**Prod Example on AWS:**
A **BFSI client built a Bedrock Agent for KYC with function calling** to `get_customer_details` and `verify_pan`. Their customer data in Aurora had inconsistent formats - `PAN: ABCDE1234F` in one table and `pan_no: abcde 1234 f` in another.

When the Agent tried to call the function, sometimes the parameter was invalid, the Lambda failed, and the Agent returned: "Sorry, I encountered an error processing your request." Same user query, 50% failure rate.

**How we fixed it on AWS:**
*   Created a normalization layer in **AWS Glue** that standardizes PAN, Aadhaar, and phone formats before indexing.
*   Added strict **input schema validation in the Bedrock Agent's Action Group** Lambda.
*   Used **CloudWatch Logs Insights + X-Ray** to track unpredictable behavior and correlate it to inconsistent data patterns.

**Result:** Agent action success rate went from 52% to 98%, behavior became deterministic.

#### 3. System Reliability - "Will your AI stay up at 2 AM?"

**In plain English:** A small data quality issue doesn't stay small. It cascades. A broken encoding in one document can fail the entire ingestion job, which makes your Knowledge Base stale, which makes your chatbot give wrong answers, which floods your support team.

Robust data validation prevents failures *before* they reach the user. Without it, you spend your time firefighting data issues, not improving the product.

**Technical impact:** Ingestion pipeline failures, vector DB index corruption, increased token usage and cost due to noisy context, downstream app crashes due to malformed JSON output.

**Prod Example on AWS:**
A **Global E-commerce client running a Product Recommendation Assistant on Bedrock** ingested 2M product descriptions daily from S3 to S3 Vectors.

One day, a supplier uploaded 10k products with broken UTF-8 characters and HTML tags like `<div>&nbsp;&&&&&`. The chunking Lambda failed, the **Knowledge Bases sync job** failed halfway, leaving the vector index in a partially updated state. The Bedrock application started returning incomplete results, and the sync job kept retrying, increasing cost and operational overhead.

**How we architect for reliability on AWS:**
*   **Fail-fast validation:** In ingestion Lambda, validate encoding and schema. Quarantine bad records to an S3 DLQ - Don't fail the whole batch.
*   **Bedrock Knowledge Bases** with automatic retry and drift detection.
*   **Monitoring:** CloudWatch Alarm on `IngestionFailureRate` and `GuardrailInterventionRate`. If it spikes, we auto-pause sync via EventBridge.
*   **Data Quality as Code:** Use **Deequ on Glue** to define quality gates - `completeness > 0.95, accuracy > 0.98` - if gate fails, pipeline stops before it pollutes the production index.

**Result:** Mean Time to Recovery went from 4 hours to 15 minutes. System reliability moved from 96.5% to 99.9%.

### Architect's Summary

| Dimension | What Business Sees | What We Measure on Bedrock | Data Quality Fix |
| :--- | :--- | :--- | :--- |
| **Response Quality** | Wrong / Hallucinated answer | Faithfulness, Relevance in Bedrock Evaluation | Clean, versioned, grounded retrieval |
| **Model Behavior** | Unpredictable, sometimes fails | Guardrail interventions, Agent success rate, latency variance | Consistent formats, schema validation |
| **System Reliability** | System down, ops team paged | Ingestion failure rate, Index freshness, MTTR | Validation gates + DLQ + CloudWatch alarms |

**My rule for production:** You can't prompt-engineer your way out of bad data. On Bedrock, build a data quality firewall with Bedrock Data Automation and Guardrails *before* the model, and a reliability observability layer with CloudWatch *after* the model.

---
---

### Building a Data Quality Mindset for Generative AI

In production GenAI, effective data quality is not an optional enhancement - it's a **fundamental requirement**, just like security and cost. You need a proactive mindset: treat every piece of data that enters **Bedrock Knowledge Bases** or a fine-tuning job as production code.

This mindset is about shifting from **"fix it when it breaks"** to **"prevent it from breaking"**, through continuous monitoring, validation, and improvement across the entire data lifecycle: **Ingest -> Validate -> Embed -> Retrieve -> Generate -> Evaluate.**

#### The 4 Principles We Enforce on Every Bedrock Production Workload

**1. Prevention Over Correction: Design quality in, don't patch it later**

**In plain English:** It's 100x cheaper to stop bad data at the door than to debug a hallucination at 2 AM.

Instead of fixing bad outputs, we build systems that prevent bad inputs.

**Prod Example:**
For a **large BFSI bank building a Bedrock Agent for customer onboarding**, they initially allowed any PDF to be uploaded to S3 for their Knowledge Base. 40% of PDFs were scanned images with poor OCR, causing bad embeddings.

We changed the mindset to prevention:
*   Implemented **Data Contracts** using **Amazon DataZone**: Business teams must publish data with a defined schema - `pan_number: valid format, doc_type: KYC, effective_date: ISO-8601`.
*   Used **Bedrock Data Automation with Blueprints** to reject documents that don't match the contract at ingestion itself, sending them to a quarantine bucket with a reason.
*   Added **Bedrock Guardrails** at the prompt layer to prevent PII leakage and prompt injection *before* it hits **Claude 3.5 Sonnet**.

**Result:** Prevention gate blocked 35% bad documents on Day 1, instead of those documents corrupting the vector index.

**2. Continuous Monitoring: Data quality is not a one-time check**

**In plain English:** Data quality decays over time. Your Knowledge Base that was perfect today will be stale, incomplete, and inconsistent in 30 days without monitoring.

One-time validation is a demo. Continuous monitoring is production.

**Prod Example:**
Same bank's loan policy changed weekly. Their RAG assistant was giving old interest rates.

**How we fixed it on AWS:**
*   Automated quality checks with **AWS Glue Deequ + Lambda**: Every 6 hours, calculate **completeness, accuracy, freshness scores**.
*   **CloudWatch Metrics & Alarms**: We publish custom metrics like `KnowledgeBaseFreshnessHours` and `IngestionFailureRate`. If `Freshness > 24h`, EventBridge triggers a re-sync and sends a Slack alert.
*   **Bedrock Model Evaluation - Automated Jobs**: Weekly automated evaluation on faithfulness and relevance. If score drops below 90%, we know data quality has degraded.

**3. Stakeholder Involvement: Data quality is a team sport**

**In plain English:** The engineering team alone cannot define what "good data" means. You need the people who *create* the data, *use* the data, and *own* the business outcome.

> **Data Producers** (Business/Ops teams): Know what is correct.
> **Data Consumers** (App/AI teams): Know what is needed for the model.
> **Business Stakeholders**: Define what is acceptable for customer trust.

**Prod Example:**
In that bank, IT defined quality as "no nulls". But the Compliance team defined quality as "every policy document must have RBI circular reference and approval ID". Without compliance, the data was technically complete but business-invalid.

**How we fix it on AWS:**
*   Used **Amazon DataZone** to create a business glossary - what is a "valid KYC document" is defined by Compliance, not just IT.
*   Created a **Data Quality Council**: Monthly review of **Bedrock Guardrails** block rates and Evaluation reports with tech, business, and risk teams.
*   End users provide feedback via thumbs down -> that feedback flows to S3 and is used as a quality signal.

**4. Quality Metrics: You can't improve what you don't measure**

**In plain English:** Define measurable SLAs for data quality and track them like you track application uptime.

**Prod Example - Our Dashboard for the Bank:**

| Quality Metric | SLA Definition | AWS】 Implementation |
| :--- | :--- | :--- |
| **Completeness** | `credit_score` field > 98% filled | Deequ check in Glue before embedding |
| **Accuracy** | PAN format valid > 99.5% | Regex validation in Bedrock Data Automation Lambda |
| **Consistency** | All dates in ISO-8601 | Glue DataBrew normalization recipe |
| **Timeliness** | Knowledge Base lag < 6 hours | CloudWatch metric `TimeSinceLastSuccessfulSync` |
| **Relevance** | RAG faithfulness > 92% | Bedrock Model Evaluation scheduled job |

We displayed this dashboard in QuickSight, visible to both CTO and Business Head.

### Architect's Takeaway: From Project to Product

Successful GenAI initiatives fail when they treat data quality as a project phase. We make it a product lifecycle:

**Define in DataZone -> Prevent at Ingestion with Data Contracts & Data Automation -> Monitor with CloudWatch & Deequ -> Measure with Bedrock Evaluation -> Improve with Stakeholder Feedback Loop.**

**My rule for customers in Gurugram and globally:** If you are spending 80% time on prompt engineering and only 20% on data quality, flip it. On Bedrock, high-quality data lets even a smaller model like **Nova Lite or Llama 3 8B** beat a large model fed with poor data, at 1/5th the cost and latency.

Mindset first, pipeline second, model last.

---
---
