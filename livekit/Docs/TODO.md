# AiSyst Billing Implementation — TODO Tracker
## Pricing Model: Model 1 — Tiered Packages (Flat Fee + Included Minutes + Overage)

> **Update this file as tasks are completed. Mark tasks with ✅ when done, 🔄 when in progress, ❌ if blocked.**

---

## PHASE 0: Pre-Implementation Checklist
> Must be fully completed before writing any edge function code.

### 0A. Stripe Dashboard Setup (Test Mode)

- [x] Switch Stripe Dashboard to **Test Mode** (toggle top-right)
- [x] **Create Billing Meter**
  - Name: `Voice Call Minutes`
  - Event name: `voice_call_minutes` ← exact string used in code
  - Aggregation: `Sum`
  - Save the **Meter ID** (`mtr_xxxxx`) → paste below:
    - Meter ID: `mtr_test_61UC5jRM8iFr375ri41Cw2MHXOSE9CXI`
    This is the meter id we are going to use for the testing.

- [x] **Create Starter Product** (`AiSyst Starter`)
Name of Product Created in Stripe: Aisyst Starter Pack
Product Id: prod_U0k3LuWytR5FgO
  - Price 1 — Flat recurring: €204/month
    - Save Price ID → `stripe_price_id`: `price_1T2iZ8Cw2MHXOSE9gGev1Lnt`
  - Price 2 — Metered graduated tiers:
    - Tier 1: Units 0–500 → €0.00/unit
    - Tier 2: Units 501+ → €0.50/unit
    - Attach to meter: `voice_call_minutes`
    - Save Price ID → `stripe_metered_price_id`: `price_1T2inYCw2MHXOSE98XehIUCb`
  - Price 3 — Flat yearly: €2,203.20/year (€204 × 12 × 0.9)
    - Save Price ID → `stripe_yearly_price_id`: `price_1T2inYCw2MHXOSE9moJp9Ac8`

- [x] **Create Growth Product** (`AiSyst Growth`)
Name of Product Created in Stripe: Aisyst Growth Pack
Product Id: prod_U0kPkpU2VA620s
  - Price 1 — Flat recurring: €366/month
    - Save Price ID → `stripe_price_id`: `price_1T2iv4Cw2MHXOSE9WyA9WrIb`
  - Price 2 — Metered graduated tiers:
    - Tier 1: Units 0–1000 → €0.00/unit
    - Tier 2: Units 1001+ → €0.50/unit
    - Attach to meter: `voice_call_minutes`
    - Save Price ID → `stripe_metered_price_id`: `price_1T2iyzCw2MHXOSE98RRDBQsp`
  - Price 3 — Flat yearly: €3,952.80/year (€366 × 12 × 0.9)
    - Save Price ID → `stripe_yearly_price_id`: `price_1T2iyzCw2MHXOSE9OyMLkOHT`

- [x] **Create Enterprise Product** (`AiSyst Enterprise`)
Name of Product Created in Stripe: Aisyst Enterprise Pack
Product Id: prod_U0kYRJ3ARpSBue
  - Price 1 — Flat recurring: €624/month
    - Save Price ID → `stripe_price_id`: `price_1T2j3MCw2MHXOSE9jdzhwNVj`
  - Price 2 — Metered graduated tiers:
    - Tier 1: Units 0–2000 → €0.00/unit
    - Tier 2: Units 2001+ → €0.50/unit
    - Attach to meter: `voice_call_minutes`
    - Save Price ID → `stripe_metered_price_id`: `price_1T2j7MCw2MHXOSE9yr7HJVAm`
  - Price 3 — Flat yearly: €6,739.20/year (€624 × 12 × 0.9)
    - Save Price ID → `stripe_yearly_price_id`: `price_1T2j7MCw2MHXOSE9evhfSPS7`

