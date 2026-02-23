# L'addition POS API — POST Order Endpoint Analysis & Integration Guide

## Integration with ElevenLabs Conversational AI & LiveKit Voice Agent

**API Base URL:** `https://api-mediation.laddition.com`
**Endpoint:** `POST /med/order`

---

## Table of Contents

1. [Endpoint Overview](#endpoint-overview)
2. [Authentication](#authentication)
3. [Request Body Breakdown — All JSON Objects](#request-body-breakdown)
4. [What Information Does This Endpoint Give Us?](#what-information-does-this-endpoint-give-us)
5. [Integration with ElevenLabs (Tools)](#integration-with-elevenlabs)
6. [Integration with LiveKit (function_tool)](#integration-with-livekit)
7. [Data Mapping — Our Order → L'addition Format](#data-mapping)
8. [Implementation Architecture](#implementation-architecture)
9. [Key Considerations](#key-considerations)

---

## Endpoint Overview

```
POST https://api-mediation.laddition.com/med/order

Purpose: Send a complete order to the L'addition POS system
         so it appears on the restaurant's POS terminal/kitchen display.

What it does:
┌──────────────────┐         POST /med/order         ┌──────────────────┐
│                  │ ──────────────────────────────► │                  │
│  Our Voice Agent │    (order + contact + items)     │  L'addition POS  │
│  (ElevenLabs or  │                                  │  (French POS     │
│   LiveKit)       │ ◄────────────────────────────── │   Terminal)      │
│                  │    (confirmation / order ID)      │                  │
└──────────────────┘                                  └──────────────────┘
```

---

## Authentication

The endpoint requires **two headers** for authentication:

| Header | Value | Description |
|--------|-------|-------------|
| `Authorization` | `Bearer {{bearer_token}}` | Your API access token from L'addition sandbox |
| `customerid` | `{{customer_id}}` | Your L'addition customer/merchant ID |
| `Content-Type` | `application/json` | Standard JSON content type |

```bash
curl --location --request POST 'https://api-mediation.laddition.com/med/order' \
  --header 'Authorization: Bearer YOUR_TOKEN' \
  --header 'customerid: YOUR_CUSTOMER_ID' \
  --header 'Content-Type: application/json' \
  --data-raw '{ ... }'
```

**Important:** Store these credentials as environment variables — never hardcode them.

```bash
# .env file
LADDITION_BEARER_TOKEN="your_bearer_token_here"
LADDITION_CUSTOMER_ID="your_customer_id_here"
```

---

## Request Body Breakdown

The POST body contains **5 top-level JSON objects**. Let's break down each one:

### Overview of All Objects

```
{
    "order"        : { ... },   ← Order metadata (serial, status, type, timing)
    "contact"      : { ... },   ← Customer contact info (name, phone, email)
    "address"      : { ... },   ← Delivery address (only for delivery orders)
    "orderLines"   : [ ... ],   ← The actual items ordered (products, menus, extras)
    "paymentLines" : [ ... ]    ← Payment information (amount, payment type)
}
```

---

### 1. `order` Object — Order Metadata

This describes the order itself — its ID, status, type, and timing.

| Field | Type | Required? | Description | Example |
|-------|------|-----------|-------------|---------|
| `serial` | string | Yes | Unique order number/ID from your system | `"2345"` |
| `serialName` | string | Yes | Human-readable order name | `"Order n°22"` |
| `status` | string | Yes | Order status | `"validated"` |
| `type` | integer | Yes | Order type (see table below) | `3` |
| `globalDiscount` | float | No | Global discount as a decimal (0.5 = 50% off) | `0.5` |
| `takeawayName` | string | No | Name for takeaway/delivery | `"L'Addition"` |
| `takeawayType` | integer | No | Takeaway type (see table below) | `1` |
| `comment` | string | No | General order comment/notes | `"Seafood allergy"` |
| `hoursOrder` | string (ISO 8601) | Yes | When the order was placed | `"2019-06-19T17:06:53+02:00"` |
| `preparationTime` | integer (Unix) | No | When to start preparing (Unix timestamp) | `1560933047` |
| `preparationTimeAsap` | boolean | No | Prepare as soon as possible? | `false` |
| `preparationDuration` | integer | No | Estimated prep time in seconds | `1800` (30 mins) |

**Order Types (`type` field):**

| Value | Meaning | Our Use Case |
|-------|---------|-------------|
| `1` | Dine-in | If customer is at the restaurant |
| `2` | Takeaway/Pickup | Customer picks up the order |
| `3` | Delivery | Order is delivered to customer |

**Takeaway Types (`takeawayType` field):**

| Value | Meaning |
|-------|---------|
| `1` | Standard takeaway |
| `2` | Drive-through |
| `3` | Other |

**Order Statuses (`status` field):**

| Value | Meaning |
|-------|---------|
| `"validated"` | Order confirmed and ready to process |
| `"pending"` | Order awaiting confirmation |
| `"cancelled"` | Order cancelled |

---

### 2. `contact` Object — Customer Information

This is the customer who placed the order.

| Field | Type | Required? | Description | Example |
|-------|------|-----------|-------------|---------|
| `firstname` | string | Yes | Customer's first name | `"Jane"` |
| `lastname` | string | Yes | Customer's last name | `"Doe"` |
| `email` | string | No | Customer's email | `"jane.doe@laddition.com"` |
| `phoneIndic` | string | Yes | Phone country code (without +) | `"33"` (France) |
| `phoneNumber` | string | Yes | Phone number (without country code) | `"6********"` |
| `birthday` | string | No | Date of birth | `"01/01/2000"` |
| `note` | string | No | Notes about the customer | `""` |

**For our voice agent:** We are already collecting `customer_name` and `customer_phone` in the `submit_order` function. We'll need to split the name into first/last and parse the phone number.

---

### 3. `address` Object — Delivery Address

Only needed for delivery orders (`type: 3`). Can be omitted or empty for pickup/dine-in.

| Field | Type | Required? | Description | Example |
|-------|------|-----------|-------------|---------|
| `mailbox_name` | string | No | Name on the mailbox | `"Jane Doe"` |
| `address` | string | Yes | Street address | `"1 place Lainée"` |
| `addressMore` | string | No | Additional address info | `"Bât C - Appt 262"` |
| `street` | string | No | Full street string | `"Jane Doe - 1 place Lainée..."` |
| `zipcode` | string | Yes | Postal code | `"33800"` |
| `city` | string | Yes | City | `"Bordeaux"` |
| `country` | string | Yes | Country | `"France"` |
| `number` | string | No | Contact phone for delivery | `"+33 6********"` |
| `info` | string | No | Delivery instructions | `"No intercom"` |
| `latitude` | float | No | GPS latitude | `44.848713` |
| `longitude` | float | No | GPS longitude | `-0.571235` |

---

### 4. `orderLines` Array — The Actual Items Ordered

This is the most important part — the list of items the customer ordered. Each item is an object in the array.

#### Item Object Structure

| Field | Type | Required? | Description | Example |
|-------|------|-----------|-------------|---------|
| `idProduct` | string | Yes | Product ID from L'addition's catalogue | `"U52E3-278515"` |
| `name` | string | Yes | Product name | `"Tapas"` |
| `price` | float | Yes | Unit price in euros | `2` |
| `discount` | float | No | Discount on this item (0 = no discount) | `0` |
| `isOffered` | boolean | No | Is this item complimentary/free? | `false` |
| `type` | string | Yes | Item type (see below) | `"product"` |
| `retailQuantity` | integer | No | Quantity in grams (for items sold by weight) | `500` |
| `subItems` | array | No | Sub-items (extras, menu choices) | `[...]` |

**Item Types (`type` field):**

| Value | Meaning | Example |
|-------|---------|---------|
| `"product"` | A standalone product | Tapas, Beef, a drink |
| `"menu"` | A combo/set menu | "Menu Entrée + Plat" |
| `"extra"` | An add-on/modifier | "Avec guacamole", "supp sauce" |

#### How Sub-Items Work

Sub-items represent **extras** (add-ons) or **menu choices** (items within a combo):

```
orderLines:
├── Product: "Tapas" ($2)
│   └── subItem (extra): "Avec guacamole" (+$1)
│
├── Menu: "Menu Entrée + Plat" ($17)
│   ├── subItem (product): "Salmon Salad" ($0) ← included in menu
│   │   └── idMenuLevel: "UB9F4-01"           ← which menu slot (starter)
│   └── subItem (product): "Salmon burger" (+$2) ← upgrade cost
│       └── idMenuLevel: "UB9F4-02"              ← which menu slot (main)
│           └── subItem (extra): "supp sauce" (+$1)
│
└── Product: "Beef per kilogram" ($2.50)
    └── retailQuantity: 500 (grams)
```

**Key insight:** The `idMenuLevel` field tells L'addition which "slot" in a combo menu the item fills (e.g., starter slot, main slot, dessert slot).

---

### 5. `paymentLines` Array — Payment Information

How the order is being paid.

| Field | Type | Required? | Description | Example |
|-------|------|-----------|-------------|---------|
| `amount` | float | Yes | Payment amount | `25.50` |
| `overpayment` | float | No | Any overpayment/tip | `0` |
| `idPaymentType` | string | Yes | Payment method ID from L'addition | `"def0-2"` |

**Payment Type IDs** will be specific to our L'addition account. We'll need to check which IDs map to which payment methods (card, cash, online, etc.) in our L'addition dashboard.

---

## What Information Does This Endpoint Gives Us?

### What We SEND to L'addition

| Data | Where It Comes From |
|------|-------------------|
| Order ID & name | Generated by our system |
| Order type (pickup/delivery/dine-in) | Collected from customer during call |
| Customer name & phone | Collected during call (we are already doing this) |
| Delivery address | Collected during call (if delivery) |
| Ordered items with IDs | Matched from L'addition's product catalogue |
| Item extras/modifiers | Collected during call (side choices, sauces, etc.) |
| Special instructions/allergies | Collected during call (we already do this via `comment`) |
| Payment info | Handled separately or passed as online payment |
| Preparation timing | Set by us (ASAP or scheduled) |

### What We GET BACK from L'addition

The response will confirm the order was received by the POS. The order then:
- Appears on the restaurant's **POS terminal**
- Shows up on the **kitchen display system (KDS)**
- Can be tracked by restaurant staff

### What We NEED Before We Can Use This Endpoint

| Requirement | Status | Notes |
|-------------|--------|-------|
| Bearer token | We have sandbox access | We will store that in env variable |
| Customer ID | We have sandbox access | We will store that in env variable |
| **Product catalogue/IDs** | **Need to get from L'addition** | We need `idProduct` values for every menu item |
| Payment type IDs | **Need to get from L'addition** | We need `idPaymentType` values |
| Menu level IDs | **Need to get from L'addition** | For combo menus, we need `idMenuLevel` values |

**Critical:** The `idProduct` field requires L'addition's internal product IDs — not our Supabase `menu_item_id`. We'll need to either:
1. Get a product catalogue endpoint from L'addition (e.g., `GET /med/products`)
2. Manually map our menu items to L'addition product IDs
3. Store L'addition product IDs alongside our existing menu data in Supabase

---

## Integration with ElevenLabs

### We need Eleven Labs Custom tools for that.

In our current ElevenLabs setup (as seen in `Eleven_Labs_Actual_Payload.JSON` — agent: "Marcellina Pizzeria"), the agent uses RAG to look up menu items. To send orders to L'addition, we need to add a **Custom Tool** that our ElevenLabs agent can call as we did previously for Lightspeed.

### How ElevenLabs Custom Tools will work with L'addition

```
FLOW:

Customer says: "I'd like a Salmon Salad and a Tapas with guacamole"
        │
        ▼
┌─────────────────────┐
│  ElevenLabs Agent    │
│  (Custom Tool)        │
│                      │
│  Agent decides to    │
│  call the tool:      │
│  "submit_order"      │
│  with parameters:    │
│  {items, name, phone}│
└──────────┬──────────┘
           │ HTTP POST (webhook)
           ▼
┌─────────────────────┐
│  Our Backend        │
│  (FastAPI)           │
│                      │
│  1. Receives tool    │
│     call from 11Labs │
│  2. Maps items to    │
│     L'addition IDs   │
│  3. Builds the POST  │
│     /med/order body  │
│  4. Sends to         │
│     L'addition API   │
│  5. Returns result   │
│     to ElevenLabs    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  L'addition POS      │
│  Order appears on    │
│  kitchen display     │
└─────────────────────┘
```

### Step 1: Define the Custom Tool in ElevenLabs

In our ElevenLabs agent configuration (Dashboard → Agent → Tools), add a new **Webhook Tool**:

**Tool Name:** `submit_order_to_pos`

**Tool Description:**
```
Submit the customer's confirmed order to the L'Additionrestaurant's POS system.
Call this ONLY after the customer has confirmed their complete order.
You must have collected: customer first name, customer phone number, and all order items.
```

**Webhook URL:** `https://our-backend.com/elevenlabs/submit-order`
(This should be our webhook URL or custom backend endpoint)

**Parameters Schema:**

```json
{
  "type": "object",
  "properties": {
    "customer_firstname": {
      "type": "string",
      "description": "Customer's first name"
    },
    "customer_lastname": {
      "type": "string",
      "description": "Customer's last name (ask if not provided, default to empty string)"
    },
    "customer_phone": {
      "type": "string",
      "description": "Customer's phone number including country code e.g. +33612345678"
    },
    "order_type": {
      "type": "string",
      "enum": ["pickup", "delivery", "dine_in"],
      "description": "Whether the order is for pickup, delivery, or dine-in"
    },
    "items": {
      "type": "array",
      "description": "List of items the customer ordered",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "Name of the menu item"
          },
          "quantity": {
            "type": "integer",
            "description": "How many of this item"
          },
          "extras": {
            "type": "array",
            "description": "Any extras or modifications",
            "items": {
              "type": "string"
            }
          },
          "special_instructions": {
            "type": "string",
            "description": "Special requests for this item"
          }
        },
        "required": ["name", "quantity"]
      }
    },
    "comment": {
      "type": "string",
      "description": "General order comments like allergies"
    }
  },
  "required": ["customer_firstname", "customer_phone", "order_type", "items"]
}
```

### Step 2: Backend Handler (Receives Tool Call → Sends to L'addition)

Your backend (n8n workflow or custom server) receives the tool call from ElevenLabs and transforms it into the L'addition API format.

**Python (FastAPI) Example:**

```python
import os
import httpx
from datetime import datetime, timezone
from fastapi import FastAPI, Request

app = FastAPI()

LADDITION_API_URL = "https://api-mediation.laddition.com/med/order"
LADDITION_BEARER_TOKEN = os.getenv("LADDITION_BEARER_TOKEN")
LADDITION_CUSTOMER_ID = os.getenv("LADDITION_CUSTOMER_ID")

# Mapping: your menu item names → L'addition product IDs
# You MUST populate this from L'addition's product catalogue
PRODUCT_ID_MAP = {
    "tapas": "U52E3-278515",
    "salmon salad": "U52E3-136534",
    "salmon burger": "U52E3-146364",
    "menu entree + plat": "def0-211",
    # ... add all your menu items here
}

EXTRA_ID_MAP = {
    "guacamole": "UB9F4-946",
    "extra sauce": "UB9F4-946",
    # ... add all extras here
}

ORDER_TYPE_MAP = {
    "dine_in": 1,
    "pickup": 2,
    "delivery": 3,
}

PAYMENT_TYPE_ID = "def0-2"  # Get the correct ID from your L'addition account


@app.post("/elevenlabs/submit-order")
async def handle_elevenlabs_tool_call(request: Request):
    """Receive tool call from ElevenLabs, send order to L'addition POS."""
    
    body = await request.json()
    
    # Extract parameters from ElevenLabs tool call
    params = body  # ElevenLabs sends the tool parameters directly
    
    # 1. Build orderLines from items
    order_lines = []
    total_amount = 0
    
    for item in params["items"]:
        item_name_lower = item["name"].lower()
        product_id = PRODUCT_ID_MAP.get(item_name_lower, "UNKNOWN")
        
        # Build sub-items for extras
        sub_items = []
        for extra in item.get("extras", []):
            extra_lower = extra.lower()
            extra_id = EXTRA_ID_MAP.get(extra_lower, "UNKNOWN")
            sub_items.append({
                "idProduct": extra_id,
                "name": extra,
                "price": 0,  # Look up actual price from your catalogue
                "discount": 0,
                "isOffered": False,
                "type": "extra",
            })
        
        order_line = {
            "idProduct": product_id,
            "name": item["name"],
            "price": 0,  # Look up actual price from your catalogue
            "discount": 0,
            "isOffered": False,
            "type": "product",
            "subItems": sub_items,
        }
        order_lines.append(order_line)
    
    # 2. Parse phone number
    phone = params["customer_phone"]
    phone_indic = "33"  # Default to France
    phone_number = phone
    if phone.startswith("+"):
        # e.g., "+33612345678" → indic="33", number="612345678"
        phone_indic = phone[1:3]
        phone_number = phone[3:]
    
    # 3. Build the L'addition payload
    now = datetime.now(timezone.utc).isoformat()
    serial = f"AI-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    laddition_payload = {
        "order": {
            "serial": serial,
            "serialName": f"Voice Order {serial}",
            "status": "validated",
            "type": ORDER_TYPE_MAP.get(params["order_type"], 2),
            "globalDiscount": 0,
            "comment": params.get("comment", ""),
            "hoursOrder": now,
            "preparationTimeAsap": True,
            "preparationDuration": 1800,  # 30 mins default
        },
        "contact": {
            "firstname": params["customer_firstname"],
            "lastname": params.get("customer_lastname", ""),
            "email": "",
            "phoneIndic": phone_indic,
            "phoneNumber": phone_number,
            "note": "Order placed via AI Voice Agent",
        },
        "address": {},  # Empty for pickup; populate for delivery
        "orderLines": order_lines,
        "paymentLines": [
            {
                "amount": total_amount,
                "overpayment": 0,
                "idPaymentType": PAYMENT_TYPE_ID,
            }
        ],
    }
    
    # 4. Send to L'addition
    async with httpx.AsyncClient() as client:
        response = await client.post(
            LADDITION_API_URL,
            headers={
                "Authorization": f"Bearer {LADDITION_BEARER_TOKEN}",
                "customerid": LADDITION_CUSTOMER_ID,
                "Content-Type": "application/json",
            },
            json=laddition_payload,
        )
    
    if response.status_code == 200:
        return {
            "status": "success",
            "message": f"Order {serial} sent to restaurant POS successfully.",
            "order_id": serial,
        }
    else:
        return {
            "status": "error",
            "message": f"Failed to send order to POS. Error: {response.text}",
        }
```

### Step 3: n8n Workflow Alternative

If you're using n8n (as seen in your ElevenLabs payload — `aisystvoice.app.n8n.cloud`):

```
n8n Workflow:

[Webhook Trigger] → [Map Items to L'addition IDs] → [Build JSON Body] → [HTTP Request to L'addition] → [Return Result]
     │                                                                           │
     │ Receives tool call                                              POST /med/order
     │ from ElevenLabs                                                 with full payload
```

1. **Webhook node:** Receives the tool call from ElevenLabs
2. **Code node:** Maps item names to L'addition `idProduct` values
3. **Code node:** Builds the full L'addition JSON payload
4. **HTTP Request node:** POST to `https://api-mediation.laddition.com/med/order`
5. **Respond to Webhook node:** Returns success/failure to ElevenLabs

---

## Integration with LiveKit

For your LiveKit setup in `Livekit_Voice_Agent.py`, the integration is more direct — you add a `@function_tool()` to the `RestaurantAgent` class.

### Modify `submit_order` to Send to L'addition

Your current `submit_order` function (line 808-873) saves to Supabase. We need to **also** send the order to L'addition POS.

### Step 1: Add L'addition Config

At the top of `Livekit_Voice_Agent.py`, add:

```python
import httpx  # Add to imports

# L'addition POS Configuration
LADDITION_API_URL = "https://api-mediation.laddition.com/med/order"
LADDITION_BEARER_TOKEN = os.getenv("LADDITION_BEARER_TOKEN")
LADDITION_CUSTOMER_ID = os.getenv("LADDITION_CUSTOMER_ID")
```

### Step 2: Add a Helper Function to Build L'addition Payload

```python
def build_laddition_payload(
    order_id: str,
    customer_name: str,
    customer_phone: str,
    order_items: list,
    order_type: str = "pickup",
    comment: str = "",
) -> dict:
    """Build the L'addition POS API payload from our order data."""
    from datetime import datetime, timezone
    
    # Split customer name
    name_parts = customer_name.strip().split(" ", 1)
    firstname = name_parts[0]
    lastname = name_parts[1] if len(name_parts) > 1 else ""
    
    # Parse phone number
    phone = customer_phone or ""
    phone_indic = "33"  # Default France
    phone_number = phone
    if phone.startswith("+"):
        phone_indic = phone[1:3]
        phone_number = phone[3:]
    
    # Map order type
    type_map = {"dine_in": 1, "pickup": 2, "delivery": 3}
    
    # Build order lines
    # NOTE: You need to map your Supabase menu_item_id → L'addition idProduct
    # Store this mapping in Supabase or a config file
    order_lines = []
    total = 0
    
    for item in order_items:
        # Get L'addition product ID from your mapping
        laddition_id = get_laddition_product_id(item["item_id"])  # You implement this
        
        sub_items = []
        # Map extras (side_choice, drink_choice, sauce_choice) to L'addition sub-items
        if item.get("side_choice"):
            sub_items.append({
                "idProduct": get_laddition_product_id(item["side_choice"]),
                "name": item["side_choice"],
                "price": 0,
                "discount": 0,
                "isOffered": False,
                "type": "extra",
            })
        if item.get("drink_choice"):
            sub_items.append({
                "idProduct": get_laddition_product_id(item["drink_choice"]),
                "name": item["drink_choice"],
                "price": 0,
                "discount": 0,
                "isOffered": False,
                "type": "extra",
            })
        if item.get("sauce_choice"):
            sub_items.append({
                "idProduct": get_laddition_product_id(item["sauce_choice"]),
                "name": item["sauce_choice"],
                "price": 0,
                "discount": 0,
                "isOffered": False,
                "type": "extra",
            })
        
        order_lines.append({
            "idProduct": laddition_id,
            "name": item["name"],
            "price": item["price"],
            "discount": 0,
            "isOffered": False,
            "type": "product",
            "subItems": sub_items,
        })
        total += item["price"] * item["quantity"]
    
    now = datetime.now(timezone.utc).isoformat()
    
    return {
        "order": {
            "serial": order_id,
            "serialName": f"Voice Order {order_id}",
            "status": "validated",
            "type": type_map.get(order_type, 2),
            "globalDiscount": 0,
            "comment": comment,
            "hoursOrder": now,
            "preparationTimeAsap": True,
            "preparationDuration": 1200,  # 20 mins (matches your current estimate)
        },
        "contact": {
            "firstname": firstname,
            "lastname": lastname,
            "email": "",
            "phoneIndic": phone_indic,
            "phoneNumber": phone_number,
            "note": "Order placed via AI Voice Agent",
        },
        "address": {},
        "orderLines": order_lines,
        "paymentLines": [
            {
                "amount": total,
                "overpayment": 0,
                "idPaymentType": "def0-2",  # Replace with your actual payment type ID
            }
        ],
    }


async def send_to_laddition(payload: dict) -> dict:
    """Send order to L'addition POS API."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            LADDITION_API_URL,
            headers={
                "Authorization": f"Bearer {LADDITION_BEARER_TOKEN}",
                "customerid": LADDITION_CUSTOMER_ID,
                "Content-Type": "application/json",
            },
            json=payload,
        )
    
    if response.status_code == 200:
        return {"success": True, "data": response.json()}
    else:
        return {"success": False, "error": response.text, "status": response.status_code}
```

### Step 3: Update `submit_order` in RestaurantAgent

Modify the existing `submit_order` function to also send to L'addition after saving to Supabase:

```python
@function_tool()
async def submit_order(self, customer_name: str, customer_phone: str) -> str:
    """Submit the order for pickup."""
    import uuid

    if not self.current_order:
        return "Your order is empty. Please add items first."

    total = sum(i["price"] * i["quantity"] for i in self.current_order)
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

    # ... existing Supabase code stays the same ...

    # ← ADD: Send to L'addition POS
    try:
        laddition_payload = build_laddition_payload(
            order_id=order_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            order_items=self.current_order,
            order_type="pickup",
            comment="",  # Could include special_instructions
        )
        pos_result = await send_to_laddition(laddition_payload)
        
        if pos_result["success"]:
            logger.info(f"✅ Order {order_id} sent to L'addition POS")
        else:
            logger.error(f"❌ L'addition POS error: {pos_result['error']}")
            # Don't fail the order — it's already in Supabase
            # The restaurant can still see it there
    except Exception as e:
        logger.error(f"❌ Failed to send to L'addition: {e}")

    # Clear order
    self.current_order = []

    return (
        f"Perfect {customer_name}, your order is in! "
        f"It'll be ready for pickup in about 20 minutes. "
        f"Thanks for calling, goodbye!"
    )
```

---

## Data Mapping

### The Critical Piece: Product ID Mapping

The biggest challenge is mapping **your menu items** to **L'addition's product IDs**.

```
YOUR SUPABASE                          L'ADDITION POS
┌─────────────────────┐                ┌─────────────────────┐
│ menu_item_id: 42    │                │ idProduct:           │
│ item_name: "Tapas"  │  ──mapping──►  │ "U52E3-278515"      │
│ price: 2.00         │                │ name: "Tapas"        │
│ category: "Starters"│                │ price: 2             │
└─────────────────────┘                └─────────────────────┘
```

### Recommended: Add L'addition IDs to Your Supabase Menu Table

Add a column `laddition_product_id` to your `menu_items` table in Supabase:

```sql
ALTER TABLE menu_items
ADD COLUMN laddition_product_id TEXT;

-- Then populate it:
UPDATE menu_items SET laddition_product_id = 'U52E3-278515' WHERE item_name = 'Tapas';
UPDATE menu_items SET laddition_product_id = 'U52E3-136534' WHERE item_name = 'Salmon Salad';
-- ... etc for all items
```

Then your `get_laddition_product_id` function becomes:

```python
def get_laddition_product_id(item_id_or_name: str) -> str:
    """Look up L'addition product ID from Supabase."""
    result = supabase.table("menu_items") \
        .select("laddition_product_id") \
        .or_(f"menu_item_id.eq.{item_id_or_name},item_name.ilike.%{item_id_or_name}%") \
        .limit(1) \
        .execute()
    
    if result.data and result.data[0].get("laddition_product_id"):
        return result.data[0]["laddition_product_id"]
    
    return "UNKNOWN"
```

---

## Implementation Architecture

### Full Flow — ElevenLabs Path

```
Phone Call → ElevenLabs Agent → Tool Call "submit_order_to_pos"
                                        │
                                        ▼
                               n8n Webhook / Backend
                                        │
                            ┌───────────┼───────────┐
                            ▼                       ▼
                     Save to Supabase      POST /med/order
                     (your database)       (L'addition POS)
                            │                       │
                            ▼                       ▼
                     Your Dashboard         Kitchen Display
                     (tracking)             (restaurant sees order)
```

### Full Flow — LiveKit Path

```
Phone Call → LiveKit Agent → @function_tool submit_order()
                                        │
                            ┌───────────┼───────────┐
                            ▼                       ▼
                     Save to Supabase      POST /med/order
                     (existing code)       (new L'addition call)
                            │                       │
                            ▼                       ▼
                     Your Dashboard         Kitchen Display
                     (tracking)             (restaurant sees order)
```

---

## Key Considerations

### 1. Product ID Mapping is Critical

You **cannot** send orders to L'addition without their internal `idProduct` values. Ask L'addition if they have a `GET /med/products` or similar endpoint to fetch their product catalogue. If not, you'll need to manually map every menu item.

### 2. Menu Sync

If the restaurant updates their menu in L'addition, your mapping could break. Consider:
- Periodic sync of product IDs
- A fallback mechanism if an ID is not found
- Alerting when unmapped items are ordered

### 3. Payment Handling

The `paymentLines` object needs a valid `idPaymentType`. For phone orders:
- If the customer pays on pickup → you might use a "pay later" or "cash" payment type
- If you collect payment online → use the appropriate online payment type ID
- Ask L'addition what payment type IDs are available in your account

### 4. Error Handling

Don't let a L'addition API failure block the entire order. Save to Supabase first (as you already do), then attempt the POS submission. If it fails, log the error and retry later or alert staff.

### 5. Sandbox Testing

Since you have sandbox access:
1. Send a test order with the example payload from their docs
2. Verify it appears in the L'addition sandbox POS
3. Note the response format so you know what to expect
4. Test error cases (invalid product ID, missing fields, etc.)

### 6. Do You Need ElevenLabs Tools?

**Yes, if you're using ElevenLabs for this French restaurant.** The tool is how the AI agent triggers the order submission. Without a tool, the agent can only talk — it can't take action.

**For LiveKit**, you already have `@function_tool()` which serves the same purpose.

Both approaches need the same backend logic to transform your order data into L'addition's format and make the API call.

---

**Document prepared for:** Aisyst Team
**Purpose:** Integrate L'addition POS (French restaurant) with existing AI voice agent platforms
