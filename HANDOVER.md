With 300 million tokens available, I would aim for something considerably more ambitious than a dashboard or a network visualiser.

My proposed mission would be:

Build an AI-assisted discovery engine that uncovers, verifies, and explains relationships between companies, governments, investments, and infrastructure projects that are difficult to identify from existing datasets.

The important word is discovery. I want the system to find things we didn't already know to look for, while being able to prove where every factual claim came from.

But I would not spend those 300 million tokens immediately. Tokens can help process and compare evidence, but they cannot overcome inaccessible documents, missing disclosures, or bad source data.

## What I would do first

1\. Find the actual gap

Compare existing platforms, datasets, and investigative tools. Identify specific questions they cannot answer reliably. The system needs a purpose beyond visualising information.

2\. Build an evidence engine

Ingest structured datasets and documents. Extract entities, relationships, events, and claims. Preserve source documents, dates, contradictions, and uncertainty.

3\. Run discovery experiments

Search for relationships across datasets, unexplained changes, common dependencies, and contradictions. Compare the findings against what existing tools already provide.

4\. Build the product around the successful discoveries

Only after demonstrating useful findings would I invest in an interactive application, relationship exploration, timelines, and automated monitoring.

I verified three useful starting resources: Global Energy Monitor already maps energy asset ownership, GLEIF provides corporate consolidation relationships, and AidData tracks Chinese development finance. Their coverage and definitions differ substantially, which creates both opportunities and risks for connecting records.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://globalenergymonitor.org\&sz=32)

Global Energy Monitor

+2



The opportunity isn't established just because those datasets differ. The first task is to demonstrate that connecting and analysing them produces something genuinely useful.

## Handover for your lead agent

This is written for the agent that will coordinate the project. Codex is a supporting engineering agent, not the project owner.

# PROJECT HANDOVER: Evidence-Driven Network Discovery Engine

**Date:** 30 October 2026\
**Status:** Exploration and technical feasibility\
**Project name:** Undecided. TRACE is only a placeholder.\
**Lead:** Main AI agent\
**Supporting engineer:** Codex\
**Available resources:** Up to 300 million model tokens, local computing, AI coding tools, public datasets, and existing research infrastructure. Minimal monetary expenditure.

## 1. Context

The project owner, Muhammad Faiz Krisnadi, has a background in international political economy, development finance, foreign investment, trade, and Southeast Asian infrastructure.

He has experience with AidData, Indonesian investment data, research evidence, Python, Streamlit, and a large-scale GLEIF entity-matching project.

His objective is not to create another academic paper, generic chatbot, or conventional dashboard.

He wants to build something genuinely interesting and useful, using his domain expertise, evidence judgment, computing resources, and AI-assisted engineering.

He is particularly interested in exploring real-world networks, finding connections that are not immediately obvious, and understanding hidden institutional or commercial dependencies.

The precise product has not yet been chosen. Do not treat any earlier proposal as final.

## 2. Your mission

Investigate, design, and begin testing an evidence-driven discovery engine for real-world institutional, commercial, and infrastructure networks.

The eventual system should be able to:

1. Ingest and connect information from multiple public sources.
2. Resolve companies, institutions, projects, locations, and other entities across datasets.
3. Identify documented relationships and dependencies.
4. Detect potentially meaningful patterns, inconsistencies, gaps, and changes.
5. Produce findings that can be independently verified against source evidence.
6. Allow users to investigate these findings interactively.

**The core challenge is discovery quality, not visualisation.**

Do not assume that drawing a network graph constitutes a useful discovery.

## 3. First assignment: Find an underserved problem

Before building a large system, investigate what existing tools already do well.

Include relevant existing offerings such as:

- Global Energy Monitor
- OCCRP Aleph
- ICIJ Offshore Leaks Database
- OpenCorporates
- OpenSanctions
- GLEIF
- AidData
- Other applicable infrastructure, corporate ownership, and project-monitoring systems

Evaluate their functionality, coverage, methodology, provenance, and limitations using actual accessible documentation and representative tests.

Identify three potentially underserved tasks.

Candidate areas worth investigating include:

**A. Cross-dataset relationship discovery**