- [ ] **Register Stripe Webhook Endpoint** ⏭️ Do after Phase 2 edge function is deployed
  - URL: `https://<your-project-ref>.supabase.co/functions/v1/stripe-webhook-handler`
  - Events to subscribe:
    - `checkout.session.completed`
    - `invoice.paid`
    - `invoice.payment_failed`
    - `customer.subscription.updated`
    - `customer.subscription.deleted`
  - Save Webhook Signing Secret → `STRIPE_WEBHOOK_SECRET`: `___________________`

---

### 0B. Supabase Schema Migrations

- [x] **Run ALTER TABLE migrations** in Supabase SQL Editor:

```sql
-- billing_plans: add missing columns for Model 1
ALTER TABLE billing_plans
  ADD COLUMN IF NOT EXISTS model_type TEXT DEFAULT 'tiered',
  ADD COLUMN IF NOT EXISTS stripe_metered_price_id TEXT,
  ADD COLUMN IF NOT EXISTS overage_rate_aud_cents INT4 DEFAULT 50,
  ADD COLUMN IF NOT EXISTS yearly_price_aud_cents INT4,
  ADD COLUMN IF NOT EXISTS stripe_yearly_price_id TEXT;

-- subscriptions: add billing_period (monthly vs yearly)
ALTER TABLE subscriptions
  ADD COLUMN IF NOT EXISTS billing_period TEXT DEFAULT 'monthly';

-- billing_cycles: existing columns are sufficient for Model 1 (Tiered)
-- ⏭️ DEFERRED: calls_used, calls_cost_aud_cents, revenue_aud_cents, revenue_share_aud_cents
-- Only needed if switching to Model 2 or Model 3 later.
```

- [x] **Seed billing_plans table** with real Stripe Price IDs:

```sql
INSERT INTO billing_plans (
  name, model_type, included_minutes,
  price_aud_cents, yearly_price_aud_cents, overage_rate_aud_cents,
  stripe_price_id, stripe_yearly_price_id, stripe_metered_price_id,
  sort_order, active
) VALUES
  ('Starter',    'tiered', 500,  20400, 220320, 50,
   'price_STARTER_MONTHLY',    'price_STARTER_YEARLY',    'price_STARTER_METERED',    1, true),
  ('Growth',     'tiered', 1000, 36600, 395280, 50,
   'price_GROWTH_MONTHLY',     'price_GROWTH_YEARLY',     'price_GROWTH_METERED',     2, true),
  ('Enterprise', 'tiered', 2000, 62400, 673920, 50,
   'price_ENTERPRISE_MONTHLY', 'price_ENTERPRISE_YEARLY', 'price_ENTERPRISE_METERED', 3, true);
-- ⚠️ Replace all price_XXXXX placeholders with real IDs from Step 0A
```

- [x] Verify `organisations` table has a `stripe_customer_id TEXT` column — ✅ added
- [x] Verify `organisations` table has an `owner_id UUID` column — ✅ confirmed with FK to `auth.users.id`

---

### 0C. Environment Variables (Supabase Edge Function Secrets)

Set these in **Supabase Dashboard → Edge Functions → Manage Secrets**:

- [x] `STRIPE_SECRET_KEY` → ✅ Configured in Supabase secrets
- [x] `STRIPE_WEBHOOK_SECRET` → ✅ Configured in Supabase secrets
- [ ] `WEBSITE_URL` → ❌ Still needs to be added (your frontend URL)
- [ ] `SUPABASE_URL` → Add if not already present
- [ ] `SUPABASE_ANON_KEY` → Add if not already present
- [ ] `SUPABASE_SERVICE_ROLE_KEY` → Add if not already present ⚠️ Keep secret
- [ ] `STRIPE_SETUP_FEE_PRICE_ID` → Price ID for the one-time €249 setup fee product

---

### 0D. Supabase Dashboard Setup

- [x] Go to **Supabase Dashboard → Edge Functions → Manage Secrets** and add all env vars from Step 0C
- [x] Verify Edge Functions section is accessible in your Supabase project
- [x] Confirm you can see the built-in code editor when clicking **"Create a new function"**

> ℹ️ **No CLI needed.** All edge functions will be created and deployed directly via the Supabase Dashboard code editor. Paste the generated code and click Deploy.

