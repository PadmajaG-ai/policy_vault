# Policy Vault — Demo Script (3 minutes)

> Rule: we build only what this script needs. If a feature is not in this script, it waits until after 12 October.

**Fictional company:** Kestrel Components Pvt Ltd, a mid-size manufacturer.
**Situation:** R. Kumar configured the expense system in 2019 and retired on 31 Dec 2025 after two verbal handover sessions and no written documentation (ticket TKT-1202). A new admin, Priya, has inherited the system.

---

## Scene 1 — The pain (0:00–0:30)

**On screen:** the retirement ticket TKT-1202: "No written documentation produced."

**Voice-over:**
"Every company has one. The person who configured the system years ago, and is the only one who knows why it works the way it does. When they leave, their knowledge leaves with them. Tools like Confluence can only search what someone wrote down. The most important knowledge was never written down."

## Scene 2 — Drift detection (0:30–1:30) ⭐ the wow moment

**Action:** the Expense pack is loaded: the policy PDF, the configuration export (17 rules) and the ticket history (13 tickets). Priya clicks **Scan**.

**On screen:** three live steps tick off with timings: *Gemini reads the policy PDF* → *Code compares policy values with the live configuration* → *Gemini searches the ticket history for root causes*. Then the drift report with 4 findings, each showing policy value vs configured value, the risk, and the evidence.

| Finding | Policy says | System does | Why (found by the Vault) |
|---|---|---|---|
| Domestic meal limit | ₹2,500/day | ₹4,000/day | Temporary offsite increase in 2021 (TKT-1042), never reverted |
| Receipt required above | ₹500 | ₹2,000 | No record found → **ask the expert** |
| Metro hotel cap | ₹8,000/night | ₹10,000/night | Policy v3.2 lowered it in 2025 (TKT-1177); system never updated |
| Controller approval above | ₹50,000 | ₹1,00,000 | Raised in 2022 "pending policy update" (TKT-1098) that never happened |

**Voice-over:**
"In seconds, it finds four places where the written policy and the live system disagree, and for three of them it finds *why*, buried in five-year-old tickets. The meal limit was raised for one sales offsite in 2021 and has been costing money ever since."

**Also show:** "12 policy rules checked: 4 drifts, 8 aligned." Proof there are no false alarms.

**Click** the meal-limit row: the evidence panel shows the policy sentence (section 5.1), the live configuration (Meals > Limits, changed 12 Mar 2021 by anil) and the full text of TKT-1042 ("Please revert to INR 2,500 after 30 June 2021") side by side.

## Scene 3 — The expert interview (1:30–2:15)

**Before:** Priya asks *"Can I show the vehicle registration field again?"* The Vault answers **"No recorded rationale found."** Nobody knows.

**On screen:** the Gap Finder lists rules with no explanation anywhere: R-012, R-013, R-014, and drift D2. The coverage meter reads **13 of 17 rules have a known reason (76%)**.

**Action:** the Vault interviews R. Kumar about R-014 (vehicle registration field hidden). The key moment is the agent connecting the dots on its own:

> **Vault:** "The vehicle registration field on the mileage form was hidden on 6 Sep 2021. Three days earlier, TKT-1135 reported mileage lines failing ERP posting with 'field length exceeded'. Are these related?"
>
> **R. Kumar:** "Yes. The field overflowed a 10-character field in the ERP interface. I hid it as a quick fix…"

**On screen:** a new **Decision Record** appears: rule, reason, decided by, date, linked ticket, risk if removed = HIGH, verified by expert ✅. The coverage meter moves to **14 of 17**.

**Voice-over:** "It doesn't just search knowledge. It creates knowledge that never existed in writing."

## Scene 4 — Ask why (2:15–2:45)

**After:** Priya asks the same question again: *"Can I show the vehicle registration field again? Fleet management wants it."*

**Vault answers:** "Not yet. It was hidden in Sept 2021 because it broke ERP posting (TKT-1135). If you re-enable it before the ERP interface mapping is fixed, mileage payments will fail again. Source: interview with R. Kumar, verified."

**Voice-over:** "Without the Vault, Priya would have turned it back on and broken employee payments."

## Scene 5 — Close (2:45–3:00)

15 seconds: click **Inventory** in the header. Same engine, no code changes, a different domain: Scan finds class A safety stock at 30 days of cover against a policy of 15, traced to a 2021 semiconductor-shortage ticket (TKT-2031) that was never reverted, plus a slow-moving threshold nobody can explain.

**Voice-over:** "Same engine, new domain. Expense today, inventory, procurement and finance tomorrow."

**Closing line:** "Policy Vault: the reasons behind your systems, captured before they walk out the door."

---

## Impact claims we can prove in the demo

- 4 of 4 planted drifts detected, 0 false alarms across 12 checkable rules (measured against `ground_truth.json`)
- 3 of 4 root causes found automatically from tickets
- 4 undocumented decisions turned into verified Decision Records; coverage 13 of 17 → 17 of 17
- Second domain (inventory) on the same engine: 2 of 2 drifts, 0 false alarms across 9 checkable rules (verify with `pytest -m live` before claiming)
- Time to find a root cause: minutes instead of the "two weeks of emailing former colleagues" it takes today
