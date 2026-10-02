# Policy Vault — Demo Script (3 minutes)

> Rule: we build only what this script needs. If a feature is not in this script, it waits until after 12 October.

**Fictional company:** Kestrel Components Pvt Ltd, a mid-size manufacturer.
**Situation:** R. Iyer configured the expense system in 2019 and retired on 31 Dec 2025 after two verbal handover sessions and no written documentation (ticket TKT-1202). A new admin, Priya, has inherited the system.

---

## Scene 1 — The pain (0:00–0:30)

**On screen:** the retirement ticket TKT-1202: "No written documentation produced."

**Voice-over:**
"Every company has one. The person who configured the system years ago, and is the only one who knows why it works the way it does. When they leave, their knowledge leaves with them. Tools like Confluence can only search what someone wrote down. The most important knowledge was never written down."

## Scene 2 — Drift detection (0:30–1:30) ⭐ the wow moment

**Action:** Priya uploads three things: the policy PDF, the configuration export, the ticket history. She clicks **Scan**.

**On screen:** a drift report with 4 findings, each showing policy value vs configured value, the risk, and the evidence.

| Finding | Policy says | System does | Why (found by the Vault) |
|---|---|---|---|
| Domestic meal limit | ₹2,500/day | ₹4,000/day | Temporary offsite increase in 2021 (TKT-1042), never reverted |
| Receipt required above | ₹500 | ₹2,000 | No record found → **ask the expert** |
| Metro hotel cap | ₹8,000/night | ₹10,000/night | Policy v3.2 lowered it in 2025 (TKT-1177); system never updated |
| Controller approval above | ₹50,000 | ₹1,00,000 | Raised in 2022 "pending policy update" (TKT-1098) that never happened |

**Voice-over:**
"In seconds, it finds four places where the written policy and the live system disagree, and for three of them it finds *why*, buried in five-year-old tickets. The meal limit was raised for one sales offsite in 2021 and has been costing money ever since."

**Also show:** "12 policy rules checked: 4 drifts, 8 aligned." Proof there are no false alarms.

## Scene 3 — The expert interview (1:30–2:15)

**On screen:** the Gap Finder lists rules with no explanation anywhere: R-012, R-013, R-014, and drift D2.

**Action:** the Vault interviews R. Iyer about R-014 (vehicle registration field hidden). The key moment is the agent connecting the dots on its own:

> **Vault:** "The vehicle registration field on the mileage form was hidden on 6 Sep 2021. Three days earlier, TKT-1135 reported mileage lines failing ERP posting with 'field length exceeded'. Are these related?"
>
> **R. Iyer:** "Yes. The field overflowed a 10-character field in the ERP interface. I hid it as a quick fix…"

**On screen:** a new **Decision Record** appears: rule, reason, decided by, date, linked ticket, risk if removed = HIGH, verified by expert ✅.

**Voice-over:** "It doesn't just search knowledge. It creates knowledge that never existed in writing."

## Scene 4 — Ask why (2:15–2:45)

**Action:** Priya types: *"Can I show the vehicle registration field again? Fleet management wants it."*

**Vault answers:** "Not yet. It was hidden in Sept 2021 because it broke ERP posting (TKT-1135). If you re-enable it before the ERP interface mapping is fixed, mileage payments will fail again. Source: interview with R. Iyer, verified."

**Voice-over:** "Without the Vault, Priya would have turned it back on and broken employee payments."

## Scene 5 — Close (2:45–3:00)

**(Stretch, only if built)** 15 seconds: switch to the Inventory pack, same engine, catches a safety-stock drift.

**Closing line:** "Policy Vault: the reasons behind your systems, captured before they walk out the door."

---

## Impact claims we can prove in the demo

- 4 of 4 planted drifts detected, 0 false alarms across 12 checkable rules (measured against `ground_truth.json`)
- 3 of 4 root causes found automatically from tickets
- 4 undocumented decisions turned into verified Decision Records
- Time to find a root cause: minutes instead of the "two weeks of emailing former colleagues" it takes today
