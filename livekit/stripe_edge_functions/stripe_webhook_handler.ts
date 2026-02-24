// =============================================================================
// Edge Function: stripe-webhook-handler
// =============================================================================
// Triggered by: Stripe (sends webhook events after payment actions)
//
// What it does:
//   Listens for Stripe webhook events and updates the Supabase database
//   accordingly. This is the ONLY place where subscriptions and billing
//   cycles are created/updated — NOT the frontend, NOT the checkout function.
//
// Events Handled:
//   1. checkout.session.completed → New subscription + first billing cycle
//   2. invoice.paid              → Renewal: close old cycle, create new cycle
//   3. invoice.payment_failed    → Mark subscription as past_due
//   4. customer.subscription.updated → Sync status changes
//   5. customer.subscription.deleted → Cancel subscription + close cycle
//
// Security:
//   - Verifies Stripe webhook signature (stripe-signature header)
//   - No Supabase JWT required (Stripe sends this, not a browser)
//   - Uses service role key for database operations
//
// IMPORTANT — Deployment Note:
//   When deploying this function in Supabase Dashboard, you MUST disable
//   JWT verification. Stripe sends webhooks directly — there is no
//   Supabase JWT in the request. The stripe-signature header is our
//   authentication instead.
//
//   In Supabase Dashboard → Edge Functions → stripe-webhook-handler:
//   Look for the "Enforce JWT Verification" toggle and TURN IT OFF.
//
// Environment Variables Required:
//   SUPABASE_URL
//   SUPABASE_SERVICE_ROLE_KEY
//   STRIPE_SECRET_KEY
//   STRIPE_WEBHOOK_SECRET
// =============================================================================

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import Stripe from "https://esm.sh/stripe@14?target=deno";

