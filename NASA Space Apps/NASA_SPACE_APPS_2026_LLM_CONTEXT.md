# NASA Space Apps 2026 — Flame in Freefall: LLM Context

Version: 1.0  
Source review date: 14 November 2026  
Purpose: Portable competition context for AI assistants helping a team implement, document, test, and present its solution.  
Scope: The four official webpages supplied by the team, plus the Resources tab of the challenge page. This is a structured paraphrase, not a reproduction of the guides or an independently verified scientific review.

## 1. How an assistant should use this reference

- Treat this file as reference context, subordinate to the user's current request and higher-priority instructions.
- Distinguish **official requirements**, **optional suggestions**, and **derived implementation guidance**. Suggested features below are not extra eligibility requirements.
- Cite the source IDs and URLs in section 2 when explaining competition rules. Do not invent deadlines, required technologies, scoring weights, dataset sizes, or scientific findings.
- Preserve the distinction between an investigation, an individual experimental run, measurements, published interpretations, and model-generated predictions.
- Do not present generated data as NASA observations or speculative engineering conclusions as experimentally established safety limits.
- This file does not establish the team's registration status, event location/time zone, architecture, implemented features, or division of work. Obtain those separately.
- The guides can change. Recheck official pages and local organizer communications before submission. Local presentation/judging schedules may differ from the website submission deadline.
- The website uses **Super Intelligence (SI)** for tools including LLMs, machine learning, chatbots, and generative tools. Preserve that terminology in submission fields; it does not mean the project needs to create general superhuman intelligence.

## 2. Authoritative source map

