---
status: accepted
---

# Build a custom Google ADK agent on the managed Agent Runtime

Build and own the study agent rather than selecting a prebuilt managed agent. The agent is a Google ADK application deployed to Google's managed Agent Runtime. Our code defines its sub-agents, skills, tools, prompts, context policy, budgets and output contracts; the runtime supplies managed execution and deployment. Antigravity is neither the agent nor a production dependency.

The first stage treats a complete chapter PDF as a native multimodal artifact and invokes Gemini document understanding to produce faithful ordered source blocks. Later bounded stages add the separate anchored annotation layer, derivation bridges and optional evidence-backed literature analysis. Provider output crosses a provider-neutral contract and is validated locally before an edition can be published or durable state updated.

This decision preserves native PDF handling while avoiding a lossy extraction boundary. It also keeps model and runtime details out of SQLite, Markdown and browser contracts, so the application can revise its internal Google agent topology without migrating durable study data. Paid execution remains disabled until credentials, privacy/region settings and visible per-job budgets are configured.
