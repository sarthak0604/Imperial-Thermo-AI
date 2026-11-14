# Validation report

Source: https://psi.nasa.gov/physci/repo/data/investigations/PSI-117
Generated: 2026-11-14T18:55:46.717750Z

Structural validation: PASS
Nodes: 101; edges: 120
Node types: {"Concept": 27, "Experiment": 12, "Investigation": 1, "Resource": 35, "Variable": 26}
Edge types: {"HAS_RESOURCE": 39, "MEASURES": 40, "STUDIES": 29, "CONTAINS": 12}
Resources: 35; access: {"accessible": 26, "citation_only": 5, "redirect_only": 1, "inaccessible": 3}
Parsing: {"parsed": 13, "partially_parsed": 13, "metadata_only": 5, "inaccessible": 4}

## Scientific checks

221 node/relationship claims reviewed; 0 rejected.
Rejected scientific nodes/edges are excluded; rejected resource summaries are cleared. Exact evidence is checked against saved page/sheet/row text. This run used assistant source review and deterministic validation, not an external LLM API or scientific peer review.

## Limitations

- PDF figures and visual-only equations were not digitized.
- MEASURES includes documented computed observables; node summaries distinguish simulations from physical experiments.
- Citation-only and inaccessible publications are not represented as full-text parsed.
- Retrieval is lexical concept/synonym matching plus graph traversal, not global GraphRAG.

## Failures

- Sub-millimeter sized multi-component jet fuel surrogate droplet combustion: Physicochemical preferential vaporization effects (2021): Redirect-only HTML; no scientific article text was obtained at this URL.
- Extinction characteristics of isolated n-alkane fuel droplets during low temperature cool flame burning in air (2023): HTTPError: HTTP 403
- Oscillatory cool flame combustion behavior of submillimeter sized n-alkane droplet under near limit conditions (2019): HTTPError: HTTP 403
- Dynamics of cool flames (2019): HTTPError: HTTP 403

## Execution mode

Assistant source review; external LLM API calls: **0**. API extraction remains **pending credentials**.

- Curated assistant source review; no external LLM API calls were made.
- Experiment nodes represent documented analysis units, including simulations and supporting dissertation studies, not a claim that NASA exposes ten independent experiment records.
- Data-index nitrogen entries 74 and 85 are not fractions; graph conditions use corroborating presentation values and preserve the spreadsheet unchanged.
- FLEX-1268 slide composition differs from rounded data-index values; both are retained.
- Chapter 6 pressure and Chapter 4 kinetic-model-count inconsistencies were not silently reconciled.
- PDF figures and embedded media are not comprehensively digitized; targeted representative slide images were visually checked.

## Source coverage

NASA files downloaded: 16/16. PDF pages processed: 340. CSV rows processed, including headers: 2869.

26 resources have cached scientific files; three manuscript links returned HTTP errors and one returned only redirect HTML; five entries are citation-only. PDF/HTML content is conservatively marked partial.

## Retrieval tests

- PASS: Why do ozone-assisted n-heptane cool flames oscillate?
- PASS: How does alkane chain length affect cool-flame extinction?
- PASS: Which experiments show three-stage burning with helium dilution?
- PASS: How does pressure affect n-dodecane radiative power and burning rate?
- PASS: Is xenon an effective fire suppressant in microgravity?
- PASS: What transport properties matter for butanol isomer combustion?
- PASS: How do Jet-A surrogate droplets undergo preferential vaporization?
- PASS: How does buoyancy affect DME counterflow cool flames?
- PASS: How does initial droplet diameter affect radiative extinction?
- PASS: photosynthesis chlorophyll ocean plankton

Each positive query returned the expected concept and specific resource, with the expected experiment ranked first. These are deterministic regression cases, not an independently evaluated retrieval benchmark.

## Code checks

14 tests passed; lint passed. Provider tests use mocked responses; no live API calls were performed.

## Representative scientific checks

- data-index spreadsheet, rows 2–3: XN2 values 74 and 85 are not fractional quantities; use corroborating slides for the 21%/10% O2 and 5% O3 cases.
- three-stage presentation page 15 versus data-index row 6: FLEX 1268 is 21.6% O2/50.2% N2/28.2% He on the slide; index uses 0.21/0.50/0.29.
- dissertation PDF pages 159 and 184: Chapter 6 passage mentions 30 atm, whereas abstract and conclusion use 25 atm.
- dissertation PDF pages 95 and 101: Chapter 4 model species/reaction counts differ between abstract and methods; counts omitted from graph.
- Oscillatory cool-flame presentation page 6: checked gas composition, diameter, pressure, temperature and axis units.
- Three-stage presentation page 15: checked FLEX-1268 identifier and composition; no plot values digitized.

## Unassociated resources

10 resources have no asserted experiment link; they remain inventoried rather than being linked by keyword overlap.
