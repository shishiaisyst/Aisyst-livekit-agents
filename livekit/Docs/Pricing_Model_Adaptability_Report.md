# Pricing Model Adaptability & Switching Analysis

## Executive Summary

**Verdict: NO full redevelopment is needed to switch between pricing models.**

All three pricing models share 70-80% of the same infrastructure. The differences lie in configuration, not architecture. If we build the system correctly from day one with a modular design, switching between pricing models requires **2-5 days of work**, not a full rebuild.

This report provides a thorough technical analysis of each pricing model, how it maps to Stripe's billing primitives, and exactly what changes when switching between them.

---

## The Three Pricing Models

### Model 1: Tiered Packages (Base Fee + Included Minutes + Overage)

| Pack | Included Minutes | Monthly Price | Overage Rate |
|------|-----------------|---------------|--------------|
| Starter | 500 mins/month | €204/month | €0.50/min |
| Growth | 1,000 mins/month | €366/month | €0.50/min |
| Enterprise | 2,000 mins/month | €624/month | €0.50/min |

- **Yearly discount:** 10% off for annual subscriptions
- **Stripe Mapping:** Subscription with graduated tiered pricing (flat fee with overages)
- **Stripe Primitives Used:**
  - Product: "AiSyst Voice Agent"
  - Price 1: Fixed recurring price (€204/€366/€624 per month)
  - Price 2: Metered usage price with graduated tiers (first X mins at €0, then €0.50/min)
  - Meter: "voice_call_minutes" (aggregation: sum)
  - Coupon: 10% off for yearly billing
  - Stripe natively supports this exact model via "Flat Fee and Overages" pricing

### Model 2: Fixed Fee + Per Call

| Component | Amount |
|-----------|--------|
| Monthly flat fee | €49/month |
| Per call charge | €0.50/call |

- **Example:** 100 calls = €49 + (100 × €0.50) = €99
- **Stripe Mapping:** Subscription with two price items (fixed + metered)
- **Stripe Primitives Used:**
  - Product 1: "AiSyst Platform Fee" — Fixed price: €49/month
  - Product 2: "AiSyst Voice Calls" — Metered price: €0.50/call
  - Meter: "voice_calls" (aggregation: count)
  - This is Stripe's standard "flat rate with usage-based pricing" model

### Model 3: Revenue-Based (Service Fee + Revenue Percentage)

| Component | Amount |
|-----------|--------|
| Monthly service fee | €199/month |
| Revenue share | 5% of total revenue generated |

- **Example:** €10,000 revenue = €199 + (5% × €10,000) = €699
- **Stripe Mapping:** Subscription + custom invoice line items
- **Stripe Primitives Used:**
  - Product: "AiSyst Service Fee" — Fixed price: €199/month
  - Custom invoice line item: 5% of reported revenue (added before invoice finalization)
  - No Stripe Meter needed (revenue is tracked in our database, not in Stripe)
  - Uses `invoice.created` webhook to add revenue share line item before invoice is sent

---

## Architectural Decomposition

### What ALL Three Models Share (The Common Layer — ~75% of the system)

These components are **identical** regardless of which pricing model we choose:

```
┌─────────────────────────────────────────────────────────────────┐
│                    SHARED INFRASTRUCTURE                        │
│                                                                 │
│  1. Stripe Customer Management                                  │
│     - Create/update customer records                            │
│     - Store payment methods                                     │
│     - Customer portal for self-service                          │
│                                                                 │
│  2. Supabase Database                                           │
│     - customers table (customer_id, stripe_customer_id, etc.)   │
│     - subscriptions table (subscription_id, plan_type, status)  │
│     - voice_calls table (call_id, duration, timestamp)          │
│     - orders table (order_id, total_value, etc.)                │
│                                                                 │
│  3. Website Frontend                                            │
│     - Pricing page (displays plans)                             │
│     - Checkout flow (redirects to Stripe)                       │
│     - Customer dashboard                                        │
│                                                                 │
│  4. Stripe Webhook Handler (Edge Function)                      │
│     - checkout.session.completed → activate subscription        │
│     - invoice.paid → record payment                             │
│     - customer.subscription.updated → sync status               │
│     - customer.subscription.deleted → handle cancellation       │
│                                                                 │
│  5. Authentication & Authorization                              │
│     - Supabase Auth                                             │
│     - Row Level Security                                        │
│                                                                 │
│  6. Voice Call Infrastructure                                   │
│     - LiveKit / ElevenLabs agent                                │
│     - Call recording & transcription                            │
│     - L'Addition POS integration                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### What DIFFERS Between Models (The Variable Layer — ~25% of the system)

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODEL-SPECIFIC COMPONENTS                    │
│                                                                 │
│  A. Stripe Product & Price Configuration                        │
│     → Different products/prices per model                       │
│     → Created via Stripe Dashboard or API                       │
│                                                                 │
│  B. Usage Tracking Logic                                        │
│     → Model 1: Track minutes → report to Stripe Meter           │
│     → Model 2: Track call count → report to Stripe Meter        │
│     → Model 3: Track revenue → add custom invoice line item     │
│                                                                 │
│  C. Usage Reporting Edge Function                               │
│     → What metric to report and how to calculate it             │
│                                                                 │
│  D. Pricing Page Content                                        │
│     → Different plan names, prices, features displayed          │
│                                                                 │
│  E. Invoice Customization (Model 3 only)                        │
│     → Webhook to add revenue share line item to invoice         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Detailed Stripe Implementation for Each Model

### Model 1: Tiered Packages — Stripe Implementation

**Stripe Setup:**
```
Meter:
  name: "voice_call_minutes"
  event_name: "voice_call_minutes"
  aggregation: sum

