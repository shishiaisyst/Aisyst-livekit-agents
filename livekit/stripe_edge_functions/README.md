# Stripe Edge Functions

This folder contains the source code for Supabase Edge Functions that handle Stripe billing integration.

> **These files are NOT deployed from here.** They are deployed by pasting the code into the **Supabase Dashboard → Edge Functions → code editor** and clicking Deploy.

## Functions

| Function | File | Purpose |
|----------|------|---------|
| `create-checkout-session` | `create_checkout_session.ts` | Creates a Stripe Checkout Session when a customer selects a plan |
| `stripe-webhook-handler` | `stripe_webhook_handler.ts` _(coming next)_ | Handles Stripe webhook events (payment success, renewal, cancellation) |
| `report-usage` | `report_usage.ts` _(coming next)_ | Reports voice call minutes to Stripe Meter after each call |

## How to Deploy

1. Open **Supabase Dashboard → Edge Functions**
2. Click **"Create a new function"**
3. Name it exactly as shown in the table above (e.g., `create-checkout-session`)
4. Copy the entire contents of the corresponding `.ts` file
5. Paste into the code editor
6. Click **Deploy**

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