---

## PHASE 1: Edge Function — `create-checkout-session`
> Triggered by frontend when customer clicks "Buy Plan"

- [ ] In Supabase Dashboard → Edge Functions → Create new function named `create-checkout-session`
- [x] COMPLETED: Verify Supabase JWT auth
- [x] COMPLETED: Parse `plan_id` and `billing_period` from request body
- [x] COMPLETED: Fetch plan from `billing_plans` table
- [x] COMPLETED: Fetch org and `stripe_customer_id` from `organisations` table
- [x] COMPLETED: Create Stripe Customer if not exists, save back to `organisations`
- [x] COMPLETED: Build `line_items` array (flat price + metered price + one-time setup fee)
- [x] COMPLETED: Create Stripe Checkout Session with metadata (`org_id`, `plan_id`, `billing_period`)
- [x] COMPLETED: Return `checkout_url` to frontend
- [x] COMPLETED: Code written → `stripe_edge_functions/create_checkout_session.ts`
- [x] COMPLETED Deploy via Supabase Dashboard → paste code → click Deploy
- [ ] Test: Call from frontend with test user, verify redirect to Stripe Checkout
- [ ] Test: Complete payment with test card `4242 4242 4242 4242`

---

## PHASE 2: Edge Function — `stripe-webhook-handler`
> Triggered by Stripe after payment events

- [ ] In Supabase Dashboard → Edge Functions → Create new function named `stripe-webhook-handler`
- [x] COMPLETED: Verify Stripe webhook signature (`stripe-signature` header) — uses `constructEventAsync` with `SubtleCryptoProvider` for Deno
- [x] COMPLETED: Handle `checkout.session.completed`:
  - [x] COMPLETED: INSERT into `subscriptions` table (with idempotency check)
  - [x] COMPLETED: INSERT into `billing_cycles` table (first cycle, status: `active`)
- [x] COMPLETED: Handle `invoice.paid` (monthly renewal):
  - [x] COMPLETED: UPDATE `subscriptions` period dates
  - [x] COMPLETED: Close previous `billing_cycles` row (status: `closed`)
  - [x] COMPLETED: INSERT new `billing_cycles` row for new period (with idempotency check)
  - [x] COMPLETED: Update first billing cycle with invoice ID on initial payment
- [x] COMPLETED: Handle `invoice.payment_failed`:
  - [x] COMPLETED: UPDATE `subscriptions` status to `past_due`
- [x] COMPLETED: Handle `customer.subscription.updated`:
  - [x] COMPLETED: Sync status, period dates, and `canceled_at_period_end` to `subscriptions` table
- [x] COMPLETED: Handle `customer.subscription.deleted`:
  - [x] COMPLETED: UPDATE `subscriptions` status to `canceled`
  - [x] COMPLETED: Set `canceled_at` timestamp
  - [x] COMPLETED: Close any active billing cycle
- [x] COMPLETED: Code written → `stripe_edge_functions/stripe_webhook_handler.ts`
- [ ] Deploy via Supabase Dashboard → paste code → click Deploy ⚠️ **Disable JWT Verification** for this function
- [ ] Register webhook URL in Stripe Dashboard (Step 0A):
  - URL format: `https://<your-project-ref>.supabase.co/functions/v1/stripe-webhook-handler`
- [ ] Test: Trigger via real Stripe test payment, check logs in Supabase Dashboard → Edge Functions → Logs
- [ ] Test: Verify `subscriptions` row created after test payment
- [ ] Test: Verify `billing_cycles` row created after test payment

---

## PHASE 3: Edge Function — `report-usage`
> Called after every voice call ends — reports minutes to Stripe Meter