Product: "AiSyst Voice Agent - Starter"
  Price (recurring): €204/month
  Price (metered, graduated tiers):
    Tier 1: 0-500 units → €0.00/unit (included in base)
    Tier 2: 501+ units → €0.50/unit (overage)

Product: "AiSyst Voice Agent - Growth"
  Price (recurring): €366/month
  Price (metered, graduated tiers):
    Tier 1: 0-1000 units → €0.00/unit
    Tier 2: 1001+ units → €0.50/unit

Product: "AiSyst Voice Agent - Enterprise"
  Price (recurring): €624/month
  Price (metered, graduated tiers):
    Tier 1: 0-2000 units → €0.00/unit
    Tier 2: 2001+ units → €0.50/unit

Coupon: "YEARLY_10_OFF"
  percent_off: 10
  duration: forever
  Applied when: customer selects yearly billing
```

**Usage Reporting (Edge Function / Backend):**
```typescript
// After each voice call ends, report minutes to Stripe
await stripe.billing.meterEvents.create({
  event_name: 'voice_call_minutes',
  payload: {
    value: callDurationMinutes.toString(),
    stripe_customer_id: customer.stripe_id
  }
});
```

**Database Schema Additions:**
```sql
-- subscription_plans table
CREATE TABLE subscription_plans (
  plan_id TEXT PRIMARY KEY,           -- 'starter', 'growth', 'enterprise'
  name TEXT NOT NULL,
  included_minutes INTEGER NOT NULL,  -- 500, 1000, 2000
  monthly_price DECIMAL(10,2),
  yearly_price DECIMAL(10,2),         -- monthly_price * 12 * 0.9
  overage_rate DECIMAL(10,2),         -- 0.50
  stripe_monthly_price_id TEXT,
  stripe_yearly_price_id TEXT,
  stripe_metered_price_id TEXT
);
```

---

### Model 2: Fixed Fee + Per Call — Stripe Implementation

**Stripe Setup:**
```
Meter:
  name: "voice_calls"
  event_name: "voice_calls"
  aggregation: count    ← counts number of events (calls)

Product 1: "AiSyst Platform Fee"
  Price: €49/month (flat recurring)

Product 2: "AiSyst Voice Calls"
  Price: €0.50/call (metered, per-unit)
  Linked to meter: "voice_calls"
```

**Usage Reporting (Edge Function / Backend):**
```typescript
// After each voice call ends, report 1 call event to Stripe
await stripe.billing.meterEvents.create({
  event_name: 'voice_calls',
  payload: {
    stripe_customer_id: customer.stripe_id
    // No value needed — aggregation is 'count'
  }
});
```

**Database Schema Additions:**
```sql
-- Simpler schema — no tiers needed
CREATE TABLE subscription_plans (
  plan_id TEXT PRIMARY KEY,           -- 'standard'
  name TEXT NOT NULL,
  flat_fee DECIMAL(10,2),             -- 49.00
  per_call_rate DECIMAL(10,2),        -- 0.50
  stripe_flat_price_id TEXT,
  stripe_metered_price_id TEXT
);
```

---

### Model 3: Revenue-Based — Stripe Implementation

**Stripe Setup:**
```
Product: "AiSyst Service Fee"
  Price: €199/month (flat recurring)

