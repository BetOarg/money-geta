---
name: trend-radar
description: Discover emerging topics for any Money-Geta content profile using evidence-backed web search; never invent social trend metrics.
---

# Trend radar

1. Confirm the active project and profile (gaming, viral, news or education); use the profile rules to shape queries.
2. Prepare 3–8 focused queries where practical: recent coverage, primary sources, different angles, and topic-specific keywords. Avoid searching for the same phrase repeatedly.
3. Run the campaign discovery CLI with explicit query arguments:
   `python -m scripts.money_geta research --project <project-id> --campaign <campaign-id> --query "<query 1>" --query "<query 2>"`
   Add more `--query` arguments up to the tool limit (10).
4. External search requires a configured Brave/Tavily provider, API key, and `MONEY_GETA_SEARCH_ALLOW_REQUESTS=true`. Check provider costs and quotas before enabling. The skill never enables network requests or calls the API automatically.
5. Interpret the ranking only as a **discovery score** (query coverage, provider score and explicit publication freshness). It is not social popularity, views, virality, factual confidence, or rights clearance.
6. Open original sources and verify date, author, context, and factual claims. Research leads stay separate from source-rights and claim ledgers until reviewed.
7. Apply profile-specific priorities:
   - Gaming: official announcements, allowed creator videos, gameplay and commentary. GTA VI is a specialized Gaming sub-profile; do not apply GTA-specific rules to other topics.
   - Viral: cross-topic public signals, source diversity and factual/rights checks before scripting.
   - News: primary sources, timestamped reporting, corroboration and correction tracking.
   - Education: authoritative references, stable explanations and reviewable examples.
8. Never manufacture views, likes, comments, rankings or trend claims. If no actual platform metric is available, label it unavailable.
9. Present up to ten leads and explain why each is worth investigating. Do not treat a search result snippet as proof.
10. Hand selected sources to source-reading and claim-check workflows; hand approved creator content to moment-finder.

## Safety

- No network call unless the operator runs the command and explicitly enables provider requests.
- No auto-download, permission attestation, campaign joining, publication, scheduling, or paid action.
- Exclude credential-bearing URLs from reports.
- Trend/discovery ranking is not a truth, rights, or editorial gate.
