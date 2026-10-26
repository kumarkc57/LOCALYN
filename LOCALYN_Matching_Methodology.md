# LOCALYN — BBMP ↔ BTP Matching Methodology

## 1. Validated BBMP data
- BBMP 2023: 119,140 records
- BBMP 2024: 207,016 records
- 31 observed BBMP categories across the combined 2023–2024 data
- 198 ward names in each year
- Core fields: Complaint ID, Category, Sub Category, Grievance Date, Ward Name, Grievance Status, Staff Remarks, Staff Name

## 2. Cross-source event families
Use only mappings marked Direct or Probable/Ambiguous in the crosswalk.
Primary validated families:
- ROAD_DAMAGE → BTP `pot_holes`
- WATERLOGGING → BTP `water_logging`
- TREE_FALL → BTP `tree_fall`
- CONSTRUCTION / ROAD_WORK / ROAD_OBSTRUCTION → BTP `construction` (probable; requires validation)

## 3. Candidate generation
A BBMP complaint and BTP event become a candidate only when:
1. Their dates are compatible.
2. Their normalized event families are compatible.
3. The BTP coordinate falls inside the same BBMP ward as the complaint, after point-in-polygon mapping.
4. The mapping is Direct/Probable/Ambiguous; `Do not map` entries are not automatically matched.

Because BBMP is ward-level while BTP is point-level, do not use exact point distance between the two sources as the primary spatial rule.

## 4. Matching score
For each candidate pair, calculate separate features:
- temporal compatibility
- ward compatibility
- semantic/category compatibility
- source/mapping strength
- optional text similarity from BBMP Sub Category + Staff Remarks and BTP description/location fields

Do not freeze feature weights before the gold set is annotated.

## 5. Gold set
Create manually labelled candidate pairs:
- positive = same real-world event
- negative = different events
- uncertain = cannot decide from available evidence

Stratify the sample across strong matches, medium matches, hard negatives, different wards, and different dates.

## 6. Baselines
Compare:
1. same date + same ward
2. same date + same ward + same normalized category
3. LOCALYN matching model using temporal + spatial + semantic evidence

Report precision, recall and F1.

## 7. Clustering and CHEF
Entity resolution comes first:
BBMP/BTP observations → candidate matching → matched pairs → clusters → canonical event.

CHEF is then computed on the canonical event as an explainable evidence-confidence score. Raw BTP records from the same source should not be counted as independent corroborating sources; source diversity matters.
