// =============================================================================
// Edge Function: create-checkout-session
// =============================================================================
// Triggered by: Frontend (when customer clicks "Buy Plan" on pricing page)
//
// What it does:
//   1. Verifies the user is logged in (via Supabase JWT)
//   2. Fetches the selected plan from billing_plans table
//   3. Creates or retrieves a Stripe Customer for the organisation
//   4. Builds a Stripe Checkout Session with the correct line items:
//      - Flat recurring fee (monthly or yearly)
//      - Metered overage price (linked to voice_call_minutes meter)
//      - One-time setup fee (€249, only for first-time subscribers)
//   5. Returns the checkout URL for frontend to redirect the customer
//
// Request:
//   POST /functions/v1/create-checkout-session
//   Headers:
//     Authorization: Bearer <supabase_jwt_token>
//     Content-Type: application/json
//   Body:
//     {
//       "plan_id": "<uuid from billing_plans table>",
//       "billing_period": "monthly" | "yearly"
//     }
//
// Response:
//   200: { "checkout_url": "https://checkout.stripe.com/pay/cs_xxx" }
//   401: { "error": "Unauthorized" }
//   400: { "error": "..." }
//   404: { "error": "..." }
//   500: { "error": "Internal server error", "details": "..." }
//
// Environment Variables Required (set in Supabase Dashboard → Edge Functions → Manage Secrets):
//   SUPABASE_URL
//   SUPABASE_ANON_KEY
//   SUPABASE_SERVICE_ROLE_KEY
//   STRIPE_SECRET_KEY
//   STRIPE_SETUP_FEE_PRICE_ID   ← Price ID for the one-time €249 setup fee
//   WEBSITE_URL                  ← Frontend URL for success/cancel redirects
// =============================================================================

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import Stripe from "https://esm.sh/stripe@14?target=deno";