No Stripe Meter needed.
Revenue tracking happens in our database.
Revenue share is added as a custom invoice line item.
```

**Revenue Share Logic (Stripe Webhook — `invoice.created`):**
```typescript
// When Stripe creates an invoice, add the revenue share line item
// BEFORE the invoice is finalized and sent to customer

webhookHandler('invoice.created', async (invoice) => {
  const customerId = invoice.customer;
  
  // Query our database for customer's total revenue last month
  const { data } = await supabase
    .from('orders')
    .select('total_value')
    .eq('stripe_customer_id', customerId)
    .gte('created_at', startOfLastMonth)
    .lte('created_at', endOfLastMonth);
  
  const totalRevenue = data.reduce((sum, order) => sum + order.total_value, 0);
  const revenueShare = totalRevenue * 0.05; // 5% revenue share
  
  if (revenueShare > 0) {
    // Add revenue share as invoice line item
    await stripe.invoiceItems.create({
      customer: customerId,
      invoice: invoice.id,
      amount: Math.round(revenueShare * 100), // in cents
      currency: 'eur',
      description: `Revenue share (5% of €${totalRevenue.toFixed(2)})`
    });
  }
});
```

**Database Schema Additions:**
```sql
-- Need revenue tracking
CREATE TABLE subscription_plans (
  plan_id TEXT PRIMARY KEY,           -- 'standard'
  name TEXT NOT NULL,
  service_fee DECIMAL(10,2),          -- 199.00
  revenue_share_pct DECIMAL(5,2),     -- 5.00
  stripe_price_id TEXT
);

