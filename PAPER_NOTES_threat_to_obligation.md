# Paper notes: threat-to-obligation (do not edit LBRO_IEEE_Paper.tex from this feature)

## Safe claims

- LBRO implements a **rule-driven pipeline** from ML attack label → curated MITRE technique links → data category vocabulary → fictional asset residency counts → declarative legal rule packs with citations and `verification_status`.
- Outputs are **suggestions** with analyst accept/dismiss; notifications are not auto-dispatched from inferred rows.
- Knowledge files are versioned and validated at startup.

## Do not claim

- That technique mappings are learned or statistically validated (they are curated heuristics from flow metadata).
- That legal deadlines or triggers are counsel-approved (`legal_review_status: unreviewed` by default).
- Any accuracy percentage for obligation inference.

## Evaluation wording

Describe qualitative scenarios (credential attack + auth asset → GDPR/DPDP evaluation; DoS → no breach-notification trigger) without implying legal correctness.