- [ ] In Supabase Dashboard → Edge Functions → Create new function named `report-usage`
- [x] COMPLETED: Accept `{ org_id, call_duration_minutes, call_id }` in request body — with full validation
- [x] COMPLETED: Authenticate caller via service_role JWT (only backend agents can call this)
- [x] COMPLETED: Idempotency check via `call_id` in `usage_records` table (prevents double billing on retries)
- [x] COMPLETED: Fetch active subscription for org from `subscriptions` table
- [x] COMPLETED: Fetch `stripe_customer_id` for the org from `organisations` table
- [x] COMPLETED: Send meter event to Stripe (`voice_call_minutes`) with idempotency key
- [x] COMPLETED: Round up call duration to nearest whole minute (standard telecom billing)
- [x] COMPLETED: UPDATE `billing_cycles` — increment `minutes_used`, recalculate `overage_minutes` and `overage_cost_aud_cents`
- [x] COMPLETED: INSERT into `usage_records` table (audit trail with raw + billed minutes)
- [x] COMPLETED: Code written → `stripe_edge_functions/report_usage.ts`
- [ ] **PRE-DEPLOY**: Create `usage_records` table (SQL provided in the file header comments)
- [ ] Deploy via Supabase Dashboard → paste code → click Deploy
- [ ] Integrate: Call this function from LiveKit/ElevenLabs agent after each call ends
- [ ] Test: Send a test meter event, verify it appears in Stripe Dashboard → Meters
- [ ] Test: Verify `billing_cycles.minutes_used` increments correctly

---

## PHASE 4: Frontend Integration

- [ ] Build pricing page with 3 plan cards (Starter / Growth / Enterprise)
- [ ] Add monthly/yearly toggle (shows 10% discount on yearly)
- [ ] Implement `handleBuyPlan(planId, billingPeriod)` function:
  - Calls `create-checkout-session` edge function with Supabase JWT
  - Redirects to `checkout_url`
- [ ] Build `/dashboard?payment=success` success page
- [ ] Build `/pricing?payment=cancelled` cancel/back page
- [ ] Show current plan and usage in customer dashboard (query `subscriptions` + `billing_cycles`)

---

## PHASE 5: End-to-End Testing

- [ ] Test full flow: Signup → Select Plan → Pay → Dashboard shows active subscription
- [ ] Test overage: Report >500 minutes for Starter plan, verify overage appears on next invoice
- [ ] Test yearly billing: Buy yearly plan, verify 10% discount applied
- [ ] Test renewal: Simulate invoice renewal, verify new `billing_cycles` row created
- [ ] Test cancellation: Cancel subscription, verify status updated in `subscriptions`
- [ ] Test payment failure: Use card `4000 0000 0000 0002`, verify `past_due` status
- [ ] Test webhook reliability: Verify no duplicate rows on repeated webhook delivery

---

## PHASE 6: Go Live Checklist (Do Last)

- [ ] Switch Stripe Dashboard to **Live Mode**
- [ ] Recreate all Products, Prices, and Meter in live mode
- [ ] Register webhook endpoint in live mode
- [ ] Swap all `sk_test_...` env vars to `sk_live_...` in Supabase secrets
- [ ] Swap `STRIPE_WEBHOOK_SECRET` to live mode signing secret
- [ ] Run final end-to-end test with a real card (small amount)
- [ ] Monitor Stripe Dashboard → Events for first real payment

---

## Key Reference IDs (Fill in as you go)

| Item | Test Mode ID |
|------|-------------|
| Stripe Meter ID | `mtr_test_61UC5jRM8iFr375ri41Cw2MHXOSE9CXI` |
| Starter — Product ID | `prod_U0k3LuWytR5FgO` |
| Starter — Monthly Price ID | `price_1T2iZ8Cw2MHXOSE9gGev1Lnt` |
| Starter — Yearly Price ID | `price_1T2inYCw2MHXOSE9moJp9Ac8` |
| Starter — Metered Price ID | `price_1T2inYCw2MHXOSE98XehIUCb` |
| Growth — Product ID | `prod_U0kPkpU2VA620s` |
| Growth — Monthly Price ID | `price_1T2iv4Cw2MHXOSE9WyA9WrIb` |
| Growth — Yearly Price ID | `price_1T2iyzCw2MHXOSE9OyMLkOHT` |
| Growth — Metered Price ID | `price_1T2iyzCw2MHXOSE98RRDBQsp` |
| Enterprise — Product ID | `prod_U0kYRJ3ARpSBue` |
| Enterprise — Monthly Price ID | `price_1T2j3MCw2MHXOSE9jdzhwNVj` |
| Enterprise — Yearly Price ID | `price_1T2j7MCw2MHXOSE9evhfSPS7` |
| Enterprise — Metered Price ID | `price_1T2j7MCw2MHXOSE9yr7HJVAm` |
| Setup Fee Price ID | `price_` ← add this |
| Webhook Signing Secret | `whsec_` ← add after Phase 2 deploy |
| Supabase Project Ref | `` ← add this |

