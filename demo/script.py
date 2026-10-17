"""Narration for the demo video, one entry per line, in playback order.

key      -> used by record.py to start the line at the right moment
say      -> what the voice speaks (written for the ear: IDs and amounts spelled the way they sound)
caption  -> the subtitle shown on screen while it plays

Edit the words here, then re-run demo/voice.py (only changed lines are re-synthesised).
"""

LINES = [
    ("intro",
     "Every company has one person who configured its systems years ago, and is the only one who knows why they work "
     "the way they do. When that person retires, the knowledge walks out of the door with them.",
     "When the expert who configured the system leaves, the reasons leave too."),
    ("meet",
     "Meet Priya. She has just inherited the expense system at Kestrel Components. Her predecessor, R. Kumar, retired "
     "with two verbal handover sessions and no written documentation. This is Policy Vault, built on Gemini, "
     "Vertex A.I. Search, Firestore and Cloud Run.",
     "Priya inherits the expense system. R. Kumar retired with no written documentation."),
    ("scan",
     "Priya starts with a scan. Gemini reads the policy P.D.F. directly. Then plain Python code compares every policy "
     "value with the live configuration, because A.I. should read, and code should compare. Finally, Gemini searches "
     "thirteen old tickets for the root cause of each mismatch.",
     "Gemini reads the policy. Code compares. Gemini searches the tickets for root causes."),
    ("results",
     "Twelve rules checked. Four drifts, eight aligned, and zero false alarms. The domestic meal limit is four thousand "
     "rupees a day in the system, but the written policy says two thousand five hundred.",
     "12 rules checked: 4 drifts, 8 aligned, 0 false alarms."),
    ("evidence",
     "One click shows the evidence side by side. The policy sentence, the live configuration, and ticket ten forty-two: "
     "a temporary increase for a 2021 sales offsite that was never reverted. It has been overpaying on every domestic "
     "trip since.",
     "Evidence: policy sentence, live configuration and ticket TKT-1042, side by side."),
    ("rootcauses",
     "Three of the four root causes were found automatically in the ticket history. The fourth, the receipt threshold, "
     "has no record anywhere. So it goes to the expert.",
     "3 of 4 root causes found in tickets. The 4th goes to the expert."),
    ("ask_before",
     "Now fleet management asks Priya to show the vehicle registration field again. Before changing anything, she asks "
     "the Vault why it was hidden.",
     "Before changing anything, Priya asks the Vault why."),
    ("ask_before_result",
     "Nobody ever wrote down the reason. So the Vault says so, honestly, instead of guessing.",
     "No recorded rationale. The Vault says so instead of guessing."),
    ("gaps",
     "The gap finder lists every rule that nobody can explain. Knowledge coverage today is thirteen of seventeen rules.",
     "Gap finder: rules nobody can explain. Coverage: 13 of 17."),
    ("interview",
     "Policy Vault interviews the retired expert. It noticed that the field was hidden three days after ticket "
     "eleven thirty-five reported E.R.P. posting failures, and it asks whether the two are related.",
     "The Vault connects the hidden field to ERP ticket TKT-1135, three days earlier."),
    ("expert",
     "R. Kumar confirms it. The registration number overflowed a ten-character field in the E.R.P. interface, so he "
     "hid it as an emergency fix.",
     "The expert confirms: it overflowed a 10-character ERP field."),
    ("record",
     "Gemini turns the answer into a structured Decision Record. What, why, who decided, when, the linked ticket, and "
     "the risk if removed, which is high.",
     "A Decision Record: what, why, who, when, sources, risk if removed."),
    ("saved",
     "It is saved only after a human verifies it, to Firestore, and indexed in Vertex A.I. Search. Coverage rises to "
     "fourteen of seventeen.",
     "Verified by a human. Saved to Firestore. Coverage rises to 14 of 17."),
    ("ask_after",
     "Priya asks the same question again.",
     "The same question, asked again."),
    ("ask_after_result",
     "This time the answer is clear. Not yet. Turning the field back on before the E.R.P. mapping is fixed would break "
     "mileage payments again. And every claim cites the Decision Record and the ticket.",
     "Not yet: it would break ERP posting. Sources cited."),
    ("inventory",
     "The same engine works for any domain, with no code changes. Here is the inventory pack. It finds class A safety "
     "stock set to thirty days of cover against a policy of fifteen, traced to a 2021 semiconductor shortage ticket "
     "that was never reversed.",
     "Same engine, new domain: inventory. Safety stock 30 days vs a policy of 15."),
    ("close",
     "Other tools search what was written down. Policy Vault captures what was never written, and checks policy "
     "against reality. Policy Vault. The reasons behind your systems, captured before they walk out of the door.",
     "Policy Vault: the reasons behind your systems, captured before they walk out the door."),
]

KEYS = [k for k, _, _ in LINES]
SAY = {k: s for k, s, _ in LINES}
CAPTION = {k: c for k, _, c in LINES}
