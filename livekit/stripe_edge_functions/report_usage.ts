// =============================================================================
// Edge Function: report-usage
// =============================================================================
//
// PURPOSE:
//   Called by the backend voice agent (LiveKit / ElevenLabs) every time a
//   voice call ends. It reports the call duration to Stripe's Billing Meter
//   so that overage charges are calculated automatically at the end of each
//   billing cycle.
//
// WHO CALLS THIS:
//   The Python LiveKit agent — NOT the frontend browser.
//   This is a backend-to-backend call. The agent authenticates using the
//   Supabase service role key as a Bearer token.
//
// WHAT IT DOES (step by step):
//   1. Authenticates the caller (must be service_role — rejects user tokens)
//   2. Validates the request body (org_id, call_duration_minutes, call_id)
//   3. Checks for duplicate call_id (idempotency — prevents double billing)
//   4. Fetches the org's active subscription from the database
//   5. Fetches the org's stripe_customer_id (required by Stripe meter API)
//   6. Sends a meter event to Stripe (voice_call_minutes)
//   7. Updates the billing_cycles table with usage stats for frontend display
//   8. Inserts an audit record into usage_records for compliance/debugging
//   9. Returns a success response with usage summary
//
// REQUEST FORMAT:
//   POST /functions/v1/report-usage
//   Headers:
//     Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>
//     Content-Type: application/json
//   Body:
//     {
//       "org_id": "uuid",                  ← which organisation made the call
//       "call_duration_minutes": 5.3,      ← raw duration from LiveKit (can be decimal)
//       "call_id": "unique-call-id"        ← unique identifier from LiveKit session
//     }
//
// RESPONSE FORMAT:
//   200: {
//     "success": true,
//     "call_id": "...",
//     "billed_minutes": 6,                 ← ceiled to nearest minute (billing standard)
//     "raw_duration_minutes": 5.3,         ← original value from agent
//     "total_minutes_used": 1856,          ← cumulative for this billing cycle
//     "overage_minutes": 0,                ← minutes beyond included allowance
//     "meter_event_sent": true
//   }
//
//   400: { "error": "Missing required fields" | "No Stripe customer ID" }
//   403: { "error": "Forbidden: service_role required" }
//   404: { "error": "No active subscription found" }
//   500: { "error": "Internal server error" }
//   502: { "error": "Failed to send meter event to Stripe" }
//
// ENVIRONMENT VARIABLES REQUIRED:
//   SUPABASE_URL              ← Supabase project URL
//   SUPABASE_SERVICE_ROLE_KEY ← Service role key (bypasses RLS for DB writes)
//   STRIPE_SECRET_KEY         ← Stripe API secret key
//
// DATABASE TABLES USED:
//   - subscriptions    → find active subscription for the org
//   - organisations    → get stripe_customer_id
//   - billing_plans    → get overage_rate_aud_cents for cost estimation
//   - billing_cycles   → track minutes_used, overage_minutes, overage_cost
//   - usage_records    → audit trail of every call (see CREATE TABLE below)
//
// IMPORTANT — usage_records TABLE:
//   If this table doesn't exist yet, create it in Supabase SQL Editor:
//
//   CREATE TABLE IF NOT EXISTS usage_records (
//     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
//     org_id UUID NOT NULL REFERENCES organisations(id),
//     subscription_id UUID REFERENCES subscriptions(id),
//     billing_cycle_id UUID REFERENCES billing_cycles(id),
//     call_id TEXT NOT NULL UNIQUE,
//     call_duration_minutes NUMERIC(10,2) NOT NULL,
//     billed_minutes INT4 NOT NULL,
//     stripe_meter_event_id TEXT,
//     created_at TIMESTAMPTZ DEFAULT now()
//   );
//
// BILLING LOGIC — HOW MINUTES ARE BILLED:
//   - Raw call duration (e.g., 3.2 minutes) is rounded UP to nearest whole
//     minute (e.g., 4 minutes). This is standard telecom billing practice.
//   - The ceiled value is sent to Stripe's Billing Meter.
//   - Stripe automatically aggregates all meter events for the billing period
//     and applies the tiered pricing (e.g., first 2000 min included, then
//     €0.50/min for overages). We do NOT calculate the final invoice — Stripe does.
//   - The billing_cycles table is updated with usage stats purely for the
//     frontend dashboard (e.g., "You've used 1,850 of 2,000 included minutes").
//
// =============================================================================

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import Stripe from "https://esm.sh/stripe@14?target=deno";

