# Trading System — What It Does and How to Use It

This is a plain-language walkthrough of the system: what each screen is for, and why it matters for running the business day to day. No technical background needed — this is written for you, not for a developer.

Everything below works on a phone as well as a desktop. If you're on the shop floor checking stock or confirming a sale with a walk-in customer, you don't need to be sitting at a desk.

---

## Signing in

Go to the site, enter your username and password, and you're in. In the top corner you'll see a circle with your initials — click it to see who's signed in or to **sign out**. You'll be asked to confirm before it actually signs you out, so there's no risk of doing it by accident.

---

## Dashboard — where the business stands

This is the first thing you see after signing in. It answers the question "how are we doing?" without you having to go dig through separate screens:

- **Balance overview** — how much cash and bank/JazzCash/Easypaisa money you actually have, how much customers owe you, and how much you owe vendors — all in one place, always up to date.
- **What's selling** — a chart of which models are moving fastest, so you can see demand trends at a glance instead of guessing.
- **What to reorder** — a ranked list of models worth ordering more of from China next, based on how fast they've actually been selling.
- **Profit report** — for each item, what you sold it for versus what it actually cost you (including the freight/cargo cost that got added on top of the China price) — so you know your real margin, not just the sale price.

---

## Purchase Orders — buying from China

This is where you record an order placed with a China vendor: which vendor, which items, how many, and the price in RMB (Chinese currency). The system automatically shows you the cost in PKR (Pakistani Rupees) using that day's exchange rate.

Important: once a purchase order is created, its RMB→PKR conversion is locked in permanently. If the exchange rate changes next week, your old orders don't silently change cost behind your back — only new orders use the new rate. This is what makes your cost records trustworthy months later.

---

## Cargo Shipments — the cost of getting it here

When goods ship from China — by sea or by air — this is where you record the shipment: which purchase orders it's carrying, how it's charged (by weight, by CBM/volume, or by piece), and the total freight cost.

The system automatically splits that one freight bill across every item in the shipment, proportional to how much space/weight each one took up. The result: every item ends up with a true "landed cost" — the China price *plus* its fair share of the shipping cost — instead of you having to work that out by hand.

---

## Inventory — what you actually have in stock

Once a shipment arrives and you mark it received, the goods show up here as stock, grouped by model. If you've reordered the same item before at a different price, you'll see it as a separate batch ("lot") — so you can always see exactly how many units you have, and at what cost, down to the specific shipment they came in on. Old stock and new stock never get blended into one confusing average.

---

## Sales Orders — selling to your customers

This is where you record a sale to a wholesale customer in Pakistan: which customer, which items, how many, and at what price. Stock is deducted automatically from your oldest batch first (so older stock always sells before newer stock — no item sits around indefinitely), and the system shows you the margin on the sale against what that batch actually cost you.

Every sale also updates that customer's running balance automatically — see the **Parties** section below for where that balance actually lives.

---

## Payments — every rupee, tracked

Whenever money moves — a customer pays you, you pay a vendor, you pay for cargo — it gets recorded here against a specific account: which bank, JazzCash, Easypaisa, or cash drawer it went through. This is what keeps your account balances (shown on the Dashboard) accurate, and gives you a paper trail for every transaction instead of relying on memory.

---

## Expenses — the cost of running the business

Day-to-day spending (food, small repairs) and fixed monthly costs (rent, bills, salaries) both get recorded here, categorized, and tied to whichever account paid for them. Recurring monthly expenses can be set up once and just get confirmed each month rather than re-entered from scratch.

---

## Parties — every vendor, customer, and contact in one place

"Party" is the system's word for anyone you do business with — a China vendor, a cargo/freight agent, a wholesale customer in Pakistan, or a local vendor you sometimes buy from or sell to. Instead of separate contact lists for each type, everyone lives in one list, tagged with whichever role(s) apply to them.

Click into any party and you get their **full statement**: complete transaction history and current balance — exactly how much they owe you, or you owe them, at a glance. This is the single source of truth for "how much does X owe us" — no more piecing it together from memory or old messages.

A local vendor who sometimes sells to you *and* sometimes buys from you is just one entry with one combined balance — not two separate, disconnected records.

---

## Catalog — your product list

This is where your actual product lineup lives, organized in a hierarchy:

- **Categories** — the type of accessory (Cover, Screen Protector, Charger, etc.) — independent of which phone it's for.
- **Brands** — the phone brand (iPhone, Samsung, etc.).
- **Models** — the specific device within a brand (iPhone 11, iPhone 11 Pro Max, iPhone 12, Samsung S23 Ultra, etc.) — each one belongs to a Brand, so "iPhone 11 Pro Max" is filed under "iPhone."
- **Items** — the actual thing you buy and sell: a Category + Model + variant (e.g. color) combination — for example "Silicone Cover — iPhone 13 — Black." This is what every purchase order line and sale actually points to.

So a full item is built from all four pieces: **Category** (what kind of accessory) + **Brand → Model** (which phone) + **variant** (color/style). Add new brands, models, and categories yourself as your product range grows — nothing is pre-set.

---

## Settings — the building blocks everything else uses

A few small lists that other screens depend on, all editable here without needing anyone to change the software itself:

- **Exchange Rates** — today's RMB→PKR rate, used whenever you create a new purchase order.
- **Payment Methods** — your bank accounts, JazzCash, Easypaisa, and cash drawer.
- **Cargo Modes** — Sea, Air (add more if you ever use another shipping method).
- **Cost Bases** — Weight, CBM, Piece — the ways a cargo shipment can be charged.
- **Expense Categories** — the categories your expenses get sorted into.

Nothing in this app is hard-coded — if your business needs a new payment method, a new expense category, or a new cargo mode, you add it here yourself, and it immediately becomes available everywhere else in the system.

---

## A note on how the numbers stay trustworthy

Two things worth knowing, because they're what make every report in this system actually reliable rather than a rough estimate:

- **Nothing gets permanently deleted.** If you remove a vendor, customer, or lookup entry, it's hidden from new use but never erased — so an old purchase order that references a vendor from two years ago never breaks.
- **Every transaction that touches money — a sale, a payment, an expense — feeds the same underlying ledger.** That's why the Dashboard's balance overview and every party's statement always agree with each other: they're reading from the same source, not separate guesses.
