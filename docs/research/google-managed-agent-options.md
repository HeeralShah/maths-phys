# Google agent options for chapter preparation

Status: recommendation based on first-party documentation, reviewed 2026-11-01. No credentialed or paid call was made.

## Decision

Build the study agent with the **Google Agent Development Kit (ADK)** and deploy it as our own application on **Gemini Enterprise Agent Platform Agent Runtime**. The local application should invoke the deployed `ReasoningEngine` resource through a narrow provider adapter, send the selected chapter as a native PDF, and accept only a provider-neutral, locally validated edition artifact.

Do **not** use an AI Studio/Gemini API “Custom Agent” as the production agent. In that product, “custom” means a saved or inline configuration layered over Google's prebuilt Antigravity managed agent. It is not an arbitrary ADK application, and that agent currently rejects the `document` input modality. [Google's Custom Agents page](https://aistudio.google.com/docs/custom-agents) says it extends the Antigravity agent; the [Agents overview](https://aistudio.google.com/docs/agents) lists ADK and the Antigravity SDK separately as agent frameworks.

Also do not confuse either of those with the newer **`google-antigravity` Python SDK**. That SDK is a promising harness, but it is currently an alpha, platform-specific package containing a compiled runtime. Google now provides a Preview ADK Labs wrapper that makes an Antigravity SDK configuration an ADK `BaseAgent`; however, the wrapper page does not itself establish an Agent Runtime deployment/support contract. ADK has the documented managed deployment lifecycle and is therefore the production foundation while the wrapper remains a focused compatibility experiment.

## The products with similar names

| Product | What it actually is | Native PDF | Managed deployment | Decision |
|---|---|---:|---:|---|
| Gemini API managed “Custom Agent” | A configuration of the prebuilt `antigravity-preview-09-2026` harness, saved by ID or supplied inline | No: Antigravity accepts text/images and lists documents as unsupported | Google-hosted managed agent, Public Preview | Reject for chapter preparation |
| Google ADK + Agent Runtime | Our Python agent code, tools and orchestration deployed as a `ReasoningEngine` | Yes, through Gemini document input or ADK artifacts | Fully managed Agent Runtime, with feature maturity varying by capability | Adopt |
| `google-antigravity` Python SDK | A programmable agent harness using Antigravity's loop, tools and context management | Yes, including document attachments | Preview ADK Labs wrapper exists; Agent Runtime deployment still needs a compatibility test | Trial candidate, not production dependency |
| Gemini File Search | A hosted retrieval/indexing tool, not an agent runtime | Imports PDFs and other files for retrieval | Hosted File Search stores | Optional retrieval accelerator only |

### AI Studio/Gemini API Custom Agents

The current documentation calls the feature “Building managed agents.” Every definition has `base_agent="antigravity-preview-09-2026"` or invokes that agent inline. Instructions, `AGENTS.md`, skills, files, custom functions and remote MCP servers customize the supplied harness; they do not replace its execution loop with our code. Saved agents are invoked by an agent ID through the Gemini Interactions API. A fresh sandbox is created for an invocation, and `previous_interaction_id` supplies conversational continuation. See [Building managed agents](https://aistudio.google.com/docs/custom-agents) and [Agents overview](https://aistudio.google.com/docs/agents).

That surface is useful for autonomous file-and-code tasks, but it fails a hard requirement here: the [Antigravity agent documentation](https://aistudio.google.com/docs/antigravity-agent) lists only text and image input and explicitly lists document/PDF input as unsupported. It also lacks the same constrained structured-output contract used by direct Gemini generation. Converting a PDF into page screenshots just to fit this API would discard the native document path the user asked for.

There is no documented conversion, shared deployment resource or automatic interoperability between a saved Gemini API managed agent and an ADK `ReasoningEngine`. They can use related Gemini models and tool concepts, but their agent definitions, session APIs, billing surfaces and runtime controls are distinct.

### ADK on Agent Runtime

[Agent Runtime](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime) is Google's fully managed runtime for deploying and scaling agentic applications. It has first-class ADK integration, supports custom containers and other frameworks, and exposes deployed agents as resources whose API name remains `ReasoningEngine` for compatibility. The [ADK quickstart](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk) builds an ADK agent, wraps it as an `AdkApp`, deploys it, and queries it.

The current client lifecycle is:

1. Define the agent, its sub-agents, callbacks, output schema and tools in an ADK package.
2. Deploy a revision to Agent Runtime. Keep an offline chapter-preparation resource/revision separate from a research-enabled resource/revision.
3. The local app obtains the deployed resource with `agentplatform.Client(...).runtimes.get(name=".../reasoningEngines/...")`.
4. For bounded work, call `async_stream_query` with a user ID, optional managed session ID and a Gemini `Content` message. The service's streaming request has a ten-minute maximum. For longer chapter jobs, Google documents long-running query jobs lasting up to seven days, but that path writes the query and result to a configured GCS location and requires corresponding service-agent permissions. It therefore needs an explicit private-bucket retention/deletion design rather than being a silent fallback. See [Use an ADK agent](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/use-an-adk-agent).
5. Collect usage-bearing events, extract the final provider-neutral JSON artifact, validate it locally, and only then publish the complete chapter edition.

Cloud sessions improve multi-turn continuity but are not durable study state. SQLite, Markdown and source files remain authoritative; reopening a chapter must not depend on recovering a cloud conversation.

### The separate Antigravity Python SDK

Google now publishes `pip install google-antigravity`. Its [product page](https://antigravity.google/product/antigravity-sdk) says it exposes the same tools, agent loop and context management as Antigravity and supports custom Python callables, MCP servers, reusable skills, and multimodal files including documents. The [official repository](https://github.com/google-antigravity/antigravity-sdk-python) documents document attachments, Vertex endpoint authentication, sub-agents, hooks and policies. It also supports native structured output through a Pydantic `response_schema` and `ChatResponse.structured_output()`; see Google's [structured-output example](https://github.com/google-antigravity/antigravity-sdk-python/blob/main/examples/getting_started/structured_output.py). Its [changelog](https://github.com/google-antigravity/antigravity-sdk-python/blob/main/google/antigravity/CHANGELOG.md) documents session `BudgetConfig` limits for model calls, tool calls, input/output/total tokens, explicit stop reasons, sub-agent controls and beta workflow primitives. These features fit the requested harness unusually well.

There is real ADK interoperability. Google's Preview [`AntigravityAgent` ADK Labs guide](https://github.com/google/adk-python/blob/main/docs/guides/labs/antigravity/index.md) wraps an Antigravity SDK `AgentConfig` as a standard ADK `BaseAgent`, streams its trajectory as ADK events, and can bridge ADK child agents as tools. This means “ADK or Antigravity SDK” is not necessarily an exclusive choice: an ADK application can use an Antigravity-powered node. It does **not** mean the Gemini API saved Custom Agent is involved.

There are material production risks:

- The package metadata currently labels it **Alpha** (`Development Status :: 3 - Alpha`). [pyproject.toml](https://github.com/google-antigravity/antigravity-sdk-python/blob/main/pyproject.toml)
- Its wheel embeds a compiled `localharness` runtime; cloning the Apache-licensed Python repository is not sufficient to run it. The executable boundary makes behavior, portability and debugging more dependent on Google's release cadence.
- “Use with Gemini Enterprise Agent Platform” in the SDK README describes authenticating model access through Vertex endpoints; endpoint routing is not itself managed deployment.
- The ADK Labs wrapper proves an official code-level seam, but it is marked Preview, opens a fresh SDK agent for each turn, relies on stored conversation IDs/directories for continuity, documents undefined same-session concurrency, and does not explicitly say that the compiled harness wheel is supported in Agent Runtime. A small deploy-and-native-PDF test is still required.

The SDK may prove to be the better **reasoning harness** because skills, sub-agents, native document attachments, structured output and budgets are built in. Keep it behind the same provider-neutral contract. If a separately authorized representative-sample run shows a material quality advantage and the ADK Labs node deploys cleanly, it can become an internal node without changing the local adapter. Pure ADK remains the safer first managed deployment because its runtime path is GA/stable at the client-package level and avoids the alpha compiled-harness dependency.

## Native chapter PDF path

Gemini's [Document processing documentation](https://aistudio.google.com/docs/document-processing) describes native visual and textual PDF understanding for documents up to **50 MB or 1,000 pages**. It reports 258 image tokens per PDF page. For Gemini 3-class models it also supplies extracted native PDF text; those native text tokens are not billed, while the page images are reported as image input.

For a normal chapter, the local adapter should:

1. Verify the registered local PDF against its stored SHA-256.
2. Copy the selected physical pages into an in-memory PDF without rasterising them. If the source file is already exactly the chapter, use its original bytes.
3. Send one Gemini `Content` message containing an `application/pdf` part and a small JSON task envelope containing source anchors, learning profile context, annotation instructions and output contract.
4. Keep the PDF in memory. Do not upload it to a persistent retrieval store or commit a generated chapter file.
5. Reject more than 1,000 selected pages or a resulting PDF larger than 50 MB before any paid call.

ADK artifacts are Gemini `Part` values and can carry `inline_data` with MIME type `application/pdf`; see [ADK Artifacts](https://google.github.io/adk-docs/artifacts/). A deployed agent can also load a PDF artifact into a model request. If the Agent Runtime request envelope proves smaller than a chapter during deployment testing, stage the bytes in a private, lifecycle-managed GCS artifact and pass a `file_data` URI. That changes transport, not the native-PDF requirement.

The source PDF remains the faithful layer. The agent's output is a separate anchored annotation layer. The output must preserve source order and notation, distinguish clarification/derivation/intuition/correction annotations, and never silently rewrite a source claim.

## Skills, tools, search and control

ADK supports custom Python function tools and remote MCP toolsets; see [Function tools](https://google.github.io/adk-docs/tools-custom/function-tools/) and [MCP tools](https://google.github.io/adk-docs/tools-custom/mcp-tools/). The deployed study agent should own:

- versioned annotation and mathematical exposition skills;
- a PDF/document pass that establishes faithful source blocks and anchors;
- bounded annotation and validation/repair passes;
- read-only, least-privilege access to selected Atlas/profile context;
- a provider-neutral JSON output schema;
- callbacks that enforce per-run LLM-call and token/cost policy.

The external adapter reserves the job's full local budget before invocation and records observed usage afterwards. ADK's `RunConfig.max_llm_calls` bounds calls, but it is not a monetary hard cap. The task envelope therefore also carries `max_total_tokens`; the deployed agent must enforce it in callbacks. A malformed or incomplete artifact never becomes a published edition.

Ordinary chapter preparation uses an agent revision with no web-search or general network tools. A job can select the separately configured research-enabled resource only when its payload explicitly says `allow_web_research=true`. Browser graph exploration and hint reveal remain local and must never invoke either agent.

### Google Search is not Google Scholar

Google's documented remote-MCP catalogue does not list Google Scholar. The official [Developer Knowledge MCP](https://developers.google.com/knowledge/reference/mcp) searches Google developer documentation, not academic literature, and the [supported Google Cloud MCP products](https://docs.cloud.google.com/mcp/supported-products) do not expose Scholar. This is a documented absence from the official catalogues, not proof that no private integration could ever exist.

ADK's [Google Search tool](https://google.github.io/adk-docs/integrations/google-search/) provides grounded public-web search. It can find publisher pages and papers, but it is not a structured Scholar citation graph and must not be labelled as one. For the literature map, use Search only for explicit discovery and evidence, and separately evaluate a bibliographic API such as Crossref, OpenAlex or Semantic Scholar. Do not scrape Google Scholar. Graph nodes should principally be external works; internal sections belong in the selected-paper detail view and may link to external evidence without creating a dense same-document graph.

## File Search and the vault

Gemini [File Search](https://aistudio.google.com/docs/file-search) chunks, embeds, indexes and retrieves uploaded material. It supports metadata filtering and page-aware citations and can be useful for a deliberately selected corpus. It is not a replacement for the local knowledge base:

- Files API objects expire after 48 hours, but imported File Search data/embeddings persist until explicitly deleted or the backing model is deprecated; there is no per-document TTL.
- Query embeddings and storage are currently free, while initial indexing embeddings and retrieved model context are billed.
- A document may be up to 100 MB. Project store limits depend on account tier, and indexed storage is larger than raw input.
- File Search cannot currently be combined in the same request with Google Search or URL Context.

SQLite, the Obsidian Markdown vault and local source files therefore remain canonical. File Search is opt-in, scoped and disposable. Do not upload the whole vault by default, and keep enough local provenance to recreate or delete every remote item.

## Privacy, retention and region

Agent Platform and the Gemini Developer API have different data terms; do not transfer a privacy conclusion from one to the other.

For Agent Platform, Google's [Service Specific Terms](https://cloud.google.com/terms/service-terms) say customer data is not used to train or fine-tune models without permission and generated output is Customer Data. The [zero-data-retention guidance](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/zero-data-retention) lists exceptions and configuration-dependent retention, including abuse monitoring, safety features, implicit caching and optional request/response logging. “No training” is not the same claim as “no temporary processing or retention.”

Agent Runtime is available in London (`europe-west2`) according to the [Agent Platform locations](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/agent-locations) page. Agent infrastructure and stored resources can be placed there, but the model endpoint has its own processing-location rules. The [data residency page](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/data-residency) warns that the global endpoint has no residency guarantee and that the EU multi-region does not include the UK. Before uploading private sources, verify the selected Gemini model and every enabled tool in the same region; do not promise UK-only processing from runtime location alone.

For the Gemini API/AI Studio route, the [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms) distinguish paid and unpaid services and contain separate terms for grounded Search. UK production use should use paid services. Those terms matter for an Antigravity SDK trial if it uses a Gemini API key rather than Vertex authentication.

## Cost model for one fully annotated 5–10 page chapter

This is an engineering estimate, not a billed trial result. It assumes one complete offline ADK job with two bounded internal passes (annotation plus validation/repair), no web search, and no persistent File Search indexing. The raw PDF contributes only about 1,290–2,580 page-image tokens at Google's stated 258 tokens/page; repeated instructions, Atlas context, reasoning and generated derivations dominate.

Assumed total use across both passes:

- 45,000–120,000 uncached input/re-input tokens;
- 10,000–30,000 output plus thinking tokens;
- 5–15 minutes of 1-vCPU/2-GiB Agent Runtime compute.

Current non-global Vertex rates on 2026-11-01 are $0.825/M input and $4.125/M output for Gemini 3.8 Flash, and $2.20/M input and $11/M output for Gemini 4 Argon. Google has announced a doubling of the base model rates on 2027-01-01 for Flash and 2026-12-01 for Argon. See [Vertex AI model pricing](https://cloud.google.com/model-garden/pricing). [Agent Platform pricing](https://cloud.google.com/products/gemini-enterprise-agent-platform/pricing) lists 50 vCPU-hours and 100 GiB-hours free per billing account each month, then $0.085/vCPU-hour and $0.009/GiB-hour; idle time between turns is not billed.

Using the 2026-10-29 Bank of England indicative rate of £1 = $1.3375 (about £0.748/$), the conservative price including runtime **as if the free tier were already exhausted** is:

| Policy | Model + runtime estimate | With one additional full retry |
|---|---:|---:|
| Gemini 3.8 Flash, non-global endpoint | **£0.07–£0.19** | **£0.13–£0.38** |
| Gemini 4 Argon, non-global endpoint | **£0.16–£0.47** | **£0.33–£0.94** |

Currency source: [Bank of England daily spot rates](https://www.bankofengland.co.uk/boeapps/database/rates.asp). Actual solo use will often pay no runtime charge while inside the free compute allowance. A research run can add Search grounding charges after the account's free monthly allowance; current model pricing lists $14 per 1,000 grounded searches beyond that allowance. File Search indexing, GCS staging, logging and network egress are excluded because the default chapter path does not use them.

These ranges are much lower than Google's published $0.30–$1.30 examples for a prebuilt Antigravity document-generation interaction because this design is a bounded custom ADK workflow rather than an open-ended 100k–500k-token autonomous sandbox loop. Until a representative sample measures real reasoning/output use, show a deliberately larger visible reservation (for example £0.50 Flash or £1 Argon per normal chapter) and settle against observed usage. The historical £20 SDK comparison cap remains unspent, but `docs/SDK-TRIAL.md` marks that provider contest superseded; it does not by itself authorize a new paid Antigravity SDK call. This research made no paid calls.

## Implementation boundary

The local Google adapter now deliberately does only the provider boundary:

- lazily constructs the Agent Platform client after an explicit job action;
- verifies and slices the registered whole chapter as native PDF bytes;
- chooses an offline or explicitly configured research runtime;
- sends the PDF plus a versioned task envelope;
- supplies `max_llm_calls` and a token/cost envelope for deployed callbacks;
- captures usage events and estimates cost without writing application state;
- extracts and validates a provider-neutral JSON artifact.

It does not create credentials, deploy agents, upload the vault, write SQLite, publish partial output or run on API startup. Durable reservation, settlement, publication and job recovery remain responsibilities of the existing local worker/store boundary.

The initial transport deliberately uses a bounded stream with a nine-minute local timeout, avoiding an implicit GCS write. Long-running jobs are not enabled until their private bucket, input/output lifecycle, cancellation and recovery semantics are designed and tested.

## Validation still required before enabling paid work

1. Deploy the minimal ADK agent in the chosen project and verify that a native inline PDF reaches Gemini through `async_stream_query`; test GCS artifact fallback if the runtime request limit binds.
2. Configure the London runtime and confirm the exact selected model/tool processing locations and retention settings.
3. If explicitly authorized, run the representative annotation sample through pure ADK and an ADK Labs `AntigravityAgent` node; compare mathematical fidelity, source anchoring, annotation usefulness, usage, latency and deployability.
4. Verify the deployed callbacks actually stop at the requested total-token/cost envelope, including sub-agents and repair passes.
5. Select and evaluate a structured bibliographic provider separately. There is no official Google Scholar API/MCP in the catalogues reviewed here.

## Primary-source inventory

All sources below were accessed 2026-11-01.

- [Gemini API Agents overview](https://aistudio.google.com/docs/agents)
- [Gemini API: Building managed agents](https://aistudio.google.com/docs/custom-agents)
- [Gemini API Antigravity agent](https://aistudio.google.com/docs/antigravity-agent)
- [Gemini document processing](https://aistudio.google.com/docs/document-processing)
- [Gemini File Search](https://aistudio.google.com/docs/file-search)
- [Google Antigravity SDK product page](https://antigravity.google/product/antigravity-sdk)
- [Google Antigravity SDK repository](https://github.com/google-antigravity/antigravity-sdk-python)
- [Antigravity SDK structured-output example](https://github.com/google-antigravity/antigravity-sdk-python/blob/main/examples/getting_started/structured_output.py)
- [Antigravity SDK changelog](https://github.com/google-antigravity/antigravity-sdk-python/blob/main/google/antigravity/CHANGELOG.md)
- [ADK Labs AntigravityAgent wrapper](https://github.com/google/adk-python/blob/main/docs/guides/labs/antigravity/index.md)
- [Agent Runtime overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime)
- [ADK Agent Runtime quickstart](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk)
- [Use an ADK agent on Agent Runtime](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/use-an-adk-agent)
- [ADK artifacts](https://google.github.io/adk-docs/artifacts/)
- [ADK function tools](https://google.github.io/adk-docs/tools-custom/function-tools/)
- [ADK MCP tools](https://google.github.io/adk-docs/tools-custom/mcp-tools/)
- [ADK Google Search](https://google.github.io/adk-docs/integrations/google-search/)
- [Agent Platform pricing](https://cloud.google.com/products/gemini-enterprise-agent-platform/pricing)
- [Vertex AI model pricing](https://cloud.google.com/model-garden/pricing)
- [Agent Platform locations](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/agent-locations)
- [Agent Platform data residency](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/data-residency)
- [Agent Platform zero-data-retention guidance](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/zero-data-retention)
- [Google Cloud Service Specific Terms](https://cloud.google.com/terms/service-terms)
- [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms)
- [Google Cloud supported MCP products](https://docs.cloud.google.com/mcp/supported-products)
- [Google Developer Knowledge MCP](https://developers.google.com/knowledge/reference/mcp)
- [Bank of England daily spot rates](https://www.bankofengland.co.uk/boeapps/database/rates.asp)
