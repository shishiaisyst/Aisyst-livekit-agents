# Stripe Edge Functions

This folder contains the source code for Supabase Edge Functions that handle Stripe billing integration.

> **These files are NOT deployed from here.** They are deployed by pasting the code into the **Supabase Dashboard → Edge Functions → code editor** and clicking Deploy.

## Functions

| Function | File | Purpose |
|----------|------|---------|
| `create-checkout-session` | `create_checkout_session.ts` | Creates a Stripe Checkout Session when a customer selects a plan |
| `stripe-webhook-handler` | `stripe_webhook_handler.ts` | Handles Stripe webhook events (payment success, renewal, cancellation) |
| `report-usage` | `report_usage.ts` | Reports voice call minutes to Stripe Meter after each call |

## How to Deploy

1. Open **Supabase Dashboard → Edge Functions**
2. Click **"Create a new function"**
3. Name it exactly as shown in the table above (e.g., `create-checkout-session`)
4. Copy the entire contents of the corresponding `.ts` file
5. Paste into the code editor
6. Click **Deploy**

### ⚠️ Special: `stripe-webhook-handler`

This function receives requests from Stripe (not a browser), so there is no Supabase JWT.
After deploying, **disable JWT Verification** for this function in the Supabase Dashboard.
Stripe's webhook signature (`stripe-signature` header) is used for authentication instead.

### Stripe Webhook Registration

After deploying `stripe-webhook-handler`:
1. Go to **Stripe Dashboard → Developers → Webhooks**
2. Click **"Add endpoint"**
3. URL: `https://<your-project-ref>.supabase.co/functions/v1/stripe-webhook-handler`
4. Select events: `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`
5. Save the **Webhook Signing Secret** (`whsec_...`) and add it to Supabase secrets as `STRIPE_WEBHOOK_SECRET`

## Environment Variables Required

Set these in **Supabase Dashboard → Edge Functions → Manage Secrets**:

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous/public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (⚠️ keep secret) |
| `STRIPE_SECRET_KEY` | Stripe API secret key (`sk_test_...` or `sk_live_...`) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret (`whsec_...`) |
| `STRIPE_SETUP_FEE_PRICE_ID` | Price ID for the one-time €249 setup fee |
| `WEBSITE_URL` | Frontend URL for success/cancel redirects |

## IDE Lint Errors

Your IDE will show errors for `Deno.*` and `https://esm.sh/` imports — **these are expected.**
The code runs on Supabase's Deno runtime, not Node.js. The imports resolve correctly when deployed.

## Frontend Usage

```typescript
const response = await fetch(
  `${SUPABASE_URL}/functions/v1/create-checkout-session`,
  {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${session.access_token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      plan_id: '<uuid from billing_plans table>',
      billing_period: 'monthly',  // or 'yearly'
    }),
  }
)

const { checkout_url } = await response.json()
window.location.href = checkout_url  // redirect to Stripe
```

## Voice Agent Usage (report-usage)

Called by the Python LiveKit agent after each voice call ends. **Not called by the frontend.**

```python
import requests

response = requests.post(
    f"{SUPABASE_URL}/functions/v1/report-usage",
    headers={
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "org_id": "uuid-of-the-organisation",
        "call_duration_minutes": 5.3,
        "call_id": "unique-livekit-session-id"
    }
)

data = response.json()
# { "success": true, "billed_minutes": 6, "total_minutes_used": 1856, ... }
```

### Pre-deploy: Create `usage_records` table

Run this in **Supabase SQL Editor** before deploying `report-usage`:

```sql
CREATE TABLE IF NOT EXISTS usage_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organisations(id),
  subscription_id UUID REFERENCES subscriptions(id),
  billing_cycle_id UUID REFERENCES billing_cycles(id),
  call_id TEXT NOT NULL UNIQUE,
  call_duration_minutes NUMERIC(10,2) NOT NULL,
  billed_minutes INT4 NOT NULL,
  stripe_meter_event_id TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
```
