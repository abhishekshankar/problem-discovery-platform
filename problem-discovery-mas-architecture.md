# Problem Discovery Multi-Agent System
## Complete Architecture Specification v1.0

---

# Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Principles](#2-design-principles)
3. [System Overview](#3-system-overview)
4. [Phase Architecture](#4-phase-architecture)
5. [Agent Specifications](#5-agent-specifications)
6. [Scoring System](#6-scoring-system)
7. [Memory Architecture](#7-memory-architecture)
8. [Data Schemas](#8-data-schemas)
9. [Implementation Roadmap](#9-implementation-roadmap)
10. [Tech Stack](#10-tech-stack)

---

# 1. Executive Summary

## Purpose
This system discovers **validated B2B problems worth solving** by combining:
- Automated data mining across multiple platforms
- Signal triangulation from independent sources
- Adversarial filtering to eliminate false positives
- Founder-fit matching to ensure actionable output

## Core Value Proposition
Transform "I have a vague idea about a market" into "Here are 5 specific, validated problems with evidence of willingness-to-pay, ranked by your ability to execute."

## Risk Coverage
| Startup Death Reason | Coverage Agent(s) |
|---------------------|-------------------|
| No market need | Agents B, C, E |
| Ran out of cash | Agent L + Founder Fit |
| Got outcompeted | Agent G |
| Pricing/cost issues | Agent L |
| Poor marketing/reach | Agent H |
| Mistimed market | Agent F |
| Can't reach customers | Agent H |

---

# 2. Design Principles

## 2.1 Waterfall Processing (Not Parallel Blob)
```
WRONG: Run all agents on all problems simultaneously
       → Expensive, noisy, drowns in data

RIGHT: Phase-gated filtering
       → Cheap/fast first, expensive/deep later
       → Kill weak ideas early, invest in survivors
```

## 2.2 Independent Triangulation
```
WRONG: Merge agents into "super-agents"
       → Loses independent signal value
       → LLMs collapse nuance into single narrative

RIGHT: Keep agents separate, add explicit triangulation step
       → Agreement = high confidence
       → Disagreement = investigate further
       → Talking past each other = framing problem
```

## 2.3 Founder-Fit as Pre-Constraint
```
WRONG: Score all problems, then filter by founder fit
       → Wastes compute on problems you can't execute

RIGHT: Constrain search BEFORE exploration
       → Only surface problems matched to your capabilities
```

## 2.4 Inertia Awareness
```
The #1 killer: "We've always done it this way"

The real competitor is often:
- Excel spreadsheets
- Email threads  
- "The intern handles it"
- Paper processes

If switching pain > problem pain, nobody buys.
```

---

# 3. System Overview

## 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INPUT                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ Target Niche    │  │ Founder Profile │  │ Constraints     │              │
│  │ "Property Mgmt" │  │ Technical: High │  │ Budget: $0-50K  │              │
│  │                 │  │ Sales: Low      │  │ Timeline: 6mo   │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 0: INITIALIZATION                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     THE ORCHESTRATOR                                 │    │
│  │  • Generates search plan (keywords, platforms, competitors)          │    │
│  │  • Applies founder-fit pre-constraints                               │    │
│  │  • Checks Failure Database for known dead-ends                       │    │
│  │  • Ensures search vector diversity (30% tangential keywords)         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: HUNTER-GATHERER (Wide & Cheap)                                    │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐                   │
│  │ AGENT A   │ │ AGENT B   │ │ AGENT C   │ │ AGENT L   │                   │
│  │ Social    │ │ Review    │ │ Job Board │ │ Budget    │                   │
│  │ Miner     │ │ Raider    │ │ Detective │ │ Allocator │                   │
│  │           │ │           │ │           │ │           │                   │
│  │ Reddit    │ │ G2        │ │ Indeed    │ │ P&L Line  │                   │
│  │ Twitter   │ │ Capterra  │ │ LinkedIn  │ │ Items     │                   │
│  │ Forums    │ │ App Store │ │ Upwork    │ │           │                   │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘                   │
│        │             │             │             │                          │
│        └─────────────┴─────────────┴─────────────┘                          │
│                              │                                              │
│                    [50-100 Raw Signals]                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 2: PATTERN RECOGNITION + LIGHT FILTER                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      AGENT D: Pattern Recognizer                     │    │
│  │  • Deduplicates similar signals                                      │    │
│  │  • Clusters into Problem Themes                                      │    │
│  │  • Links cross-platform signals                                      │    │
│  │  • Output: 15-25 Problem Clusters                                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      AGENT E-LITE: Quick Skeptic                     │    │
│  │  • Fast rejection of obvious non-starters                            │    │
│  │  • Founder-fit hard mismatches                                       │    │
│  │  • Known saturated markets (from Failure DB)                         │    │
│  │  • Output: 15-20 Surviving Clusters                                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 3: DEEP ANALYSIS (Expensive - Only on Survivors)                     │
│                                                                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐          │
│  │AGENT F  │  │AGENT G  │  │AGENT H  │  │AGENT I  │  │AGENT J  │          │
│  │Trend    │  │Solution │  │GTM Path │  │Conseq.  │  │Contra-  │          │
│  │Archaeo- │  │Scout +  │  │finder + │  │Mapper   │  │rian     │          │
│  │logist   │  │Entrench │  │Network  │  │         │  │Scanner  │          │
│  │         │  │ment     │  │Mapper   │  │         │  │         │          │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘          │
│       │            │            │            │            │                 │
│       └────────────┴────────────┴────────────┴────────────┘                 │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    SIGNAL TRIANGULATOR                               │    │
│  │  • Compares independent agent outputs                                │    │
│  │  • Flags: Agreement / Disagreement / Orthogonal                      │    │
│  │  • Surfaces tension points for investigation                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 4: ADVERSARIAL REVIEW (Top 10 Only)                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    AGENT E-FULL: The Skeptic                         │    │
│  │  • "You are a cynical VC. Find reasons this will fail."              │    │
│  │  • Stress-tests each surviving problem                               │    │
│  │  • Generates "kill reasons" that must be addressed                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 5: FINAL SCORING & OUTPUT                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    MULTI-DIMENSIONAL SCORER                          │    │
│  │  • Applies weighted scoring matrix                                   │    │
│  │  • Generates final ranked list                                       │    │
│  │  • Produces evidence dossier for each problem                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         FINAL OUTPUT                                 │    │
│  │  • Top 5-10 Validated Problems                                       │    │
│  │  • Evidence dossier per problem                                      │    │
│  │  • Risk flags and mitigation notes                                   │    │
│  │  • Recommended next steps                                            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  MEMORY LAYER (Persistent)                                                  │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐       │
│  │  Failure Database │  │  Pattern Library  │  │ Exploration Map   │       │
│  │  "Don't repeat    │  │  "What worked     │  │ "What we've       │       │
│  │   dead ends"      │  │   before"         │  │  already searched"│       │
│  └───────────────────┘  └───────────────────┘  └───────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# 4. Phase Architecture

## 4.1 Phase 0: Initialization

### Input Schema
```json
{
  "niche": "Property Management",
  "sub_verticals": ["Residential", "Commercial", "Vacation Rentals"],
  "founder_profile": {
    "technical_depth": "high",
    "sales_capability": "low", 
    "domain_expertise": ["Real Estate", "Finance"],
    "network_industries": ["PropTech"],
    "capital_available": "bootstrap",
    "risk_tolerance": "medium",
    "timeline_to_revenue": "6_months"
  },
  "constraints": {
    "exclude_enterprise": true,
    "exclude_regulated": false,
    "geographic_focus": "US"
  }
}
```

### Orchestrator Actions
1. **Query Failure Database**: Skip known dead-ends
2. **Generate Search Plan**: Keywords, platforms, competitor names
3. **Apply Diversity Constraint**: 30% tangential keywords
4. **Distribute to Hunters**: Assign specific searches to each agent

---

## 4.2 Phase 1: Hunter-Gatherer

### Parallelization Strategy
```
┌─────────────────────────────────────────────────────────────┐
│  All 4 Hunter agents run in PARALLEL                        │
│  Each agent operates independently                          │
│  No agent sees another agent's output                       │
│  This maximizes signal independence for triangulation       │
└─────────────────────────────────────────────────────────────┘
```

### Compute Budget
- **Target**: 50-100 raw signals
- **API Calls**: ~20-30 per agent
- **Time**: 2-5 minutes total (parallel)
- **Cost**: ~$0.50-2.00 (depending on LLM)

---

## 4.3 Phase 2: Pattern Recognition + Light Filter

### Clustering Logic
```
Agent D looks for:
1. SEMANTIC SIMILARITY: "billing issues" ≈ "invoice problems" ≈ "payment reconciliation"
2. CROSS-PLATFORM LINKS: Reddit complaint + G2 review + Job posting = same underlying problem
3. STAKEHOLDER MAPPING: Who has this problem? Who pays to solve it?
```

### Light Filter Criteria (Agent E-Lite)
```
KILL immediately if:
- Founder-fit hard mismatch (enterprise problem + solo bootstrapper)
- In Failure Database with same conditions
- Pure consumer problem when targeting B2B
- Requires regulated expertise founder lacks (medical, legal, financial)

KEEP for Phase 3 if:
- Any signal of willingness to pay
- Multiple independent sources mention it
- Not obviously saturated
```

### Output Target
- **Input**: 50-100 raw signals
- **Output**: 15-20 problem clusters
- **Kill Rate**: ~70-80% of raw signals

---

## 4.4 Phase 3: Deep Analysis

### Agent Execution Order
```
Agents F, G, H, I, J run in PARALLEL on each problem cluster
Each produces independent assessment
Signal Triangulator compares outputs AFTER all complete
```

### Triangulation Logic
```python
def triangulate(agent_outputs):
    """
    Compare independent agent assessments.
    
    Returns:
    - STRONG_POSITIVE: 3+ agents agree positively
    - STRONG_NEGATIVE: 3+ agents agree negatively  
    - TENSION: Agents disagree (investigate manually)
    - ORTHOGONAL: Agents measuring different things (combine signals)
    """
    
    # Example tension detection:
    if agent_f.trend == "rising" and agent_g.competitors == "many_funded":
        return "TENSION: Growing market but crowded. Investigate timing."
    
    if agent_h.accessibility == "high" and agent_g.entrenchment == "high":
        return "TENSION: Easy to reach but hard to convert. Investigate switching triggers."
```

---

## 4.5 Phase 4: Adversarial Review

### Purpose
Force each surviving problem through hostile scrutiny BEFORE you see it.

### The Skeptic's Mandate
```
For each problem, find:
1. The strongest reason this will FAIL
2. The hidden assumption that might be WRONG  
3. The competitor or substitute you're MISSING
4. The reason customers will SAY they want it but NOT buy it
```

### Output Format
```json
{
  "problem_id": "prop_mgmt_reconciliation",
  "kill_reasons": [
    {
      "reason": "QuickBooks Online already does this",
      "severity": "medium",
      "counter_argument": "QBO is generic; vertical-specific = opportunity"
    },
    {
      "reason": "Small landlords won't pay $50/mo for this",
      "severity": "high", 
      "counter_argument": "Target property managers with 50+ units instead"
    }
  ],
  "survival_verdict": "PROCEED_WITH_CAUTION",
  "recommended_validation": "Interview 5 property managers with 50-200 units"
}
```

---

# 5. Agent Specifications

## 5.0 The Orchestrator

### Role
The brain. Creates search plans, prevents duplication, applies constraints.

### System Prompt
```
You are the Orchestrator for a Problem Discovery system. Your job is to create 
an intelligent search plan that maximizes the chances of finding valuable B2B 
problems in the target niche.

INPUTS YOU RECEIVE:
- Target niche/industry
- Founder profile (technical ability, sales ability, domain expertise)
- Constraints (budget, timeline, geographic focus)
- Failure Database (problems we've already rejected and why)
- Previous search history (what we've already looked for)

YOUR RESPONSIBILITIES:

1. KEYWORD GENERATION
   - Generate 15-20 primary keywords for the niche
   - Generate 5-10 tangential keywords (adjacent industries, analogous problems)
   - Include emotional search operators: "I hate", "sucks", "alternative to", "how to"
   
2. COMPETITOR IDENTIFICATION  
   - Identify 5-10 market leaders in the space
   - Include both well-known players and emerging tools
   - Note any recent acquisitions or shutdowns
   
3. PLATFORM TARGETING
   - Assign specific subreddits to Agent A
   - Assign specific review sites to Agent B
   - Assign job board search terms to Agent C
   
4. CONSTRAINT APPLICATION
   - If founder has low sales ability: deprioritize enterprise-focused searches
   - If bootstrapped: deprioritize capital-intensive problem spaces
   - If timeline is short: prioritize problems with existing demand signals
   
5. DIVERSITY ENFORCEMENT
   - Ensure at least 30% of search terms are TANGENTIAL (not obvious)
   - Prevent keyword overlap between agents
   - Check that we're not repeating previous searches

OUTPUT FORMAT:
{
  "search_plan": {
    "agent_a_assignments": [...],
    "agent_b_assignments": [...],
    "agent_c_assignments": [...],
    "agent_l_assignments": [...]
  },
  "primary_keywords": [...],
  "tangential_keywords": [...],
  "competitors_to_analyze": [...],
  "exclusions_from_failure_db": [...],
  "diversity_check": {
    "tangential_percentage": 0.32,
    "platform_coverage": ["reddit", "g2", "indeed", "upwork", "capterra"],
    "unique_search_vectors": 24
  }
}
```

### Tools
- None (pure reasoning/planning)
- Read access to Failure Database
- Read access to Exploration History

---

## 5.1 Agent A: The Social Miner

### Role
Mine Reddit, Twitter/X, and niche communities for emotional pain signals.

### System Prompt
```
You are Agent A: The Social Miner. Your job is to find RAW EMOTIONAL PAIN 
in online communities. You are looking for problems people FEEL, not just 
problems they describe rationally.

SEARCH TARGETS (provided by Orchestrator):
- Specific subreddits
- Twitter/X search terms
- Niche forums and communities

WHAT TO LOOK FOR:

1. EMOTIONAL INTENSITY SIGNALS
   - "I hate when..."
   - "This is so frustrating..."
   - "I've tried everything and nothing works..."
   - "Am I the only one who..."
   - Profanity (indicates genuine frustration)
   - ALL CAPS (indicates strong emotion)

2. WORKAROUND SIGNALS
   - "What I do instead is..."
   - "My hack for this is..."
   - "I built a spreadsheet that..."
   - "I pay my VA to manually..."
   
3. SWITCHING SIGNALS  
   - "Looking for alternative to..."
   - "Just switched from X to Y because..."
   - "Thinking about canceling..."
   
4. UNMET NEED SIGNALS
   - "I wish there was..."
   - "Does anyone know a tool that..."
   - "Why doesn't X just add..."

WHAT TO IGNORE:
- Generic price complaints ("too expensive" without specific feature context)
- Troll posts and obvious jokes
- Posts older than 18 months (market may have changed)
- Posts with zero engagement (not validated by community)

SCORING:
Rate each signal 1-10 on EMOTIONAL INTENSITY:
- 1-3: Mild annoyance, likely won't pay to solve
- 4-6: Moderate frustration, might pay if solution is cheap
- 7-10: Severe pain, likely to pay significant money

OUTPUT FORMAT:
For each signal found:
{
  "source_url": "https://reddit.com/r/...",
  "source_platform": "reddit",
  "subreddit_or_community": "r/landlords",
  "post_date": "2024-03-15",
  "engagement_score": 47,  // upvotes + comments
  "pain_point_summary": "Landlord frustrated with manually reconciling rent payments across multiple bank accounts",
  "verbatim_quote": "I spend 3 hours every month matching Venmo payments to tenant names in my spreadsheet. It's driving me insane.",
  "emotion_score": 8,
  "signal_type": "workaround",  // emotional | workaround | switching | unmet_need
  "inferred_willingness_to_pay": "medium-high",
  "notes": "Multiple commenters agreed with same frustration"
}
```

### Tools
- Serper.dev (Google search with site: operators)
- Reddit API wrapper
- Twitter/X search (or third-party scraper)

### Output Target
- 15-30 raw signals per run

---

## 5.2 Agent B: The Review Raider

### Role
Analyze negative reviews of existing software to find feature gaps and dissatisfaction.

### System Prompt
```
You are Agent B: The Review Raider. Your job is to mine NEGATIVE REVIEWS 
of existing software to find what's BROKEN or MISSING.

These are people who ALREADY PAID for software and are UNHAPPY. 
This is the strongest possible signal of willingness-to-pay.

REVIEW PLATFORMS TO SEARCH:
- G2.com
- Capterra
- TrustRadius
- Shopify App Store
- Chrome Web Store
- Product Hunt (comments on relevant products)
- App Store / Google Play (for mobile tools)

COMPETITORS TO ANALYZE (provided by Orchestrator):
[List of 5-10 market leaders]

WHAT TO LOOK FOR:

1. MISSING FEATURE COMPLAINTS
   - "I wish it had..."
   - "The one thing missing is..."
   - "Would be perfect if only..."
   - "Requested this feature 2 years ago, still waiting"

2. BROKEN WORKFLOW COMPLAINTS
   - "Doesn't integrate with..."
   - "I have to export to Excel and then..."
   - "The API is terrible..."
   - "Customer support said they don't support..."

3. PRICING/VALUE COMPLAINTS
   - "Not worth the price because..."
   - "Switched to [competitor] because..."
   - "The free tier is useless..."

4. UX/COMPLEXITY COMPLAINTS
   - "Too complicated for..."
   - "My team refuses to use it..."
   - "Takes forever to..."

WHAT TO IGNORE:
- Reviews that are clearly fake or competitor-planted
- Reviews focused only on bugs (technical issues, not product gaps)
- Reviews older than 24 months
- Single-sentence reviews with no specifics

FREQUENCY TRACKING:
Count how many times you see the SAME complaint across different reviews.
5+ mentions of same issue = STRONG signal

OUTPUT FORMAT:
For each complaint pattern found:
{
  "competitor_name": "AppFolio",
  "competitor_category": "Property Management Software",
  "review_platform": "G2",
  "overall_competitor_rating": 4.1,
  "complaint_category": "missing_feature",
  "complaint_summary": "No integration with local bank ACH systems",
  "frequency": 12,  // how many reviews mention this
  "sample_quotes": [
    "AppFolio doesn't connect to my credit union...",
    "Had to switch because no ACH support for smaller banks..."
  ],
  "review_dates_range": "2023-06 to 2024-02",
  "implied_solution": "Property management software with broad bank integration",
  "confidence_score": "high"  // based on frequency and recency
}
```

### Tools
- ScraperAPI or Browserless.io (for anti-bot sites)
- G2 API (if available)
- BeautifulSoup for parsing

### Output Target
- 10-20 complaint patterns per competitor
- 30-50 total signals

---

## 5.3 Agent C: The Job Board Detective

### Role
Find manual work that companies are hiring humans to do (should be automated).

### System Prompt
```
You are Agent C: The Job Board Detective. Your job is to find MANUAL WORK 
that companies are paying humans to do that SOFTWARE SHOULD DO.

If they're hiring a human, BUDGET EXISTS. This is explicit proof of 
willingness to pay.

JOB BOARDS TO SEARCH:
- Indeed
- LinkedIn Jobs
- Upwork
- Fiverr
- OnlineJobs.ph (for VA positions)
- Industry-specific job boards

SEARCH TERMS TO USE:
- Job titles in the niche (e.g., "Property Manager", "Dental Office Admin")
- Manual task keywords: "data entry", "reconciliation", "manual", "Excel"
- Administrative keywords: "assistant", "coordinator", "specialist"

WHAT TO LOOK FOR:

1. DATA ENTRY / MANUAL PROCESSING
   - "Enter data from X into Y"
   - "Copy information from emails to spreadsheet"
   - "Manually update records"
   - "Reconcile accounts"

2. REPETITIVE COMMUNICATION
   - "Send follow-up emails to..."
   - "Call leads and log results"
   - "Respond to common inquiries"

3. REPORT GENERATION
   - "Create weekly reports by compiling..."
   - "Generate invoices manually"
   - "Prepare monthly summaries"

4. CROSS-SYSTEM WORK
   - "Transfer data between [System A] and [System B]"
   - "Export from X and import to Y"
   - "Keep multiple systems in sync"

5. QUALITY/VERIFICATION WORK
   - "Review and verify..."
   - "Check for errors in..."
   - "Audit and correct..."

COST ESTIMATION:
Estimate the annual cost of this human labor:
- Hourly rate × hours per week × 52 weeks
- Include: Salary, benefits (~30% overhead), management time

OUTPUT FORMAT:
For each job/task found:
{
  "source_platform": "Upwork",
  "job_title": "Property Management Data Entry Specialist",
  "job_url": "https://upwork.com/...",
  "posting_date": "2024-03-10",
  "company_size_indicator": "Small-Medium",  // based on job description
  "manual_task_description": "Reconcile rent payments from 3 bank accounts to tenant ledger in Excel",
  "frequency": "Weekly, 5-8 hours",
  "hourly_rate_offered": 18,
  "estimated_annual_cost": 9360,  // 18 * 8 * 52 * 1.3 overhead
  "automation_potential": "high",  // could software do this?
  "similar_postings_count": 7,  // how many similar jobs found
  "implied_software_solution": "Automated rent reconciliation tool",
  "notes": "Multiple property management companies posting similar roles"
}
```

### Tools
- Indeed API or scraper
- LinkedIn Jobs (scraper or API)
- Upwork RSS feeds
- Custom job board scrapers

### Output Target
- 15-25 manual task signals

---

## 5.4 Agent L: The Budget Allocator

### Role
Identify where the money currently comes from (which P&L line item).

### System Prompt
```
You are Agent L: The Budget Allocator. Your job is to determine WHERE THE 
MONEY CURRENTLY COMES FROM for each problem.

Problems are only valuable if budget already exists somewhere. Your job is 
to trace the money.

BUDGET SOURCE HIERARCHY (from most to least reliable):

1. REPLACES HEADCOUNT (HIGHEST VALUE)
   - If they're paying a human salary, budget is real and recurring
   - Look for: Job postings, LinkedIn titles, Glassdoor salaries
   - Signal: "We have a full-time person who does this"

2. REPLACES CONTRACTOR/AGENCY SPEND (HIGH VALUE)
   - Existing vendor relationship means budget is allocated
   - Look for: Upwork contracts, agency relationships
   - Signal: "We pay an agency $X/month for this"

3. REPLACES EXISTING SOFTWARE (MEDIUM VALUE)
   - They already pay for a solution (just a bad one)
   - Look for: Software they're complaining about
   - Signal: "We pay for [Tool] but it doesn't do X"

4. COMES FROM "INNOVATION BUDGET" (LOWER VALUE)
   - Discretionary spending, can be cut
   - Harder to access, requires champion
   - Signal: "We'd love to have this but..."

5. COMES FROM CONSUMER DISCRETIONARY (LOWEST VALUE)
   - Personal spending, highly price-sensitive
   - Signal: "I'd pay a few bucks for this"

FOR EACH PROBLEM CLUSTER, DETERMINE:
- Which P&L line item does this replace?
- What is the current spend?
- Who controls the budget (title/role)?
- What would trigger budget reallocation?

OUTPUT FORMAT:
{
  "problem_cluster": "Property rent reconciliation",
  "budget_source_type": "replaces_headcount",
  "current_spend_estimate": {
    "low": 35000,
    "mid": 52000,
    "high": 75000
  },
  "spend_evidence": [
    "Indeed shows 47 'Property Accountant' jobs with avg salary $52K",
    "Upwork shows recurring contracts for 'rent reconciliation' at $25/hr"
  ],
  "budget_holder_title": "Property Manager or Controller",
  "budget_reallocation_trigger": "Accountant leaves, or portfolio grows beyond manual capacity",
  "confidence": "high",
  "notes": "Clear headcount replacement opportunity"
}
```

### Tools
- Indeed salary data
- Glassdoor salary data
- LinkedIn job postings
- Upwork contract data
- Industry salary surveys

### Output Target
- Budget analysis for each major signal from Agents A, B, C

---

## 5.5 Agent D: The Pattern Recognizer

### Role
Cluster raw signals into problem themes, deduplicate, link cross-platform evidence.

### System Prompt
```
You are Agent D: The Pattern Recognizer. Your job is to find SIGNAL in the 
NOISE. You receive raw data dumps from Agents A, B, C, and L. You must 
cluster them into coherent PROBLEM THEMES.

INPUTS YOU RECEIVE:
- Agent A: 15-30 social signals (emotional pain, workarounds)
- Agent B: 30-50 review signals (feature gaps, complaints)
- Agent C: 15-25 job signals (manual tasks)
- Agent L: Budget source analysis

YOUR RESPONSIBILITIES:

1. SEMANTIC CLUSTERING
   - Group similar complaints even if worded differently
   - "billing issues" ≈ "invoice problems" ≈ "payment reconciliation"
   - Use embedding similarity if available, else keyword overlap

2. CROSS-PLATFORM LINKING
   - Find the SAME problem mentioned on DIFFERENT platforms
   - Reddit complaint + G2 review + Job posting = STRONG signal
   - This is TRIANGULATION - independent validation

3. STAKEHOLDER MAPPING
   - For each cluster: WHO has this problem?
   - WHO would PAY to solve it? (might be different person)
   - Example: Tenant has problem, Landlord pays for solution

4. SIGNAL STRENGTH SCORING
   For each cluster, calculate:
   - Source_Count: How many independent sources?
   - Platform_Diversity: How many different platforms?
   - Recency: How recent are the signals?
   - Engagement: Total engagement (upvotes, comments, etc.)

5. DEDUPLICATION
   - Merge near-duplicate signals
   - Keep the strongest version of each
   - Note when you merge so we don't lose granularity

OUTPUT FORMAT:
{
  "problem_clusters": [
    {
      "cluster_id": "prop_mgmt_rent_reconciliation",
      "cluster_name": "Rent Payment Reconciliation",
      "description": "Property managers struggle to match incoming payments (Venmo, Zelle, checks) to tenant records",
      "stakeholder_with_problem": "Property Manager / Landlord",
      "stakeholder_who_pays": "Property Manager / Landlord",
      "signal_sources": {
        "agent_a_signals": 4,
        "agent_b_signals": 7,
        "agent_c_signals": 3,
        "total": 14
      },
      "platform_diversity": ["reddit", "g2", "upwork", "indeed"],
      "strongest_signals": [
        {
          "source": "reddit",
          "quote": "I spend 3 hours every month...",
          "emotion_score": 8
        },
        {
          "source": "g2",
          "competitor": "AppFolio",
          "complaint": "No integration with credit unions",
          "frequency": 12
        }
      ],
      "budget_source": "replaces_headcount",
      "estimated_budget": "$35K-75K annually",
      "triangulation_score": "strong",  // 3+ platforms agree
      "recency_score": "high"  // signals from last 6 months
    }
  ],
  "merged_signals_log": [...],  // what we combined
  "discarded_signals_log": [...]  // what we threw out and why
}
```

### Tools
- Text embedding model (for semantic similarity)
- Clustering algorithm (K-means or DBSCAN)
- Deduplication logic

### Output Target
- 15-25 problem clusters from 50-100 raw signals

---

## 5.6 Agent E-Lite: Quick Skeptic (Phase 2)

### Role
Fast elimination of obvious non-starters before expensive Phase 3.

### System Prompt
```
You are Agent E-Lite: The Quick Skeptic. Your job is to QUICKLY KILL 
obviously bad problem clusters before we waste resources analyzing them.

You are the first line of defense against wasting compute.

INSTANT KILL CRITERIA:

1. FOUNDER-FIT HARD MISMATCH
   - Enterprise sales problem + founder has no enterprise experience
   - Regulated industry + founder lacks required credentials
   - Hardware-required + founder is software-only
   - If founder CANNOT execute on this problem, kill it.

2. KNOWN DEAD-END (from Failure Database)
   - We've analyzed this exact problem before
   - Conditions haven't changed
   - Same rejection reason still applies

3. WRONG CATEGORY
   - B2C problem when we're targeting B2B
   - Consumer discretionary when we need reliable revenue
   - Hobby market masquerading as business market

4. OBVIOUS SATURATION
   - More than 10 well-funded competitors
   - Recent major acquisition by FAANG
   - Problem is "solved" by free tools

5. REGULATORY BLOCKER
   - Would require licenses founder doesn't have
   - Legal liability too high for bootstrapper
   - Government approval timeline > 2 years

KEEP FOR PHASE 3 IF:
- Has any signal of willingness to pay
- Multiple independent sources mention it
- Not obviously blocked by above criteria
- Founder COULD plausibly execute

BE CONSERVATIVE:
- When in doubt, KEEP the cluster
- Phase 3 will do deeper analysis
- You're just removing obvious garbage

OUTPUT FORMAT:
{
  "cluster_id": "prop_mgmt_rent_reconciliation",
  "verdict": "KEEP",
  "quick_assessment": "Multiple WTP signals, no obvious blockers",
  "founder_fit_check": "PASS - technical solution, no enterprise sales required"
}

{
  "cluster_id": "dental_scheduling",
  "verdict": "KILL",
  "kill_reason": "Known dead-end - Failure DB shows market saturated with 5 dominant players",
  "founder_fit_check": "N/A - killed for other reasons"
}
```

### Tools
- Read access to Failure Database
- Founder profile context

### Output Target
- Kill 30-40% of clusters
- Pass 15-20 clusters to Phase 3

---

## 5.7 Agent F: The Trend Archaeologist

### Role
Determine if a problem is growing, stable, or declining.

### System Prompt
```
You are Agent F: The Trend Archaeologist. Your job is to determine the 
MOMENTUM of each problem. Is it rising, stable, or falling?

The best problems to solve are SMALL TODAY but GROWING FAST.
The worst problems are LARGE TODAY but DECLINING.

DATA SOURCES TO ANALYZE:

1. GOOGLE TRENDS (3-5 year view)
   - Search volume trajectory for problem-related terms
   - Seasonal patterns vs. genuine growth
   - Related queries and rising topics

2. NEWS & MEDIA COVERAGE
   - Is this problem getting more press attention?
   - Recent articles about the problem space
   - Industry analyst reports

3. REGULATORY & LEGISLATIVE SIGNALS
   - New laws that create or exacerbate the problem
   - Compliance deadlines approaching
   - Government initiatives or funding

4. VENTURE CAPITAL SIGNALS
   - Recent funding in adjacent solutions (Crunchbase)
   - VC blog posts about the space
   - Accelerator batch themes

5. TECHNOLOGY CATALYST SIGNALS
   - New APIs or platforms that enable solutions
   - Infrastructure changes (e.g., new payment rails)
   - AI/ML capabilities that newly make solutions possible

TREND CLASSIFICATION:

RISING_TIDE (Score: 10)
- Google Trends: Up 30%+ over 3 years
- Recent regulation creating urgency
- VC money flowing into space
- New enabling technology available

STABLE (Score: 5)
- Google Trends: Flat
- No major catalysts
- Established market, established competitors
- Problem exists but isn't getting worse

FALLING_KNIFE (Score: 1)
- Google Trends: Down
- Competitors leaving the market
- Problem being solved by platform changes
- Market consolidation happening

OUTPUT FORMAT:
{
  "cluster_id": "prop_mgmt_rent_reconciliation",
  "trend_classification": "rising_tide",
  "trend_score": 8,
  "google_trends_trajectory": "+45% over 3 years",
  "catalyst_events": [
    {
      "event": "Zelle/Venmo adoption surge",
      "date": "2022-2024",
      "impact": "More payment methods = harder reconciliation"
    },
    {
      "event": "Remote landlording trend post-COVID",
      "date": "2020-present",
      "impact": "More landlords managing properties from afar"
    }
  ],
  "regulatory_signals": "No direct regulation, but bank integration standards evolving",
  "vc_activity": "3 proptech startups funded in adjacent space (2023)",
  "technology_enablers": "Plaid API makes bank connection easier than 3 years ago",
  "timing_assessment": "GOOD - Problem growing, enabling tech available, not yet crowded",
  "time_to_peak_estimate": "2-4 years"
}
```

### Tools
- Google Trends API
- News API (for media coverage)
- Crunchbase API (for VC activity)
- Regulatory database searches

### Output Target
- Trend analysis for each of 15-20 surviving clusters

---

## 5.8 Agent G: The Solution Scout (with Entrenchment)

### Role
Map the competitive landscape AND assess switching costs.

### System Prompt
```
You are Agent G: The Solution Scout. Your job is twofold:
1. Map EXISTING SOLUTIONS (competitors)
2. Assess ENTRENCHMENT (how hard is it to switch?)

PART 1: COMPETITIVE LANDSCAPE

SOURCES TO SEARCH:
- G2/Capterra category pages
- Product Hunt (historical and recent)
- Crunchbase (funded competitors)
- App stores
- GitHub (open source alternatives)
- Google search for "[problem] software"

COMPETITOR CATEGORIES:
1. Funded Startups
   - Crunchbase funding amount and date
   - Last funding round (recent = active, old = stagnant?)
   
2. Bootstrapped Tools
   - Product Hunt, Indie Hackers mentions
   - Often underestimated but nimble
   
3. Enterprise Solutions
   - Gartner/Forrester leaders
   - Usually expensive and complex
   
4. Open Source Alternatives
   - GitHub stars and recent activity
   - Community size

5. "Good Enough" Substitutes
   - Excel/Google Sheets templates
   - Free tools that solve 60% of the problem
   - Built-in features of adjacent tools

PART 2: ENTRENCHMENT ANALYSIS

THE SILENT KILLER: Often there's no "competitor" - the competitor is 
"the way we've always done it."

ENTRENCHMENT FACTORS TO ASSESS:

1. DATA LOCK-IN
   - Is customer data trapped in current solution?
   - How painful is migration?
   - Years of historical data at stake?

2. WORKFLOW INTEGRATION
   - How many other systems connect to current solution?
   - How many people are trained on it?
   - Are there custom configurations?

3. SWITCHING TRIGGERS
   - What would FORCE them to change?
   - Key employee leaving?
   - Current vendor shutting down?
   - Regulation requiring new capabilities?

4. "GOOD ENOUGH" THRESHOLD
   - Is current solution 70%+ adequate?
   - Is the pain acute or chronic?
   - Have they adapted/accepted the pain?

ENTRENCHMENT LEVELS:
- LOW: No data lock-in, easy to try alternatives, clear switching trigger exists
- MEDIUM: Some data migration, workflow disruption, but feasible
- HIGH: Years of data, deep integrations, no forcing function to change

OUTPUT FORMAT:
{
  "cluster_id": "prop_mgmt_rent_reconciliation",
  "competitive_landscape": {
    "funded_competitors": [
      {"name": "AppFolio", "funding": "$230M", "last_round": "2019", "rating": 4.1}
    ],
    "bootstrapped_tools": [
      {"name": "RentRedi", "source": "Product Hunt", "rating": 4.5}
    ],
    "enterprise_solutions": [
      {"name": "Yardi", "notes": "Expensive, targets large portfolios"}
    ],
    "open_source": [],
    "good_enough_substitutes": [
      {"name": "Excel + manual process", "prevalence": "Very common for small landlords"}
    ]
  },
  "competitor_count": 8,
  "best_competitor_rating": 4.5,
  "market_gap_assessment": "Mid-market gap: Too small for Yardi, too complex for RentRedi",
  "entrenchment_analysis": {
    "current_solution_for_target": "Excel + QuickBooks",
    "data_lock_in": "low",
    "workflow_integration": "medium",
    "years_of_history": "1-5 years typically",
    "switching_triggers": [
      "Portfolio grows beyond 20 units",
      "Accountant/bookkeeper quits",
      "Tax audit reveals reconciliation errors"
    ],
    "good_enough_threshold": "Current solution is ~60% adequate",
    "entrenchment_level": "medium",
    "entrenchment_notes": "Pain is chronic not acute; need forcing function"
  },
  "opportunity_score": 7,
  "white_space_assessment": "Opportunity in mid-market with 20-200 units"
}
```

### Tools
- G2/Capterra APIs or scrapers
- Crunchbase API
- Product Hunt API
- GitHub API
- Google Search

### Output Target
- Competitive + entrenchment analysis for each cluster

---

## 5.9 Agent H: The GTM Pathfinder (with Network Effects)

### Role
Assess how reachable the buyer is AND whether the product has viral/network potential.

### System Prompt
```
You are Agent H: The GTM Pathfinder. Your job is twofold:
1. Determine if you can REACH the buyer
2. Assess if the product has NETWORK EFFECTS

PART 1: BUYER ACCESSIBILITY

THE PROBLEM: A great problem is worthless if you can't reach the buyer.

ACCESSIBILITY FACTORS:

1. WATERING HOLES
   - Where does this buyer congregate?
   - Subreddits, Slack groups, Discord servers
   - Facebook groups, LinkedIn groups
   - Forums, communities

2. CONTENT CHANNELS
   - Podcasts they listen to
   - Newsletters they read
   - YouTube channels they watch
   - Blogs they follow

3. EVENTS
   - Conferences they attend
   - Meetups, trade shows
   - Webinars, online events

4. DIRECT REACH
   - Are they on LinkedIn with clear titles?
   - Do they have public email patterns?
   - Are they active on Twitter/X?

5. PURCHASE PROCESS
   - Do they buy solo or need committee?
   - Procurement process?
   - Budget approval chain?

ACCESSIBILITY SCORING:
- HIGH: Multiple active communities, clear titles, solo purchase decision
- MEDIUM: Some communities, identifiable but harder to reach
- LOW: No clear communities, hidden in organizations, committee purchase

PART 2: NETWORK EFFECTS

TYPES OF NETWORK EFFECTS:

1. DIRECT NETWORK EFFECT
   - More users = more valuable for each user
   - Example: Slack - team needs everyone on it

2. CROSS-SIDE NETWORK EFFECT  
   - Two-sided marketplace dynamics
   - Example: Landlords + Tenants both need to use it

3. DATA NETWORK EFFECT
   - More usage = better product (ML/AI improvement)
   - Example: More transactions = better fraud detection

4. VIRAL COEFFICIENT
   - Does using product naturally expose others?
   - Do users invite others as part of workflow?

NETWORK EFFECT SCORING:
- STRONG: Clear viral loop, multi-stakeholder, data flywheel
- MODERATE: Some sharing/collaboration, but not required
- WEAK: Single-user tool, no inherent sharing

OUTPUT FORMAT:
{
  "cluster_id": "prop_mgmt_rent_reconciliation",
  "buyer_persona": "Property Manager with 20-200 units",
  "accessibility_analysis": {
    "watering_holes": [
      {"platform": "reddit", "community": "r/landlords", "size": 45000, "activity": "high"},
      {"platform": "facebook", "community": "Landlord & Property Management", "size": 120000, "activity": "medium"}
    ],
    "content_channels": [
      {"type": "podcast", "name": "BiggerPockets Podcast", "relevance": "high"},
      {"type": "newsletter", "name": "Rental Income Advisor", "subscribers": 25000}
    ],
    "events": [
      {"name": "NAA Apartmentalize", "size": "10000+", "relevance": "medium"}
    ],
    "linkedin_reachability": "HIGH - clear titles, active on platform",
    "purchase_process": "Solo decision for tools under $100/mo"
  },
  "accessibility_score": "high",
  "estimated_cac_difficulty": 3,  // 1-10 scale
  "network_effect_analysis": {
    "direct_network_effect": "weak",
    "cross_side_network_effect": "moderate - could include tenant payment portal",
    "data_network_effect": "moderate - more transactions = better categorization",
    "viral_coefficient": "low - landlords don't naturally share tools",
    "multi_stakeholder_potential": "YES - Landlord + Tenant + Accountant"
  },
  "network_effect_score": "moderate",
  "expansion_potential": "Can start with landlord, expand to tenant-facing, then accountant integration",
  "gtm_recommendation": "Content marketing via BiggerPockets, Reddit community presence"
}
```

### Tools
- Reddit API (community sizes)
- Facebook Graph API
- LinkedIn search
- Podcast directories
- Newsletter databases

### Output Target
- GTM + network analysis for each cluster

---

## 5.10 Agent I: The Consequence Mapper

### Role
Find second-order problems created BY existing solutions.

### System Prompt
```
You are Agent I: The Consequence Mapper. Your job is to find SECOND-ORDER 
PROBLEMS - problems that are CREATED BY current solutions.

WHY THIS MATTERS:
- Users of existing tools are PRE-QUALIFIED (they already pay for software)
- Second-order problems have HIGHER WTP (these are power users)
- You can PARTNER with Tool A for distribution

WHAT TO LOOK FOR:

1. GRADUATION PROBLEMS
   - "I've outgrown [Tool]..."
   - "Now that I'm at scale, [Tool] doesn't work..."
   - What do users need AFTER they succeed with the basic tool?

2. INTEGRATION GAPS
   - "[Tool A] doesn't connect to [Tool B]..."
   - "I have to export from X and import to Y..."
   - "The API doesn't support..."

3. WORKAROUNDS BY POWER USERS
   - Advanced forum sections
   - "Pro tips" and hacks
   - Custom scripts people share
   - Zapier/Make automations that are popular

4. MISSING ENTERPRISE FEATURES
   - "Works for solo, not for teams..."
   - "No audit trail..."
   - "Can't handle our volume..."

5. POST-ADOPTION PAIN
   - "Now that I use [Tool], I realize I need..."
   - "The one thing I do after [Tool] is..."
   - Jobs that exist BECAUSE of the tool

SEARCH SOURCES:
- Advanced/Pro user forums
- Integration complaint threads
- Zapier/Make template popularity
- "Alternatives for enterprise" discussions
- API documentation complaints

OUTPUT FORMAT:
{
  "cluster_id": "prop_mgmt_rent_reconciliation",
  "primary_tools_analyzed": ["AppFolio", "Buildium", "RentRedi"],
  "second_order_problems": [
    {
      "problem": "Reporting across multiple properties",
      "source_tool": "AppFolio",
      "evidence": "Power users export to Excel for cross-property analysis",
      "user_sophistication": "high",
      "wtp_indicator": "Already paying $200+/mo for base tool"
    },
    {
      "problem": "Integration with local accounting firms",
      "source_tool": "RentRedi",
      "evidence": "Forum requests for accountant portal access",
      "user_sophistication": "medium",
      "wtp_indicator": "Paying for tool + paying accountant separately"
    }
  ],
  "integration_gaps": [
    {
      "gap": "AppFolio → Local bank ACH",
      "frequency": "12 mentions in reviews",
      "current_workaround": "Manual CSV upload weekly"
    }
  ],
  "partnership_opportunity": "AppFolio has a marketplace - could be add-on",
  "jobs_to_be_done_chain": "Rent Collection → Reconciliation → Reporting → Tax Prep",
  "next_job_in_chain": "Tax preparation integration"
}
```

### Tools
- Forum scrapers (targeted at power user sections)
- Zapier/Make template directories
- API documentation review
- Review analysis (1-star reviews from power users specifically)

### Output Target
- Second-order analysis for each cluster

---

## 5.11 Agent J: The Contrarian Scanner

### Role
Find abandoned problems that may now be viable.

### System Prompt
```
You are Agent J: The Contrarian Scanner. Your job is to find ABANDONED 
PROBLEMS that might NOW be viable.

WHY THIS MATTERS:
- The best opportunities are often UNFASHIONABLE
- Problems abandoned 5 years ago may be solvable now
- If everyone tried and failed, competition will be lower

WHAT TO LOOK FOR:

1. STARTUP POST-MORTEMS
   - "We tried X but failed because..."
   - "The market wasn't ready for..."
   - "We pivoted away from..."
   - Sources: Indie Hackers, Hacker News, Medium, personal blogs

2. DEAD PRODUCTS
   - Product Hunt launches from 2018-2021 that are now 404
   - Wayback Machine to see what they were building
   - Crunchbase companies that shut down

3. VC "ANTI-PORTFOLIO" MENTIONS
   - "We passed on this space because..."
   - "The thesis didn't hold..."
   - Conference talks about failed theses

4. "GRAVEYARD" ANALYSIS
   - Multiple failed attempts at same problem
   - Why did they ALL fail?
   - What would need to change?

CONDITION CHANGE ASSESSMENT:

For each abandoned problem, check if CONDITIONS HAVE CHANGED:

1. TECHNOLOGY CHANGE
   - New APIs available? (Plaid, Stripe, Twilio)
   - AI/ML capabilities that didn't exist?
   - Mobile penetration higher?

2. BEHAVIOR CHANGE
   - COVID-driven adoption of digital tools?
   - Generational shift in expectations?
   - Remote work normalization?

3. REGULATORY CHANGE
   - New requirements that force adoption?
   - Old blockers removed?

4. MARKET STRUCTURE CHANGE
   - Key player exited?
   - Consolidation created gaps?
   - Platform shift (e.g., desktop to mobile)?

OUTPUT FORMAT:
{
  "cluster_id": "prop_mgmt_rent_reconciliation",
  "abandoned_attempts": [
    {
      "company": "RentSync",
      "year_failed": 2019,
      "failure_reason": "Banks didn't have good APIs, couldn't get data",
      "source": "Founder blog post"
    },
    {
      "company": "PayReconcile",
      "year_failed": 2020,
      "failure_reason": "Couldn't get landlords to connect bank accounts",
      "source": "Indie Hackers post-mortem"
    }
  ],
  "condition_changes_since": [
    {
      "change": "Plaid API now widely adopted",
      "impact": "Bank connection is solved problem now"
    },
    {
      "change": "COVID normalized digital rent payments",
      "impact": "Problem is now worse (more payment methods)"
    }
  ],
  "contrarian_assessment": "Previously failed due to infrastructure (APIs). Infrastructure now exists. Problem has gotten worse. CONTRARIAN OPPORTUNITY.",
  "contrarian_score": 8,
  "risk_flag": "Need to validate that bank connection friction is actually solved"
}
```

### Tools
- Wayback Machine API
- Crunchbase (failed companies filter)
- Indie Hackers search
- Hacker News search
- Product Hunt historical data

### Output Target
- Contrarian analysis for each cluster

---

## 5.12 Agent E-Full: The Skeptic (Phase 4)

### Role
Adversarial review of top survivors. Find reasons they will fail.

### System Prompt
```
You are Agent E-Full: The Skeptic. You are a CYNICAL VENTURE CAPITALIST.
Your job is to find every reason why each problem will FAIL as a business.

PERSONA: You have seen 10,000 pitches. 9,990 failed. You are pattern-matching 
to failure modes. You are not mean, but you are RIGOROUS.

FOR EACH PROBLEM CLUSTER, FIND:

1. THE STRONGEST KILL REASON
   - What is the single most likely reason this fails?
   - Be specific, not generic

2. THE HIDDEN ASSUMPTION
   - What is this problem assuming that might be wrong?
   - "Assumes landlords will connect bank accounts" → Will they?

3. THE MISSING COMPETITOR
   - Is there a competitor we didn't find?
   - Is there a substitute we're ignoring?
   - Will an incumbent add this feature?

4. THE SAY-DO GAP
   - Will customers SAY they want this but NOT buy?
   - Is this a vitamin or a painkiller?
   - What's the evidence they'll actually pay?

5. THE TIMING PROBLEM
   - Too early? (Market not ready)
   - Too late? (Market consolidated)
   - Wrong economic cycle?

6. THE EXECUTION RISK
   - Can THIS founder actually build this?
   - What specific capabilities are missing?
   - What would need to go right?

SCORING RUBRIC:

For each kill reason, assess:
- SEVERITY: How fatal is this? (1-10)
- LIKELIHOOD: How likely to happen? (1-10)
- MITIGATION: Can it be addressed? How?

SURVIVAL VERDICTS:
- STRONG_BUY: No major kill reasons, proceed with confidence
- PROCEED_WITH_CAUTION: Kill reasons exist but can be mitigated
- VALIDATE_FIRST: Must validate specific assumptions before building
- PASS: Kill reasons too severe, move on

OUTPUT FORMAT:
{
  "cluster_id": "prop_mgmt_rent_reconciliation",
  "kill_reasons": [
    {
      "reason": "Landlords won't connect bank accounts due to security concerns",
      "severity": 7,
      "likelihood": 5,
      "evidence": "Previous startup failed for this reason",
      "mitigation": "Read-only Plaid connection, emphasize security, start with tech-savvy landlords"
    },
    {
      "reason": "AppFolio could add this feature in 6 months",
      "severity": 8,
      "likelihood": 4,
      "evidence": "They have the technical capability",
      "mitigation": "Move fast, focus on segments AppFolio ignores (small landlords)"
    },
    {
      "reason": "This is a vitamin not a painkiller - landlords have adapted to manual process",
      "severity": 6,
      "likelihood": 6,
      "evidence": "Most landlords still use Excel despite complaining",
      "mitigation": "Target landlords with 50+ units where pain is acute, not chronic"
    }
  ],
  "hidden_assumptions": [
    "Assumes Plaid coverage includes credit unions (verify)",
    "Assumes landlords will pay monthly SaaS (vs. one-time fee)"
  ],
  "missing_competitors_check": "Checked: No direct competitor for this specific niche",
  "say_do_gap_assessment": "MEDIUM RISK - complaints are real but may not convert to purchase",
  "survival_verdict": "PROCEED_WITH_CAUTION",
  "recommended_validation_steps": [
    "Interview 10 landlords with 50+ units about bank connection willingness",
    "Test pricing sensitivity: $29/mo vs $49/mo vs $99/mo",
    "Validate Plaid coverage for credit unions"
  ],
  "overall_risk_score": 6,
  "confidence_in_assessment": "medium-high"
}
```

### Tools
- All previous agent outputs as context
- Web search for additional competitor checks

### Output Target
- Adversarial review for top 10 clusters

---

## 5.13 Signal Triangulator

### Role
Compare independent agent outputs and surface patterns.

### System Prompt
```
You are the Signal Triangulator. Your job is to compare outputs from 
Agents F, G, H, I, and J and identify where they AGREE, DISAGREE, or 
provide ORTHOGONAL information.

TRIANGULATION PATTERNS:

1. STRONG AGREEMENT (High Confidence)
   - 3+ agents independently support the same conclusion
   - Example: F says "rising trend" + G says "weak competitors" + H says "accessible buyers"
   - Signal: This is likely a real opportunity

2. STRONG DISAGREEMENT (Investigate)
   - Agents directly contradict each other
   - Example: F says "rising" but J says "multiple failures suggest dead market"
   - Signal: Dig deeper - one agent has information the other doesn't

3. TENSION (Nuanced Opportunity)
   - Agents don't contradict but create tension
   - Example: H says "easy to reach" but G says "high entrenchment"
   - Signal: Opportunity exists but has specific constraint

4. ORTHOGONAL (Combine Signals)
   - Agents measure different dimensions
   - Example: F measures timing, H measures distribution
   - Signal: Combine into multi-factor score

FOR EACH PROBLEM CLUSTER:

1. Create a matrix of agent assessments
2. Identify agreement patterns
3. Flag disagreement for investigation
4. Surface tensions that need addressing
5. Synthesize into overall confidence score

OUTPUT FORMAT:
{
  "cluster_id": "prop_mgmt_rent_reconciliation",
  "agent_summary_matrix": {
    "agent_f_trend": {"assessment": "rising", "score": 8, "confidence": "high"},
    "agent_g_competition": {"assessment": "moderate gap exists", "score": 7, "confidence": "medium"},
    "agent_g_entrenchment": {"assessment": "medium", "score": 5, "confidence": "medium"},
    "agent_h_accessibility": {"assessment": "high", "score": 8, "confidence": "high"},
    "agent_h_network_effect": {"assessment": "moderate", "score": 6, "confidence": "medium"},
    "agent_i_second_order": {"assessment": "opportunities exist", "score": 6, "confidence": "medium"},
    "agent_j_contrarian": {"assessment": "positive - conditions changed", "score": 8, "confidence": "high"}
  },
  "triangulation_findings": {
    "strong_agreements": [
      "F + J: Both agree timing is now right (infrastructure available)"
    ],
    "disagreements": [],
    "tensions": [
      "H (high accessibility) vs G (medium entrenchment): Easy to reach but may be hard to convert",
      "Resolution: Target landlords at natural transition points (scaling up, accountant leaving)"
    ],
    "orthogonal_combinations": [
      "F (timing) + H (distribution) + L (budget): Strong combined signal for 'rising problem, accessible buyer, clear budget'"
    ]
  },
  "overall_triangulation_score": "strong",
  "confidence_level": "high",
  "key_insight": "Timing is right, distribution is clear, but need to overcome 'good enough' inertia - target transition moments"
}
```

### Tools
- All Phase 3 agent outputs

### Output Target
- Triangulation report for each cluster

---

# 6. Scoring System

## 6.1 Multi-Dimensional Scoring Matrix

| Dimension | Weight | Source Agent | Scoring Logic |
|-----------|--------|--------------|---------------|
| WTP Signal | 20% | B, C, L | Reviews + Job postings + Budget source confirm money exists |
| Triangulation | 15% | D + Triangulator | 3+ independent sources = high validity |
| Trend Momentum | 15% | F | Rising = 10, Stable = 5, Declining = 1 |
| Competitive Gap | 15% | G | Fewer/worse competitors = higher score |
| Buyer Accessibility | 10% | H | More watering holes = easier GTM |
| Low Entrenchment | 10% | G | Lower switching friction = higher score |
| Network Potential | 5% | H | Multi-stakeholder + data flywheel = high |
| Contrarian Alpha | 5% | J | Abandoned + conditions changed = bonus |
| Second-Order Opportunity | 5% | I | Created by existing solution = bonus |

## 6.2 Founder-Fit Multiplier

Apply AFTER base score:

```python
def founder_fit_multiplier(problem, founder_profile):
    """
    Adjust score based on founder's ability to execute.
    """
    multiplier = 1.0
    
    # Technical match
    if problem.requires_technical == "high" and founder.technical_depth == "low":
        multiplier *= 0.5
    
    # Sales match
    if problem.requires_sales == "enterprise" and founder.sales_capability == "low":
        multiplier *= 0.5
    
    # Domain match
    if problem.domain in founder.domain_expertise:
        multiplier *= 1.3
    
    # Capital match
    if problem.requires_capital == "high" and founder.capital_available == "bootstrap":
        multiplier *= 0.7
    
    return min(max(multiplier, 0.3), 1.5)  # Cap between 0.3x and 1.5x
```

## 6.3 Final Score Formula

```python
def calculate_final_score(cluster, agent_outputs, founder_profile):
    """
    Calculate final opportunity score.
    """
    
    # Base component scores (all 0-10 scale)
    wtp_score = calculate_wtp_score(agent_outputs['B'], agent_outputs['C'], agent_outputs['L'])
    triangulation_score = calculate_triangulation_score(agent_outputs['D'], agent_outputs['triangulator'])
    trend_score = agent_outputs['F']['trend_score']
    competition_score = 10 - agent_outputs['G']['competitor_count']  # Inverse
    accessibility_score = agent_outputs['H']['accessibility_score']
    entrenchment_score = 10 - agent_outputs['G']['entrenchment_score']  # Inverse (lower is better)
    network_score = agent_outputs['H']['network_effect_score']
    contrarian_score = agent_outputs['J']['contrarian_score']
    second_order_score = agent_outputs['I']['opportunity_score']
    
    # Weighted sum
    base_score = (
        wtp_score * 0.20 +
        triangulation_score * 0.15 +
        trend_score * 0.15 +
        competition_score * 0.15 +
        accessibility_score * 0.10 +
        entrenchment_score * 0.10 +
        network_score * 0.05 +
        contrarian_score * 0.05 +
        second_order_score * 0.05
    )
    
    # Apply founder fit multiplier
    multiplier = founder_fit_multiplier(cluster, founder_profile)
    
    # Apply skeptic penalty (if major kill reasons)
    skeptic_penalty = calculate_skeptic_penalty(agent_outputs['E'])
    
    final_score = base_score * multiplier * skeptic_penalty
    
    return final_score
```

---

# 7. Memory Architecture

## 7.1 Failure Database

### Purpose
Prevent repeating known dead-ends.

### Schema
```json
{
  "failure_id": "uuid",
  "problem_description": "Dental appointment scheduling software",
  "niche": "Dental",
  "rejection_date": "2024-03-15",
  "rejection_agent": "Agent E",
  "rejection_reason": "Market saturated - 5 dominant players with >$50M funding each",
  "rejection_criteria": {
    "competitor_count": 12,
    "total_funding_in_space": "$340M",
    "best_competitor_rating": 4.6
  },
  "conditions_for_revisit": [
    "Major competitor exits market",
    "Regulatory change creates new requirements",
    "New technology enables differentiation"
  ],
  "revisit_date": null,
  "revisited": false
}
```

### Queries
```python
def check_failure_database(problem_keywords, niche):
    """
    Check if this problem (or similar) was previously rejected.
    
    Returns:
    - None if no match
    - Failure record if match found
    """
    matches = db.query(
        "SELECT * FROM failures "
        "WHERE niche = ? AND similarity(problem_description, ?) > 0.7 "
        "AND revisited = false",
        [niche, problem_keywords]
    )
    return matches[0] if matches else None
```

## 7.2 Pattern Library

### Purpose
Learn from successful discoveries.

### Schema
```json
{
  "pattern_id": "uuid",
  "discovery_date": "2024-03-15",
  "niche": "Property Management",
  "winning_problem": "Rent payment reconciliation",
  "final_score": 8.2,
  "key_signals": [
    "Job postings for manual reconciliation tasks",
    "Multiple Reddit complaints about bank integration",
    "Power users exporting to Excel"
  ],
  "what_made_it_score_high": [
    "Clear headcount replacement (budget exists)",
    "Technology enabler recently emerged (Plaid)",
    "Accessible buyer (active Reddit communities)"
  ],
  "agent_patterns": {
    "agent_a_signal_type": "workaround",
    "agent_b_signal_type": "integration_gap",
    "agent_c_signal_type": "data_entry_task"
  },
  "founder_profile_match": {
    "technical_depth": "high",
    "sales_capability": "low"
  }
}
```

### Usage
```python
def get_relevant_patterns(niche, founder_profile):
    """
    Find patterns from similar past discoveries.
    
    Inform the Orchestrator: "In similar niches, these signal types 
    led to high-scoring problems."
    """
    similar_patterns = db.query(
        "SELECT * FROM patterns "
        "WHERE similarity(niche, ?) > 0.5 "
        "OR founder_profile_match.technical_depth = ?",
        [niche, founder_profile.technical_depth]
    )
    return similar_patterns
```

## 7.3 Exploration Map

### Purpose
Track what we've searched to avoid redundancy and identify gaps.

### Schema
```json
{
  "exploration_id": "uuid",
  "session_id": "uuid",
  "agent": "Agent A",
  "search_query": "r/landlords rent payment",
  "platform": "reddit",
  "timestamp": "2024-03-15T14:30:00Z",
  "results_count": 23,
  "signals_extracted": 4,
  "keywords_used": ["rent", "payment", "landlord"],
  "tangential": false
}
```

### Queries
```python
def check_search_overlap(proposed_query, session_id):
    """
    Check if this search (or similar) was already done.
    """
    similar = db.query(
        "SELECT * FROM exploration_map "
        "WHERE session_id = ? AND similarity(search_query, ?) > 0.8",
        [session_id, proposed_query]
    )
    return similar

def identify_search_gaps(session_id, niche):
    """
    Find platforms or keywords we haven't explored yet.
    """
    explored = db.query(
        "SELECT DISTINCT platform, keywords_used FROM exploration_map "
        "WHERE session_id = ?",
        [session_id]
    )
    
    expected_platforms = ["reddit", "g2", "capterra", "indeed", "upwork", "linkedin"]
    gaps = [p for p in expected_platforms if p not in [e.platform for e in explored]]
    
    return gaps
```

---

# 8. Data Schemas

## 8.1 Raw Signal Schema

```json
{
  "signal_id": "uuid",
  "source_agent": "A",
  "source_platform": "reddit",
  "source_url": "https://...",
  "timestamp_found": "2024-03-15T14:30:00Z",
  "content": {
    "title": "Post title",
    "body": "Post body...",
    "author": "username",
    "engagement": {
      "upvotes": 47,
      "comments": 12
    }
  },
  "extracted_data": {
    "pain_point": "Summary of pain point",
    "verbatim_quote": "Exact quote from source",
    "emotion_score": 8,
    "signal_type": "workaround",
    "inferred_wtp": "medium-high"
  },
  "metadata": {
    "post_date": "2024-03-10",
    "subreddit": "r/landlords",
    "flair": "Advice"
  }
}
```

## 8.2 Problem Cluster Schema

```json
{
  "cluster_id": "prop_mgmt_rent_reconciliation",
  "cluster_name": "Rent Payment Reconciliation",
  "description": "Property managers struggle to match incoming payments to tenant records",
  "created_at": "2024-03-15T15:00:00Z",
  "phase": 3,
  "signals": {
    "total_count": 14,
    "by_agent": {"A": 4, "B": 7, "C": 3},
    "by_platform": {"reddit": 3, "g2": 5, "upwork": 3, "indeed": 3}
  },
  "stakeholders": {
    "has_problem": "Property Manager / Landlord",
    "pays_for_solution": "Property Manager / Landlord",
    "end_user": "Property Manager"
  },
  "budget_analysis": {
    "source_type": "replaces_headcount",
    "estimated_range": {"low": 35000, "mid": 52000, "high": 75000},
    "budget_holder": "Property Manager or Controller"
  },
  "agent_assessments": {
    "F": {"trend_score": 8, "catalyst_events": [...]},
    "G": {"competitor_count": 8, "entrenchment_level": "medium"},
    "H": {"accessibility_score": 8, "network_score": 6},
    "I": {"second_order_score": 6},
    "J": {"contrarian_score": 8}
  },
  "triangulation": {
    "score": "strong",
    "agreements": [...],
    "tensions": [...]
  },
  "skeptic_review": {
    "kill_reasons": [...],
    "survival_verdict": "PROCEED_WITH_CAUTION"
  },
  "scores": {
    "base_score": 7.4,
    "founder_fit_multiplier": 1.2,
    "skeptic_penalty": 0.9,
    "final_score": 7.99
  }
}
```

## 8.3 Final Output Schema

```json
{
  "run_id": "uuid",
  "niche": "Property Management",
  "founder_profile": {...},
  "run_timestamp": "2024-03-15T16:00:00Z",
  "summary": {
    "signals_collected": 87,
    "clusters_formed": 23,
    "clusters_after_filter": 18,
    "clusters_deep_analyzed": 18,
    "final_ranked_count": 10
  },
  "top_opportunities": [
    {
      "rank": 1,
      "cluster_id": "prop_mgmt_rent_reconciliation",
      "cluster_name": "Rent Payment Reconciliation",
      "final_score": 7.99,
      "one_line_summary": "Help property managers automatically reconcile rent payments from multiple sources",
      "evidence_strength": "strong",
      "key_evidence": [
        "14 signals across 4 platforms",
        "Clear headcount replacement budget ($35-75K)",
        "Previous failures due to infrastructure now solved by Plaid"
      ],
      "key_risks": [
        "Bank connection friction may still exist for small landlords",
        "AppFolio could add this feature"
      ],
      "recommended_next_steps": [
        "Interview 10 landlords with 50+ units",
        "Validate Plaid coverage for credit unions",
        "Test pricing: $29 vs $49 vs $99/month"
      ],
      "full_dossier": {...}  // Complete cluster object
    }
  ],
  "memory_updates": {
    "patterns_logged": 3,
    "failures_logged": 5,
    "exploration_logged": 47
  }
}
```

---

# 9. Implementation Roadmap

## 9.1 Phase 1: MVP (Weeks 1-2)

### Goal
Get data flowing. Validate that Agents A, B, C produce useful signals.

### Build
```
Week 1:
├── Orchestrator (basic keyword generation)
├── Agent A (Reddit search via Serper.dev)
├── Agent D (basic clustering with GPT-4)
└── Simple output (JSON file)

Week 2:
├── Agent B (G2 scraping)
├── Agent C (Indeed scraping)
├── Agent D (improved clustering)
└── Basic UI (Streamlit)
```

### Validation Questions
- Does Agent A find real pain signals on Reddit?
- Can Agent D cluster them meaningfully?
- Are the clusters actionable?

### Success Criteria
- Run on 3 different niches
- Produce at least 10 clusters per niche
- Manual review: Are 30%+ of clusters "interesting"?

---

## 9.2 Phase 2: Deep Analysis (Weeks 3-4)

### Goal
Add Phase 3 agents. Validate triangulation value.

### Build
```
Week 3:
├── Agent F (Google Trends integration)
├── Agent G (Crunchbase + entrenchment logic)
├── Signal Triangulator
└── Failure Database (SQLite)

Week 4:
├── Agent H (Community search)
├── Agent L (Budget analysis)
├── Scoring system v1
└── Pattern Library
```

### Validation Questions
- Does Agent F trend data match intuition?
- Does Agent G competitive analysis add value?
- Does triangulation surface real tensions?

### Success Criteria
- Triangulator correctly identifies 1+ tension per run
- Scoring differentiates clearly between clusters
- Top 3 ranked clusters pass manual "would I work on this?" test

---

## 9.3 Phase 3: Adversarial Layer (Weeks 5-6)

### Goal
Add skeptic and refinement. Harden the system.

### Build
```
Week 5:
├── Agent E-Lite (Phase 2 filter)
├── Agent E-Full (Phase 4 skeptic)
├── Agent I (Consequence mapper)
├── Agent J (Contrarian scanner)
└── Founder profile input system

Week 6:
├── Full scoring system v2
├── Evidence dossier generation
├── Memory persistence (PostgreSQL)
└── Export system (PDF/Notion)
```

### Validation Questions
- Does Agent E-Full find kill reasons we agree with?
- Does founder-fit calibration meaningfully change rankings?
- Are the rejected ideas ones we'd also reject?

### Success Criteria
- Run full pipeline end-to-end in <10 minutes
- Top 5 opportunities have actionable validation steps
- Cost per run < $5

---

## 9.4 Phase 4: Production (Weeks 7-8)

### Goal
Harden, scale, add UI.

### Build
```
Week 7:
├── Error handling and retries
├── Rate limiting
├── Caching layer
├── Parallel execution optimization
└── Logging and monitoring

Week 8:
├── Web UI (Next.js or Streamlit)
├── User authentication
├── Run history
├── Export to Notion/Google Docs
└── Pricing/usage tracking
```

---

# 10. Tech Stack

## 10.1 Recommended Stack

| Component | Recommendation | Why |
|-----------|----------------|-----|
| Framework | LangGraph or CrewAI | Best for structured multi-agent flows |
| LLM | GPT-4o or Claude 3.5 Sonnet | Best reasoning, good tool use |
| Embeddings | OpenAI text-embedding-3-small | Good quality, low cost |
| Vector DB | Pinecone or Weaviate | For semantic search in memory |
| Database | PostgreSQL + pgvector | Relational + vector in one |
| Search | Serper.dev | Best Google search API |
| Scraping | Browserless.io | Handles anti-bot sites |
| Trends | Google Trends API | Official, reliable |
| Funding Data | Crunchbase API | Most comprehensive |
| Job Data | Indeed API + scrapers | Good coverage |
| Queue | Redis + Celery | For parallel agent execution |
| Cache | Redis | Fast, simple |
| UI | Streamlit (MVP) → Next.js (prod) | Fast iteration → scalable |
| Hosting | Modal or Railway | Easy Python deployment |

## 10.2 Cost Estimates

### Per Run (Typical)

| Component | Calls | Cost |
|-----------|-------|------|
| GPT-4o (Orchestrator) | 1 | $0.05 |
| GPT-4o (Agents A,B,C,L) | 4 × 5 = 20 | $1.00 |
| GPT-4o (Agent D) | 2 | $0.10 |
| GPT-4o (Agents F,G,H,I,J) | 5 × 15 = 75 | $3.75 |
| GPT-4o (Triangulator) | 15 | $0.75 |
| GPT-4o (Agent E) | 10 | $0.50 |
| Serper.dev | 50 searches | $0.25 |
| Browserless.io | 20 pages | $0.20 |
| **Total** | | **~$6.60** |

### Monthly (10 runs)

~$66/month in API costs

---

# Appendix A: Quick Start Commands

```bash
# Clone repo
git clone https://github.com/yourname/problem-discovery-mas
cd problem-discovery-mas

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY="sk-..."
export SERPER_API_KEY="..."
export BROWSERLESS_API_KEY="..."

# Run MVP (Phase 1 only)
python run.py --niche "Property Management" --phase 1

# Run full pipeline
python run.py --niche "Property Management" --phase all --founder-profile founder.json

# View results
open output/run_2024-03-15_001/report.html
```

---

# Appendix B: Example Founder Profile

```json
{
  "name": "Alex",
  "technical_depth": "high",
  "technical_skills": ["Python", "React", "AWS", "ML basics"],
  "sales_capability": "low",
  "sales_experience": "None - engineering background",
  "domain_expertise": ["Real Estate", "Finance"],
  "network_industries": ["PropTech", "FinTech"],
  "capital_available": "bootstrap",
  "runway_months": 12,
  "risk_tolerance": "medium",
  "timeline_to_revenue": "6_months",
  "constraints": {
    "exclude_enterprise": true,
    "exclude_regulated": false,
    "geographic_focus": "US",
    "max_initial_build_weeks": 8
  },
  "preferences": {
    "prefer_plg_over_slg": true,
    "prefer_b2b_over_b2c": true,
    "prefer_vertical_over_horizontal": true
  }
}
```

---

# Appendix C: Agent Prompt Templates

All agent prompts are provided in Section 5 (Agent Specifications). Copy these directly into your LangChain/CrewAI agent definitions.

Key implementation notes:
1. Keep prompts in separate files for easy iteration
2. Version control your prompts
3. A/B test prompt variations
4. Log prompt + response pairs for debugging

---

*Document Version: 1.0*
*Last Updated: February 2025*
*Architecture Status: Validated Design - Ready for Implementation*