Can combining data reveal documented relationships between projects, investors, contractors, lenders, and institutions that individual sources do not readily expose?

**B. Institutional dependency discovery**

Can the system identify the agreements, authorisations, and infrastructure commitments on which a particular investment depends?

**C. Temporal and contradictory-evidence discovery**

Can the system identify meaningful changes or inconsistencies across announcements, filings, contracts, regulations, and project updates?

These are hypotheses, not confirmed gaps. Reject them if existing tools already solve them adequately.

Choose a narrowly scoped initial use case based on evidence availability, distinctiveness, practical value, and technical feasibility.

Prioritise Indonesia and Southeast Asia initially, particularly infrastructure, energy, development finance, and industrial investment.

Do not restrict the architecture permanently to those sectors.

## 4. Data acquisition strategy

Start with legitimate bulk downloads and documented APIs wherever possible. Web scraping is a fallback, not the default.

Investigate the accessibility and conditions of:

- AidData Global Chinese Development Finance data
- Global Energy Monitor trackers and ownership data
- GLEIF Level 1 and Level 2 records
- Indonesian government regulations and project documents
- PLN and other relevant utility publications
- Corporate annual reports and stock exchange disclosures
- Public procurement, environmental, and licensing documents
- Credible news and project announcements

For every source, document its coverage, update frequency, licensing, access method, completeness, and limitations.

Important distinctions:

- GLEIF accounting consolidation relationships are not automatically beneficial ownership.
- Investment announcements are not evidence of disbursement or project completion.
- Historical project datasets cannot establish current project status without updates.
- A shared name or location is not sufficient evidence of a corporate relationship.

Respect robots.txt, platform terms, licensing, rate limits, and access restrictions. Do not bypass authentication, CAPTCHAs, paywalls, or security controls.

Do not indiscriminately collect personal information or build private networks about individuals.

## 5. Technical proof of concept

Construct a small end-to-end working system rather than a large empty framework.

Suggested initial sample: 20 to 30 projects with enough available documentary evidence to test relationships across sources.

Build five components:

**A. Source ingestion**

- Download or retrieve records.
- Preserve metadata and original source links.
- Record collection timestamps and document versions.
- Avoid duplicate downloads.

**B. Structured extraction**

- Extract organisations, projects, agreements, financing events, permissions, and dated claims.
- Preserve exact supporting passages or structured fields.
- Allow the model to abstain when evidence is insufficient.

**C. Entity resolution**

- Match alternate names and corporate identities.
- Use stable identifiers when available.
- Avoid automatically merging ambiguous entities.
- Preserve multiple candidate matches.

**D. Evidence graph**

- Store typed, directed, dated relationships.
- Link every factual edge to its evidence.
- Separate documented facts, reported claims, inferred hypotheses, and unknowns.
- Represent conflicting evidence without silently choosing a winner.

**E. Discovery queries**

- Find shared dependencies.
- Trace connections between projects or organisations.
- Detect changes across time.
- Identify conflicting claims.
- Surface unusual patterns for human investigation.

Use deterministic data processing wherever possible. Reserve expensive model calls for extraction, ambiguity resolution, and genuine reasoning tasks.

## 6. Codex's role

Codex is a supporting engineering agent. It must not independently redefine the project's mission.

Delegate bounded engineering assignments to Codex, including:

1. Building ingestion adapters and data-normalisation scripts.
2. Designing schemas for sources, entities, claims, events, and relationships.
3. Implementing entity-resolution candidates and matching diagnostics.
4. Developing graph traversal, temporal filtering, and discovery queries.
5. Writing unit tests, data validation tests, and reproducible evaluation scripts.
6. Creating a small interactive explorer when the underlying evidence system works.

For each assignment, give Codex the expected inputs, outputs, test cases, and acceptance criteria.

The lead agent owns research direction, source evaluation, interpretation, architecture decisions, quality control, and final integration.

Never let an automatically generated relationship become a verified finding without an evidence check.

## 7. Evaluation: Can it discover anything worthwhile?

Establish a human-verified reference set.

Evaluate at least:

- Entity-matching accuracy and false merges.
- Precision of extracted relationships.
- Correctness of relationship types and dates.
- Source attribution accuracy.
- Handling of contradictions and unknowns.
- Whether findings are meaningful rather than trivial shared connections.
- Whether discoveries add value beyond existing databases and ordinary search.

Compare the system's output against an appropriate baseline using the same investigative questions.

Produce a small collection of candidate discoveries and independently audit them.

A compelling discovery must have a clear explanation, supporting evidence, and an account of what makes it useful or previously difficult to identify.

Do not claim novelty merely because the connection was absent from one dataset.

If the system repeatedly generates misleading connections, improve or narrow it before expanding collection.

## 8. Token budget and scaling discipline

Treat 300 million tokens as an available ceiling, not a consumption target.

Suggested initial authorisation limits:

- Up to 1 million tokens for landscape assessment, source reconnaissance, and experiment design.
- Up to 5 million additional tokens for the initial ingestion and extraction proof of concept.
- Up to 10 million additional tokens for benchmarking, error analysis, and a useful interactive demonstration.

These are spending limits, not required usage or estimates of task complexity.

Do not launch broad, expensive scraping or extraction simply because the budget exists.

Track token usage, model calls, failed requests, collection costs, and duplicated processing.

Use caching, batching, incremental updates, and selective reprocessing.

Expansion beyond the initial experiment requires evidence that the system is producing valuable discoveries.

## 9. Required outputs

Create actual working artifacts, not just a proposal.

Initial deliverables:

1. **Opportunity assessment:** Three possible problems, existing alternatives, and a reasoned choice of the initial target.
2. **Source registry:** Verified accessible datasets, formats, terms, coverage, and limitations.
3. **Evidence schema:** A concrete representation of entities, claims, relationships, events, sources, and uncertainties.
4. **Working pipeline:** A reproducible small-scale system that ingests real data and produces evidence-linked relationships.
5. **Discovery evaluation:** Candidate discoveries, verification results, failures, and comparisons against baseline tools.
6. **Interactive demonstration:** A small interface focused on investigation, if the evidence engine passes the initial quality tests.
7. **Next-stage decision:** Expand, pivot, or stop, supported by the experiment's results.

Keep the project in a clean, reproducible repository. Do not modify the owner's existing repositories without clear authorisation.

Maintain concise progress and decision logs so another agent can continue the work.

## 10. Operating principles

- Build something useful, not merely impressive.
- Prefer original sources.
- Never invent data, sources, relationships, or verification results.
- Keep raw evidence separate from model-generated interpretations.
- Distinguish a genuinely unknown relationship from one that is merely missing in the dataset.
- Avoid unsupported claims of influence, control, or causation.
- Use network analysis as an investigative aid, not an automatic measure of political power.
- Challenge the project's assumptions when evidence contradicts them.
- Avoid unnecessary dashboards, elaborate UI work, and premature scaling.
- Favour a working and evaluated prototype over a large unfinished platform.

## 11. Immediate execution order

Begin by investigating the existing tool landscape and accessible data.

Then select three specific investigative questions that could plausibly be answered better by combining sources.

Choose the strongest question and build the smallest end-to-end experiment capable of testing it.

Delegate implementation tasks to Codex where useful.

Return with an evidence-backed demonstration, including both successful and failed discovery attempts.

**Do not conclude the first milestone merely by delivering another project proposal. The objective is to learn whether a genuinely useful discovery engine can be built.**

## One architectural decision I'd make now

I would not begin with Neo4j, a vector database, or a complicated multi-agent framework simply because the eventual system might be enormous.

Start with Python, Parquet/DuckDB or PostgreSQL, and a simple evidence graph. Introduce specialised infrastructure only when a demonstrated workload requires it.

The strongest architecture principle is that every discovery must be reversible to its underlying evidence. If the system tells you that two infrastructure projects have a common dependency, you should be able to follow that statement back to the individual documents, see when each claim was made, and check whether the connection is still valid.

That is more important than the number of nodes or tokens processed.

My preferred first milestone is one working investigation that produces a finding you would have struggled to uncover manually. If we can demonstrate that, the 300-million-token budget becomes a powerful resource for scaling something that has already shown value.