---

## Useful Stripe Docs

| Topic | Link |
|-------|------|
| Flat Fee + Overages (our exact model) | https://docs.stripe.com/billing/subscriptions/usage-based-v1/use-cases/flat-fee-and-overages |
| Creating & Using Meters | https://docs.stripe.com/billing/subscriptions/usage-based/recording-usage |
| Graduated Tier Pricing | https://docs.stripe.com/billing/subscriptions/usage-based-legacy/pricing-models |
| Stripe Checkout | https://docs.stripe.com/payments/checkout |
| Subscriptions API | https://docs.stripe.com/api/subscriptions |
| Webhook Events Reference | https://docs.stripe.com/webhooks |
| Webhook Signature Verification | https://docs.stripe.com/webhooks/signatures |
| Prices API | https://docs.stripe.com/api/prices |
| Meter Events API | https://docs.stripe.com/api/billing/meter-event |
| Coupons (yearly discount) | https://docs.stripe.com/billing/subscriptions/coupons |
| Supabase Edge Functions | https://supabase.com/docs/guides/functions |
| Stripe CLI (local webhook testing) | https://docs.stripe.com/stripe-cli |

---

## Progress Log

| Date | Update |
|------|--------|
| Feb 20, 2026 | TODO.md created. Pre-implementation checklist defined. Model 1 (Tiered Packages) chosen. |
| Feb 20, 2026 | Phase 0 largely complete. Stripe test mode configured: Billing Meter, 3 pack products + Setup Fee product created with all prices. `billing_plans` table updated and seeded with real Price IDs. `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` set in Supabase secrets. `owner_id` column confirmed on `organisations` table. |
| Feb 23, 2026 | Phase 1 implementation complete. `create-checkout-session` edge function written in `stripe_edge_functions/create_checkout_session.ts`. Function handles JWT auth, plan fetching, Stripe Customer creation, line items building (flat + metered + setup fee), and Checkout Session creation. Frontend requirements documented: need plan UUIDs, edge function endpoint, and success/cancel routes. Remaining: add `WEBSITE_URL` and `STRIPE_SETUP_FEE_PRICE_ID` to Supabase secrets, deploy function, test end-to-end. Ready for Phase 2 (webhook handler) next. |
| Feb 24, 2026 | Phase 2 complete. `stripe-webhook-handler` edge function written in `stripe_edge_functions/stripe_webhook_handler.ts`. Handles 5 Stripe events: `checkout.session.completed` (creates subscription + first billing cycle), `invoice.paid` (renewal cycle management), `invoice.payment_failed` (marks past_due), `customer.subscription.updated` (syncs status), `customer.subscription.deleted` (cancels + closes cycle). Includes idempotency checks, Stripe signature verification via SubtleCryptoProvider. |
| Feb 24, 2026 | Phase 3 complete. `report-usage` edge function written in `stripe_edge_functions/report_usage.ts`. Called by Python voice agent after each call. Authenticates via service_role JWT, sends meter events to Stripe, updates billing_cycles with usage stats, inserts audit trail in usage_records. Includes idempotency via call_id, Math.ceil billing, and Stripe idempotency keys. **All 3 edge functions now coded. Next: create `usage_records` table, deploy all functions, register webhook URL in Stripe.** |