-- Existing orders table already tracks revenue per customer
-- Just need to aggregate it at billing time
```

---

## Switching Analysis: What Changes Between Models

### Switch 1: Model 1 (Tiered) → Model 2 (Fixed + Per Call)

| Component | Change Required | Effort |
|-----------|----------------|--------|
| **Stripe Products/Prices** | Create new product + prices | 30 min |
| **Stripe Meter** | Change from "sum of minutes" to "count of calls" | 30 min |
| **Usage Reporting Logic** | Change: report minutes → report call count | 1-2 hours |
| **Database: subscription_plans** | Update plan records | 30 min |
| **Website: Pricing Page** | Update UI to show new pricing | 2-4 hours |
| **Existing Customers** | Cancel old subscriptions, create new ones | 1-2 hours (scripted) |
| **Edge Function** | Minimal change to usage reporting function | 1-2 hours |
| **Webhook Handler** | No change needed | 0 |
| **Customer Management** | No change needed | 0 |
| **Voice Call System** | No change needed | 0 |
| **Total Effort** | | **~1-2 days** |

### Switch 2: Model 1 (Tiered) → Model 3 (Revenue-Based)

| Component | Change Required | Effort |
|-----------|----------------|--------|
| **Stripe Products/Prices** | Create new product + price (service fee only) | 30 min |
| **Stripe Meter** | Remove meter (not needed for Model 3) | 15 min |
| **Usage Reporting Logic** | Remove meter event reporting | 30 min |
| **Revenue Tracking** | Ensure orders table tracks revenue per customer | 1-2 hours |
| **Invoice Webhook** | **NEW:** Add `invoice.created` handler for revenue share | 3-4 hours |
| **Database: subscription_plans** | Update plan records with revenue_share_pct | 30 min |
| **Website: Pricing Page** | Update UI to show new pricing | 2-4 hours |
| **Existing Customers** | Cancel old subscriptions, create new ones | 1-2 hours (scripted) |
| **Webhook Handler** | Add invoice.created handler | 2-3 hours |
| **Customer Management** | No change needed | 0 |
| **Voice Call System** | No change needed | 0 |
| **Total Effort** | | **~2-4 days** |

### Switch 3: Model 2 (Fixed + Per Call) → Model 1 (Tiered)

| Component | Change Required | Effort |
|-----------|----------------|--------|
| **Stripe Products/Prices** | Create 3 tiered products with graduated pricing | 1 hour |
| **Stripe Meter** | Change from "count" to "sum of minutes" | 30 min |
| **Usage Reporting Logic** | Change: report call count → report minutes | 1-2 hours |
| **Database: subscription_plans** | Add tier definitions (included_minutes, overage_rate) | 1 hour |
| **Website: Pricing Page** | Update UI to show tier comparison | 3-4 hours |
| **Existing Customers** | Migrate subscriptions to new plans | 1-2 hours (scripted) |
| **Yearly Discount Logic** | Add coupon creation and application | 1-2 hours |
| **Webhook Handler** | No change needed | 0 |
| **Customer Management** | No change needed | 0 |
| **Voice Call System** | No change needed | 0 |
| **Total Effort** | | **~2-3 days** |

### Switch 4: Model 2 (Fixed + Per Call) → Model 3 (Revenue-Based)

| Component | Change Required | Effort |
|-----------|----------------|--------|
| **Stripe Products/Prices** | Create new service fee product | 30 min |
| **Stripe Meter** | Remove meter | 15 min |
| **Usage Reporting** | Remove meter event reporting | 30 min |
| **Invoice Webhook** | **NEW:** Add `invoice.created` handler | 3-4 hours |
| **Revenue Tracking** | Verify orders table tracks revenue per customer | 1 hour |
| **Website: Pricing Page** | Update UI | 2-4 hours |
| **Existing Customers** | Migrate subscriptions | 1-2 hours (scripted) |
| **Total Effort** | | **~2-4 days** |

### Switch 5: Model 3 (Revenue-Based) → Model 1 (Tiered)

| Component | Change Required | Effort |
|-----------|----------------|--------|
| **Stripe Products/Prices** | Create 3 tiered products with graduated pricing | 1 hour |
| **Stripe Meter** | **NEW:** Create "voice_call_minutes" meter | 30 min |
| **Usage Reporting** | **NEW:** Add meter event reporting after each call | 2-3 hours |
| **Invoice Webhook** | Remove `invoice.created` revenue share logic | 30 min |
| **Database** | Add tier definitions | 1 hour |
| **Website: Pricing Page** | Update UI to show tier comparison | 3-4 hours |
| **Yearly Discount** | Add coupon logic | 1-2 hours |
| **Existing Customers** | Migrate subscriptions | 1-2 hours (scripted) |
| **Total Effort** | | **~2-4 days** |

### Switch 6: Model 3 (Revenue-Based) → Model 2 (Fixed + Per Call)

| Component | Change Required | Effort |
|-----------|----------------|--------|
| **Stripe Products/Prices** | Create flat fee + metered products | 30 min |
| **Stripe Meter** | **NEW:** Create "voice_calls" meter (count) | 30 min |
| **Usage Reporting** | **NEW:** Add meter event reporting after each call | 2-3 hours |
| **Invoice Webhook** | Remove `invoice.created` revenue share logic | 30 min |
| **Website: Pricing Page** | Update UI | 2-4 hours |
| **Existing Customers** | Migrate subscriptions | 1-2 hours (scripted) |
| **Total Effort** | | **~2-3 days** |

---

## Switching Effort Summary Matrix

| From ↓ / To → | Model 1 (Tiered) | Model 2 (Fixed+Call) | Model 3 (Revenue) |
|----------------|-------------------|----------------------|--------------------|
| **Model 1 (Tiered)** | — | **1-2 days** (easiest) | **2-4 days** |
| **Model 2 (Fixed+Call)** | **2-3 days** | — | **2-4 days** |
| **Model 3 (Revenue)** | **2-4 days** | **2-3 days** | — |

**Key takeaway: Maximum switching effort is 2-4 days. Never a full redevelopment.**

---

## Why No Full Redevelopment Is Needed

### 1. Stripe Is Designed for Model Changes

Stripe's Subscriptions API explicitly supports:
- **Changing prices** on existing subscriptions (`POST /v1/subscriptions/{id}`)
- **Adding/removing subscription items** (switch from single to multi-item)
- **Prorations** when switching mid-cycle
- **Subscription schedules** for planned migrations
- **Bulk customer migration** via API scripts

Reference: [Stripe — Modify Subscriptions](https://docs.stripe.com/billing/subscriptions/change)

### 2. The Core Architecture Doesn't Change

```
                     UNCHANGED                      CHANGES
              ┌─────────────────────┐      ┌─────────────────────┐
              │                     │      │                     │
              │  ✅ Customer Auth    │      │  🔄 Stripe Config    │
              │  ✅ Database Schema  │      │  🔄 Usage Metric     │
              │  ✅ Webhook Handler  │      │  🔄 Pricing Page UI  │
              │  ✅ Voice Call System│      │  🔄 Reporting Logic  │
              │  ✅ POS Integration  │      │                     │
              │  ✅ SMS/Email        │      │                     │
              │  ✅ Customer Portal  │      │                     │
              │                     │      │                     │
              │     ~75% of code    │      │    ~25% of code     │
              └─────────────────────┘      └─────────────────────┘
