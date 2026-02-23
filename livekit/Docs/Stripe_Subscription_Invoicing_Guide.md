# Stripe Subscription & Automatic Invoicing Guide

## A Complete Guide to Setting Up Automatic Subscription Billing and Custom Invoice Generation

**Last Updated:** February 2026
**Stripe API Version:** 2024+
**Official Documentation:** https://docs.stripe.com/subscriptions

---

## Table of Contents

1. [What Problem Are We Solving?](#what-problem-are-we-solving)
2. [How Stripe Subscriptions Work (The Big Picture)](#how-stripe-subscriptions-work)
3. [Key Building Blocks](#key-building-blocks)
4. [Pricing Models — Which One Fits Our Use Case?](#pricing-models)
5. [Setting Up Subscription Tiers](#setting-up-subscription-tiers)
6. [Tracking Usage (Voice Call Minutes)](#tracking-usage)
7. [Automatic Invoice Generation](#automatic-invoice-generation)
8. [Customising Invoices with Brand Identity](#customising-invoices-with-brand-identity)
9. [Including Unused Credits in Invoices](#including-unused-credits-in-invoices)
10. [Sending Invoice Emails to Clients](#sending-invoice-emails-to-clients)
11. [Webhook Events — Tracking Everything in Your Frontend](#webhook-events)
12. [API Endpoints Reference — Which One to Use When](#api-endpoints-reference)
13. [Customer Self-Service Portal](#customer-self-service-portal)
14. [Handling Payment Failures](#handling-payment-failures)
15. [Testing Your Integration](#testing-your-integration)
16. [Implementation Checklist](#implementation-checklist)
17. [Additional Resources](#additional-resources)

---

## What Problem Are We Solving?

Think of it like a mobile phone plan:

```
Our Business Model:
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Client signs up for Tier 1 → 500 mins voice calls → $299  │
│                                                             │
│  Client only uses 395 mins this month                       │
│                                                             │
│  We need to:                                                │
│  1. Automatically charge $299 every billing cycle           │
│  2. Send a BRANDED invoice via email                        │
│  3. Show "You used 395 of 500 minutes" on the invoice      │
│  4. Show "105 unused minutes" as a credit/info line         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**What Stripe gives us:**
- Automatic recurring payments (charge the client's card every month)
- Automatic invoice generation (Stripe creates the invoice for us)
- Custom branding (our logo, colours, company info on the invoice)
- Usage tracking (track how many minutes each client uses)
- Email delivery (Stripe sends the invoice email for us)
- Webhook notifications (Stripe tells our app(Frontend) when things happen)

---

## How Stripe Subscriptions Work

### The Subscription Lifecycle


```
SUBSCRIPTION LIFECYCLE:

Step 1: CREATE
  Client picks up a plan → We create a Subscription in Stripe based on tier selected
  Stripe creates a Customer + stores their payment method

Step 2: INVOICE
  Every billing cycle, Stripe automatically creates an Invoice
  The invoice lists what the client is being charged for

Step 3: CHARGE
  Stripe automatically charges the client's payment method
  (credit card, bank account, etc.)

Step 4: EMAIL
  If payment succeeds → Stripe sends a branded invoice email
  If payment fails → Stripe retries and notifies us

Step 5: REPEAT
  Go back to Step 2 next billing cycle
```

### Subscription Statuses — What They Mean



| Status | What It Means | What To Do |
|--------|--------------|------------|
| `trialing` | Client is on a free trial period | Nothing — wait for trial to end |
| `active` | Everything is good, client is paying | Nothing — just keep providing the service |
| `incomplete` | First payment hasn't gone through yet | Wait for the client to complete payment (23-hour window) |
| `incomplete_expired` | Client never completed first payment | Subscription is dead — client needs to sign up again |
| `past_due` | A renewal payment failed | Stripe retries automatically; notify the client |
| `canceled` | Subscription has been cancelled | Revoke access to your service |
| `unpaid` | Multiple payment retries failed | Revoke access; wait for client to update payment |
| `paused` | You paused the subscription manually | Resume when ready |

### Payment Statuses — The Invoice Side

Every time Stripe tries to charge a client, it creates a `PaymentIntent`. Here's what happens:

| PaymentIntent Status | Invoice Status | Subscription Status | What It Means |
|---------------------|----------------|-------------------|---------------|
| `succeeded` | `paid` | `active` | Payment worked |
| `requires_payment_method` | `open` | `incomplete` | Card declined — need new card |
| `requires_action` | `open` | `incomplete` | Client needs to do 3D Secure verification |

---

## Key Building Blocks

Before we build anything, let's understand what Stripe gives us:

### 1. Customer

A **Customer** is a record in Stripe that represents one of our clients.

```
Think of it as: A folder with our client's name on it
Contains: Name, email, payment method, billing address
API: POST /v1/customers
```

### 2. Product

A **Product** is WHAT we sell.

```
Example: "Aisyst Voice AI — Tier 1"
API: POST /v1/products
```

### 3. Price

A **Price** is HOW MUCH we charge and HOW OFTEN.

```
Example: $299/month, recurring
API: POST /v1/prices
```

### 4. Subscription

A **Subscription** links a Customer to a Price. It's the actual "deal."

```
Example: "Client ABC is on Tier 1 ($299/month)"
API: POST /v1/subscriptions
```

### 5. Invoice

An **Invoice** is the bill that Stripe generates automatically.

```
Example: The receipt/bill sent to the client.
Created automatically every billing cycle
API: GET /v1/invoices
```

### 6. Meter (for usage tracking)

A **Meter** tracks how much of something a client uses.

```
Think of it as: The electricity meter in your house
Example: Counts voice call minutes
API: POST /v1/billing/meters
```

### How They All Connect

```
                    ┌──────────┐
                    │ Customer │  (Client ABC)
                    └────┬─────┘
                         │
                         │ has a
                         ▼
                  ┌──────────────┐
                  │ Subscription │  (Tier 1 plan)
                  └──────┬───────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          ▼          ▼
         ┌────────┐ ┌────────┐ ┌────────┐
         │ Price  │ │Invoice │ │ Meter  │
         │$299/mo │ │(auto)  │ │(mins)  │
         └────────┘ └────────┘ └────────┘
```

---

## Pricing Models

Stripe supports multiple pricing models. Let's see which one fits our use case:

### Available Pricing Models

| Model | How It Works | Good For | Our Use Case? |
|-------|-------------|----------|---------------|
| **Flat Rate** | Same price every month (e.g., $299/month) | Fixed subscription tiers | **Yes — Primary** |
| **Per-Seat** | Price x Number of users (e.g., $10/user/month) | Team plans | Maybe for enterprise |
| **Usage-Based** | Pay only for what you use (e.g., $0.05/min) | Pay-as-you-go | **Yes — For tracking** |
| **Tiered** | Different price at different usage levels | Volume discounts | Maybe for advanced tiers |

### Our Recommended Approach: Flat Rate + Usage Tracking

Since we have fixed subscription tiers ($299 for 500 mins), we should:

1. **Charge a flat rate** — $299/month for Tier 1 or $399/month for Tier 2
2. **Track usage via Meters** — count voice call minutes
3. **Add usage info to invoices** — show "395 of 500 mins used"

This is called a **Licensed + Metered hybrid** approach.

```
curl https://api.stripe.com/v1/prices \
  -u "sk_test_YOUR_KEY:" \
  -d "product"="prod_TIER1_ID" \
  -d "unit_amount"=29900 \
  -d "currency"="usd" \
  -d "recurring[interval]"="month"
```

---

## Setting Up Subscription Tiers

### Step 1: Create Products (One Per Tier)

Each subscription tier is a separate **Product** in Stripe.

```bash
# Tier 1: 500 minutes at $299/month
curl https://api.stripe.com/v1/products \
  -u "sk_test_YOUR_KEY:" \
  -d "name"="Aisyst Voice AI — Tier 1" \
  -d "description"="500 minutes of voice calls per month"

# Tier 2: 1000 minutes at $499/month
curl https://api.stripe.com/v1/products \
  -u "sk_test_YOUR_KEY:" \
  -d "name"="Aisyst Voice AI — Tier 2" \
  -d "description"="1000 minutes of voice calls per month"

# Tier 3: Unlimited minutes at $899/month
curl https://api.stripe.com/v1/products \
  -u "sk_test_YOUR_KEY:" \
  -d "name"="Aisyst Voice AI — Tier 3" \
  -d "description"="Unlimited voice calls per month"
```

**API Endpoint:** `POST /v1/products`
**Docs:** https://docs.stripe.com/api/products/create

### Step 2: Create Prices (Monthly Recurring)

Each Product needs a **Price** — this defines how much to charge and how often.

```bash
# Tier 1 Price: $299/month
curl https://api.stripe.com/v1/prices \
  -u "sk_test_YOUR_KEY:" \
  -d "product"="prod_TIER1_ID" \
  -d "unit_amount"=29900 \
  -d "currency"="usd" \
  -d "recurring[interval]"="month"

# Tier 2 Price: $499/month
curl https://api.stripe.com/v1/prices \
  -u "sk_test_YOUR_KEY:" \
  -d "product"="prod_TIER2_ID" \
  -d "unit_amount"=49900 \
  -d "currency"="usd" \
  -d "recurring[interval]"="month"
```

**API Endpoint:** `POST /v1/prices`
**Docs:** https://docs.stripe.com/api/prices/create

### Step 3: Create a Customer

When a client signs up, create a Customer in Stripe:

```bash
curl https://api.stripe.com/v1/customers \
  -u "sk_test_YOUR_KEY:" \
  -d "name"="ABC Restaurant" \
  -d "email"="billing@abcrestaurant.com" \
  -d "payment_method"="pm_card_visa" \
  -d "invoice_settings[default_payment_method]"="pm_card_visa"
```

**API Endpoint:** `POST /v1/customers`
**Docs:** https://docs.stripe.com/api/customers/create

### Step 4: Create the Subscription

Link the Customer to a Price to start the subscription:

```bash
curl https://api.stripe.com/v1/subscriptions \
  -u "sk_test_YOUR_KEY:" \
  -d "customer"="cus_CLIENT_ABC" \
  -d "items[0][price]"="price_TIER1_ID" \
  -d "payment_behavior"="default_incomplete" \
  -d "collection_method"="charge_automatically"
```

**Important Parameters:**

| Parameter | Value | Why |
|-----------|-------|-----|
| `payment_behavior` | `default_incomplete` | Handles failed payments and 3DS gracefully |
| `collection_method` | `charge_automatically` | Stripe charges the card automatically |
| `collection_method` | `send_invoice` | Stripe emails an invoice, client pays manually |

**API Endpoint:** `POST /v1/subscriptions`
**Docs:** https://docs.stripe.com/api/subscriptions/create

---

## Tracking Usage

### Why Track Usage?

Even though we charge a flat rate, we want to **track** how many minutes each client uses so we can:

1. Show usage on the invoice ("You used 395 of 500 minutes")
2. Alert clients when they're close to their limit
3. Handle overage charges if needed

### How Stripe Usage Tracking Works

Stripe uses a system called **Meters** to track usage:

```
YOUR APP                          STRIPE
┌─────────┐     meter event      ┌──────────┐
│ Voice   │ ──────────────────► │  Meter   │
│ Agent   │  "5 mins call"       │  (Sum)   │
│ Server  │                      │          │
│         │  "12 mins call"      │  Total:  │
│         │ ──────────────────► │  395 min │
│         │                      │          │
│         │  "3 mins call"       │          │
│         │ ──────────────────► │          │
└─────────┘                      └──────────┘
```

### Step 1: Create a Meter

A Meter defines WHAT you're counting and HOW to aggregate it.

**Dashboard:** Go to https://dashboard.stripe.com/test/meters → Create meter

**API:**
```bash
curl https://api.stripe.com/v1/billing/meters \
  -u "sk_test_YOUR_KEY:" \
  -d "display_name"="Voice Call Minutes" \
  -d "event_name"="voice_call_minutes" \
  -d "default_aggregation[formula]"="sum"
```

**Aggregation Options:**

| Formula | What It Does | Example |
|---------|-------------|---------|
| `sum` | Adds up all values | Total minutes used (our case) |
| `count` | Counts the number of events | Number of calls made |
| `last` | Uses the most recent value | Current storage size |

**API Endpoint:** `POST /v1/billing/meters`
**Docs:** https://docs.stripe.com/billing/subscriptions/usage-based/meters/configure

### Step 2: Send Meter Events (Record Usage)

Every time a voice call ends, send a meter event to Stripe:

```bash
curl https://api.stripe.com/v1/billing/meter_events \
  -u "sk_test_YOUR_KEY:" \
  -d "event_name"="voice_call_minutes" \
  -d "payload[value]"=5 \
  -d "payload[stripe_customer_id]"="cus_CLIENT_ABC"
```

**In Python (after each call ends):**

```python
import stripe

stripe.api_key = "sk_test_YOUR_KEY"

def record_call_usage(customer_id: str, minutes_used: int):
    """Record voice call minutes after each call ends."""
    stripe.billing.MeterEvent.create(
        event_name="voice_call_minutes",
        payload={
            "value": str(minutes_used),
            "stripe_customer_id": customer_id,
        },
    )
```

**Important Rules for Meter Events:**

| Rule | Details |
|------|---------|
| **Timestamp** | Must be within past 35 calendar days |
| **Values** | Must be whole numbers (no decimals) |
| **Rate Limit** | 1,000 calls/second in live mode |
| **Processing** | Asynchronous — may not appear instantly |
| **Idempotency** | Use unique identifiers to prevent duplicates |

**API Endpoint:** `POST /v1/billing/meter_events`
**Docs:** https://docs.stripe.com/billing/subscriptions/usage-based/recording-usage-api

### Step 3: Monitor Usage with Alerts

Stripe lets you set alerts when a client hits a usage threshold:

```
Use Cases:
- Email client when they've used 400 of 500 minutes (80% threshold)
- Alert your sales team when a client exceeds their tier limit
- Auto-deprovision access when free trial usage runs out
```

**Dashboard:** Set up alerts at https://dashboard.stripe.com/test/meters

**Docs:** https://docs.stripe.com/billing/subscriptions/usage-based/monitor

---

## Automatic Invoice Generation

### How Invoice Creation Works

Stripe **automatically** creates invoices for subscriptions. You don't need to create them manually.

```
INVOICE LIFECYCLE FOR SUBSCRIPTIONS:

1. BILLING CYCLE ENDS
   └── Stripe creates a DRAFT invoice
       └── Status: "draft"
       └── You have ~1 hour to modify it

2. ONE HOUR LATER
   └── Stripe FINALISES the invoice
       └── Status: "open"
       └── Invoice is now locked (can't change amounts)

3. PAYMENT ATTEMPT
   └── Stripe charges the client's payment method
       ├── SUCCESS → Status: "paid" ✅
       └── FAILURE → Status: "open" (Stripe retries) ⚠️

4. EMAIL SENT
   └── Stripe sends the invoice email to the client
       └── Includes PDF attachment
       └── Includes link to Hosted Invoice Page
```

### The 1-Hour Draft Window — Why It Matters

When Stripe creates a renewal invoice, it's a **draft** for about 1 hour. During this window, you can:

- Add extra line items (like overage charges)
- Add custom descriptions (like usage summaries)
- Modify amounts
- Add metadata

**This is where we add the "You used 395 of 500 minutes" line.**

### How to Modify a Draft Invoice

Listen for the `invoice.created` webhook, then add custom items:

```python
import stripe

stripe.api_key = "sk_test_YOUR_KEY"

def handle_invoice_created(invoice):
    """Add usage summary line item to draft invoice."""
    
    # Only modify subscription invoices (not one-off invoices)
    if not invoice.subscription:
        return
    
    # Get the customer's usage for this billing period
    customer_id = invoice.customer
    minutes_used = get_usage_from_meter(customer_id)  # your function
    minutes_included = 500  # Tier 1 includes 500 mins
    minutes_unused = minutes_included - minutes_used
    
    # Add an informational line item showing usage
    # Amount = 0 because this is just informational
    stripe.InvoiceItem.create(
        customer=customer_id,
        invoice=invoice.id,  # Attach to THIS specific invoice
        amount=0,
        currency="usd",
        description=f"Usage Summary: {minutes_used} of {minutes_included} minutes used ({minutes_unused} minutes unused)",
    )
```

**API Endpoints Used:**
- `POST /v1/invoiceitems` — Add items to an invoice
- `GET /v1/invoices/{id}` — Retrieve an invoice
- `POST /v1/invoices/{id}/finalize` — Manually finalise

### Preview an Upcoming Invoice

Before the billing cycle ends, you can preview what the next invoice will look like:

```bash
curl https://api.stripe.com/v1/invoices/create_preview \
  -u "sk_test_YOUR_KEY:" \
  -d "customer"="cus_CLIENT_ABC" \
  -d "subscription"="sub_SUBSCRIPTION_ID"
```

**API Endpoint:** `POST /v1/invoices/create_preview`
**Docs:** https://docs.stripe.com/api/invoices/create_preview

---

## Customising Invoices with Brand Identity

### Branding Options

Stripe lets you customise the look and feel of your invoices so they match your company identity.

### 1. Account-Level Branding (Applies to Everything)

Go to **Dashboard → Settings → Branding** (https://dashboard.stripe.com/account/branding)

| Setting | What It Controls | Requirements |
|---------|-----------------|--------------|
| **Icon** | Square logo (used in emails, receipts) | JPG/PNG, ≥128×128px, <512KB |
| **Logo** | Non-square logo (overrides icon in some places) | JPG/PNG, <512KB |
| **Brand Colour** | Primary colour on invoices, receipts, portal | Hex colour code |
| **Accent Colour** | Background colour on emails and pages | Hex colour code |

### 2. Invoice-Specific Customisation

Go to **Dashboard → Settings → Billing → Invoice** (https://dashboard.stripe.com/settings/billing/invoice)

| Feature | What It Does | How to Set It |
|---------|-------------|---------------|
| **Memo/Description** | Notes section on the invoice (e.g., "Thank you for your business!") | Dashboard or API: `description` field |
| **Footer** | Legal text at bottom of invoice PDF (e.g., company registration number) | Dashboard or API: `footer` field |
| **Custom Fields** | Up to 4 key-value pairs in the invoice header (e.g., PO number, contract ID) | Dashboard or API: `custom_fields` |
| **Invoice Number Prefix** | Custom prefix for invoice numbers (e.g., "AISYST-0001") | Dashboard settings |
| **PDF Page Size** | A4 or US Letter | Dashboard settings |

### 3. Invoice Rendering Templates

Templates let you create reusable sets of invoice customisations for different groups of clients.

```
Example Templates:
┌─────────────────────────────────┐
│ Template: "Australia Clients"   │
│ Footer: "ABN: 12 345 678 901"  │
│ Memo: "GST included"           │
│ Custom Field: Region=APAC      │
├─────────────────────────────────┤
│ Template: "US Clients"          │
│ Footer: "Terms: Net 30"        │
│ Memo: "Thank you!"             │
│ Custom Field: Region=US         │
└─────────────────────────────────┘
```

**How to Create:** Dashboard → Settings → Billing → Invoice → Templates tab

**How to Apply:**
- Per invoice (in Invoice Editor)
- Per subscription (in Subscription Editor)
- Per customer (in Customer invoice settings)

**Priority Order** (highest to lowest):
1. Values set directly on the invoice
2. Invoice rendering template on the invoice
3. Invoice rendering template on the subscription
4. Invoice rendering template on the customer
5. Account-level defaults

**Docs:** https://docs.stripe.com/invoicing/invoice-rendering-template

### 4. Setting Custom Fields via API

```python
# Set custom fields when creating an invoice
stripe.Invoice.create(
    customer="cus_CLIENT_ABC",
    custom_fields=[
        {"name": "Client ID", "value": "AISYST-001"},
        {"name": "Tier", "value": "Tier 1 — 500 mins"},
        {"name": "Contract", "value": "CTR-2026-0042"},
    ],
    description="Monthly subscription — Aisyst Voice AI Platform",
    footer="Aisyst Pty Ltd | ABN: 12 345 678 901 | support@aisyst.com",
)
```

### 5. Customer Preferred Languages

Stripe can localise invoice PDFs and emails in 40+ languages.

```python
# Set when creating the customer
stripe.Customer.create(
    name="Tokyo Restaurant",
    email="billing@tokyo-restaurant.jp",
    preferred_locales=["ja"],  # Japanese
)
```

Supported languages include: English (US/UK), Japanese, Chinese (Simplified/Traditional), Korean, Spanish, French, German, Italian, Portuguese, Arabic, Hindi, Thai, Vietnamese, and 25+ more.

---

## Including Unused Credits in Invoices

This is the key part of our use case. We want the invoice to show:

```
┌──────────────────────────────────────────────────────┐
│                    INVOICE                            │
│                                                      │
│  Aisyst Voice AI — Tier 1         $299.00            │
│  (Monthly subscription)                              │
│                                                      │
│  ──────────────────────────────────────────           │
│  Usage Summary:                                      │
│  Voice Call Minutes Used:     395 of 500 mins        │
│  Unused Minutes:              105 mins               │
│  ──────────────────────────────────────────           │
│                                                      │
│  Subtotal:                        $299.00            │
│  Tax (GST 10%):                    $29.90            │
│  TOTAL:                           $328.90            │
└──────────────────────────────────────────────────────┘
```

### Approach 1: Add Informational Line Items (Simplest)

Use the 1-hour draft window to add zero-cost line items:

```python
import stripe

stripe.api_key = "sk_test_YOUR_KEY"

# TIER CONFIGURATION
TIER_LIMITS = {
    "price_TIER1": {"name": "Tier 1", "minutes": 500, "price": 299},
    "price_TIER2": {"name": "Tier 2", "minutes": 1000, "price": 499},
    "price_TIER3": {"name": "Tier 3", "minutes": -1, "price": 899},  # -1 = unlimited
}

def add_usage_summary_to_invoice(invoice_id: str, customer_id: str, subscription_id: str):
    """Add usage summary line items to a draft invoice."""
    
    # 1. Get the subscription to find which tier
    subscription = stripe.Subscription.retrieve(subscription_id)
    price_id = subscription["items"]["data"][0]["price"]["id"]
    tier = TIER_LIMITS.get(price_id)
    
    if not tier:
        return
    
    # 2. Get usage from Stripe Meter
    # (You could also get this from your own database)
    minutes_used = get_meter_usage(customer_id)
    minutes_included = tier["minutes"]
    
    if minutes_included == -1:
        # Unlimited tier
        stripe.InvoiceItem.create(
            customer=customer_id,
            invoice=invoice_id,
            amount=0,
            currency="usd",
            description=f"Voice Call Minutes Used This Period: {minutes_used} mins (Unlimited Plan)",
        )
    else:
        minutes_unused = max(0, minutes_included - minutes_used)
        
        # Add usage line
        stripe.InvoiceItem.create(
            customer=customer_id,
            invoice=invoice_id,
            amount=0,
            currency="usd",
            description=f"Voice Call Minutes Used: {minutes_used} of {minutes_included} mins",
        )
        
        # Add unused credits line
        stripe.InvoiceItem.create(
            customer=customer_id,
            invoice=invoice_id,
            amount=0,
            currency="usd",
            description=f"Unused Minutes Remaining: {minutes_unused} mins",
        )
        
        # Optional: Add overage warning
        if minutes_used > minutes_included:
            overage = minutes_used - minutes_included
            stripe.InvoiceItem.create(
                customer=customer_id,
                invoice=invoice_id,
                amount=0,  # or charge for overage
                currency="usd",
                description=f"⚠️ Overage: {overage} mins over plan limit",
            )

def get_meter_usage(customer_id: str) -> int:
    """Get total voice minutes used from Stripe Meter."""
    # Use Meter Event Summaries API
    summaries = stripe.billing.MeterEventSummary.list(
        customer=customer_id,
        meter="mtr_YOUR_METER_ID",
    )
    total = sum(s.aggregated_value for s in summaries.data)
    return int(total)
```

### Approach 2: Using Billing Credits (For Prepaid Models)

If you want clients to "buy" minutes upfront and deduct as they use:

```python
# Grant 500 minutes as billing credits when client subscribes
stripe.billing.CreditGrant.create(
    customer="cus_CLIENT_ABC",
    category="paid",  # or "promotional" for free credits
    amount={
        "type": "monetary",
        "value": 29900,  # $299 in cents
        "currency": "usd",
    },
    applicability_config={
        "scope": {
            "price_type": "metered",
        },
    },
)
```

**Note:** Billing Credits is currently in **Public Preview**. It's best for pure pay-as-you-go models. For our fixed-tier model, Approach 1 (informational line items) is simpler.

**Docs:** https://docs.stripe.com/billing/subscriptions/usage-based/billing-credits

### Approach 3: Using Invoice Metadata

Store usage data as metadata on the invoice for your frontend to render:

```python
# Update invoice with usage metadata
stripe.Invoice.modify(
    "in_INVOICE_ID",
    metadata={
        "minutes_used": "395",
        "minutes_included": "500",
        "minutes_unused": "105",
        "tier_name": "Tier 1",
        "usage_percentage": "79",
    },
)
```

Your frontend can then read this metadata to display usage dashboards.

---

## Sending Invoice Emails to Clients

### Stripe's Built-In Email System

Stripe can automatically send branded emails for you. You don't need a separate email service.

### What Emails Can Stripe Send?

| Email Type | When It's Sent | How to Enable |
|------------|---------------|---------------|
| **Finalised invoice** | When a subscription invoice is ready | Dashboard → Billing → Subscriptions and emails |
| **Successful payment receipt** | After payment succeeds | Dashboard → Settings → Customer emails |
| **Failed payment notice** | When a card payment fails | Dashboard → Billing → Subscriptions and emails |
| **Upcoming invoice** | A few days before renewal | Automatic for `charge_automatically` subscriptions |
| **Expiring card warning** | When saved card is about to expire | Dashboard → Billing → Subscriptions and emails |
| **3D Secure authentication** | When client needs to verify payment | Dashboard → Billing → 3D Secure settings |
| **Trial ending reminder** | 3 days before trial ends | Automatic |
| **Credit note** | When a credit note is issued | Automatic |

### How to Enable Invoice Emails

1. Go to **Dashboard → Settings → Billing → Subscriptions and emails**
   (https://dashboard.stripe.com/settings/billing/automatic)

2. Under **Manage invoices sent to customers**:
   - ✅ Enable "Send finalised invoices and credit notes to customers"

3. Under **Email notifications and customer management**:
   - ✅ Enable "Send emails when card payments fail"
   - ✅ Enable "Send emails about expiring cards"

### Email Contains:

- Your company logo and brand colours
- Invoice details (line items, amounts, tax)
- Link to the **Hosted Invoice Page** (where client can pay and download PDF)
- PDF attachment of the invoice

### Adding Extra Email Recipients

Sometimes the billing contact is different from the account owner.

**Dashboard method:**
1. Go to Customers → Select customer
2. Edit → Billing information
3. Add CC email addresses

### Custom Email Domain

You can send invoice emails from your own domain (e.g., `billing@aisyst.com`) instead of Stripe's default.

**Setup:** Dashboard → Settings → Account → Email domain

### Disable Stripe Emails and Send Your Own

If you want full control over the email design:

1. Disable Stripe's automatic emails in Dashboard settings
2. Listen for webhook events (`invoice.finalized`, `invoice.paid`)
3. Build and send your own emails using your email service (SendGrid, SES, etc.)
4. Use the `hosted_invoice_url` from the invoice object to link to the payment page

```python
# Get the hosted invoice URL for your custom email
invoice = stripe.Invoice.retrieve("in_INVOICE_ID")
hosted_url = invoice.hosted_invoice_url  # Link to Stripe-hosted payment page
invoice_pdf = invoice.invoice_pdf          # Direct link to PDF download
```

---

## Webhook Events

### What Are Webhooks?

Think of webhooks as **text message notifications** from Stripe. Every time something happens (payment succeeds, subscription cancels, etc.), Stripe sends a message to your server.

### Setting Up Webhooks

1. **Dashboard:** Go to https://dashboard.stripe.com/webhooks → Add endpoint
2. **Your endpoint URL:** `https://your-server.com/stripe/webhook`
3. **Select events** you want to receive

### Essential Webhook Events for Our Use Case

#### Subscription Events

| Event | When It Fires | What You Should Do |
|-------|--------------|-------------------|
| `customer.subscription.created` | New subscription created | Store subscription info in your database |
| `customer.subscription.updated` | Subscription changed (upgrade/downgrade) | Update client's plan in your database |
| `customer.subscription.deleted` | Subscription cancelled | Revoke access to service |
| `customer.subscription.trial_will_end` | 3 days before trial ends | Remind client to add payment method |
| `customer.subscription.paused` | Subscription paused | Pause service access |
| `customer.subscription.resumed` | Subscription resumed | Restore service access |

#### Invoice Events

| Event | When It Fires | What You Should Do |
|-------|--------------|-------------------|
| `invoice.created` | Draft invoice created (~1 hour before finalisation) | **Add usage summary line items** |
| `invoice.finalized` | Invoice is finalised and locked | Send custom email (if not using Stripe's) |
| `invoice.paid` | Payment succeeded | Confirm access, update database |
| `invoice.payment_failed` | Payment failed | Notify client, suggest updating payment method |
| `invoice.payment_action_required` | Client needs to complete 3D Secure | Redirect client to authentication page |
| `invoice.upcoming` | Sent a few days before the next invoice | Add extra charges or preview |
| `invoice.updated` | Invoice was modified | Track changes |

#### Payment Events

| Event | When It Fires | What You Should Do |
|-------|--------------|-------------------|
| `payment_intent.succeeded` | Payment went through | Log successful payment |
| `payment_intent.payment_failed` | Payment failed | Trigger retry or notification |

### Webhook Handler Example (Python/Flask)

```python
import stripe
from flask import Flask, request, jsonify

app = Flask(__name__)
stripe.api_key = "sk_test_YOUR_KEY"
WEBHOOK_SECRET = "whsec_YOUR_WEBHOOK_SECRET"

@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except ValueError:
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400
    
    # Handle specific events
    if event["type"] == "invoice.created":
        invoice = event["data"]["object"]
        # Add usage summary to draft invoice (1-hour window)
        if invoice.get("subscription"):
            add_usage_summary_to_invoice(
                invoice_id=invoice["id"],
                customer_id=invoice["customer"],
                subscription_id=invoice["subscription"],
            )
    
    elif event["type"] == "invoice.paid":
        invoice = event["data"]["object"]
        # Payment successful — update your database
        update_client_payment_status(
            customer_id=invoice["customer"],
            status="paid",
            amount=invoice["amount_paid"],
        )
    
    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        # Payment failed — notify client
        notify_client_payment_failed(
            customer_id=invoice["customer"],
            invoice_id=invoice["id"],
        )
    
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        # Subscription cancelled — revoke access
        revoke_client_access(
            customer_id=subscription["customer"],
        )
    
    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        # Subscription changed — maybe tier upgrade/downgrade
        update_client_tier(
            customer_id=subscription["customer"],
            new_status=subscription["status"],
        )
    
    return jsonify({"status": "ok"}), 200
```

### Tracking Webhooks in Your Frontend

To display real-time subscription and invoice status in your frontend:

```
FRONTEND ARCHITECTURE:

┌──────────┐    webhook    ┌──────────┐    API/WS    ┌──────────┐
│  Stripe  │ ────────────► │  Your    │ ───────────► │ Frontend │
│  Server  │               │  Server  │              │ Dashboard│
└──────────┘               └──────────┘              └──────────┘
                                │
                                ▼
                           ┌──────────┐
                           │ Database │
                           │ (store   │
                           │  status) │
                           └──────────┘
```

**What to show in frontend:**

| Data | Source API | When to Refresh |
|------|-----------|-----------------|
| Current plan/tier | `GET /v1/subscriptions/{id}` | On `customer.subscription.updated` |
| Minutes used | `GET /v1/billing/meter_event_summaries` | Periodically (e.g., every hour) |
| Payment history | `GET /v1/invoices?customer={id}` | On `invoice.paid` |
| Next invoice date | `GET /v1/subscriptions/{id}` → `current_period_end` | On subscription change |
| Invoice PDF | `GET /v1/invoices/{id}` → `invoice_pdf` | On `invoice.finalized` |

---

## API Endpoints Reference

### Quick Reference — Which Endpoint for Which Scenario

#### Creating Things

| Scenario | Endpoint | Method |
|----------|----------|--------|
| Create a new client | `POST /v1/customers` | Create Customer |
| Create a product/tier | `POST /v1/products` | Create Product |
| Set a price | `POST /v1/prices` | Create Price |
| Start a subscription | `POST /v1/subscriptions` | Create Subscription |
| Record usage | `POST /v1/billing/meter_events` | Create Meter Event |
| Create a meter | `POST /v1/billing/meters` | Create Meter |
| Add line item to invoice | `POST /v1/invoiceitems` | Create Invoice Item |
| Grant billing credits | `POST /v1/billing/credit_grants` | Create Credit Grant |

#### Reading/Retrieving Things

| Scenario | Endpoint | Method |
|----------|----------|--------|
| Get a client's details | `GET /v1/customers/{id}` | Retrieve Customer |
| Get subscription status | `GET /v1/subscriptions/{id}` | Retrieve Subscription |
| Get an invoice | `GET /v1/invoices/{id}` | Retrieve Invoice |
| List all invoices for a client | `GET /v1/invoices?customer={id}` | List Invoices |
| Preview next invoice | `POST /v1/invoices/create_preview` | Create Preview Invoice |
| Get usage summaries | `GET /v1/billing/meter_event_summaries` | List Meter Event Summaries |
| Get credit balance | `GET /v1/billing/credit_balance_summary` | Get Credit Balance |

#### Updating Things

| Scenario | Endpoint | Method |
|----------|----------|--------|
| Upgrade/downgrade plan | `POST /v1/subscriptions/{id}` | Update Subscription |
| Update payment method | `POST /v1/subscriptions/{id}` | Update default_payment_method |
| Modify draft invoice | `POST /v1/invoices/{id}` | Update Invoice |
| Update client info | `POST /v1/customers/{id}` | Update Customer |
| Finalise an invoice | `POST /v1/invoices/{id}/finalize` | Finalize Invoice |

#### Cancelling/Deleting Things

| Scenario | Endpoint | Method |
|----------|----------|--------|
| Cancel subscription | `DELETE /v1/subscriptions/{id}` | Cancel Subscription |
| Void an invoice | `POST /v1/invoices/{id}/void` | Void Invoice |
| Cancel meter event | `POST /v1/billing/meter_event_adjustments` | Cancel Meter Event |

---

## Customer Self-Service Portal

Stripe provides a **hosted customer portal** where your clients can manage their own subscriptions — no extra coding needed.

### What Clients Can Do in the Portal

- Update their payment method (credit card, bank account)
- View and download current and past invoices
- Upgrade or downgrade their subscription tier
- Cancel their subscription
- Update billing address and tax IDs
- View payment history

### How to Set It Up

1. **Dashboard:** Go to https://dashboard.stripe.com/settings/billing/portal
2. Enable features you want (update payment, cancel subscription, etc.)
3. Customise branding to match your company
4. Generate portal links for your clients

### Creating Portal Sessions via API

```python
# Create a portal session for a client
session = stripe.billing_portal.Session.create(
    customer="cus_CLIENT_ABC",
    return_url="https://your-app.com/dashboard",
)

# Redirect client to: session.url
```

### Embedding Portal Links in Emails

When Stripe sends emails, you can configure them to include links to the customer portal (instead of a custom URL). This lets clients:

- Click "Update payment method" → Goes to portal
- Click "Manage subscription" → Goes to portal
- Click "View invoices" → Goes to portal

**Docs:** https://docs.stripe.com/customer-management

---

## Handling Payment Failures

### What Happens When a Payment Fails?

```
PAYMENT FAILURE FLOW:

Payment fails
    ├── Stripe marks invoice as "open"
    ├── Subscription goes to "past_due" (or "incomplete" for first invoice)
    ├── Stripe sends invoice.payment_failed webhook
    │
    ├── AUTOMATIC RETRY (Smart Retries)
    │   ├── Stripe uses ML to pick the best time to retry
    │   ├── Retries happen over several days
    │   └── If retry succeeds → subscription goes back to "active"
    │
    ├── CUSTOMER EMAIL
    │   ├── Stripe emails the client about the failed payment
    │   └── Email includes link to update payment method
    │
    └── FINAL FAILURE
        ├── After all retries exhausted
        └── Subscription → "canceled" or "unpaid" (your choice in settings)
```

### Smart Retries

Stripe's **Smart Retries** uses machine learning to determine the optimal time to retry a failed payment. It considers:

- Day of the week
- Time of day
- Card issuer patterns
- Historical data

**Enable in Dashboard:** Settings → Billing → Subscriptions and emails → Manage failed payments

### Revenue Recovery Settings

Configure what happens after all retries fail:

| Setting | What Happens |
|---------|-------------|
| Cancel subscription | Subscription ends; client loses access |
| Mark as unpaid | Subscription stays but stops generating new invoices |
| Leave as past_due | Subscription remains active but flagged |

**Dashboard:** https://dashboard.stripe.com/settings/billing/automatic

---

## Testing Your Integration

### Stripe Test Mode

Stripe provides a complete sandbox environment. All test mode resources use `sk_test_` and `pk_test_` API keys.

### Test Card Numbers

| Card Number | Behaviour |
|-------------|----------|
| `4242 4242 4242 4242` | Always succeeds |
| `4000 0000 0000 0341` | Always fails (card_declined) |
| `4000 0025 0000 3155` | Requires 3D Secure authentication |
| `4000 0000 0000 9995` | Insufficient funds |

### Testing Webhooks Locally

Use the **Stripe CLI** to forward webhooks to your local server:

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Forward webhooks to your local server
stripe listen --forward-to localhost:8000/stripe/webhook

# In another terminal, trigger a test event
stripe trigger invoice.created
stripe trigger invoice.paid
stripe trigger customer.subscription.created
```

### Test Meter Events

```bash
# Send a test meter event
curl https://api.stripe.com/v1/billing/meter_events \
  -u "sk_test_YOUR_KEY:" \
  -d "event_name"="voice_call_minutes" \
  -d "payload[value]"=50 \
  -d "payload[stripe_customer_id]"="cus_TEST_CUSTOMER"
```

### Verify Invoice Preview

```bash
# Preview what the next invoice will look like
curl https://api.stripe.com/v1/invoices/create_preview \
  -u "sk_test_YOUR_KEY:" \
  -d "customer"="cus_TEST_CUSTOMER" \
  -d "subscription"="sub_TEST_SUB"
```

---

## Implementation Checklist

### Phase 1: Foundation

- [ ] Create Stripe account and get API keys
- [ ] Set up branding (logo, colours) in Dashboard
- [ ] Create Products for each subscription tier
- [ ] Create Prices for each tier (monthly recurring)
- [ ] Create a Meter for voice call minutes
- [ ] Set up webhook endpoint on your server
- [ ] Register webhook endpoint in Stripe Dashboard

### Phase 2: Subscription Flow

- [ ] Implement customer creation flow
- [ ] Implement subscription creation with `payment_behavior=default_incomplete`
- [ ] Handle 3D Secure authentication if needed
- [ ] Listen for `customer.subscription.created` webhook
- [ ] Listen for `customer.subscription.updated` webhook
- [ ] Listen for `customer.subscription.deleted` webhook

### Phase 3: Usage Tracking

- [ ] Send meter events after each voice call
- [ ] Implement idempotency keys for meter events
- [ ] Set up usage alerts for 80% and 100% thresholds
- [ ] Build a usage dashboard for clients

### Phase 4: Invoice Customisation

- [ ] Listen for `invoice.created` webhook
- [ ] Add usage summary line items during draft window
- [ ] Set up invoice templates with company branding
- [ ] Configure custom fields (Client ID, Tier name, etc.)
- [ ] Set default memo and footer text
- [ ] Enable invoice emails in Dashboard

### Phase 5: Payment Handling

- [ ] Listen for `invoice.paid` webhook → confirm access
- [ ] Listen for `invoice.payment_failed` webhook → notify client
- [ ] Enable Smart Retries in Dashboard
- [ ] Configure revenue recovery settings
- [ ] Implement payment method update flow

### Phase 6: Client Portal

- [ ] Enable customer portal in Dashboard
- [ ] Customise portal branding
- [ ] Add portal links to your app's dashboard
- [ ] Test upgrade/downgrade flow through portal

### Phase 7: Testing & Go Live

- [ ] Test with Stripe test card numbers
- [ ] Test webhook handling with Stripe CLI
- [ ] Test meter events and invoice previews
- [ ] Test payment failures and retries
- [ ] Switch to live API keys
- [ ] Verify first real invoice looks correct

---

## Environment Variables

```bash
# Stripe API Keys
STRIPE_SECRET_KEY="sk_test_..."      # Use sk_live_... in production
STRIPE_PUBLISHABLE_KEY="pk_test_..." # Use pk_live_... in production
STRIPE_WEBHOOK_SECRET="whsec_..."    # Webhook signing secret

# Product/Price IDs (set after creating in Stripe)
STRIPE_TIER1_PRICE_ID="price_..."
STRIPE_TIER2_PRICE_ID="price_..."
STRIPE_TIER3_PRICE_ID="price_..."

# Meter ID
STRIPE_VOICE_METER_ID="mtr_..."
```

---

## Additional Resources

### Official Stripe Documentation

| Topic | URL |
|-------|-----|
| Subscriptions Overview | https://docs.stripe.com/subscriptions |
| How Subscriptions Work | https://docs.stripe.com/billing/subscriptions/overview |
| Subscription Invoices | https://docs.stripe.com/billing/invoices/subscription |
| Usage-Based Billing | https://docs.stripe.com/billing/subscriptions/usage-based |
| Record Usage (API) | https://docs.stripe.com/billing/subscriptions/usage-based/recording-usage-api |
| Configure Meters | https://docs.stripe.com/billing/subscriptions/usage-based/meters/configure |
| Billing Credits | https://docs.stripe.com/billing/subscriptions/usage-based/billing-credits |
| Monitor Usage | https://docs.stripe.com/billing/subscriptions/usage-based/monitor |
| Customise Invoices | https://docs.stripe.com/invoicing/customize |
| Invoice Templates | https://docs.stripe.com/invoicing/invoice-rendering-template |
| Hosted Invoice Page | https://docs.stripe.com/invoicing/hosted-invoice-page |
| Send Customer Emails | https://docs.stripe.com/invoicing/send-email |
| Webhooks for Subscriptions | https://docs.stripe.com/billing/subscriptions/webhooks |
| Pricing Models | https://docs.stripe.com/products-prices/pricing-models |
| Customer Portal | https://docs.stripe.com/customer-management |
| Design an Integration | https://docs.stripe.com/billing/subscriptions/design-an-integration |
| Smart Retries | https://docs.stripe.com/billing/revenue-recovery/smart-retries |
| Stripe API Reference | https://docs.stripe.com/api |

### Stripe Dashboard Quick Links

| What | URL |
|------|-----|
| Products | https://dashboard.stripe.com/products |
| Subscriptions | https://dashboard.stripe.com/subscriptions |
| Invoices | https://dashboard.stripe.com/invoices |
| Customers | https://dashboard.stripe.com/customers |
| Meters | https://dashboard.stripe.com/meters |
| Webhooks | https://dashboard.stripe.com/webhooks |
| Branding | https://dashboard.stripe.com/account/branding |
| Invoice Settings | https://dashboard.stripe.com/settings/billing/invoice |
| Email Settings | https://dashboard.stripe.com/settings/billing/automatic |
| Customer Portal | https://dashboard.stripe.com/settings/billing/portal |

### Sample Code Repositories

| Repository | Description |
|-----------|-------------|
| https://github.com/stripe-samples/subscription-use-cases | Build a custom subscription page |
| https://github.com/stripe-samples/checkout-single-subscription | Prebuilt subscription page with Checkout |

---

**Document prepared for:** Aisyst Team
**Purpose:** Implement automatic subscription billing with branded invoice generation using Stripe
