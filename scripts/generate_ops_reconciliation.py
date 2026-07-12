#!/usr/bin/env python3
"""Generate the ops-reconciliation benchmark file.

Each question is a self-contained, multi-step back-office task (the kind of real,
economically valuable work an agent would do) that funnels to ONE deterministic,
exactly-checkable answer. To guarantee there is exactly one correct answer:

  * The reference solver below IS the ground truth, and it is the single source
    of the embedded answer (no hand-typed answers).
  * The data table shown to the model is RENDERED FROM THE SAME Python data the
    solver consumes, so the prompt and the solver can never diverge.
  * Every rule that could otherwise be read two ways is pinned down in the prompt:
    rounding is always round-half-up to 2 decimals, date ranges state inclusivity,
    ordering of operations is explicit, and ties have a stated tie-break.

Questions are ordered easiest -> hardest. Run:

    python3 scripts/generate_ops_reconciliation.py
    python3 main.py --questions questions/ops-reconciliation.json
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "questions" / "ops-reconciliation.json"

TWO = Decimal("0.01")


def D(x):
    return Decimal(str(x))


def hu(x):
    """Round-half-up to 2 decimals."""
    return D(x).quantize(TWO, rounding=ROUND_HALF_UP)


def money(x):
    return f"{hu(x):.2f}"


def render_table(headers, rows):
    cols = list(zip(*([headers] + rows))) if rows else [[h] for h in headers]
    widths = [max(len(str(c)) for c in col) for col in cols]
    def fmt(r):
        return " | ".join(str(c).ljust(w) for c, w in zip(r, widths)).rstrip()
    line = fmt(headers)
    sep = "-+-".join("-" * w for w in widths)
    return "\n".join([line, sep] + [fmt(r) for r in rows])


FORMAT_2DP = (
    "Answer as a plain number with exactly two decimal places, no currency symbol "
    "and no thousands separators (for example: 1234.50)."
)
FORMAT_INT = "Answer as a plain integer with no separators (for example: 42)."

QUESTIONS = []


def add(qid, title, prompt, answer, rules_exercised, worked, expect=None):
    if expect is not None:
        assert answer == expect, f"{qid}: solver={answer!r} expected={expect!r}"
    QUESTIONS.append({
        "id": qid,
        "title": title,
        "scrambled": "",
        "task": prompt,
        "answer": answer,
        "rules_exercised": rules_exercised,
        "worked_solution": worked,
    })


# ---------------------------------------------------------------------------
# Q1  expense-audit  (easiest)
# ---------------------------------------------------------------------------
def build_q1():
    FX = {"USD": "1.0", "EUR": "1.10", "GBP": "1.25", "JPY": "0.0068"}
    tx = [
        ("T1", "2026-03-02", "Lufthansa", "flight", "320.00", "EUR", "yes"),
        ("T2", "2026-03-02", "Hotel Berlin", "lodging", "180.00", "EUR", "yes"),
        ("T3", "2026-03-02", "Bar Mitte", "alcohol", "40.00", "EUR", "yes"),
        ("T4", "2026-03-02", "Cafe Berlin", "meal", "30.00", "EUR", "yes"),
        ("T5", "2026-03-02", "Restaurant Zur", "meal", "60.00", "EUR", "yes"),
        ("T6", "2026-03-03", "City Taxi", "ground", "22.00", "EUR", "no"),
        ("T7", "2026-03-03", "Conference Fee", "registration", "500.00", "USD", "no"),
        ("T8", "2026-02-27", "Pre-trip Dinner", "meal", "50.00", "USD", "yes"),
        ("T9", "2026-03-05", "Eurostar", "train", "90.00", "GBP", "yes"),
        ("T10", "2026-03-05", "Eurostar", "train", "90.00", "GBP", "yes"),
        ("T11", "2026-03-06", "Tokyo Hotel", "lodging", "20000", "JPY", "yes"),
        ("T12", "2026-03-06", "Izakaya", "meal", "5000", "JPY", "yes"),
        ("T13", "2026-03-06", "Sake Bar", "alcohol", "3000", "JPY", "yes"),
    ]
    # solver
    seen = set()
    rows = []
    for t in tx:
        key = (t[2], t[4], t[5], t[1])
        if key in seen:
            continue
        seen.add(key)
        rows.append(t)
    meals = {}
    total = D(0)
    for tid, dt, m, cat, amt, cur, rcpt in rows:
        if not ("2026-03-01" <= dt <= "2026-03-07"):
            continue
        if cat == "alcohol":
            continue
        usd = hu(D(amt) * D(FX[cur]))
        if usd > D("25.00") and rcpt == "no":
            continue
        if cat == "meal":
            meals[dt] = meals.get(dt, D(0)) + usd
        else:
            total += usd
    for dt, m in meals.items():
        total += min(m, D("75.00"))
    answer = money(total)

    prompt = (
        "You are an operations analyst processing an employee's expense report for "
        "reimbursement. Apply the policy to the ledger and compute the requested figure.\n\n"
        "POLICY\n"
        "- Reporting currency is USD. Convert each amount to USD by multiplying by the "
        "rate (USD 1.0, EUR 1.10, GBP 1.25, JPY 0.0068) and round-half-up to 2 decimals.\n"
        "- R1 window: only transactions dated 2026-03-01 through 2026-03-07 inclusive are "
        "eligible; exclude anything outside that range entirely.\n"
        "- R2 alcohol: 'alcohol' category is never reimbursable.\n"
        "- R3 meal cap: 'meal' transactions are reimbursable only up to a combined 75.00 USD "
        "per calendar day; any amount above 75.00 on a given day is not reimbursable.\n"
        "- R4 receipt: any single transaction whose converted USD amount exceeds 25.00 "
        "requires receipt=yes; if its receipt is no, exclude it.\n"
        "- R5 duplicates: transactions sharing the same merchant, original amount, original "
        "currency, and date are a double-entry; count such a group only once.\n\n"
        "LEDGER\n"
        + render_table(
            ["id", "date", "merchant", "category", "amount", "currency", "receipt"],
            tx,
        )
        + "\n\nQUESTION\nWhat is the total reimbursable amount in USD? " + FORMAT_2DP
    )
    add(
        "expense-audit-1", "Expense report reimbursement audit", prompt, answer,
        ["fx-normalization", "eligibility-window", "category-exclusion",
         "per-day-meal-cap", "receipt-threshold", "exact-duplicate-dedup"],
        "Kept: T1 352.00, T2 198.00, T6 24.20, T9 112.50 (T10 dup dropped), T11 136.00; "
        "meals 03-02 99.00->75.00, 03-06 34.00; excluded T3/T13 alcohol, T7 >25 no receipt, "
        "T8 out of window. Total 931.70.",
        expect="931.70",
    )


# ---------------------------------------------------------------------------
# Q2  invoice discount reconciliation
# ---------------------------------------------------------------------------
def build_q2():
    # terms: (discount_pct, discount_days)  net days irrelevant to the question
    TERMS = {
        "2/10 net 30": (D("0.02"), 10),
        "1/15 net 45": (D("0.01"), 15),
        "net 30": (D("0"), 0),
    }
    invoices = [
        ("INV1", "2026-05-01", "1000.00", "2/10 net 30"),
        ("INV2", "2026-05-03", "2500.00", "1/15 net 45"),
        ("INV3", "2026-05-05", "800.00", "net 30"),
        ("INV4", "2026-05-10", "1500.00", "2/10 net 30"),
        ("INV5", "2026-05-12", "3200.00", "1/15 net 45"),
        ("INV6", "2026-05-15", "600.00", "2/10 net 30"),
        ("INV7", "2026-05-16", "400.00", "net 30"),
    ]
    payments = [
        ("2026-05-08", "INV1", "980.00"),
        ("2026-05-25", "INV2", "2475.00"),
        ("2026-05-20", "INV3", "800.00"),
        ("2026-05-16", "INV4", "1470.00"),
        ("2026-05-14", "INV5", "3000.00"),
        ("2026-05-20", "INV7", "450.00"),
        ("2026-05-22", "INV9", "500.00"),  # unknown invoice -> ignored
    ]

    inv = {i[0]: i for i in invoices}
    pay = {p[1]: p for p in payments if p[1] in inv}  # ignore unknown refs

    def days_between(d1, d2):
        a = datetime.strptime(d1, "%Y-%m-%d").date()
        b = datetime.strptime(d2, "%Y-%m-%d").date()
        return (b - a).days

    total = D(0)
    for iid, idate, amt, terms in invoices:
        amt = D(amt)
        disc_pct, disc_days = TERMS[terms]
        if iid in pay:
            pdate, _, paid = pay[iid]
            paid = D(paid)
            discounted = hu(amt * (1 - disc_pct))
            earned = (disc_pct > 0 and days_between(idate, pdate) <= disc_days
                      and paid >= discounted)
            required = discounted if earned else amt
            owed = max(D(0), required - paid)
        else:
            owed = amt
        total += owed
    answer = money(total)

    prompt = (
        "You are in accounts receivable. Apply the customer payments to the open invoices "
        "and report how much money customers still owe.\n\n"
        "RULES\n"
        "- Terms 'X/Y net Z' mean: the customer earns an X% early-payment discount if they "
        "pay within Y days of the invoice date. Terms 'net 30' offer no discount.\n"
        "- 'Within Y days' means payment_date minus invoice_date is at most Y calendar days.\n"
        "- A discount is EARNED only if the payment is within the discount window AND the "
        "paid amount is at least the discounted required amount "
        "(required = round-half-up(invoice_amount * (1 - X%), 2)). A partial payment inside "
        "the window does NOT earn the discount.\n"
        "- If the discount is earned, the required amount is the discounted amount; otherwise "
        "the required amount is the full invoice amount.\n"
        "- Amount still owed on an invoice = max(0, required amount - amount paid). "
        "Overpayments are not refunded and do not offset other invoices.\n"
        "- There is at most one payment per invoice. A payment that references an invoice id "
        "not in the invoice list is misapplied and must be ignored entirely.\n\n"
        "INVOICES\n"
        + render_table(["invoice", "date", "amount", "terms"], invoices)
        + "\n\nPAYMENTS\n"
        + render_table(["date", "invoice", "amount"], payments)
        + "\n\nQUESTION\nWhat is the total amount still owed across all invoices? " + FORMAT_2DP
    )
    add(
        "invoice-recon-1", "Accounts-receivable early-payment reconciliation", prompt, answer,
        ["early-pay-discount-window", "partial-payment-forfeits-discount",
         "max-zero-overpayment", "ignore-unknown-reference"],
        "INV1 earned->0; INV2 late, owe 25.00; INV3 paid full 0; INV4 earned 0; "
        "INV5 partial<discounted so full required, owe 200.00; INV6 unpaid owe 600.00; "
        "INV7 overpaid 0; ignored INV9. Total 825.00.",
        expect="825.00",
    )


# ---------------------------------------------------------------------------
# Q3  payroll daily overtime
# ---------------------------------------------------------------------------
def build_q3():
    rates = {"Alice": D("30.00"), "Bob": D("22.00"), "Carol": D("40.00")}
    shifts = [
        ("Alice", "2026-06-01", "10.0"),
        ("Alice", "2026-06-02", "5.0"),
        ("Bob", "2026-06-01", "13.0"),
        ("Bob", "2026-06-03", "8.5"),
        ("Carol", "2026-06-01", "7.0"),
        ("Carol", "2026-06-02", "14.0"),
    ]
    total = D(0)
    for emp, dt, hrs in shifts:
        h = D(hrs)
        if h > D("6.0"):
            h = h - D("0.5")  # unpaid meal break
        reg = min(h, D("8"))
        ot1 = min(max(h - D("8"), D("0")), D("4"))   # hours 8..12
        ot2 = max(h - D("12"), D("0"))               # hours over 12
        eq = reg * D("1") + ot1 * D("1.5") + ot2 * D("2")
        total += hu(eq * rates[emp])
    answer = money(total)

    prompt = (
        "You are running payroll. Compute the total gross pay for the pay period using the "
        "daily overtime rules below.\n\n"
        "RULES (apply per shift, in this order)\n"
        "1. Meal break: if a shift is longer than 6.0 hours, subtract 0.5 unpaid hours from "
        "that shift's hours before doing anything else.\n"
        "2. Daily tiers on the resulting paid hours: the first 8.0 hours pay at 1.0x the "
        "employee's rate; hours above 8.0 up to 12.0 pay at 1.5x; hours above 12.0 pay at "
        "2.0x.\n"
        "3. A shift's pay = (regular hours * 1.0 + tier-1.5 hours * 1.5 + tier-2.0 hours * "
        "2.0) * hourly rate, round-half-up to 2 decimals.\n"
        "4. Gross pay is the sum of all shift pays.\n\n"
        "HOURLY RATES\nAlice 30.00, Bob 22.00, Carol 40.00\n\n"
        "SHIFTS\n"
        + render_table(["employee", "date", "hours"], shifts)
        + "\n\nQUESTION\nWhat is the total gross pay for the period? " + FORMAT_2DP
    )
    add(
        "payroll-ot-1", "Daily-overtime payroll calculation", prompt, answer,
        ["unpaid-meal-break", "daily-overtime-tiers-1.5x-2x"],
        "Alice 307.50+150.00; Bob 330.00+176.00; Carol 260.00+680.00 = 1903.50.",
        expect="1903.50",
    )


# ---------------------------------------------------------------------------
# Q4  FIFO COGS
# ---------------------------------------------------------------------------
def build_q4():
    # lots in purchase order; freight allocated per unit (round per-unit cost)
    lots = [
        ("L1", "2026-04-01", 100, "10.00", "50.00"),
        ("L2", "2026-04-05", 150, "12.00", "90.00"),
        ("L3", "2026-04-10", 200, "11.00", "0.00"),
    ]
    sales = [
        ("S1", "2026-04-06", 120),
        ("S2", "2026-04-12", 180),
    ]
    # build FIFO queue of (unit_cost, qty)
    queue = []
    for lid, dt, qty, unit, freight in lots:
        per_unit = hu(D(unit) + D(freight) / D(qty))
        queue.append([per_unit, qty])
    cogs = D(0)
    for sid, dt, qty in sales:
        need = qty
        while need > 0:
            cost, avail = queue[0]
            take = min(need, avail)
            cogs += cost * take
            queue[0][1] -= take
            need -= take
            if queue[0][1] == 0:
                queue.pop(0)
    answer = money(cogs)

    prompt = (
        "You are doing inventory accounting. Compute the cost of goods sold (COGS) for the "
        "period using FIFO (first-in, first-out).\n\n"
        "RULES\n"
        "- Each purchase lot has a freight cost. Allocate freight evenly across the lot's "
        "units: per-unit cost = round-half-up(unit cost + freight / quantity, 2). Use this "
        "per-unit cost for every unit in that lot.\n"
        "- Process sales in date order. Under FIFO each sale consumes the oldest available "
        "units first. There is always enough inventory on hand for every sale.\n"
        "- COGS = sum over all sold units of the per-unit cost of the lot the unit came from "
        "(no intermediate rounding beyond the per-unit cost above).\n\n"
        "PURCHASE LOTS\n"
        + render_table(["lot", "date", "quantity", "unit cost", "freight"], lots)
        + "\n\nSALES\n"
        + render_table(["sale", "date", "quantity"], [(s[0], s[1], s[2]) for s in sales])
        + "\n\nQUESTION\nWhat is the total COGS for the period? " + FORMAT_2DP
    )
    add(
        "fifo-cogs-1", "FIFO cost-of-goods-sold with freight allocation", prompt, answer,
        ["per-unit-freight-allocation", "fifo-lot-consumption"],
        "Per-unit: L1 10.50, L2 12.60, L3 11.00. S1=100*10.50+20*12.60=1302.00; "
        "S2=130*12.60+50*11.00=2188.00. Total 3490.00.",
        expect="3490.00",
    )


# ---------------------------------------------------------------------------
# Q5  tiered commission
# ---------------------------------------------------------------------------
def build_q5():
    reps = [
        ("R1", "40000", "5000"),
        ("R2", "12000", "1000"),
        ("R3", "1500", "0"),
        ("R4", "26000", "4000"),
        ("R5", "60000", "35000"),
    ]
    total = D(0)
    for rid, gross, returns in reps:
        net = D(gross) - D(returns)
        if net < D("2000"):
            comm = D(0)
        else:
            t1 = min(net, D("10000")) * D("0.05")
            t2 = (min(net, D("25000")) - D("10000")).max(D("0")) * D("0.08")
            t3 = (net - D("25000")).max(D("0")) * D("0.12")
            comm = t1 + t2 + t3
            if net >= D("30000"):
                comm += D("500")
        total += hu(comm)
    answer = money(total)

    prompt = (
        "You administer the sales commission plan. Compute the total commission owed across "
        "all reps.\n\n"
        "RULES\n"
        "- Net sales = gross sales - returns.\n"
        "- If a rep's net sales are below 2000, that rep earns 0 commission (no tiers, no "
        "bonus).\n"
        "- Otherwise commission is MARGINAL across these tiers of net sales: the portion from "
        "0 to 10000 earns 5%, the portion from 10000 to 25000 earns 8%, and the portion above "
        "25000 earns 12%.\n"
        "- Quota bonus: if net sales are 30000 or more, add a flat 500 bonus to that rep's "
        "commission.\n"
        "- Round each rep's commission (tiers plus any bonus) to 2 decimals (half-up), then "
        "sum across reps.\n\n"
        "REPS\n"
        + render_table(["rep", "gross sales", "returns"], reps)
        + "\n\nQUESTION\nWhat is the total commission owed? " + FORMAT_2DP
    )
    add(
        "commission-1", "Marginal-tier sales commission", prompt, answer,
        ["net-of-returns", "minimum-floor", "marginal-tiers", "quota-bonus"],
        "R1 net35000=2900+500=3400; R2 net11000=580; R3 net1500<2000=0; R4 net22000=1460; "
        "R5 net25000=1700. Total 7140.00.",
        expect="7140.00",
    )


# ---------------------------------------------------------------------------
# Q6  subscription proration (forces half-up rounding)
# ---------------------------------------------------------------------------
def build_q6():
    DAYS = 31  # July 2026
    PRICE = {"Basic": D("30.00"), "Pro": D("90.00"), "Enterprise": D("300.00")}
    # each customer -> list of (plan, active_days)
    customers = {
        "C1": [("Pro", 31)],
        "C2": [("Basic", 15), ("Pro", 16)],
        "C3": [("Enterprise", 20), ("Basic", 11)],
        "C4": [("Pro", 20)],
        "C5": [("Pro", 25)],
    }
    descriptions = [
        ("C1", "Pro for the entire month (Jul 1-31)."),
        ("C2", "Basic from Jul 1, upgraded to Pro on Jul 16."),
        ("C3", "Enterprise from Jul 1, downgraded to Basic on Jul 21."),
        ("C4", "Joined Jul 12 on Pro, active through Jul 31."),
        ("C5", "Pro from Jul 1, cancellation effective Jul 26."),
    ]
    total = D(0)
    for cid, segs in customers.items():
        for plan, d in segs:
            total += hu(PRICE[plan] * d / DAYS)
    answer = money(total)

    prompt = (
        "You run monthly subscription billing for July 2026, which has 31 days. Compute the "
        "total amount billed to all customers.\n\n"
        "RULES\n"
        "- Monthly plan prices: Basic 30.00, Pro 90.00, Enterprise 300.00.\n"
        "- A plan is billed pro-rata: charge = round-half-up(monthly price * active_days / 31, "
        "2), where active_days is the number of calendar days that plan was active during July.\n"
        "- On a day a customer changes plans, that day counts toward the NEW plan.\n"
        "- 'Cancellation effective on date D' means the plan is NOT active on day D; the last "
        "active day is the day before D.\n"
        "- A customer's bill is the sum of the charges for each plan segment they had; the "
        "month total is the sum over all customers.\n\n"
        "CUSTOMERS\n"
        + render_table(["customer", "activity in July 2026"], descriptions)
        + "\n\nQUESTION\nWhat is the total amount billed for July 2026? " + FORMAT_2DP
    )
    add(
        "proration-1", "Mid-month subscription proration", prompt, answer,
        ["calendar-day-proration", "change-day-to-new-plan", "cancellation-day-exclusive",
         "half-up-rounding"],
        "C1 90.00; C2 14.52+46.45=60.97; C3 193.55+10.65=204.20; C4 58.06; C5 72.58. "
        "Total 485.81.",
        expect="485.81",
    )


# ---------------------------------------------------------------------------
# Q7  bank reconciliation
# ---------------------------------------------------------------------------
def build_q7():
    book_balance = D("13900.00")
    bank_balance = D("14750.00")
    outstanding_checks = [("#501", "1200.00"), ("#505", "850.00"), ("#506", "400.00")]
    deposit_in_transit = D("1500.00")
    service_fee = D("35.00")
    nsf = D("600.00")
    interest = D("85.00")
    book_error = D("450.00")  # check recorded as 720 but was 270 -> add back 450

    oc = sum(D(a) for _, a in outstanding_checks)
    adj_bank = bank_balance - oc + deposit_in_transit
    adj_book = book_balance - service_fee - nsf + interest + book_error
    assert adj_bank == adj_book
    answer = money(adj_bank)

    prompt = (
        "You are reconciling the company's cash. Adjust both the bank balance and the book "
        "(general-ledger) balance to the same true cash figure, and report that reconciled "
        "balance.\n\n"
        "STARTING BALANCES\n"
        f"- Bank statement ending balance: {bank_balance:.2f}\n"
        f"- Book (general-ledger) cash balance: {book_balance:.2f}\n\n"
        "BANK-SIDE ADJUSTMENTS (the bank does not yet reflect these)\n"
        "- Outstanding checks (issued, not yet cleared the bank): "
        + ", ".join(f"{n} {a}" for n, a in outstanding_checks)
        + " -- subtract from the bank balance.\n"
        f"- Deposit in transit: {deposit_in_transit:.2f} -- add to the bank balance.\n\n"
        "BOOK-SIDE ADJUSTMENTS (the books do not yet reflect these)\n"
        f"- Bank service fee charged: {service_fee:.2f} -- subtract from the book balance.\n"
        f"- NSF (bounced) customer check: {nsf:.2f} -- subtract from the book balance.\n"
        f"- Interest credited by the bank: {interest:.2f} -- add to the book balance.\n"
        "- Bookkeeping error: a check written for 270.00 was recorded in the books as 720.00. "
        "Correct the books by adding the 450.00 difference back to the book balance.\n\n"
        "QUESTION\nAfter both sides are adjusted they agree. What is the reconciled cash "
        "balance? " + FORMAT_2DP
    )
    add(
        "bank-recon-1", "Bank-to-book cash reconciliation", prompt, answer,
        ["bank-side-adjustments", "book-side-adjustments", "bookkeeping-error-correction",
         "two-sided-cross-check"],
        "Adjusted bank 14750-2450+1500=13800; adjusted book 13900-35-600+85+450=13800. "
        "Reconciled 13800.00.",
        expect="13800.00",
    )


# ---------------------------------------------------------------------------
# Q8  loan amortization with an extra payment
# ---------------------------------------------------------------------------
def build_q8():
    balance = D("20000.00")
    rate = D("0.01")           # 1.0% per month
    payment = D("600.00")
    extra_month = 6
    extra_amount = D("1000.00")
    months = 12
    for m in range(1, months + 1):
        interest = hu(balance * rate)
        principal = payment - interest
        balance = balance - principal
        if m == extra_month:
            balance = balance - extra_amount
        balance = hu(balance)
    answer = money(balance)

    prompt = (
        "You are servicing a loan. Compute the remaining principal balance after 12 monthly "
        "payments.\n\n"
        "RULES (repeat each month, in this order)\n"
        "- Starting balance: 20000.00. Monthly interest rate: 1.0% (0.01).\n"
        "- Each month: interest = round-half-up(current balance * 0.01, 2). The fixed monthly "
        "payment is 600.00. Principal paid = 600.00 - interest. New balance = current balance "
        "- principal paid.\n"
        "- In month 6 ONLY, after the regular payment is applied, an extra principal-only "
        "payment of 1000.00 is also applied (subtract 1000.00 from the balance).\n"
        "- After each month's steps, round the balance to 2 decimals (half-up) before the next "
        "month. The balance never reaches zero within these 12 months.\n\n"
        "QUESTION\nWhat is the remaining balance after the 12th payment? " + FORMAT_2DP
    )
    add(
        "amortization-1", "Loan amortization with extra principal payment", prompt, answer,
        ["monthly-interest-rounding", "principal-paydown", "one-time-extra-principal"],
        "Iterate 12 months at 1%/600 payment with a 1000 extra-principal hit in month 6; "
        f"final balance {answer}.",
    )


# ---------------------------------------------------------------------------
# Q9  shipping carrier optimization
# ---------------------------------------------------------------------------
def build_q9():
    orders = [
        ("O1", 4, 2, "no", "1000"),
        ("O2", 30, 5, "no", "5000"),
        ("O3", 10, 3, "yes", "800"),
        ("O4", 60, 1, "no", "3000"),
        ("O5", 5, 4, "no", "2500"),
        ("O6", 20, 2, "yes", "0"),
        ("O7", 45, 4, "no", "10000"),
    ]

    def std_base(w):
        if w <= 5:
            return D("8.00")
        if w <= 20:
            return D("15.00")
        if w <= 50:
            return D("28.00")
        return None  # not served over 50

    def std_zone(z):
        return {1: D("0"), 2: D("0"), 3: D("5.00"), 4: D("5.00"), 5: D("12.00")}[z]

    def standard_cost(w, z, res, val):
        base = std_base(w)
        if base is None:
            return None  # ineligible (weight)
        sub = base + std_zone(z) + (D("4.00") if res == "yes" else D("0"))
        return hu(sub * D("1.12"))  # 12% fuel surcharge

    def express_cost(w, z, res, val):
        if z == 5:
            return None  # EXPRESS does not serve zone 5
        if w <= 5:
            base = D("16.00")
        elif w <= 20:
            base = D("26.00")
        elif w <= 70:
            base = D("48.00")
        else:
            return None
        return hu(base + D(val) * D("0.02"))  # 2% declared-value insurance

    total = D(0)
    for oid, w, z, res, val in orders:
        s = standard_cost(w, z, res, val)
        e = express_cost(w, z, res, val)
        options = []
        if s is not None:
            options.append(("STANDARD", s))
        if e is not None:
            options.append(("EXPRESS", e))
        # cheapest; tie-break STANDARD (priority order as listed)
        options.sort(key=lambda o: (o[1], 0 if o[0] == "STANDARD" else 1))
        total += options[0][1]
    answer = money(total)

    prompt = (
        "You are choosing carriers to minimize shipping cost. For each order pick the cheapest "
        "carrier that can carry it, and report the total of the chosen costs.\n\n"
        "CARRIERS\n"
        "STANDARD (serves all zones; max weight 50 lb):\n"
        "  base by weight: <=5 lb -> 8.00, 6-20 lb -> 15.00, 21-50 lb -> 28.00.\n"
        "  zone surcharge: zones 1-2 -> 0, zones 3-4 -> 5.00, zone 5 -> 12.00.\n"
        "  residential surcharge: +4.00 if residential.\n"
        "  then a 12% fuel surcharge on the running subtotal: "
        "cost = round-half-up((base + zone + residential) * 1.12, 2).\n"
        "EXPRESS (serves zones 1-4 only; max weight 70 lb; no zone/residential/fuel charges):\n"
        "  base by weight: <=5 lb -> 16.00, 6-20 lb -> 26.00, 21-70 lb -> 48.00.\n"
        "  insurance: + 2% of declared value. cost = round-half-up(base + value * 0.02, 2).\n\n"
        "RULES\n"
        "- A carrier is eligible for an order only if it serves the order's zone and the order "
        "weight is within that carrier's maximum.\n"
        "- Choose the eligible carrier with the lower cost. If both eligible carriers cost "
        "exactly the same, choose STANDARD.\n"
        "- Weight breaks are inclusive of their upper bound; all weights below are whole "
        "numbers of pounds.\n\n"
        "ORDERS\n"
        + render_table(["order", "weight_lb", "zone", "residential", "declared_value"], orders)
        + "\n\nQUESTION\nWhat is the total chosen shipping cost across all orders? " + FORMAT_2DP
    )
    add(
        "shipping-opt-1", "Cheapest-eligible-carrier shipping optimization", prompt, answer,
        ["weight-break-tables", "zone-and-service-eligibility", "fuel-surcharge",
         "value-insurance", "per-order-min-with-tiebreak"],
        "O1 8.96, O2 44.80 (EXPRESS ineligible zone5), O3 26.88, O4 108.00 (STANDARD "
        "ineligible >50lb), O5 14.56, O6 21.28, O7 36.96. Total 261.44.",
        expect="261.44",
    )


# ---------------------------------------------------------------------------
# Q10  cohort revenue funnel
# ---------------------------------------------------------------------------
def build_q10():
    # (user, type, date, amount)
    events = [
        ("U1", "signup", "2026-07-03", ""),
        ("U1", "purchase", "2026-07-05", "120.00"),
        ("U1", "purchase", "2026-07-12", "80.00"),
        ("U2", "signup", "2026-07-07", ""),
        ("U2", "purchase", "2026-07-14", "200.00"),
        ("U3", "signup", "2026-07-07", ""),
        ("U3", "purchase", "2026-07-15", "90.00"),
        ("U4", "signup", "2026-07-02", ""),
        ("U4", "purchase", "2026-07-02", "60.00"),
        ("U4", "purchase", "2026-07-04", "40.00"),
        ("U5", "signup", "2026-07-10", ""),
        ("U5", "purchase", "2026-07-11", "500.00"),
        ("U6", "signup", "2026-07-01", ""),
        ("U7", "signup", "2026-07-05", ""),
        ("U7", "purchase", "2026-07-12", "300.00"),
    ]

    def d(s):
        return datetime.strptime(s, "%Y-%m-%d").date()

    signup = {}
    purchases = {}
    for u, typ, dt, amt in events:
        if typ == "signup":
            signup[u] = d(dt)
        else:
            purchases.setdefault(u, []).append((d(dt), D(amt)))

    total = D(0)
    for u, sdate in signup.items():
        if not (d("2026-07-01") <= sdate <= d("2026-07-07")):
            continue
        in_window = [(pd, amt) for pd, amt in purchases.get(u, [])
                     if (pd - sdate).days <= 7]
        if not in_window:
            continue  # user did not purchase within 7 days -> not a qualifying user
        total += sum((amt for _, amt in in_window), D(0))
    answer = money(total)

    prompt = (
        "You are a revenue analyst. Compute a cohort metric from the event log.\n\n"
        "DEFINITIONS\n"
        "- The week-1 cohort is every user whose signup date is between 2026-07-01 and "
        "2026-07-07 inclusive. Users who signed up outside that range are excluded entirely.\n"
        "- A purchase is 'within 7 days of signup' if purchase_date minus signup_date is at "
        "most 7 calendar days (the signup day itself is day 0; day 7 still counts).\n"
        "- A cohort user QUALIFIES if they made at least one purchase within 7 days of signup.\n"
        "- The metric is the sum of the amounts of ALL purchases made within 7 days of signup, "
        "across qualifying users only.\n\n"
        "EVENT LOG\n"
        + render_table(["user", "type", "date", "amount"], events)
        + "\n\nQUESTION\nWhat is the total within-7-day purchase revenue for the week-1 "
        "cohort? " + FORMAT_2DP
    )
    add(
        "cohort-funnel-1", "Week-1 cohort 7-day purchase revenue", prompt, answer,
        ["cohort-signup-window", "per-user-7-day-window", "qualification-gate",
         "windowed-sum"],
        "U1 120 (Jul12 out); U2 200 (day7 in); U3 0 (day8 out, disqualified); U4 60+40=100; "
        "U5 excluded (signup Jul10); U6 no purchase; U7 300 (day7 in). Total 720.00.",
        expect="720.00",
    )


# ---------------------------------------------------------------------------
# Q11  SLA business-hours penalty
# ---------------------------------------------------------------------------
def build_q11():
    HOLIDAYS = {date(2026, 9, 7)}  # Labor Day (Monday)
    OPEN, CLOSE = 9 * 60, 17 * 60  # minutes from midnight
    SLA_MIN = 8 * 60
    RATE = D("25.00")
    tickets = [
        ("T1", "2026-09-08 09:00", "2026-09-08 14:00"),
        ("T2", "2026-09-08 15:00", "2026-09-09 11:00"),
        ("T3", "2026-09-04 13:00", "2026-09-08 16:00"),
        ("T4", "2026-09-09 16:30", "2026-09-10 09:45"),
        ("T5", "2026-09-08 09:00", "2026-09-09 17:00"),
        ("T6", "2026-09-09 10:20", "2026-09-10 12:50"),
    ]

    def business_minutes(start, end):
        s = datetime.strptime(start, "%Y-%m-%d %H:%M")
        e = datetime.strptime(end, "%Y-%m-%d %H:%M")
        # all endpoints are guaranteed within business hours on business days
        mins = 0
        day = s.date()
        while day <= e.date():
            if day.weekday() < 5 and day not in HOLIDAYS:
                day_open = OPEN
                day_close = CLOSE
                lo = day_open
                hi = day_close
                if day == s.date():
                    lo = s.hour * 60 + s.minute
                if day == e.date():
                    hi = e.hour * 60 + e.minute
                if hi > lo:
                    mins += hi - lo
            day += timedelta(days=1)
        return mins

    total = D(0)
    for tid, c, r in tickets:
        bm = business_minutes(c, r)
        if bm > SLA_MIN:
            over_hours = D(bm - SLA_MIN) / D("60")
            total += hu(over_hours * RATE)
    answer = money(total)

    prompt = (
        "You are tracking support SLAs. Compute the total penalty owed for breached tickets.\n\n"
        "RULES\n"
        "- Business hours are Monday-Friday 09:00-17:00 (8 hours/day). 2026-09-07 (a Monday) "
        "is a holiday with no business hours. Weekends have no business hours.\n"
        "- A ticket's handling time is measured ONLY in business minutes between its created "
        "and resolved timestamps (minutes outside business hours, on weekends, or on the "
        "holiday do not count). Every timestamp below falls on a business day within 09:00-"
        "17:00, so you never need to clamp an endpoint.\n"
        "- The SLA target is 8 business hours. A ticket breaches if its business-hours handling "
        "time exceeds 8 hours.\n"
        "- Penalty for a breached ticket = round-half-up(overage_hours * 25.00, 2), where "
        "overage_hours = (business minutes over 8 hours) / 60. Non-breached tickets owe 0.\n\n"
        "TICKETS\n"
        + render_table(["ticket", "created", "resolved"], tickets)
        + "\n\nQUESTION\nWhat is the total SLA penalty across all tickets? " + FORMAT_2DP
    )
    add(
        "sla-penalty-1", "Business-hours SLA penalty", prompt, answer,
        ["business-hours-arithmetic", "weekend-and-holiday-skip", "sla-overage-penalty"],
        "T3 11h ->3h*25=75.00; T5 16h ->8h*25=200.00; T6 10.5h ->2.5h*25=62.50; rest within "
        "SLA. Total 337.50.",
        expect="337.50",
    )


# ---------------------------------------------------------------------------
# Q12  payroll tax with FICA caps and Medicare surtax (hardest)
# ---------------------------------------------------------------------------
def build_q12():
    # marginal federal brackets: (upper_bound, rate); last is None upper
    BRACKETS = [
        (D("11000"), D("0.10")),
        (D("44725"), D("0.12")),
        (D("95375"), D("0.22")),
        (D("182100"), D("0.24")),
        (D("231250"), D("0.32")),
        (None, D("0.35")),
    ]
    SS_RATE = D("0.062")
    SS_WAGE_BASE = D("168600")
    MEDICARE_RATE = D("0.0145")
    MEDICARE_SURTAX = D("0.009")
    MEDICARE_SURTAX_THRESHOLD = D("200000")
    STATE_RATE = D("0.05")

    employees = [("E1", "50000"), ("E2", "120000"), ("E3", "210000")]

    def federal(wage):
        tax = D(0)
        lower = D(0)
        for upper, rate in BRACKETS:
            if upper is None:
                taxable = max(D(0), wage - lower)
            else:
                taxable = max(D(0), min(wage, upper) - lower)
            tax += taxable * rate
            if upper is not None:
                lower = upper
            if upper is not None and wage <= upper:
                break
        return tax

    total = D(0)
    for eid, w in employees:
        wage = D(w)
        fed = hu(federal(wage))
        ss = hu(min(wage, SS_WAGE_BASE) * SS_RATE)
        med = hu(wage * MEDICARE_RATE
                 + max(D(0), wage - MEDICARE_SURTAX_THRESHOLD) * MEDICARE_SURTAX)
        state = hu(wage * STATE_RATE)
        total += fed + ss + med + state
    answer = money(total)

    prompt = (
        "You are computing payroll taxes. For the three employees below, compute the TOTAL tax "
        "(all four components, all employees).\n\n"
        "TAX COMPONENTS (per employee, on annual gross wage)\n"
        "1. Federal income tax -- MARGINAL brackets:\n"
        "   0-11000 -> 10%; 11000-44725 -> 12%; 44725-95375 -> 22%; 95375-182100 -> 24%; "
        "182100-231250 -> 32%; above 231250 -> 35%.\n"
        "2. Social Security -- 6.2% of wages, but only on wages up to the wage base 168600 "
        "(wages above 168600 are not taxed for Social Security).\n"
        "3. Medicare -- 1.45% of ALL wages, PLUS an additional 0.9% on the portion of wages "
        "above 200000.\n"
        "4. State income tax -- a flat 5% of all wages.\n\n"
        "ROUNDING\n"
        "Compute each of the four components per employee and round each component to 2 "
        "decimals (half-up). Then sum every component across all employees.\n\n"
        "EMPLOYEES\n"
        + render_table(["employee", "annual gross wage"], employees)
        + "\n\nQUESTION\nWhat is the total tax across all employees? " + FORMAT_2DP
    )
    add(
        "payroll-tax-1", "Payroll tax: marginal brackets, FICA cap, Medicare surtax", prompt,
        answer,
        ["marginal-federal-brackets", "social-security-wage-base-cap",
         "medicare-additional-surtax", "flat-state-tax", "per-component-rounding"],
        "Sum of federal (marginal) + Social Security (capped at 168600) + Medicare "
        "(1.45% all + 0.9% over 200000) + 5% state, across E1/E2/E3; "
        f"total {answer}.",
    )


# ---------------------------------------------------------------------------
# Q13  commercial time-of-use electricity bill
# ---------------------------------------------------------------------------
def build_q13():
    HOLIDAYS = {"2026-06-19"}  # Juneteenth (a Friday): treated as off-peak all day
    # (date, weekday, hour_start, kwh) -- each reading is a 1-hour interval, so
    # the kWh value equals the average kW demand for that interval.
    reads = [
        ("2026-06-01", "Mon", 8, 120),
        ("2026-06-01", "Mon", 13, 205),
        ("2026-06-01", "Mon", 17, 340),
        ("2026-06-01", "Mon", 19, 410),
        ("2026-06-01", "Mon", 23, 90),
        ("2026-06-02", "Tue", 6, 70),
        ("2026-06-02", "Tue", 11, 185),
        ("2026-06-02", "Tue", 14, 260),
        ("2026-06-02", "Tue", 18, 395),
        ("2026-06-02", "Tue", 22, 140),
        ("2026-06-03", "Wed", 7, 95),
        ("2026-06-03", "Wed", 16, 380),
        ("2026-06-03", "Wed", 20, 425),
        ("2026-06-03", "Wed", 21, 150),
        ("2026-06-04", "Thu", 7, 110),
        ("2026-06-04", "Thu", 15, 240),
        ("2026-06-04", "Thu", 18, 405),
        ("2026-06-04", "Thu", 20, 300),
        ("2026-06-05", "Fri", 9, 160),
        ("2026-06-05", "Fri", 16, 390),
        ("2026-06-05", "Fri", 23, 80),
        ("2026-06-06", "Sat", 12, 200),
        ("2026-06-06", "Sat", 18, 220),
        ("2026-06-07", "Sun", 10, 130),
        ("2026-06-07", "Sun", 19, 180),
        ("2026-06-08", "Mon", 17, 415),
        ("2026-06-08", "Mon", 21, 145),
        ("2026-06-09", "Tue", 16, 360),
        ("2026-06-09", "Tue", 18, 385),
        ("2026-06-11", "Thu", 14, 250),
        ("2026-06-12", "Fri", 18, 300),
        ("2026-06-13", "Sat", 17, 210),
        ("2026-06-19", "Fri", 17, 360),
        ("2026-06-19", "Fri", 12, 150),
        ("2026-06-19", "Fri", 19, 430),
    ]
    RATE = {"PEAK": D("0.2840"), "SHOULDER": D("0.1450"), "OFFPEAK": D("0.0890")}
    CONTRACTED_DEMAND = D("520")

    def period(dt, wd, hr):
        if dt in HOLIDAYS:
            return "OFFPEAK"
        if wd in ("Sat", "Sun"):
            return "OFFPEAK"
        if 16 <= hr <= 20:
            return "PEAK"
        if (7 <= hr <= 15) or hr in (21, 22):
            return "SHOULDER"
        return "OFFPEAK"

    kwh = {"PEAK": 0, "SHOULDER": 0, "OFFPEAK": 0}
    peak_demand = 0
    for dt, wd, hr, k in reads:
        p = period(dt, wd, hr)
        kwh[p] += k
        if p == "PEAK":
            peak_demand = max(peak_demand, k)
    energy = sum((hu(D(kwh[p]) * RATE[p]) for p in kwh), D(0))
    billed_demand = max(D(peak_demand), hu(CONTRACTED_DEMAND * D("0.80")))
    demand = hu(billed_demand * D("14.50"))
    power_factor = D("0.91")
    pf_penalty = hu(demand * (D("0.95") - power_factor)) if power_factor < D("0.95") else D(0)
    customer = D("32.00")
    subtotal = energy + demand + pf_penalty + customer
    tax = hu(subtotal * D("0.065"))
    total_kwh = sum(kwh.values())
    franchise = hu(D(total_kwh) * D("0.00250"))
    answer = money(subtotal + tax + franchise)

    prompt = (
        "You are billing a commercial electricity account for one monthly cycle. Rate every "
        "metered interval, add demand and fixed charges, then apply tax and a franchise fee.\n\n"
        "TIME-OF-USE PERIODS (use the weekday given in the table; do not compute it yourself)\n"
        "- HOLIDAY OVERRIDE: 2026-06-19 is a holiday. EVERY interval on that date is OFFPEAK "
        "regardless of its hour, and holiday intervals never count toward peak demand.\n"
        "- PEAK: Monday-Friday (non-holiday) only, for interval-start hours 16, 17, 18, 19, 20 "
        "(i.e. 16:00-21:00). Rate 0.2840 per kWh.\n"
        "- SHOULDER: Monday-Friday (non-holiday) only, for interval-start hours 7-15 or 21-22. "
        "Rate 0.1450 per kWh.\n"
        "- OFFPEAK: every interval not classified above. This INCLUDES all Saturday and Sunday "
        "intervals regardless of hour, all holiday intervals, and weekday hours 0-6 and 23. "
        "Rate 0.0890 per kWh.\n\n"
        "CHARGES (apply in this order)\n"
        "1. Energy charge: for EACH period, sum that period's kWh and multiply by the period "
        "rate, rounding that period's energy charge half-up to 2 decimals. The energy charge is "
        "the sum of the three rounded period charges.\n"
        "2. Demand charge with ratchet: the measured demand is the single highest kWh value "
        "among PEAK intervals only (each 1-hour interval's kWh equals its kW). However, billed "
        "demand may not fall below 80% of the contracted demand of 520 kW; that is, billed "
        "demand = max(measured peak demand, round-half-up(0.80 * 520, 2)). Demand charge = "
        "round-half-up(billed demand * 14.50, 2).\n"
        "3. Power-factor penalty: the metered average power factor for the cycle is 0.91. If "
        "it is below 0.95, add a penalty = round-half-up(demand charge * (0.95 - power "
        "factor), 2); otherwise the penalty is 0.\n"
        "4. Customer charge: a flat 32.00.\n"
        "5. Subtotal = energy + demand + power-factor penalty + customer.\n"
        "6. Utility tax = round-half-up(subtotal * 0.065, 2). It is added to the subtotal.\n"
        "7. Franchise fee = round-half-up((total kWh across ALL periods) * 0.00250, 2). It is "
        "added AFTER tax and is itself not taxed.\n\n"
        "Each interval below is a 1-hour interval beginning at the listed hour.\n\n"
        "METER READINGS\n"
        + render_table(["date", "weekday", "hour_start", "kwh"], reads)
        + "\n\nQUESTION\nWhat is the total bill? " + FORMAT_2DP
    )
    add(
        "utility-billing-1", "Time-of-use commercial electricity bill", prompt, answer,
        ["tou-period-classification", "weekend-overrides-peak-hours", "holiday-all-offpeak",
         "demand-ratchet", "power-factor-penalty", "ordered-tax-then-untaxed-fee",
         "per-period-rounding"],
        "Classify all 35 intervals (holiday 06-19 all off-peak incl its 430 kWh, which is "
        "therefore NOT a demand candidate; weekend peak-hours off-peak). Energy = sum of three "
        "rounded period charges. Billed demand = max(measured peak demand, ratchet floor "
        "0.80*520=416). PF penalty = demand*(0.95-0.91). Subtotal+tax(6.5%)+untaxed franchise "
        f"(total kWh*0.00250). Solver answer {answer}.",
    )


# ---------------------------------------------------------------------------
# Q14  perpetual weighted-average-cost inventory (running COGS)
# ---------------------------------------------------------------------------
def build_q14():
    # (line, type, qty, unit, freight) processed strictly top to bottom.
    txns = [
        ("L1", "PURCHASE", 50, "22.00", "60.00"),
        ("L2", "SALE", 80, "", ""),
        ("L3", "PURCHASE", 120, "25.00", "180.00"),
        ("L4", "PURCHASE_RETURN", 30, "", ""),
        ("L5", "SALE", 100, "", ""),
        ("L6", "PURCHASE", 40, "19.50", "0.00"),
        ("L7", "SALE", 75, "", ""),
        ("L8", "PURCHASE", 90, "23.40", "95.00"),
        ("L9", "SALE", 60, "", ""),
        ("L10", "PURCHASE", 65, "26.10", "120.00"),
        ("L11", "PURCHASE_RETURN", 25, "", ""),
        ("L12", "SALE", 85, "", ""),
        ("L13", "PURCHASE", 110, "21.75", "150.00"),
        ("L14", "SALE", 100, "", ""),
        ("L15", "PURCHASE", 35, "27.80", "40.00"),
        ("L16", "SALE", 50, "", ""),
    ]
    qty = 100
    cost = D("2000.00")  # beginning inventory: 100 units, total cost 2000.00
    total_cogs = D(0)
    for line, typ, q, unit, freight in txns:
        wac = (cost / D(qty)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if typ == "PURCHASE":
            lot = D(unit) * D(q) + D(freight)
            qty += q
            cost += lot
        elif typ == "PURCHASE_RETURN":
            relief = hu(D(q) * wac)
            qty -= q
            cost -= relief
        else:  # SALE
            cogs = hu(D(q) * wac)
            total_cogs += cogs
            qty -= q
            cost -= cogs
    answer = money(total_cogs)

    prompt = (
        "You maintain a perpetual inventory under the moving weighted-average-cost method. "
        "Process the transactions strictly in the order listed and report total cost of goods "
        "sold.\n\n"
        "RULES\n"
        "- Beginning inventory is 100 units with a total cost of 2000.00.\n"
        "- The weighted-average unit cost (WAC) at any moment = (running total inventory cost) "
        "/ (running unit quantity), and you must recompute it to 4 decimal places, round-half-"
        "up, immediately BEFORE processing each transaction.\n"
        "- PURCHASE: the lot's total cost = qty * unit_cost + freight. Add the qty to the "
        "running quantity and the lot total cost to the running total cost.\n"
        "- PURCHASE_RETURN: goods returned TO the supplier. Remove them at the current WAC: "
        "reduce the running quantity by qty and reduce the running total cost by "
        "round-half-up(qty * current WAC, 2). This is not a sale and produces no COGS.\n"
        "- SALE: cost of goods sold for the sale = round-half-up(qty * current WAC, 2). Add "
        "that to total COGS; then subtract the sold qty from the running quantity and subtract "
        "the sale's COGS (the rounded figure) from the running total cost.\n"
        "- The unit_cost/freight columns apply only to PURCHASE rows; other rows leave them "
        "blank.\n\n"
        "TRANSACTIONS\n"
        + render_table(["line", "type", "qty", "unit_cost", "freight"], txns)
        + "\n\nQUESTION\nWhat is the total cost of goods sold across all sales? " + FORMAT_2DP
    )
    add(
        "wac-inventory-1", "Perpetual weighted-average-cost COGS", prompt, answer,
        ["moving-weighted-average", "freight-in-capitalization", "4dp-wac-recompute",
         "purchase-return-relief", "rounded-cost-relief", "strict-transaction-ordering"],
        "Process all 16 transactions in order, recomputing 4dp WAC before each; sum COGS over "
        "the SALE rows only (purchase returns relieve cost at WAC but add no COGS). Rounded "
        f"WAC and rounded cost relief compound across the sequence. Solver answer {answer}.",
    )


# ---------------------------------------------------------------------------
# Q15  royalty waterfall: cumulative marginal tiers, advance recoupment
# ---------------------------------------------------------------------------
def build_q15():
    # (period, gross_units, returned_units) processed in order.
    periods = [
        ("P1", 8500, 500),
        ("P2", 9300, 300),
        ("P3", 12400, 400),
        ("P4", 6300, 300),
        ("P5", 5300, 300),
        ("P6", 7200, 200),
        ("P7", 4800, 300),
        ("P8", 9100, 100),
        ("P9", 6700, 200),
        ("P10", 5400, 400),
    ]
    tiers = [(10000, D("1.50")), (25000, D("2.25")), (50000, D("3.00")),
             (None, D("3.75"))]

    cum = 0
    earned = D(0)
    total_net = 0
    last_period_earned = D(0)
    for _, gross, ret in periods:
        net = gross - ret
        total_net += net
        remaining = net
        local_cum = cum
        period_earned = D(0)
        for upper, rate in tiers:
            if remaining <= 0:
                break
            cap = (upper - local_cum) if upper is not None else remaining
            take = min(remaining, max(cap, 0)) if upper is not None else remaining
            if take <= 0:
                continue
            period_earned += D(take) * rate
            remaining -= take
            local_cum += take
        earned += period_earned
        last_period_earned = period_earned
        cum += net
    guarantee = D(total_net) * D("2.00")
    royalty = max(earned, guarantee)
    commission = hu(royalty * D("0.10"))
    audit_fee = D("1500.00")
    advance = D("50000.00")
    returns_reserve = hu(last_period_earned * D("0.20"))  # held back this statement
    payable = royalty - commission - audit_fee - advance - returns_reserve
    if payable < 0:
        payable = D(0)
    answer = money(payable)

    prompt = (
        "You are preparing a royalty statement. Compute the cash payable to the author after "
        "the minimum guarantee, agent commission, an audit fee, a returns reserve, and "
        "recoupment of the advance.\n\n"
        "RULES (apply in order)\n"
        "- For each period, net units = gross units - returned units.\n"
        "- Tiered royalty is earned on a CUMULATIVE marginal-tier basis across periods "
        "processed in order P1...P10. Tier rates apply to cumulative net units to date: "
        "units 1-10000 at 1.50 each; units 10001-25000 at 2.25 each; units 25001-50000 at 3.00 "
        "each; units above 50000 at 3.75 each. A single period's units can straddle tier "
        "boundaries.\n"
        "- Minimum guarantee: the author is guaranteed at least 2.00 per net unit across all "
        "periods. The royalty used downstream is the GREATER of the total tiered royalty and "
        "this guaranteed minimum (2.00 * total net units).\n"
        "- Agent commission = round-half-up(royalty * 0.10, 2), computed on the royalty figure "
        "from the previous step.\n"
        "- A flat audit fee of 1500.00 is deducted.\n"
        "- Returns reserve: 20% of the MOST RECENT period's (P10) tiered royalty earned is "
        "held back on this statement (released on a later statement). The reserve = "
        "round-half-up(P10 tiered royalty earned * 0.20, 2) and is subtracted.\n"
        "- A recoupable advance of 50000.00 was already paid to the author and must be "
        "subtracted.\n"
        "- Cash payable = royalty - commission - audit fee - returns reserve - advance. If "
        "that is negative, the advance is not yet fully recouped and the payable is 0.00.\n\n"
        "SALES BY PERIOD\n"
        + render_table(["period", "gross_units", "returned_units"], periods)
        + "\n\nQUESTION\nWhat is the cash payable to the author? " + FORMAT_2DP
    )
    add(
        "royalty-waterfall-1", "Royalty waterfall with cumulative tiers and recoupment",
        prompt, answer,
        ["net-of-returns", "cumulative-marginal-tiers", "four-tier-schedule",
         "minimum-guarantee-greater-of", "commission-on-royalty", "audit-fee",
         "returns-reserve-on-last-period", "advance-recoupment", "floor-at-zero"],
        "Accumulate net units across all 10 periods through the 4-tier cumulative schedule "
        "(boundaries 10000/25000/50000); royalty = max(tiered total, 2.00*total net units); "
        "then subtract commission (10%), 1500 audit, 20% reserve on P10's earned, and the "
        f"50000 advance, flooring at 0. Solver answer {answer}.",
    )


# ---------------------------------------------------------------------------
# Q16  multilateral intercompany netting with FX and settlement fee
# ---------------------------------------------------------------------------
def build_q16():
    FX = {"USD": "1.00", "EUR": "1.08", "GBP": "1.27", "JPY": "0.0067",
          "CHF": "1.12", "CAD": "0.73"}
    # (id, payer, payee, amount, currency)
    obligations = [
        ("O1", "A", "B", "100000", "EUR"),
        ("O2", "B", "C", "50000", "GBP"),
        ("O3", "C", "A", "8000000", "JPY"),
        ("O4", "D", "A", "75000", "USD"),
        ("O5", "A", "C", "40000", "GBP"),
        ("O6", "B", "D", "90000", "EUR"),
        ("O7", "C", "D", "30000", "USD"),
        ("O8", "D", "B", "5000000", "JPY"),
        ("O9", "E", "A", "60000", "CHF"),
        ("O10", "A", "E", "20000", "USD"),
        ("O11", "E", "C", "100000", "CAD"),
        ("O12", "D", "E", "40000", "EUR"),
        ("O13", "F", "B", "80000", "EUR"),
        ("O14", "C", "F", "200000", "CAD"),
        ("O15", "F", "D", "50000", "USD"),
        ("O16", "A", "F", "30000", "GBP"),
        ("O17", "G", "A", "90000", "CHF"),
        ("O18", "B", "G", "120000", "CAD"),
        ("O19", "G", "H", "40000", "USD"),
        ("O20", "H", "C", "60000", "EUR"),
        ("O21", "H", "F", "7000000", "JPY"),
        ("O22", "D", "H", "35000", "GBP"),
        ("O23", "E", "G", "25000", "USD"),
        ("O24", "F", "H", "55000", "CHF"),
    ]
    net = {}
    for _, payer, payee, amt, cur in obligations:
        usd = hu(D(amt) * D(FX[cur]))
        net[payer] = net.get(payer, D(0)) - usd
        net[payee] = net.get(payee, D(0)) + usd
    settlement = sum((v for v in net.values() if v > 0), D(0))

    def tiered_fee(payable):
        first = min(payable, D("50000"))
        rest = max(payable - D("50000"), D(0))
        return hu(first * D("0.0025") + rest * D("0.0015"))

    fees = sum((tiered_fee(-v) for v in net.values() if v < 0), D(0))
    answer = money(settlement + fees)

    prompt = (
        "Eight subsidiaries (A, B, C, D, E, F, G, H) owe each other money in several "
        "currencies. Run a multilateral netting and report the total cash that changes hands "
        "in settlement.\n\n"
        "RULES\n"
        "- Convert each obligation to USD by multiplying the amount by its rate (USD 1.00, EUR "
        "1.08, GBP 1.27, JPY 0.0067, CHF 1.12, CAD 0.73) and round-half-up to 2 decimals.\n"
        "- For each entity compute its net position = (sum of obligations owed TO it) - (sum "
        "of obligations it OWES). Entities with a positive net are net receivers; entities "
        "with a negative net are net payers.\n"
        "- The settlement amount = the sum of all positive net positions (equivalently, the "
        "sum of the absolute values of the negative ones).\n"
        "- Each net payer is charged a TIERED settlement fee on its net payable: 0.25% on the "
        "first 50000.00 of the payable plus 0.15% on the portion above 50000.00, rounded "
        "half-up to 2 decimals. Sum the fees across net payers.\n"
        "- Total cash that changes hands = settlement amount + total fees.\n\n"
        "OBLIGATIONS (payer owes payee)\n"
        + render_table(["id", "payer", "payee", "amount", "currency"], obligations)
        + "\n\nQUESTION\nWhat is the total cash that changes hands? " + FORMAT_2DP
    )
    add(
        "intercompany-netting-1", "Multilateral intercompany FX netting", prompt, answer,
        ["fx-normalization", "bilateral-to-net-position", "positive-net-settlement",
         "tiered-per-payer-fee"],
        "Convert all 24 obligations to USD; compute each of the 8 entities' net positions "
        "(receivables - payables); settlement = sum of positive nets; add each net payer's "
        "tiered fee (0.25% on first 50000 of payable + 0.15% above). Solver answer "
        f"{answer}.",
    )


# ---------------------------------------------------------------------------
# Q17  construction progress billing with change orders and retainage
# ---------------------------------------------------------------------------
def build_q17():
    CUTOFF = "2026-06-30"  # billing cutoff; CO must be approved on or before this date
    # (id, amount, status, approved_date)
    change_orders = [
        ("CO1", "45000.00", "approved", "2026-05-10"),
        ("CO2", "20000.00", "pending", "2026-06-01"),
        ("CO3", "-15000.00", "approved", "2026-06-20"),
        ("CO4", "30000.00", "approved", "2026-07-05"),
        ("CO5", "18000.00", "rejected", "2026-06-10"),
        ("CO6", "12000.00", "approved", "2026-06-30"),
        ("CO7", "9000.00", "approved", "2026-04-22"),
        ("CO8", "-6000.00", "approved", "2026-06-28"),
        ("CO9", "25000.00", "pending", "2026-06-15"),
        ("CO10", "14000.00", "approved", "2026-07-01"),
        ("CO11", "-3500.00", "approved", "2026-06-05"),
        ("CO12", "21000.00", "rejected", "2026-05-30"),
        ("CO13", "7500.00", "approved", "2026-06-12"),
    ]
    original = D("800000.00")
    revised = original + sum(
        (D(a) for _, a, s, ad in change_orders if s == "approved" and ad <= CUTOFF), D(0)
    )
    cost_to_date = D("438900.00")
    total_estimated_cost = D("710000.00")
    pct_complete = (cost_to_date / total_estimated_cost).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP)
    earned = hu(revised * pct_complete)
    retainage = hu(earned * D("0.10"))
    stored_materials = D("12000.00")  # billed in full this period, no retainage
    liquidated_damages = D("500.00") * D("3")  # 3 days behind schedule
    retainage_release = D("8000.00")  # prior retainage released this period (>50% milestone)
    prior_payments = D("380000.00")
    due = (earned - retainage + stored_materials - liquidated_damages
           + retainage_release - prior_payments)
    answer = money(due)

    prompt = (
        "You are preparing a construction progress billing (AIA-style) and must compute the "
        "current payment due. The billing cutoff date is 2026-06-30.\n\n"
        "RULES (apply in order)\n"
        "- Start from the original contract value of 800000.00.\n"
        "- Adjust the contract ONLY for change orders that are BOTH status 'approved' AND have "
        "an approved_date on or before the cutoff 2026-06-30 (add their amount; a negative "
        "amount is a deductive change order). Ignore any change order that is not 'approved' "
        "(e.g. 'pending' or 'rejected') and any change order approved after the cutoff. Note "
        "that on-or-before the cutoff includes a change order approved exactly on 2026-06-30. "
        "The result is the revised contract value.\n"
        "- Percent complete is measured by cost: percent complete = round-half-up(cost "
        "incurred to date / total estimated cost, 4), using cost incurred to date of 438900.00 "
        "and total estimated cost of 710000.00.\n"
        "- Work completed to date = round-half-up(revised contract * percent complete, 2).\n"
        "- Retainage withheld = round-half-up(work completed to date * 0.10, 2).\n"
        "- Materials stored on site this period of 12000.00 are billed at 100% and are NOT "
        "subject to retainage.\n"
        "- Liquidated damages: the project is 3 days behind schedule, assessed at 500.00 per "
        "day; deduct the total.\n"
        "- Retainage release: the project passed its 50%-complete milestone, so 8000.00 of "
        "previously withheld retainage is released back to the contractor this period; add it.\n"
        "- Amount earned this billing (net) = (work completed to date) - retainage + stored "
        "materials - liquidated damages + retainage release.\n"
        "- Less prior payments already received of 380000.00.\n"
        "- Current payment due = amount earned this billing (net) - prior payments.\n\n"
        "CHANGE ORDERS\n"
        + render_table(["id", "amount", "status", "approved_date"], change_orders)
        + "\n\nQUESTION\nWhat is the current payment due? " + FORMAT_2DP
    )
    add(
        "progress-billing-1", "Construction progress billing with retainage", prompt, answer,
        ["approved-and-dated-change-orders", "deductive-change-order", "rejected-co-excluded",
         "cutoff-boundary-inclusive", "cost-to-cost-percent-complete", "percent-complete-earned",
         "retainage-withholding", "stored-materials-exempt", "liquidated-damages",
         "retainage-release", "net-of-prior-billings"],
        "Revised contract = 800000 + sum of change orders that are BOTH approved AND dated on "
        "or before 2026-06-30 (CO1,CO3,CO6,CO7,CO8,CO11,CO13; CO2/CO9 pending, CO5/CO12 "
        "rejected, CO4/CO10 after cutoff). Pct=round(438900/710000,4)=0.6182. Earned = "
        "round(revised*pct,2); then -10% retainage +12000 stored -1500 LD +8000 release "
        f"-380000 prior. Solver answer {answer}.",
    )


# ---------------------------------------------------------------------------
# Q18  bond accrued interest across day-count conventions
# ---------------------------------------------------------------------------
def build_q18():
    # (bond, face, annual_rate, convention, last_coupon, settlement)
    bonds = [
        ("B1", "100000", "0.0500", "30/360", "2026-01-31", "2026-04-30"),
        ("B2", "250000", "0.0450", "ACT/365", "2026-02-15", "2026-06-27"),
        ("B3", "50000", "0.0600", "30/360", "2025-12-31", "2026-03-31"),
        ("B4", "180000", "0.0380", "ACT/360", "2026-03-15", "2026-06-27"),
        ("B5", "120000", "0.0440", "30/360", "2026-05-31", "2026-08-31"),
        ("B6", "200000", "0.0525", "ACT/365", "2026-01-31", "2026-04-15"),
        ("B7", "75000", "0.0610", "30/360", "2026-02-28", "2026-05-31"),
        ("B8", "300000", "0.0345", "ACT/360", "2026-04-30", "2026-07-31"),
        ("B9", "90000", "0.0480", "30/360", "2026-06-30", "2026-09-30"),
        ("B10", "150000", "0.0555", "ACT/365", "2026-03-31", "2026-06-30"),
        ("B11", "60000", "0.0420", "ACT/360", "2026-05-15", "2026-08-15"),
    ]
    # (bond, redemption_date, principal_paid)
    redemptions = [
        ("B1", "2026-03-31", "10000"),
        ("B1", "2026-05-31", "5000"),
        ("B2", "2026-04-15", "25000"),
        ("B4", "2026-06-01", "30000"),
        ("B5", "2026-07-31", "20000"),
        ("B5", "2026-08-31", "8000"),
        ("B6", "2026-03-01", "40000"),
        ("B7", "2026-04-15", "15000"),
        ("B8", "2026-06-15", "50000"),
        ("B8", "2026-07-31", "25000"),
        ("B10", "2026-05-31", "30000"),
        ("B10", "2026-06-30", "10000"),
        ("B11", "2026-07-01", "12000"),
    ]

    def days_30_360(d1, d2):
        y1, m1, day1 = d1.year, d1.month, d1.day
        y2, m2, day2 = d2.year, d2.month, d2.day
        if day1 == 31:
            day1 = 30
        if day2 == 31 and day1 == 30:
            day2 = 30
        return 360 * (y2 - y1) + 30 * (m2 - m1) + (day2 - day1)

    total = D(0)
    for bid, face, rate, conv, lc, st in bonds:
        d1 = datetime.strptime(lc, "%Y-%m-%d").date()
        d2 = datetime.strptime(st, "%Y-%m-%d").date()
        # current face = original face less principal redeemed strictly before settlement
        redeemed = sum(
            (D(p) for b, rd, p in redemptions if b == bid and rd < st), D(0)
        )
        cur_face = D(face) - redeemed
        if conv == "30/360":
            days = days_30_360(d1, d2)
            denom = "360"
        elif conv == "ACT/365":
            days = (d2 - d1).days
            denom = "365"
        else:  # ACT/360
            days = (d2 - d1).days
            denom = "360"
        accr = cur_face * D(rate) * D(days) / D(denom)
        total += hu(accr)
    answer = money(total)

    prompt = (
        "You are computing accrued interest on a bond portfolio as of each bond's settlement "
        "date. Each bond is a sinking-fund bond that may have redeemed principal before "
        "settlement; accrue on the CURRENT face.\n\n"
        "STEP 1 -- CURRENT FACE\n"
        "- A redemption reduces a bond's face ONLY if its redemption_date is STRICTLY BEFORE "
        "that bond's settlement date (a redemption dated exactly on the settlement date does "
        "not reduce the face). Current face = original face - sum of qualifying principal "
        "redemptions for that bond.\n\n"
        "STEP 2 -- DAY-COUNT CONVENTIONS\n"
        "- '30/360' (US): let the last-coupon date be (Y1,M1,D1) and settlement be (Y2,M2,D2). "
        "If D1 is 31, set D1 to 30. Then, if D2 is 31 AND D1 is now 30, set D2 to 30. "
        "Day count = 360*(Y2-Y1) + 30*(M2-M1) + (D2-D1). Accrued = current_face * annual_rate "
        "* daycount / 360.\n"
        "- 'ACT/365': day count = the actual number of calendar days from the last-coupon date "
        "to the settlement date. Accrued = current_face * annual_rate * daycount / 365.\n"
        "- 'ACT/360': day count = the actual number of calendar days from the last-coupon date "
        "to the settlement date (same day count as ACT/365), BUT divide by 360. Accrued = "
        "current_face * annual_rate * daycount / 360.\n"
        "- Compute each bond's accrued interest and round it half-up to 2 decimals, then sum "
        "across all bonds.\n\n"
        "BONDS\n"
        + render_table(
            ["bond", "face", "annual_rate", "convention", "last_coupon", "settlement"], bonds
        )
        + "\n\nREDEMPTIONS (principal repaid)\n"
        + render_table(["bond", "redemption_date", "principal_paid"], redemptions)
        + "\n\nQUESTION\nWhat is the total accrued interest across the portfolio? " + FORMAT_2DP
    )
    add(
        "accrued-interest-1", "Bond accrued interest across day-count conventions", prompt,
        answer,
        ["sinking-fund-current-face", "strictly-before-settlement", "30-360-day-count",
         "actual-365-day-count", "actual-360-day-count", "31st-day-adjustment",
         "per-bond-rounding"],
        "For each of the 11 bonds: current face = original - principal redeemed strictly before "
        "settlement (redemptions on the settlement date do not reduce face); accrue using the "
        "stated convention's day count and denominator; round per bond and sum. Solver answer "
        f"{answer}.",
    )


# ---------------------------------------------------------------------------
# Q19  retroactive volume rebate with tier-driving unit counting
# ---------------------------------------------------------------------------
def build_q19():
    # (line, category, gross_amount, line_discount_pct, returns_amount)
    lines = [
        ("L1", "standard", "120000.00", "0.10", "0.00"),
        ("L2", "standard", "90000.00", "0.05", "4500.00"),
        ("L3", "clearance", "40000.00", "0.20", "0.00"),
        ("L4", "premium", "250000.00", "0.00", "0.00"),
        ("L5", "standard", "70000.00", "0.00", "2000.00"),
        ("L6", "sample", "0.00", "0.00", "0.00"),
        ("L7", "premium", "180000.00", "0.05", "3000.00"),
        ("L8", "standard", "64000.00", "0.125", "1500.00"),
        ("L9", "clearance", "55000.00", "0.30", "0.00"),
        ("L10", "standard", "48000.00", "0.075", "0.00"),
        ("L11", "sample", "0.00", "0.00", "0.00"),
        ("L12", "premium", "95000.00", "0.10", "5000.00"),
        ("L13", "standard", "132000.00", "0.15", "8000.00"),
        ("L14", "clearance", "27000.00", "0.40", "0.00"),
        ("L15", "standard", "58500.00", "0.04", "2500.00"),
        ("L16", "premium", "210000.00", "0.08", "0.00"),
    ]
    eligible_net = D(0)
    premium_net = D(0)
    for _, cat, gross, disc, ret in lines:
        net = hu(D(gross) * (D(1) - D(disc))) - D(ret)
        if cat not in ("clearance", "sample"):
            eligible_net += net
        if cat == "premium":
            premium_net += net
    # marginal brackets on eligible net spend
    brackets = [(D("100000"), D("0.02")), (D("300000"), D("0.04")), (None, D("0.06"))]
    bonus = D("0.01") if premium_net >= D("200000.00") else D("0.00")
    rebate = D(0)
    lower = D(0)
    remaining = eligible_net
    for upper, rate in brackets:
        if remaining <= 0:
            break
        span = (upper - lower) if upper is not None else remaining
        take = min(remaining, span)
        rebate += take * (rate + bonus)
        remaining -= take
        lower = upper if upper is not None else lower
    rebate = hu(rebate)
    rebate = min(rebate, D("100000.00"))
    answer = money(rebate)

    prompt = (
        "You are computing an annual volume rebate for a customer.\n\n"
        "RULES (apply in order)\n"
        "- Category semantics: 'clearance' and 'sample' lines are NOT eligible for rebate; all "
        "other categories are eligible.\n"
        "- Each line's net amount = round-half-up(gross_amount * (1 - line_discount), 2) minus "
        "the line's returns_amount.\n"
        "- Total eligible net = the sum of the net amounts of the ELIGIBLE lines.\n"
        "- The rebate is computed on total eligible net using MARGINAL brackets: the first "
        "100000.00 of eligible net earns 2%; the portion from 100000.01 to 300000.00 earns 4%; "
        "the portion above 300000.00 earns 6%.\n"
        "- Premium incentive: if the total net amount of the 'premium' category alone is at "
        "least 200000.00, add 1 percentage point to EVERY bracket rate (i.e. 3% / 5% / 7%).\n"
        "- Rebate = the sum of the marginal-bracket amounts, rounded half-up to 2 decimals, "
        "but capped at a maximum of 100000.00.\n\n"
        "ORDER LINES\n"
        + render_table(
            ["line", "category", "gross_amount", "line_discount", "returns_amount"],
            lines,
        )
        + "\n\nQUESTION\nWhat is the rebate owed to the customer? " + FORMAT_2DP
    )
    add(
        "volume-rebate-1", "Volume rebate with marginal brackets on eligible spend", prompt,
        answer,
        ["clearance-and-sample-excluded", "per-line-net-of-returns", "marginal-spend-brackets",
         "premium-mix-bonus-on-all-brackets", "rebate-cap"],
        "Net each of the 16 lines (round discount, subtract returns); sum the eligible "
        "(non-clearance, non-sample) lines; if premium-category net >= 200000 add 1pp to each "
        "bracket (3/5/7); apply marginal brackets (100000/300000) and cap at 100000. Solver "
        f"answer {answer}.",
    )


# ---------------------------------------------------------------------------
# Q20  multi-line telecom bill: proration, rollover, tiered overage, discount
# ---------------------------------------------------------------------------
def build_q20():
    # (line, data_gb, full_cycle, intl_minutes, device_installment)
    lines = [
        ("L1", 22, "yes", 40, "0.00"),
        ("L2", 14, "yes", 0, "18.00"),
        ("L3", 9, "no", 0, "0.00"),  # activated on day 16 of a 30-day cycle
        ("L4", 7, "yes", 100, "0.00"),
        ("L5", 11, "yes", 0, "0.00"),
        ("L6", 18, "yes", 25, "12.50"),
        ("L7", 6, "no", 60, "0.00"),  # activated on day 16 of a 30-day cycle
        ("L8", 13, "yes", 0, "9.99"),
        ("L9", 20, "yes", 15, "0.00"),
        ("L10", 8, "yes", 200, "22.00"),
    ]
    per_line_base = D("30.00")
    cycle_days = 30
    new_line_active_days = 15  # day 16..30 inclusive
    base = D(0)
    discount = D(0)
    intl_minutes = 0
    devices = D(0)
    for line, gb, full, intl, dev in lines:
        if full == "yes":
            base += per_line_base
            discount += D("5.00")
        else:
            base += hu(per_line_base * D(new_line_active_days) / D(cycle_days))
        intl_minutes += intl
        devices += D(dev)
    base_after_discount = base - discount
    autopay = hu(base_after_discount * D("0.10"))
    base_net = base_after_discount - autopay
    total_gb = sum(gb for _, gb, _, _, _ in lines)
    allowance = 30 + 5  # 30 GB plan + 5 GB rolled over
    overage_gb = max(total_gb - allowance, 0)
    tier1 = min(overage_gb, 8)
    tier2 = max(overage_gb - 8, 0)
    overage = hu(D(tier1) * D("8.00") + D(tier2) * D("12.00"))
    international = hu(D(intl_minutes) * D("0.15"))
    pretax = base_net + overage + international
    tax = hu(pretax * D("0.08"))
    answer = money(pretax + tax + devices)

    prompt = (
        "You are generating a monthly bill for a 5-line shared mobile plan.\n\n"
        "PLAN AND RULES (apply in order)\n"
        "- Each line has a base charge of 30.00 per 30-day cycle. A line that was active the "
        "FULL cycle is billed the full 30.00; a line activated mid-cycle is billed "
        "round-half-up(30.00 * active_days / 30, 2). Each mid-cycle line below (the lines "
        "marked active_full_cycle = no, namely L3 and L7) was activated on day 16 of the "
        "30-day cycle, so each was active for 15 days (days 16 through 30 inclusive).\n"
        "- Multi-line discount: 5.00 off for each line that was active the full cycle. A "
        "line activated mid-cycle does NOT receive this discount.\n"
        "- Autopay discount: after the multi-line discount, take an additional 10% off the "
        "base subtotal: autopay discount = round-half-up(base-after-multi-line-discount * 0.10, "
        "2). This applies ONLY to the base subtotal, not to overage, international, tax, or "
        "device charges.\n"
        "- Data is pooled across all lines. The plan includes 30 GB; an additional 5 GB rolled "
        "over from last month, so the allowance this cycle is 35 GB.\n"
        "- Overage is charged on total pooled usage above the allowance, in tiers: the first 8 "
        "GB of overage at 8.00 per GB; any overage beyond that at 12.00 per GB. (All usage "
        "values are whole GB.)\n"
        "- International calling is charged at 0.15 per international minute, summed across all "
        "lines: international charge = round-half-up(total international minutes * 0.15, 2).\n"
        "- Pre-tax total = (base subtotal after multi-line AND autopay discounts) + overage "
        "charge + international charge.\n"
        "- Tax = round-half-up(pre-tax total * 0.08, 2), added to the pre-tax total.\n"
        "- Device installments are billed AFTER tax and are NOT taxed: add the sum of the "
        "device_installment column to the post-tax total.\n\n"
        "LINES\n"
        + render_table(
            ["line", "data_gb", "active_full_cycle", "intl_minutes", "device_installment"],
            lines,
        )
        + "\n\nQUESTION\nWhat is the total bill? " + FORMAT_2DP
    )
    add(
        "telecom-rating-1", "Multi-line telecom bill with proration and tiered overage",
        prompt, answer,
        ["midcycle-base-proration", "discount-only-full-cycle-lines", "autopay-discount-on-base",
         "rollover-allowance", "pooled-tiered-overage", "international-usage",
         "tax-on-base-plus-overage", "untaxed-device-installment"],
        "Sum base over 10 lines (full lines 30.00; L3 and L7 prorated to 15.00); subtract 5.00 "
        "per full-cycle line, then 10% autopay on that base; add pooled tiered overage on "
        "(total GB - 35) and international (total intl min * 0.15); tax 8% on the pre-tax "
        f"total; add untaxed device installments. Solver answer {answer}.",
    )


for fn in [build_q1, build_q2, build_q3, build_q4, build_q5, build_q6,
           build_q7, build_q8, build_q9, build_q10, build_q11, build_q12,
           build_q13, build_q14, build_q15, build_q16, build_q17, build_q18,
           build_q19, build_q20]:
    fn()

doc = {
    "category": "ops-reconciliation",
    "description": (
        "Self-contained, multi-step back-office tasks (expense audits, AR reconciliation, "
        "payroll, inventory/FIFO, commissions, proration, bank reconciliation, loan "
        "amortization, shipping optimization, cohort analytics, SLA penalties, payroll tax) "
        "that each funnel to a single deterministic, exactly-checkable number. Ordered "
        "easiest to hardest. Every answer is produced by the reference solver in "
        "scripts/generate_ops_reconciliation.py; data tables are rendered from the same data "
        "the solver consumes, and all rounding/inclusivity/ordering/tie-breaks are pinned in "
        "the prompt so exactly one answer is correct. Runs on the existing harness via "
        "`python3 main.py --questions questions/ops-reconciliation.json`."
    ),
    "prompt_template": "{task}\n\nReturn exactly JSON with one key \"answer\", whose value is the answer as a string formatted exactly as specified above.",
    "questions": QUESTIONS,
}

OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {len(QUESTIONS)} questions to {OUT}")
for q in QUESTIONS:
    print(f"  {q['id']:18} {q['answer']:>12}   {q['title']}")