```

### 3. The Usage Tracking Layer Is the Only Variable

All three models track something after each call. The only difference is **what** they track:

| Model | What We Track | Where We Report It |
|-------|--------------|-------------------|
| Model 1 | Call duration (minutes) | Stripe Meter ("sum" aggregation) |
| Model 2 | Call count (1 per call) | Stripe Meter ("count" aggregation) |
| Model 3 | Order revenue (€ amount) | Custom invoice line item via webhook |

The voice call system already tracks all three data points (duration, count, and order value). We just need to choose which one to report to Stripe.

---

## Recommended Modular Architecture

To make switching effortless, we should build the system with this modular structure:

```
┌───────────────────────────────────────────────────────────────────┐
│                        MODULAR ARCHITECTURE                       │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    CONFIG LAYER (env vars)                   │  │
│  │                                                              │  │
│  │  PRICING_MODEL = "tiered" | "per_call" | "revenue_based"    │  │
│  │  STRIPE_PRODUCT_IDS = { ... }                                │  │
│  │  STRIPE_PRICE_IDS = { ... }                                  │  │
│  │  STRIPE_METER_NAME = "voice_call_minutes" | "voice_calls"   │  │
│  │  FLAT_FEE = 204 | 49 | 199                                  │  │
│  │  USAGE_RATE = 0.50                                           │  │
│  │  REVENUE_SHARE_PCT = 5                                       │  │
│  │                                                              │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                 USAGE TRACKING SERVICE                       │  │
│  │                                                              │  │
│  │  function reportUsage(callData) {                            │  │
│  │    switch(PRICING_MODEL) {                                   │  │
│  │      case "tiered":                                          │  │
│  │        → report call duration to Stripe Meter                │  │
│  │      case "per_call":                                        │  │
│  │        → report call event to Stripe Meter                   │  │
│  │      case "revenue_based":                                   │  │
│  │        → store revenue in database (no Stripe meter)         │  │
│  │    }                                                         │  │
│  │  }                                                           │  │
│  │                                                              │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                 INVOICE HANDLER SERVICE                      │  │
│  │                                                              │  │
│  │  webhook: invoice.created                                    │  │
│  │    if (PRICING_MODEL === "revenue_based") {                  │  │
│  │      → calculate revenue share                               │  │
│  │      → add custom line item to invoice                       │  │
│  │    }                                                         │  │
│  │    // Models 1 & 2: Stripe handles automatically via meter   │  │
│  │                                                              │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              SHARED SERVICES (unchanged)                     │  │
│  │                                                              │  │
│  │  • Customer management                                       │  │
│  │  • Subscription lifecycle (create, cancel, pause)            │  │
│  │  • Webhook handling (payment success/failure)                │  │
│  │  • Website frontend                                          │  │
│  │  • Voice call system                                         │  │
│  │  • POS integration                                           │  │
│  │                                                              │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

With this architecture, switching pricing models becomes:
1. **Change environment variables** (PRICING_MODEL, STRIPE_PRICE_IDS)
2. **Create new products/prices in Stripe** (Dashboard or API)
3. **Update pricing page content** (plan names, prices, features)
4. **Run migration script** for existing customers
5. **Done.** No code rewrite needed.

---

## Risk Analysis

### Low Risk (Model 1 ↔ Model 2)
- Both use Stripe Meters
- Both have similar subscription structures (fixed + metered)
- Only the metric changes (minutes vs call count)
- **Switching effort: 1-3 days**

### Medium Risk (Model 1/2 → Model 3)
- Model 3 does NOT use Stripe Meters
- Requires custom invoice line item logic (new webhook handler)
- Revenue tracking must be reliable and accurate
- **Switching effort: 2-4 days**
- **Main risk:** Revenue tracking accuracy must be auditable

### Medium Risk (Model 3 → Model 1/2)
- Need to ADD Stripe Meter (new component)
- Need to ADD usage reporting after each call
- Need to REMOVE custom invoice logic
- **Switching effort: 2-4 days**
- **Main risk:** Ensuring meter events are reliably reported

---

## Which Model to Start With: Strategic Recommendation

### Start with Model 1 (Tiered Packages) — Recommended