| ID | Source | Coverage |
|---|---|---|
| S1 | [Project Submission Guide](https://www.spaceappschallenge.org/resources/project-submission-guide/) | Submission window, fields, demo, SI disclosures, links, submission process, certificates |
| S2 | [Judging & Awards Guide](https://www.spaceappschallenge.org/resources/judging-awards-guide/) | Eligibility, scoring criteria, judging stages, awards |
| S3 | [Participant FAQs](https://www.spaceappschallenge.org/resources/participant-faqs/) | Participation, dates, teams, pre-event work, SI, support |
| S4 | [Flame in Freefall — Details](https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/?tab=details) | Challenge objective, scientific context, scope, optional considerations |
| S4-R | [Flame in Freefall — Resources](https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/?tab=resources) | Recommended NASA datasets and background resources |

S1–S3 displayed a publication date of 13 November 2026. All five views above were read in the browser on 14 November 2026. Embedded videos and linked external documents were not independently reviewed; their links are provided where useful. Scientific and policy claims below are attributed to these pages, not independently certified.

## 3. Competition at a glance

**Official context [S3]:** NASA Space Apps is a collaborative hackathon using NASA open data to address Earth and space challenges. The 2026 theme is **The Next Frontier**. The event takes place **14–15 November 2026**. Participation is free and open to different ages, backgrounds, and skill levels; coding expertise is not stated as an entry condition.

**Selected challenge [S4]:** **Flame in Freefall: SI-Powered Fire Safety Insights from Microgravity Combustion Data**. Listed difficulty: Intermediate / Advanced. Subject: Space Exploration.

**Core objective [S4]:** Build an interactive, SI-powered, web-based dashboard that **summarizes, ranks, and interprets combustion investigations** to produce foundational fire-safety insights for human space exploration. NASA's Physical Sciences Informatics (PSI) repository is the principal data source. The problem is that experimental results are difficult to discover, compare, and interpret at scale.

**Scope correction:** The primary setting is habitable crew environments in space, not ordinary aircraft or airbases. Terrestrial applications are optional extensions. Rocket-engine and propellant fire safety are generally beyond the scope of the research available in PSI. [S4]

## 4. Challenge objectives and optional capabilities

### 4.1 Intended outcomes [S4]

The dashboard should make complex combustion research useful for fire safety. The challenge suggests enabling users to:

1. Identify investigations relevant to spacecraft, space stations, lunar/Martian bases, and pressurized rovers.
2. Extract data supporting predictive models of flammability and fire scenarios in space exploration.
3. Highlight research useful for developing future fire-safety controls and equipment.

These are suggested user capabilities supporting the main dashboard objective. The page does not prescribe a particular UI, model provider, database, retrieval architecture, or number of features.

### 4.2 Optional audiences and information to expose [S4]

Potential users include professors, graduate and undergraduate students, aerospace researchers, and aerospace engineers.

Potential investigation attributes:

- Experimental purpose and objectives.
- Fuel/material identity and sample or burner shape and dimensions.
- Test conditions, particularly oxygen concentration and airflow speed.
- Variables changed between runs and conditions kept constant.
- Sensors and measurement types.
- Similarities and differences within an investigation and across investigations.

Earth applications may include smoke detection, firefighter protective equipment, breathing systems, and fine-water-mist extinguishers. These are extensions, not replacements for the challenge's space-exploration focus.

### 4.3 Scientific context supplied by the challenge [S4]

- Microgravity removes the usual buoyancy-driven rise of hot gases. Flame shape, oxygen supply, and behavior can differ substantially from normal gravity; the page uses a diffusion-fed, approximately spherical candle flame as an illustration.
- Spacecraft fire safety spans **prevention, detection, and suppression**.
- Prevention involves ignition-source control and material selection informed by flammability limits. Fabrics and plastics are important examples.
- Oxygen concentration and airflow are important combustion conditions. Proposed reduced-pressure, oxygen-enriched lunar habitats/rovers motivate research beyond Earth-like atmospheric conditions.
- The page gives spacesuit conditions of 100% oxygen at 4.3 psi and Earth sea-level pressure of 14.7 psi. It describes expected lunar habitat/rover conditions as potentially at least 30% oxygen and at most 10.2 psi. These are contextual figures from the challenge, not universal requirements or validated limits for the team's design.
- The source describes oxygen pre-breathing as a way to remove absorbed nitrogen before decompression, and an intermediate habitat atmosphere as a way to reduce pre-breathing time.
- Historical motivating incidents include Apollo 1, Apollo 13, and the Mir fire. The page also references an Artemis II smoke alarm. This file does not independently verify the historical narrative.

## 5. Experiment and hardware map

The relationships below are described on the challenge page; they are useful indexing context, not a substitute for examining individual datasets. [S4]

| Investigation/project | Relevance described by the challenge | Important distinction |
|---|---|---|
| BASS and BASS-II | Burning and suppression of solid fuels; material flammability | Solid-material studies relevant to prevention |
| Saffire-I, -II, -III | Spacecraft fire-safety demonstrations; solid-material flammability | Do not assume all Saffire runs share the same configuration |
| SAME and SAME-R | Smoke/aerosol measurements for microgravity fire detection | Detection studies, not interchangeable with flame-spread datasets |
| FLEX | Suppression through atmospheric dilution with carbon dioxide and helium | Burning liquid droplets; suppression relevance |
| FLEX-2 and CFI | Liquid-droplet combustion | Shared apparatus does not imply identical objectives or conditions |
| DAFT and DAFT-2 | Dust/aerosol measurement feasibility | Used an instrument also used in SAME/SAME-R, but for dust |
| BRE, within ACME | Materials-flammability behavior in still atmospheres as a function of material properties | Used gaseous fuel as an emulator; not simply a solid-sample test |
| ACME | Six gaseous-fuel experiments | Shared modular ACME hardware in the Combustion Integrated Rack (CIR) |
| CFI-G, within ACME | High-oxygen, inside-out flame tests | Burner oxygen/nitrogen stream reached up to 85% oxygen; chamber held nitrogen plus flammable gas. Do not describe 85% as a uniform cabin atmosphere |
| E-FIELD Flames, within ACME | Electric fields acting on flame ions mimicked some partial-gravity effects | Analogue behavior is not direct partial-gravity combustion measurement |
| SPICE and SLICE | Gaseous-fuel studies among the related glovebox investigations | Shared hardware context helps comparison but does not establish equivalent tests |
| LUCI and FM2 | Named as future sources of partial-gravity combustion data | Future availability, not confirmed existing PSI data |

Hardware relationships:

- FLEX, FLEX-2, and CFI used the **Multi-user Droplet Combustion Apparatus (MDCA)** in the **CIR**.
- ACME's six experiments used its common modular hardware in the **CIR**.
- BASS, BASS-II, SPICE, and SLICE used the **Microgravity Science Glovebox (MSG)** and the modular fan-driven flow duct originally built for SPICE; collectively they involved solid and gaseous fuels.

### 5.1 Partial-gravity evidence boundary [S4]

At the time represented by the challenge page, **PSI contains no partial-gravity combustion data**. Future LUCI and FM2 results are anticipated. The challenge suggests normal-gravity and microgravity results might bound intermediate-gravity behavior, and mentions electric-field experiments as analogues.

**Derived guidance:** Label lunar/Martian predictions, interpolation, analogues, and experimental observations separately. Never label microgravity data as direct lunar or Martian test data. A possible bound is not a guaranteed interpolation law.

## 6. Official resource catalogue

The descriptions below summarize the Resources tab. Linked resource contents were not separately audited in this compilation. [S4-R]

| Resource | Intended use |
|---|---|
| [PSI combustion search](https://psi.nasa.gov/physci/repo/search?q=combustion) | Primary repository for the challenge's experimental data |
| [NASA Combustion Science](https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science/) | Background on many investigations represented in PSI |
| [NASA ScienceCasts: The Power of Studying Combustion on the ISS](https://www.youtube.com/watch?v=W1oXykoz9zg) | Approximately 3.6-minute introductory video from 2018 |
| [A Researcher's Guide to ISS Combustion Science](https://www.nasa.gov/missions/station/a-researchers-guide-to-combustion-science/) | 2015 review, over 50 pages, of performed/planned ISS combustion research |
| [Apollo 1](https://sma.nasa.gov/sma-disciplines/accllp/apollo-1) | Incident, investigation, and lessons learned |
| [Apollo 13](https://sma.nasa.gov/sma-disciplines/accllp/apollo-13) | Oxygen-tank accident, investigation, and lessons learned |
| [Mir fire retrospective](https://www.nasa.gov/history/25-years-ago-fire-aboard-space-station-mir/) | 1997 oxygen-generator fire context |
| [Fireman's Air Tanks](https://spinoff.nasa.gov/node/9582) | Spacesuit-derived firefighter breathing equipment |
| [Fire Detector](https://spinoff.nasa.gov/node/9407) | Smoke/dust discrimination and reduced nuisance alarms |
| [New Technology for the Fire Attire](https://spinoff.nasa.gov/node/9918) | Spacesuit-derived firefighter clothing |

NASA does not endorse non-U.S.-Government entities linked from the page. External sites' data-use conditions still apply. Resources may be added before the event. [S4-R, S4]

## 7. Participation, team, and work rules

### 7.1 Official requirements [S1–S3]

- Respond to **one official challenge**. A participant may belong to only **one team**, and a team may work on only **one challenge**.
- Maximum team size: **six**.
- Global-judging minimum: **one member** for a Local Event team; **two members** for a Universal Event team.
- Every teammate, including the Team Owner, must be registered for the same Local Event or all for the Universal Event, be accepted rather than waitlisted, and appear on the team's Members tab.
- Members cannot be added after project submission closes.
- Teams **may not begin working on challenges before the hackathon**. Early publication of challenge statements does not authorize advance challenge implementation. The FAQ does not provide a detailed boundary for generic preparation, reusable tools, or existing code; do not invent an exemption. [S3]
- At least **one NASA datum/resource** must be used for Global Award eligibility. Meaningful NASA-data integration is also a scoring criterion. [S1, S2]
- External code, text, images, data, resources, and tools must be credited, even when open source or freely available. Obtain permission for copyrighted material where required.
- The team must confirm that its submitted work is original and accept the applicable submission terms, participant terms, and privacy policy.
- The judging guide describes a NASA review for prohibited bilateral activity involving China or Chinese-owned entities. Eligibility is determined by NASA; consult the [official terms](https://www.spaceappschallenge.org/legal/) for the full policy. Do not infer a person's eligibility from nationality alone. [S2]

### 7.2 Participation logistics [S3]

- Participants create/sign into an account, register for 2026, choose an event, and join/create a team. Registration remains open through 15 November.
- Local Events may be in person or virtual. The Universal Event is virtual and asynchronous.
- A waitlisted participant should contact the Local Lead. If acceptance is unavailable, the team needs an event able to accept all members. [S1]
- Under-18 participants require parent/legal-guardian registration and accompaniment throughout the event; local requirements may add restrictions. They must not upload their own avatar/team photo or include under-18 photos, video, voices, or likenesses in the submitted project or demo. [S3]
- The demo and final project may not include images, audio, video, or other likenesses of anyone under 18. [S1]

## 8. Dates and deadlines

| Milestone | Official date/time | Source |
|---|---|---|
| Registration opened | 26 August 2026 | S3 |
| Summaries and team formation opened | 17 September 2026 | S3 |
| Full challenge statements published | 28 October 2026 | S3 |
| Space Apps Connect opened | 3 November 2026 | S3 |
| Challenge resources, global offers, submission/judging guides available | 13 November 2026 | S3 |
| Hackathon | 14–15 November 2026 | S3 |
| Project submission opens | Saturday 14 November, 09:00 | S1 |
| Project submission closes | Sunday 15 November, 23:59 | S1, S2 |
| Global Nominees announced | 3 December 2026 | S2 |
| Global Finalists and Honorable Mentions announced | 17 December 2026 | S2 |
| Global Winners announced | 26 January 2027 | S2 |
| Virtual winners' celebration | Early 2027; no exact date provided | S2 |

**Time-zone rule:** Submission opening/closing uses the team's Local Event time zone. For the Universal Event, use the Team Owner's area-of-residence local time. Do not default to the assistant's or another teammate's time zone. Local judging/presentation times may differ; ask the Local Lead. [S1]

## 9. Required submission package

### 9.1 Project page fields [S1]

| Field | What to prepare |
|---|---|
| Project Name | Clear project title |
| High-Level Project Summary | What was developed, how it addresses the challenge, and why it matters |
| Link to Project Demo | Public link to the compliant slide deck or video |
| Link to Final Project | Public link to the website, repository, hosted artifact, or other final output |
| Detailed Project Description | Function, mechanism, benefits, goals, tools, languages, hardware/software |
| Use of Super Intelligence (SI) | Whether and how SI tools/software were used |
| NASA Data | Specific NASA data/resources used; explain their contribution |
| Space Agency Partner Data and Other References | All other data, code, text, imagery, tools, and resources, including open-source material |

Complete every field marked required in the live form. The guide lists fields but this reference does not infer hidden UI validation rules or unstated word limits.

### 9.2 Demo rules [S1, S2]

- Every team must provide a demo.
- Choose **a slide deck of at most seven slides total**, counting title and introduction slides, **or a video lasting at most 30 seconds**.
- Exceeding either applicable limit makes a project ineligible for Global Judging.
- Host the demo externally and provide an accessible link. Video and document files cannot be uploaded directly to the project page.
- Use English on the submission page and in linked materials. A spoken non-English demo video is permitted only with English subtitles. Slide decks must be in English.
- Show the solution, user experience, and contribution of NASA/partner data. Include team name, member names, and chosen challenge in slides.
- The demo contributes to evaluation, but most evaluation is based on the project submission. Presentation scoring considers the demo and full project.

**Official presentation advice, not extra mandatory fields:** Assign a demo lead early; use readable visuals and few words; explain the value to an audience without prior technical context. The suggested video sequence is introductions at 0:00, challenge/motivation at 0:02, project title/tagline at 0:05, mechanism/user experience/data at 0:10, and future impact at 0:20–0:30. [S1]

### 9.3 Links and uploads [S1]

- Demo and final-project links must work without login, registration, passwords, or access requests.
- Test links using a private browser or a teammate without owner access.
- Images can be uploaded/pasted: JPG, PNG, GIF, up to 10 MB. Documents/videos must be hosted elsewhere.
- Hosting examples include YouTube, Google Drive, GitHub, OneDrive, and Dropbox; these are examples, not required providers.
- Optional: request [FortiGuard Web Filter Classification](https://www.fortiguard.com/faq/wfratingsubmit) for a new website to reduce access issues. Select the fitting category and use N/A as the company name. This is not required and NASA cannot control the classification outcome.

### 9.4 Save versus submit [S1]

1. Open profile menu → My Team → Project. The Project tab becomes available when the event opens locally.
2. Click Edit and save progress frequently. Saved drafts are visible to the team until submitted.
3. Coordinate editing. The edit lock is advisory: another teammate can remove it and overwrite unpublished changes.
4. Complete required fields, references, and confirmations.
5. Click **Submit for Judging** before the applicable deadline. Saving alone is insufficient.
6. Verify the success banner and confirmation message.
7. Edits and resubmissions are allowed before close; the guide says only the last saved submission is reviewed. After an edit, explicitly resubmit and verify confirmation rather than assuming a draft update counts.

Late saved/submitted projects are not eligible for judging. [S1]

## 10. SI/AI use and attribution

### 10.1 Official rules [S1, S3]

- SI tools are permitted to accelerate innovation, development, and creativity. Examples include machine learning, chatbots, LLMs, code generation, and image/video tools.
- S1 adds a restriction: SI should not be used to originate the team's idea for solving the challenge. S3's general permission does not remove that specific limitation.
- Describe where and how SI tools were used in development.
- SI-generated content may not use, contain, or modify NASA branding/design elements such as logos, flags, or mission identifiers. See [NASA brand guidelines](https://www.nasa.gov/nasa-brand-center/brand-guidelines/).
- Generated images and videos must carry a **visible SI-generation watermark**.
- Generated audio, code, and data must acknowledge SI generation in **descriptive text and metadata**.
- The SI form response is described as being collected for data purposes and not shown to judges. Visible disclosures within the project are seen by judges and can inform their assessment of originality, intent, and execution.

### 10.2 Derived implementation practice — not additional competition rules

- Keep a record of tools used, what each generated, and what the team reviewed or changed.
- Preserve human ownership of the solution concept. Use assistants to implement, explain, verify, and document the team's chosen approach.
- Keep synthetic/demo data separate from NASA measurements, with labels that persist in charts, exports, and metadata.
- Include AI acknowledgements in repository documentation and generated artifact metadata as applicable; do not assume the form field alone satisfies artifact disclosure requirements.

## 11. Judging rubric and how to supply evidence

Every judging stage scores each of five criteria on a **1–5 scale**. The guide does not state separate weights, a tie-breaker, or a numerical aggregation formula. [S2]

| Criterion | Official emphasis, paraphrased | Derived evidence for this dashboard |
|---|---|---|
| Impact | Importance of the problem; reach, benefit, and effectiveness | A clear user need and example of research made easier to find or interpret |
| Creativity | Originality, inventive execution, or meaningful improvement | Explain the distinctive contribution beyond a generic chat interface |
| Validity | Scientific grounding, feasibility, functionality, completeness, and usability | Reproducible calculations, source-backed answers, valid comparisons, and a working workflow |
| Relevance | Direct challenge fit and meaningful, integral use of NASA data | Real PSI investigations driving retrieval, comparison, and outputs |
| Presentation | Clear, organized, compelling communication of problem, solution, and significance | A readable project page and concise demo with a visible user journey |

A top score is described as exceptional impact, strong originality, a scientifically sound and usable implementation, deeply integrated NASA data, and polished storytelling. A proposal may be evaluated before full maturity, but the highest Validity description emphasizes readiness and completeness. Do not claim production readiness without evidence. [S2]

### 11.1 Judging progression [S2, S3]

1. **Local/Universal judging → Global Nominees.** Local judges are organized by Local Leads. Universal projects are assessed by subject-matter experts against other Universal submissions; advancement is proportionate/comparable to Local Events. Local awards are separate from global advancement. Only officially submitted Global Nominees enter Global Judging.
2. **Global judging → Global Finalists and Honorable Mentions.** Expert judges assess nominees using the same criteria. Honorable Mentions do not advance to Executive Judging or become eligible for the subsequent awards.
3. **Executive judging → Global Winners.** NASA and partner-agency executives review finalists and nominate winners in ten categories. Winners receive an invitation to a virtual celebration.

### 11.2 Global award categories [S2]

| Award | Focus |
|---|---|
| Best Use of Science | Rigorous, effective scientific method |
| Best Use of Data | Accessibility of space data or an unusual application |
| Best Use of Technology | Innovative technology use |
| Galactic Impact | Potential benefit to Earth or beyond |
| Best Mission Concept | Plausible concept and design |
| Most Inspirational | Inspiring human appeal |
| Best Storytelling Award | Creative communication of open data's potential |
| Global Connection Award | Connecting people worldwide through technology |
| Art & Technology Award | Combining technical and creative abilities |
| Local Impact Award | Potential benefit to a local community |

These categories are not separate mandatory deliverables. Do not invent cash prizes, travel awards, or a requirement to enter a category explicitly; these pages do not establish those details.

## 12. Derived engineering guidance for AI assistance

This section translates the challenge and rubric into practical habits. It is **not an official specification or an approved team architecture**.

1. **Make NASA evidence central.** Connect outputs to real PSI investigation records, relevant files/runs, and source descriptions. Show what evidence supports a result.
2. **Separate discovery, extraction, calculation, and interpretation.** An LLM explanation should not conceal missing measurements or silently replace a numerical method.
3. **Make ranking explainable.** State why a study matches a user's material, atmosphere, flow, gravity, measurement, or prevention/detection/suppression question.
4. **Compare compatible conditions.** Record units, pressure, oxygen fraction, airflow, geometry, fuel, apparatus, and gravity where available. Missing information should remain explicitly missing.
5. **Respect evidence boundaries.** Distinguish measured values, derived values, simulations, and hypotheses; expose assumptions and extrapolation.
6. **Demonstrate a complete path.** A small, reliable workflow from user question to relevant investigations to cited interpretation gives concrete evidence of utility. No page requires processing every PSI file.
7. **Keep scope disciplined.** Prioritize habitable spacecraft/space habitats and material fire safety. Do not turn the solution into a rocket-engine simulator merely because it involves combustion.
8. **Document limitations honestly.** Note data coverage, unsupported queries, validation performed, and uncertainty. Research support is not certification of a spacecraft's safety.
9. **Plan submission alongside implementation.** Maintain a reference list, SI-use record, public artifact links, and demo materials throughout development.

## 13. Submission-readiness checklist

### Official compliance checks

- [ ] All members accepted at the same event and visible in the team roster.
- [ ] Team size satisfies the Local/Universal minimum and six-person maximum.
- [ ] One official challenge selected; project directly addresses it.
- [ ] No challenge work was begun before the hackathon, per S3; any ambiguity resolved with organizers.
- [ ] At least one NASA data/resource is used and specifically documented.
- [ ] All required project-page fields complete and written in English.
- [ ] Linked materials meet English requirements; non-English demo speech has English subtitles.
- [ ] Demo meets the seven-slide total or 30-second maximum.
- [ ] Demo and final-project links work without authentication or permission requests.
- [ ] All external resources credited and needed permissions obtained.
- [ ] SI use documented; generated artifacts carry required disclosures/watermarks.
- [ ] Generated content does not contain/modify NASA branding elements.
- [ ] Project/demo contains no under-18 likenesses, including voices.
- [ ] Team reviews and accepts the required originality/terms confirmations.
- [ ] Submit for Judging completed before the correct event/owner-local deadline.
- [ ] Success banner/confirmation verified; later edits explicitly resubmitted.

### Quality checks derived from the challenge and rubric

- [ ] A clear target user and fire-safety question are demonstrated.
- [ ] Real NASA data drives the result, with traceable sources.
- [ ] Investigation/run distinctions, conditions, and units are preserved.
- [ ] Rankings and cross-investigation comparisons have understandable reasons.
- [ ] Scientific claims are supported; missing evidence and extrapolation are visible.
- [ ] The main user workflow works reliably and is easy to demonstrate.
- [ ] Impact, originality, validity, relevance, and presentation are each addressed.

## 14. Support, certificates, and remaining uncertainties

### Support and participation [S1, S3]

- **Local Lead:** primary source for venue, local schedule, registration/waitlist, and local judging questions; contact details are on the Local Event page.
- **Space Apps Connect:** optional free community forum for registered participants; connects teams, SMEs, Navigators, organizers, and collaborators. Opened 3 November and closes at the end of the hackathon. [Forum](https://github.com/nasa/spaceapps) · [Guide](https://www.spaceappschallenge.org/resources/space-app-connect-guide/).
- **General enquiries / improper participation-fee requests:** info@spaceappschallenge.org.
- **Conduct concerns:** Local Lead and/or conduct@spaceappschallenge.org.
- **Certificate technical issues:** web@spaceappschallenge.org; include username and team name.
- **Other guidance:** [Contact page](https://www.spaceappschallenge.org/contact-us/) · [Team Formation Guide](https://www.spaceappschallenge.org/resources/team-formation-guide/) · [Participant terms](https://www.spaceappschallenge.org/legal/).

Participants on teams that submit by the deadline receive a downloadable PDF certificate through Profile → Participant Information → 2026 NASA Space Apps Challenge. Certificate names follow the profile's Full Name, which can be updated. A desktop/laptop is recommended. Choose Letter paper; the guide's printed millimetre dimensions are inconsistent with its Letter label, so do not copy those dimensions into automation. [S1]

### Not established by the reviewed pages

- The team's actual event, registration acceptance, local judging schedule, or time zone.
- Dataset size (including any claim of 13 TB), file counts, formats, API behavior, or individual run quality.
- A compulsory requirement to ingest all PSI data, train an LLM, use a knowledge graph/vector database, or implement a particular thermodynamic solver.
- A mandatory natural-language prompt interface; that is a possible implementation choice.
- A fixed list of deliverables beyond the dashboard objective and submission package.
- Exact boundaries for pre-event generic preparation versus prohibited challenge work.
- Detailed legal/IP/licensing terms beyond what the four guides summarize; the linked legal page must be read for a complete interpretation.
- Independent confirmation of every historical/scientific statement on the challenge page.
- The FAQ's cited explanation for the SI terminology change was not independently verified and is unnecessary for implementing the challenge.

## 15. Compact context for short prompts

We are working on NASA Space Apps 2026, Flame in Freefall. The official objective is an interactive SI-powered web dashboard that summarizes, ranks, and interprets NASA PSI combustion investigations for fire safety in habitable space environments. Prioritize evidence-based discovery, comparison, and interpretation of prevention, detection, and suppression research. Preserve experimental conditions and source provenance; distinguish observations from derived/modelled results. Partial-gravity combustion data is described as absent from PSI in the challenge page; do not fabricate lunar/Martian measurements. Earth applications are optional; rockets/propellants are generally outside scope. The five judging criteria are Impact, Creativity, Validity, Relevance, and Presentation, each scored 1–5. NASA data must be meaningfully integrated, and at least one NASA datum/resource is required for Global Award eligibility. Teams have at most six people; Local minimum one, Universal minimum two; all must be accepted at the same event. Submission closes 15 November 2026 at 23:59 in the Local Event time zone, or the Universal Team Owner's residence time zone. Local judging may be earlier. Prepare an English project page, a public final-project link, and a public demo of at most seven slides or 30 seconds. Credit all external resources, disclose SI use, watermark SI-generated visuals, and label generated audio/code/data in descriptive text and metadata. SI is permitted to support implementation, but the submission guide says it should not originate the solution idea. No pre-hackathon challenge work. Saving is not submitting: verify Submit for Judging confirmation. These are source-based constraints, not evidence that our team has already met them.