// =============================================================================
// CORS headers — included for consistency across all edge functions.
// Although this function is called by a backend agent (not a browser),
// having CORS headers doesn't hurt and allows flexibility if we ever
// need to call it from a browser-based admin panel.
// =============================================================================
const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// =============================================================================
// Helper: Build a consistent JSON response with CORS headers
// =============================================================================
// Every response from this function uses this helper to ensure:
//   1. Correct Content-Type header
//   2. CORS headers are always included
//   3. Body is always valid JSON
// =============================================================================
function jsonResponse(body: Record<string, unknown>, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

// =============================================================================
// MAIN REQUEST HANDLER
// =============================================================================
// Deno.serve() is the Supabase Edge Function entry point.
// It receives every HTTP request sent to this function's URL.
// =============================================================================

Deno.serve(async (req) => {
  // =========================================================================
  // Handle CORS preflight request
  // =========================================================================
  // Browsers send an OPTIONS request before the actual POST to check if
  // the server allows cross-origin requests. We respond with 200 and
  // the CORS headers. This is unlikely for backend-to-backend calls
  // but included for completeness.
  // =========================================================================
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  // Only allow POST — usage reports are always POST requests
  if (req.method !== "POST") {
    return jsonResponse({ error: "Method not allowed" }, 405);
  }

  try {
    // =====================================================================
    // STEP 1: Authenticate the caller
    // =====================================================================
    // This function is called by the Python voice agent, NOT by end users.
    // The agent passes the Supabase SERVICE ROLE KEY as the Bearer token.
    //
    // We decode the JWT (without full verification — Supabase already
    // verified it) and check that the role claim is 'service_role'.
    // This prevents regular users from spoofing usage reports.
    //
    // How the Python agent should call this:
    //   requests.post(
    //     f"{SUPABASE_URL}/functions/v1/report-usage",
    //     headers={
    //       "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    //       "Content-Type": "application/json"
    //     },
    //     json={
    //       "org_id": "...",
    //       "call_duration_minutes": 5.3,
    //       "call_id": "..."
    //     }
    //   )
    // =====================================================================
    const authHeader = req.headers.get("Authorization");
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      console.error("Missing or malformed Authorization header");
      return jsonResponse({ error: "Missing Authorization header" }, 401);
    }

    const token = authHeader.replace("Bearer ", "");

    // Decode the JWT payload (second segment of the JWT, base64url-encoded)
    // JWT structure: header.payload.signature — we only need the payload
    // to read the 'role' claim. No need to verify the signature here
    // because Supabase's gateway already verified it before reaching us.
    let jwtPayload: { role?: string };
    try {
      jwtPayload = JSON.parse(atob(token.split(".")[1]));
    } catch {
      console.error("Failed to decode JWT payload");
      return jsonResponse({ error: "Invalid token format" }, 401);
    }

    // Only allow service_role — block regular user tokens (role: 'anon' or 'authenticated')
    if (jwtPayload.role !== "service_role") {
      console.error(
        `Forbidden: expected role 'service_role', got '${jwtPayload.role}'`
      );
      return jsonResponse(
        { error: "Forbidden: this endpoint requires service_role authentication" },
        403
      );
    }

    // =====================================================================
    // STEP 2: Parse and validate the request body
    // =====================================================================
    // Expected JSON body from the voice agent:
    //   {
    //     "org_id": "uuid",                 ← organisation that made the call
    //     "call_duration_minutes": 5.3,     ← raw duration (can be decimal)
    //     "call_id": "lk_session_abc123"    ← unique ID from LiveKit session
    //   }
    // =====================================================================
    const body = await req.json();
    const { org_id, call_duration_minutes, call_id } = body;

    // Validate all required fields are present
    if (
      !org_id ||
      call_duration_minutes === undefined ||
      call_duration_minutes === null ||
      !call_id
    ) {
      return jsonResponse(
        {
          error: "Missing required fields",
          required: {
            org_id: "uuid",
            call_duration_minutes: "number (positive)",
            call_id: "string (unique per call)",
          },
          received: { org_id, call_duration_minutes, call_id },
        },
        400
      );
    }

    // Validate call_duration_minutes is a positive number
    const durationMinutes = Number(call_duration_minutes);
    if (isNaN(durationMinutes) || durationMinutes <= 0) {
      return jsonResponse(
        {
          error: "call_duration_minutes must be a positive number",
          received: call_duration_minutes,
        },
        400
      );
    }

    // Round UP to the nearest whole minute for billing purposes
    // This is standard telecom billing practice:
    //   3.0 minutes → billed as 3 minutes
    //   3.1 minutes → billed as 4 minutes
    //   0.5 minutes → billed as 1 minute
    const billedMinutes = Math.ceil(durationMinutes);

    console.log(
      `report-usage: org=${org_id}, call=${call_id}, ` +
        `raw_duration=${durationMinutes}min, billed=${billedMinutes}min`
    );

    // =====================================================================
    // STEP 3: Initialize Supabase admin client and Stripe client
    // =====================================================================
    // We use the service role key for Supabase because:
    //   - This is a backend function (no user context)
    //   - We need to write to tables that have RLS enabled
    //   - The service role key bypasses RLS (intentional and safe here
    //     because the caller is already authenticated as service_role)
    // =====================================================================
    const supabaseAdmin = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY")!, {
      apiVersion: "2023-10-16",
      httpClient: Stripe.createFetchHttpClient(),
    });

    // =====================================================================
    // STEP 4: Idempotency check — prevent duplicate billing
    // =====================================================================
    // The voice agent might retry this call if it gets a network timeout.
    // If we've already processed this call_id, return success without
    // sending another meter event to Stripe. This prevents double-billing.
    //
    // We check the usage_records table for an existing row with this call_id.
    // The call_id column has a UNIQUE constraint for extra safety.
    // =====================================================================
    const { data: existingRecord } = await supabaseAdmin
      .from("usage_records")
      .select("id")
      .eq("call_id", call_id)
      .maybeSingle();

    if (existingRecord) {
      console.log(`Call ${call_id} already processed — returning early (idempotent)`);
      return jsonResponse({
        success: true,
        duplicate: true,
        message: "This call has already been reported — no duplicate meter event sent",
      });
    }

    // =====================================================================
    // STEP 5: Fetch the active subscription for this organisation
    // =====================================================================
    // An organisation must have an active (or trialing) subscription to
    // report usage. If there's no active subscription, the call minutes
    // can't be billed, so we reject the request.
    //
    // We order by created_at DESC and take the first one — in case an org
    // has multiple subscriptions (e.g., cancelled an old one, started a new one).
    // =====================================================================
    const { data: subscription, error: subError } = await supabaseAdmin
      .from("subscriptions")
      .select("id, plan_id, stripe_customer_id, status")
      .eq("org_id", org_id)
      .in("status", ["active", "trialing"])
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (subError) {
      console.error("Error fetching subscription:", subError.message);
      return jsonResponse({ error: "Failed to fetch subscription" }, 500);
    }

    if (!subscription) {
      console.error(`No active subscription found for org: ${org_id}`);
      return jsonResponse(
        {
          error: "No active subscription found for this organisation",
          org_id,
          hint: "The organisation must have an active subscription before usage can be reported",
        },
        404
      );
    }

    console.log(
      `Found subscription: ${subscription.id} (status: ${subscription.status})`
    );

    // =====================================================================
    // STEP 6: Fetch the Stripe Customer ID from the organisations table
    // =====================================================================
    // Stripe's Billing Meter API requires the stripe_customer_id to know
    // which customer the usage belongs to. This ID was saved when the
    // customer first checked out (in create-checkout-session).
    //
    // We fetch from the organisations table (not subscriptions) because
    // the stripe_customer_id belongs to the org, not the subscription.
    // An org keeps the same Stripe Customer ID across plan changes.
    // =====================================================================
    const { data: org, error: orgError } = await supabaseAdmin
      .from("organisations")
      .select("stripe_customer_id")
      .eq("id", org_id)
      .single();

    if (orgError || !org) {
      console.error("Error fetching organisation:", orgError?.message);
      return jsonResponse({ error: "Organisation not found" }, 404);
    }

    const stripeCustomerId = org.stripe_customer_id;

    // If no Stripe Customer ID, billing was never set up for this org
    if (!stripeCustomerId) {
      console.error(`Organisation ${org_id} has no stripe_customer_id`);
      return jsonResponse(
        {
          error: "Organisation does not have a Stripe customer ID",
          hint: "The organisation must complete checkout before usage can be reported",
        },
        400
      );
    }

    console.log(`Stripe customer: ${stripeCustomerId}`);

    // =====================================================================
    // STEP 7: Send meter event to Stripe
    // =====================================================================
    // THIS IS THE MOST CRITICAL STEP.
    //
    // We send a meter event to Stripe's Billing Meter with:
    //   - event_name: 'voice_call_minutes' (matches the meter we created in Stripe Dashboard)
    //   - value: the billed minutes (ceiled to nearest whole minute)
    //   - stripe_customer_id: which customer to attribute the usage to
    //
    // Stripe aggregates ALL meter events for the billing period and
    // automatically calculates the overage charge based on the tiered
    // pricing we configured (e.g., first 2000 min at €0, then €0.50/min).
    //
    // The idempotencyKey ensures that if the agent retries this call,
    // Stripe won't create a duplicate meter event. The key is derived
    // from the unique call_id.
    //
    // If this step fails, we return an error immediately — we do NOT
    // continue to update the database. This ensures our internal tracking
    // stays in sync with what Stripe knows about.
    // =====================================================================
    let meterEventId: string | null = null;

    try {
      const meterEvent = await stripe.billing.meterEvents.create(
        {
          event_name: "voice_call_minutes",
          payload: {
            value: billedMinutes.toString(),
            stripe_customer_id: stripeCustomerId,
          },
        },
        {
          idempotencyKey: `usage_${call_id}`,
        }
      );

      // The meter event response includes an identifier we can store for reference
      meterEventId = meterEvent.identifier || null;

      console.log(
        `✓ Stripe meter event sent: ${billedMinutes} min for customer ${stripeCustomerId}`
      );
    } catch (stripeError) {
      // If the Stripe meter event fails, this is CRITICAL.
      // The customer won't be billed for their usage if we don't report it.
      // Return a 502 (Bad Gateway) so the agent knows to retry.
      const errMsg =
        stripeError instanceof Error ? stripeError.message : "Unknown Stripe error";
      console.error(`✗ Stripe meter event FAILED: ${errMsg}`);
      return jsonResponse(
        {
          error: "Failed to send meter event to Stripe",
          details: errMsg,
        },
        502
      );
    }

    // =====================================================================
    // STEP 8: Update billing_cycles — internal usage tracking
    // =====================================================================
    // Now that the meter event is sent to Stripe, we update our own database
    // for internal tracking. This allows the frontend to display:
    //   - "You've used 1,850 of 2,000 included minutes"
    //   - "Estimated overage: €25.00"
    //
    // We find the ACTIVE billing cycle for this subscription and:
    //   1. Add the billed minutes to minutes_used
    //   2. Calculate overage_minutes (minutes beyond the plan's included allowance)
    //   3. Estimate overage_cost_aud_cents (overage_minutes × overage_rate)
    //
    // NOTE: The overage cost here is an ESTIMATE for display purposes.
    // The actual billing amount is calculated by Stripe based on the meter
    // events and the tiered pricing configuration. The two should match,
    // but Stripe is the source of truth for invoicing.
    //
    // If this step fails, we log the error but do NOT fail the request.
    // The meter event was already sent (Step 7), which is what matters
    // for billing accuracy. The DB can be reconciled later if needed.
    // =====================================================================
    const { data: activeCycle, error: cycleError } = await supabaseAdmin
      .from("billing_cycles")
      .select("id, minutes_used, minutes_included")
      .eq("subscription_id", subscription.id)
      .eq("status", "active")
      .maybeSingle();

    if (cycleError) {
      // Non-critical error — log it but continue
      console.error("Error fetching billing cycle:", cycleError.message);
    }

    // These variables track the updated usage stats for the response
    let updatedMinutesUsed = billedMinutes;
    let overageMinutes = 0;
    let overageCostAudCents = 0;

    if (activeCycle) {
      // ── Calculate new usage totals ─────────────────────────────────────
      updatedMinutesUsed = (activeCycle.minutes_used || 0) + billedMinutes;
      const includedMinutes = activeCycle.minutes_included || 0;

      // Overage = how many minutes BEYOND the plan's included allowance
      // Example: Plan includes 2,000 min. Org has used 2,100 min.
      //          Overage = max(0, 2100 - 2000) = 100 minutes
      overageMinutes = Math.max(0, updatedMinutesUsed - includedMinutes);

      // ── Fetch the overage rate from the plan ───────────────────────────
      // overage_rate_aud_cents is the cost per overage minute in cents
      // Example: 50 = €0.50 per minute
      const { data: plan } = await supabaseAdmin
        .from("billing_plans")
        .select("overage_rate_aud_cents")
        .eq("id", subscription.plan_id)
        .single();

      const overageRate = plan?.overage_rate_aud_cents || 50; // fallback: €0.50/min
      overageCostAudCents = overageMinutes * overageRate;

      // ── Write updated stats back to billing_cycles ─────────────────────
      const { error: updateError } = await supabaseAdmin
        .from("billing_cycles")
        .update({
          minutes_used: updatedMinutesUsed,
          overage_minutes: overageMinutes,
          overage_cost_aud_cents: overageCostAudCents,
        })
        .eq("id", activeCycle.id);

      if (updateError) {
        // Non-critical: log but don't fail (meter event was already sent)
        console.error("Error updating billing cycle:", updateError.message);
      } else {
        console.log(
          `✓ Billing cycle ${activeCycle.id} updated: ` +
            `${updatedMinutesUsed}/${includedMinutes} min used, ` +
            `${overageMinutes} overage min, ` +
            `est. overage cost: ${(overageCostAudCents / 100).toFixed(2)} EUR`
        );
      }
    } else {
      // No active billing cycle found — this shouldn't normally happen
      // (a cycle is created when the subscription starts), but we handle
      // it gracefully. The meter event was already sent, so billing is fine.
      console.warn(
        `No active billing cycle found for subscription ${subscription.id}. ` +
          `Meter event was sent to Stripe but local usage tracking was skipped.`
      );
    }

    // =====================================================================
    // STEP 9: Insert audit record into usage_records
    // =====================================================================
    // Every call gets a row in usage_records for:
    //   - Audit trail / compliance (who made what call, when, for how long)
    //   - Debugging billing disputes ("I was charged for a 10-min call but
    //     it was only 5 min" — we can look up the original duration)
    //   - Usage analytics (call patterns, peak hours, etc.)
    //
    // The call_id column has a UNIQUE constraint, so even if our idempotency
    // check in Step 4 is somehow bypassed, the database will reject duplicates.
    //
    // If the usage_records table doesn't exist yet, this will fail with
    // "relation does not exist". See the CREATE TABLE SQL at the top of
    // this file.
    // =====================================================================
    const { error: recordError } = await supabaseAdmin
      .from("usage_records")
      .insert({
        org_id: org_id,
        subscription_id: subscription.id,
        billing_cycle_id: activeCycle?.id || null,
        call_id: call_id,
        call_duration_minutes: durationMinutes, // raw value (decimal)
        billed_minutes: billedMinutes,           // ceiled value (integer)
        stripe_meter_event_id: meterEventId,
      });

    if (recordError) {
      // Non-critical: the meter event is already sent and billing cycle updated.
      // Log the error so we can investigate, but don't fail the request.
      console.error("Error inserting usage record:", recordError.message);
      if (recordError.message.includes("does not exist")) {
        console.error(
          "HINT: The usage_records table does not exist. " +
            "Create it using the SQL at the top of this file."
        );
      }
    } else {
      console.log(`✓ Usage record created for call ${call_id}`);
    }

    // =====================================================================
    // STEP 10: Return success response
    // =====================================================================
    // We return a detailed response so the voice agent can log the result
    // and optionally display usage info.
    // =====================================================================
    return jsonResponse({
      success: true,
      call_id: call_id,
      billed_minutes: billedMinutes,
      raw_duration_minutes: durationMinutes,
      total_minutes_used: updatedMinutesUsed,
      overage_minutes: overageMinutes,
      meter_event_sent: true,
    });
  } catch (error) {
    // Catch-all for any unhandled errors
    const errMessage = error instanceof Error ? error.message : "Unknown error";
    console.error("Unhandled error in report-usage:", errMessage);
    return jsonResponse(
      { error: "Internal server error", details: errMessage },
      500
    );
  }
});