// CORS headers — required so the frontend (different origin) can call this function
const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// Helper: build a consistent JSON response with CORS headers
function jsonResponse(body: Record<string, unknown>, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

Deno.serve(async (req) => {
  // ── Handle CORS preflight request ──────────────────────────────────────
  // Browsers send an OPTIONS request before the actual POST request to check CORS.
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  // Only allow POST
  if (req.method !== "POST") {
    return jsonResponse({ error: "Method not allowed" }, 405);
  }

  try {
    // =====================================================================
    // STEP 1: Verify the user is authenticated
    // =====================================================================
    // The frontend sends the Supabase JWT in the Authorization header.
    // We use this to identify which user is making the request.
    // Here, we are retrieveing the value of specific HTTP request header called Authorisation.
    // If in the request header, Authorisation is not present, then it will return 401.
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) {
      console.error("Missing authorization header");
      return jsonResponse({ error: "Missing authorization header" }, 401);
    }

    // Create a Supabase client using the user's JWT (respects RLS)
    // Supabase Auth here which is a supabase client instance which is used to verify the identity of the 
    // user by calling this specific method. supabaseAuth.auth.getUser().
    const supabaseAuth = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
      { global: { headers: { Authorization: authHeader } } }
    );

    // Supabase client here respects here the row level security and is used only for user authentication.
    // It is not used for any database operations.
    const {
      data: { user },
      error: authError,
    } = await supabaseAuth.auth.getUser();
 
    // If the user is not authenticated, then it will return 401.
    // Otherwise, it will proceed to use the user.id to look up their organization and billing details.
    if (authError || !user) {
      console.error("Auth error:", authError?.message || "No user found");
      return jsonResponse({ error: "Unauthorized" }, 401);
    }

    console.log(`Authenticated user: ${user.id} (${user.email})`);

    // =====================================================================
    // STEP 2: Parse and validate request body
    // =====================================================================
    // json is a method used to parse the body of an incoming HTTP request.
    // This json method is called on a request object in Deno's runtime environment to extract 
    // and parse JSON formatted data sent by the client.
    // Here the client is our frontend application.
    // This single line of code is used to retrieve the user's chosen plan and the billing period from
    // the frontend.
    const body = await req.json();
    // This edge function expects  plan id and billing period as input from the frontend.
    // If the plan id is not provided, then it will return 400.
    // If the billing period is not provided, then it will default to monthly.
    const { plan_id, billing_period = "monthly" } = body;

    if (!plan_id) {
      return jsonResponse({ error: "plan_id is required" }, 400);
    }

    if (!["monthly", "yearly"].includes(billing_period)) {
      return jsonResponse(
        { error: 'billing_period must be "monthly" or "yearly"' },
        400
      );
    }

    console.log(
      `Request: plan_id=${plan_id}, billing_period=${billing_period}`
    );

    // =====================================================================
    // STEP 3: Fetch plan details from billing_plans table
    // =====================================================================
    // Use service role client to bypass RLS for database operations
    const supabaseAdmin = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    const { data: plan, error: planError } = await supabaseAdmin
      .from("billing_plans")
      .select("*")
      .eq("id", plan_id)
      .eq("active", true)
      .single();

    if (planError || !plan) {
      console.error("Plan fetch error:", planError?.message || "Plan not found");
      return jsonResponse({ error: "Plan not found or inactive" }, 404);
    }

    console.log(`Plan found: ${plan.name} (${plan.id})`);

    // =====================================================================
    // STEP 4: Fetch the organisation for this user
    // =====================================================================
    const { data: org, error: orgError } = await supabaseAdmin
      .from("organisations")
      .select("id, stripe_customer_id")
      .eq("owner_id", user.id)
      .single();

    if (orgError || !org) {
      console.error(
        "Org fetch error:",
        orgError?.message || "Organisation not found"
      );
      return jsonResponse(
        { error: "Organisation not found for this user" },
        404
      );
    }

    console.log(
      `Organisation: ${org.id}, existing stripe_customer_id: ${org.stripe_customer_id || "none"}`
    );

    // =====================================================================
    // STEP 5: Create or retrieve Stripe Customer
    // =====================================================================
    // If this org has never checked out before, stripe_customer_id will be null.
    // We create a new Stripe Customer and save the ID back to the org row.
    // On subsequent checkouts, we reuse the same Stripe Customer.
    const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY")!, {
      apiVersion: "2023-10-16",
      httpClient: Stripe.createFetchHttpClient(),
    });

    let stripeCustomerId = org.stripe_customer_id;

    if (!stripeCustomerId) {
      console.log("No Stripe Customer exists — creating one...");

      const customer = await stripe.customers.create({
        email: user.email,
        metadata: {
          org_id: org.id,
          supabase_user_id: user.id,
        },
      });

      stripeCustomerId = customer.id;

      // Save stripe_customer_id back to organisations table
      const { error: updateError } = await supabaseAdmin
        .from("organisations")
        .update({ stripe_customer_id: stripeCustomerId })
        .eq("id", org.id);

      if (updateError) {
        console.error(
          "Failed to save stripe_customer_id:",
          updateError.message
        );
        // Non-fatal: we can still proceed with the checkout
      }

      console.log(`Stripe Customer created: ${stripeCustomerId}`);
    } else {
      console.log(`Reusing existing Stripe Customer: ${stripeCustomerId}`);
    }

    // =====================================================================
    // STEP 6: Build line items for the Checkout Session
    // =====================================================================
    // Determine which flat price to use based on billing period
    const flatPriceId =
      billing_period === "yearly"
        ? plan.stripe_yearly_price_id
        : plan.stripe_price_id;

    if (!flatPriceId) {
      console.error(
        `No ${billing_period} price configured for plan: ${plan.name}`
      );
      return jsonResponse(
        { error: `No ${billing_period} price configured for this plan` },
        400
      );
    }

    // Start with the flat recurring fee
    const lineItems: { price: string; quantity?: number }[] = [
      { price: flatPriceId, quantity: 1 },
    ];

    // Add metered price for overage tracking
    // (Stripe will bill overages automatically at end of billing cycle based on meter events)
    if (plan.stripe_metered_price_id) {
      lineItems.push({ price: plan.stripe_metered_price_id });
      // Note: no quantity for metered prices — Stripe determines this from meter events
    }

    // Check if this is a first-time subscriber (to include the one-time setup fee)
    const { data: existingSubs } = await supabaseAdmin
      .from("subscriptions")
      .select("id")
      .eq("org_id", org.id)
      .in("status", ["active", "trialing", "past_due"])
      .limit(1);

    const isFirstSubscription = !existingSubs || existingSubs.length === 0;

    const setupFeePriceId = Deno.env.get("STRIPE_SETUP_FEE_PRICE_ID");
    if (setupFeePriceId && isFirstSubscription) {
      lineItems.push({ price: setupFeePriceId, quantity: 1 });
      console.log("Including one-time setup fee (first subscription)");
    } else if (!isFirstSubscription) {
      console.log("Skipping setup fee (org already has/had a subscription)");
    }

    console.log(
      `Line items: ${lineItems.map((li) => li.price).join(", ")}`
    );

    // =====================================================================
    // STEP 7: Create Stripe Checkout Session
    // =====================================================================
    const websiteUrl =
      Deno.env.get("WEBSITE_URL") || "http://localhost:3000";

    const session = await stripe.checkout.sessions.create({
      customer: stripeCustomerId,
      mode: "subscription",
      line_items: lineItems,
      success_url: `${websiteUrl}/dashboard?payment=success&session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${websiteUrl}/pricing?payment=cancelled`,
      // Metadata is passed to the webhook so we know which org/plan this belongs to
      metadata: {
        org_id: org.id,
        plan_id: plan.id,
        billing_period: billing_period,
      },
      // Subscription metadata — persists on the subscription object itself
      subscription_data: {
        metadata: {
          org_id: org.id,
          plan_id: plan.id,
          billing_period: billing_period,
        },
      },
      // Allow promotion codes if you set them up in Stripe Dashboard
      allow_promotion_codes: true,
    });

    console.log(`Checkout session created: ${session.id}, URL: ${session.url}`);

    // =====================================================================
    // STEP 8: Return checkout URL to the frontend
    // =====================================================================
    return jsonResponse({
      checkout_url: session.url,
      session_id: session.id,
    });
  } catch (error) {
    // Catch-all error handler
    const errMessage =
      error instanceof Error ? error.message : "Unknown error";
    console.error("Unhandled error in create-checkout-session:", errMessage);

    return jsonResponse(
      { error: "Internal server error", details: errMessage },
      500
    );
  }
});