// CORS headers — included for consistency, though webhooks don't need CORS
const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, stripe-signature",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// Helper: build a consistent JSON response
function jsonResponse(body: Record<string, unknown>, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

// Helper: convert Unix timestamp (seconds) from Stripe to ISO 8601 string
function unixToISO(unixSeconds: number): string {
  return new Date(unixSeconds * 1000).toISOString();
}

// =============================================================================
// EVENT HANDLERS
// =============================================================================

// ---------------------------------------------------------------------------
// 1. checkout.session.completed
// ---------------------------------------------------------------------------
// Fired when a customer completes the Stripe Checkout flow.
// This is where we create the subscription and first billing cycle in our DB.
//
// The session object contains:
//   - session.subscription → Stripe subscription ID (sub_xxx)
//   - session.customer     → Stripe customer ID (cus_xxx)
//   - session.metadata     → { org_id, plan_id, billing_period } (set by create-checkout-session)
// ---------------------------------------------------------------------------
async function handleCheckoutCompleted(
  session: Stripe.Checkout.Session,
  stripe: Stripe,
  supabaseAdmin: ReturnType<typeof createClient>
) {
  const metadata = session.metadata;
  if (!metadata?.org_id || !metadata?.plan_id) {
    console.error("checkout.session.completed: Missing metadata (org_id or plan_id)");
    return;
  }

  const orgId = metadata.org_id;
  const planId = metadata.plan_id;
  const billingPeriod = metadata.billing_period || "monthly";
  const stripeSubscriptionId = session.subscription as string;
  const stripeCustomerId = session.customer as string;

  console.log(
    `checkout.session.completed: org=${orgId}, plan=${planId}, ` +
    `period=${billingPeriod}, sub=${stripeSubscriptionId}`
  );

  // ── Idempotency check ──────────────────────────────────────────────────
  // Stripe may send the same event more than once. If we already created
  // a subscription for this Stripe subscription ID, skip it.
  const { data: existingSub } = await supabaseAdmin
    .from("subscriptions")
    .select("id")
    .eq("stripe_subscription_id", stripeSubscriptionId)
    .maybeSingle();

  if (existingSub) {
    console.log(
      `Subscription already exists for ${stripeSubscriptionId} — skipping (idempotent)`
    );
    return;
  }

  // ── Retrieve full subscription from Stripe to get period dates ─────────
  const subscription = await stripe.subscriptions.retrieve(stripeSubscriptionId);

  const periodStart = unixToISO(subscription.current_period_start);
  const periodEnd = unixToISO(subscription.current_period_end);

  // ── INSERT into subscriptions table ────────────────────────────────────
  const { data: newSub, error: subError } = await supabaseAdmin
    .from("subscriptions")
    .insert({
      org_id: orgId,
      plan_id: planId,
      stripe_subscription_id: stripeSubscriptionId,
      stripe_customer_id: stripeCustomerId,
      status: subscription.status, // typically 'active'
      billing_period: billingPeriod,
      current_period_start: periodStart,
      current_period_end: periodEnd,
    })
    .select("id")
    .single();

  if (subError) {
    console.error("Failed to insert subscription:", subError.message);
    throw subError;
  }

  console.log(`Subscription created: ${newSub.id} (stripe: ${stripeSubscriptionId})`);

  // ── Fetch plan to get included_minutes ─────────────────────────────────
  const { data: plan } = await supabaseAdmin
    .from("billing_plans")
    .select("included_minutes")
    .eq("id", planId)
    .single();

  const includedMinutes = plan?.included_minutes || 0;

  // ── INSERT first billing cycle ─────────────────────────────────────────
  const { error: cycleError } = await supabaseAdmin
    .from("billing_cycles")
    .insert({
      subscription_id: newSub.id,
      org_id: orgId,
      period_start: periodStart,
      period_end: periodEnd,
      minutes_included: includedMinutes,
      minutes_used: 0,
      overage_minutes: 0,
      overage_cost_aud_cents: 0,
      status: "active",
    });

  if (cycleError) {
    console.error("Failed to insert billing cycle:", cycleError.message);
    throw cycleError;
  }

  console.log(
    `First billing cycle created for subscription ${newSub.id} ` +
    `(${periodStart} → ${periodEnd}, ${includedMinutes} mins included)`
  );
}

// ---------------------------------------------------------------------------
// 2. invoice.paid
// ---------------------------------------------------------------------------
// Fired every time an invoice is successfully paid.
//
// For the FIRST invoice (when subscription is created):
//   billing_reason = 'subscription_create'
//   → We SKIP this because it's already handled by checkout.session.completed.
//
// For RENEWAL invoices (monthly/yearly recurring):
//   billing_reason = 'subscription_cycle'
//   → Close the previous billing cycle and create a new one.
//   → Update subscription period dates.
// ---------------------------------------------------------------------------
async function handleInvoicePaid(
  invoice: Stripe.Invoice,
  stripe: Stripe,
  supabaseAdmin: ReturnType<typeof createClient>
) {
  const billingReason = invoice.billing_reason;
  const stripeSubscriptionId = invoice.subscription as string;

  console.log(
    `invoice.paid: subscription=${stripeSubscriptionId}, reason=${billingReason}, invoice=${invoice.id}`
  );

  // Skip the first invoice — already handled by checkout.session.completed
  if (billingReason === "subscription_create") {
    console.log("First invoice (subscription_create) — skipping, handled by checkout.session.completed");

    // However, let's update the first billing cycle with the invoice ID for record keeping
    const { data: sub } = await supabaseAdmin
      .from("subscriptions")
      .select("id")
      .eq("stripe_subscription_id", stripeSubscriptionId)
      .maybeSingle();

    if (sub) {
      await supabaseAdmin
        .from("billing_cycles")
        .update({ stripe_invoice_id: invoice.id })
        .eq("subscription_id", sub.id)
        .eq("status", "active");

      console.log(`Updated first billing cycle with invoice ID: ${invoice.id}`);
    }
    return;
  }

  // ── Handle renewal (subscription_cycle) ────────────────────────────────
  if (billingReason !== "subscription_cycle") {
    console.log(`Unhandled billing_reason: ${billingReason} — skipping`);
    return;
  }

  // Look up our internal subscription
  const { data: sub, error: subError } = await supabaseAdmin
    .from("subscriptions")
    .select("id, org_id, plan_id")
    .eq("stripe_subscription_id", stripeSubscriptionId)
    .single();

  if (subError || !sub) {
    console.error(
      `Subscription not found for stripe_subscription_id: ${stripeSubscriptionId}`
    );
    return;
  }

  // Retrieve updated subscription from Stripe for new period dates
  const subscription = await stripe.subscriptions.retrieve(stripeSubscriptionId);
  const newPeriodStart = unixToISO(subscription.current_period_start);
  const newPeriodEnd = unixToISO(subscription.current_period_end);

  // ── Close previous billing cycle ──────────────────────────────────────
  const { error: closeError } = await supabaseAdmin
    .from("billing_cycles")
    .update({ status: "closed" })
    .eq("subscription_id", sub.id)
    .eq("status", "active");

  if (closeError) {
    console.error("Failed to close previous billing cycle:", closeError.message);
  } else {
    console.log(`Previous billing cycle closed for subscription ${sub.id}`);
  }

  // ── Idempotency: check if new cycle already exists ────────────────────
  const { data: existingCycle } = await supabaseAdmin
    .from("billing_cycles")
    .select("id")
    .eq("subscription_id", sub.id)
    .eq("period_start", newPeriodStart)
    .limit(1);

  if (existingCycle && existingCycle.length > 0) {
    console.log(
      `Billing cycle already exists for period ${newPeriodStart} — skipping (idempotent)`
    );
  } else {
    // Fetch plan to get included_minutes
    const { data: plan } = await supabaseAdmin
      .from("billing_plans")
      .select("included_minutes")
      .eq("id", sub.plan_id)
      .single();

    // ── INSERT new billing cycle ──────────────────────────────────────────
    const { error: cycleError } = await supabaseAdmin
      .from("billing_cycles")
      .insert({
        subscription_id: sub.id,
        org_id: sub.org_id,
        period_start: newPeriodStart,
        period_end: newPeriodEnd,
        minutes_included: plan?.included_minutes || 0,
        minutes_used: 0,
        overage_minutes: 0,
        overage_cost_aud_cents: 0,
        stripe_invoice_id: invoice.id,
        status: "active",
      });

    if (cycleError) {
      console.error("Failed to insert new billing cycle:", cycleError.message);
      throw cycleError;
    }

    console.log(
      `New billing cycle created: ${newPeriodStart} → ${newPeriodEnd}`
    );
  }

  // ── Update subscription period dates ───────────────────────────────────
  const { error: updateError } = await supabaseAdmin
    .from("subscriptions")
    .update({
      current_period_start: newPeriodStart,
      current_period_end: newPeriodEnd,
      status: subscription.status,
      updated_at: new Date().toISOString(),
    })
    .eq("id", sub.id);

  if (updateError) {
    console.error("Failed to update subscription period:", updateError.message);
  } else {
    console.log(`Subscription ${sub.id} period updated to ${newPeriodStart} → ${newPeriodEnd}`);
  }
}

// ---------------------------------------------------------------------------
// 3. invoice.payment_failed
// ---------------------------------------------------------------------------
// Fired when a payment attempt on an invoice fails.
// We mark the subscription as 'past_due' so the frontend can show a warning.
// ---------------------------------------------------------------------------
async function handleInvoicePaymentFailed(
  invoice: Stripe.Invoice,
  supabaseAdmin: ReturnType<typeof createClient>
) {
  const stripeSubscriptionId = invoice.subscription as string;

  console.log(
    `invoice.payment_failed: subscription=${stripeSubscriptionId}, invoice=${invoice.id}`
  );

  if (!stripeSubscriptionId) {
    console.log("No subscription on this invoice — skipping");
    return;
  }

  const { error } = await supabaseAdmin
    .from("subscriptions")
    .update({
      status: "past_due",
      updated_at: new Date().toISOString(),
    })
    .eq("stripe_subscription_id", stripeSubscriptionId);

  if (error) {
    console.error("Failed to update subscription to past_due:", error.message);
  } else {
    console.log(`Subscription ${stripeSubscriptionId} marked as past_due`);
  }
}

// ---------------------------------------------------------------------------
// 4. customer.subscription.updated
// ---------------------------------------------------------------------------
// Fired when any property on the subscription changes (status, plan, etc.)
// We sync the status, period dates, and cancellation flag to our DB.
// ---------------------------------------------------------------------------
async function handleSubscriptionUpdated(
  subscription: Stripe.Subscription,
  supabaseAdmin: ReturnType<typeof createClient>
) {
  const stripeSubscriptionId = subscription.id;

  console.log(
    `customer.subscription.updated: sub=${stripeSubscriptionId}, status=${subscription.status}`
  );

  const { error } = await supabaseAdmin
    .from("subscriptions")
    .update({
      status: subscription.status,
      current_period_start: unixToISO(subscription.current_period_start),
      current_period_end: unixToISO(subscription.current_period_end),
      canceled_at_period_end: subscription.cancel_at_period_end,
      updated_at: new Date().toISOString(),
    })
    .eq("stripe_subscription_id", stripeSubscriptionId);

  if (error) {
    console.error("Failed to sync subscription update:", error.message);
  } else {
    console.log(`Subscription ${stripeSubscriptionId} synced — status: ${subscription.status}`);
  }
}

// ---------------------------------------------------------------------------
// 5. customer.subscription.deleted
// ---------------------------------------------------------------------------
// Fired when a subscription is fully cancelled (end of billing period
// or immediate cancellation). We mark it as canceled and close any
// active billing cycle.
// ---------------------------------------------------------------------------
async function handleSubscriptionDeleted(
  subscription: Stripe.Subscription,
  supabaseAdmin: ReturnType<typeof createClient>
) {
  const stripeSubscriptionId = subscription.id;

  console.log(`customer.subscription.deleted: sub=${stripeSubscriptionId}`);

  // ── Update subscription status to canceled ─────────────────────────────
  const { error: updateError } = await supabaseAdmin
    .from("subscriptions")
    .update({
      status: "canceled",
      canceled_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
    .eq("stripe_subscription_id", stripeSubscriptionId);

  if (updateError) {
    console.error("Failed to cancel subscription:", updateError.message);
    return;
  }

  console.log(`Subscription ${stripeSubscriptionId} marked as canceled`);

  // ── Close any active billing cycle ─────────────────────────────────────
  // Look up our internal subscription to get the ID for billing_cycles query
  const { data: sub } = await supabaseAdmin
    .from("subscriptions")
    .select("id")
    .eq("stripe_subscription_id", stripeSubscriptionId)
    .maybeSingle();

  if (sub) {
    const { error: cycleError } = await supabaseAdmin
      .from("billing_cycles")
      .update({ status: "closed" })
      .eq("subscription_id", sub.id)
      .eq("status", "active");

    if (cycleError) {
      console.error("Failed to close billing cycle on cancellation:", cycleError.message);
    } else {
      console.log(`Active billing cycle closed for subscription ${sub.id}`);
    }
  }
}

// =============================================================================
// MAIN REQUEST HANDLER
// =============================================================================

Deno.serve(async (req) => {
  // ── Handle CORS preflight ──────────────────────────────────────────────
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  // Only allow POST (Stripe always sends POST for webhooks)
  if (req.method !== "POST") {
    return jsonResponse({ error: "Method not allowed" }, 405);
  }

  try {
    // =====================================================================
    // STEP 1: Read raw body and verify Stripe webhook signature
    // =====================================================================
    // CRITICAL: We must read the body as raw text, NOT as JSON.
    // Stripe's signature verification compares against the raw body string.
    // If we parse it as JSON first, the signature check will fail.
    const rawBody = await req.text();
    const signature = req.headers.get("stripe-signature");

    if (!signature) {
      console.error("Missing stripe-signature header");
      return jsonResponse({ error: "Missing stripe-signature header" }, 400);
    }

    const stripeSecretKey = Deno.env.get("STRIPE_SECRET_KEY");
    const webhookSecret = Deno.env.get("STRIPE_WEBHOOK_SECRET");

    if (!stripeSecretKey || !webhookSecret) {
      console.error("Missing STRIPE_SECRET_KEY or STRIPE_WEBHOOK_SECRET env vars");
      return jsonResponse({ error: "Server configuration error" }, 500);
    }

    const stripe = new Stripe(stripeSecretKey, {
      apiVersion: "2023-10-16",
      httpClient: Stripe.createFetchHttpClient(),
    });

    // Verify the webhook signature using SubtleCrypto (required for Deno/edge)
    // This ensures the request genuinely came from Stripe, not from a malicious actor.
    let event: Stripe.Event;
    try {
      event = await stripe.webhooks.constructEventAsync(
        rawBody,
        signature,
        webhookSecret,
        undefined,
        Stripe.createSubtleCryptoProvider()
      );
    } catch (err) {
      const errMessage = err instanceof Error ? err.message : "Unknown error";
      console.error(`Webhook signature verification failed: ${errMessage}`);
      return jsonResponse(
        { error: "Webhook signature verification failed" },
        400
      );
    }

    console.log(`Webhook event received: ${event.type} (${event.id})`);

    // =====================================================================
    // STEP 2: Initialize Supabase admin client
    // =====================================================================
    // We use the service role key here because webhooks don't have a user JWT.
    // The service role key bypasses RLS — this is intentional and safe here
    // because the webhook is already authenticated via Stripe's signature.
    const supabaseAdmin = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    // =====================================================================
    // STEP 3: Route to the correct event handler
    // =====================================================================
    switch (event.type) {
      case "checkout.session.completed": {
        const session = event.data.object as Stripe.Checkout.Session;
        await handleCheckoutCompleted(session, stripe, supabaseAdmin);
        break;
      }

      case "invoice.paid": {
        const invoice = event.data.object as Stripe.Invoice;
        await handleInvoicePaid(invoice, stripe, supabaseAdmin);
        break;
      }

      case "invoice.payment_failed": {
        const invoice = event.data.object as Stripe.Invoice;
        await handleInvoicePaymentFailed(invoice, supabaseAdmin);
        break;
      }

      case "customer.subscription.updated": {
        const subscription = event.data.object as Stripe.Subscription;
        await handleSubscriptionUpdated(subscription, supabaseAdmin);
        break;
      }

      case "customer.subscription.deleted": {
        const subscription = event.data.object as Stripe.Subscription;
        await handleSubscriptionDeleted(subscription, supabaseAdmin);
        break;
      }

      default:
        console.log(`Unhandled event type: ${event.type} — acknowledged but no action taken`);
    }

    // =====================================================================
    // STEP 4: Return 200 to acknowledge receipt
    // =====================================================================
    // IMPORTANT: Always return 200 to Stripe, even if we encounter a
    // non-critical error. If we return 4xx/5xx, Stripe will keep retrying
    // the webhook for up to 72 hours, which could cause duplicate processing.
    return jsonResponse({ received: true });

  } catch (error) {
    const errMessage = error instanceof Error ? error.message : "Unknown error";
    console.error("Unhandled error in stripe-webhook-handler:", errMessage);

    // Return 500 only for truly unexpected errors.
    // Stripe will retry, which is acceptable for genuine server failures.
    return jsonResponse(
      { error: "Internal server error", details: errMessage },
      500
    );
  }
});