**Reasoning:**
1. **Most flexible starting point** — already uses Stripe Meters (needed for Model 2 switch)
2. **Easiest to explain to customers** — clear "what you get" for each tier
3. **Predictable revenue** — base fees provide stability
4. **Stripe natively supports it** — uses "Flat Fee and Overages" pricing model directly, minimizing custom code
5. **Yearly discount is built-in** — Stripe supports coupons natively
6. **Switching to Model 2 is trivial** — just change the meter metric and simplify pricing
7. **Switching to Model 3 requires moderate effort** — add invoice webhook, remove meter

### Why NOT Start with Model 3

Model 3 requires the most custom code (invoice webhook for revenue share). If you start there and switch to Model 1 or 2, you'd need to add Stripe Meters (which you didn't need before). Starting with Model 1 means the Meter infrastructure is already in place.

---

## Database Schema: Universal Design (Works for All Models)

```sql
-- Works for ALL pricing models. Only subscription_plans content changes.
CREATE TABLE subscription_plans (
  plan_id TEXT PRIMARY KEY,
  model_type TEXT NOT NULL,               -- 'tiered', 'per_call', 'revenue_based'
  name TEXT NOT NULL,
  description TEXT,
  monthly_price DECIMAL(10,2) NOT NULL,
  yearly_price DECIMAL(10,2),
  included_units INTEGER DEFAULT 0,       -- Model 1: minutes; Model 2: 0; Model 3: 0
  unit_type TEXT,                          -- 'minutes', 'calls', null
  overage_rate DECIMAL(10,2) DEFAULT 0,   -- Model 1: 0.50; Model 2: 0.50; Model 3: 0
  revenue_share_pct DECIMAL(5,2) DEFAULT 0, -- Model 3: 5.00; Others: 0
  stripe_product_id TEXT,
  stripe_monthly_price_id TEXT,
  stripe_yearly_price_id TEXT,
  stripe_metered_price_id TEXT,           -- null for Model 3
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE customer_subscriptions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  customer_id UUID REFERENCES customers(id),
  plan_id TEXT REFERENCES subscription_plans(plan_id),
  stripe_subscription_id TEXT UNIQUE,
  stripe_customer_id TEXT,
  status TEXT DEFAULT 'active',
  billing_period TEXT DEFAULT 'monthly',   -- 'monthly' or 'yearly'
  current_period_start TIMESTAMPTZ,
  current_period_end TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Usage tracking — stores ALL metrics regardless of model
CREATE TABLE usage_records (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  customer_id UUID REFERENCES customers(id),
  call_id TEXT,
  call_duration_minutes DECIMAL(10,2),    -- Always tracked (for Model 1)
  call_count INTEGER DEFAULT 1,            -- Always tracked (for Model 2)
  order_revenue DECIMAL(10,2) DEFAULT 0,   -- Always tracked (for Model 3)
  reported_to_stripe BOOLEAN DEFAULT false,
  billing_period_start TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Key insight:** By always tracking all three metrics (minutes, call count, revenue), switching models only requires changing which metric gets reported to Stripe. No database migration needed.

---

## Final Verdict

| Question | Answer |
|----------|--------|
| **Do we need full redevelopment to switch?** | **NO. Absolutely not.** |
| **Maximum switching effort?** | **2-4 days** (worst case: Model 1/2 ↔ Model 3) |
| **Minimum switching effort?** | **1-2 days** (Model 1 ↔ Model 2) |
| **What % of code changes?** | **~20-25%** (usage reporting + pricing page + Stripe config) |
| **What % stays the same?** | **~75-80%** (auth, database, webhooks, voice system, POS) |
| **Best model to start with?** | **Model 1 (Tiered Packages)** — most infrastructure reuse |
| **Does Stripe support all models?** | **Yes.** Models 1 & 2 natively. Model 3 via custom invoice items. |

### Bottom Line

Build the system once with a modular design. Track all usage metrics from day one. When the business decision is made, we plug in the chosen pricing model like a configuration change — not a rewrite.

---

**Document Version:** 1.0  
**Date:** February 19, 2026  
**References:**
- [Stripe — Usage-Based Billing](https://docs.stripe.com/billing/subscriptions/usage-based)
- [Stripe — Flat Fee and Overages](https://docs.stripe.com/billing/subscriptions/usage-based-v1/use-cases/flat-fee-and-overages)
- [Stripe — Flat Rate with Usage-Based Pricing](https://docs.stripe.com/billing/subscriptions/usage-based-legacy/pricing-models)
- [Stripe — Modify Subscriptions](https://docs.stripe.com/billing/subscriptions/change)
- [Stripe — Meters](https://docs.stripe.com/billing/subscriptions/usage-based/recording-usage)
