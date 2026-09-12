# Exemplar Gap Analysis

## Revision status

The fast publication fixes identified below were implemented on September 12,
2026: an early benchmark overview figure, a consolidated primary-results
table, residual-error analysis from the frozen labels, scoped utility and
mechanism claims, a factual closest-work table, author affiliation text, and
PDF metadata. The canonical manuscript was subsequently converted to an
eight-page IEEE-style two-column layout; the Springer/INSAI source remains a
separate single-column venue variant. The remaining gaps require new evidence:
human validation, component ablation, successful-tool controls, and native-tool
transfer.

## Scope

This review compares the current INSAI manuscript with three supplied ICASSP
2026 benchmark papers:

- *A Cocktail-Party Benchmark*
- *SSEU-Bench*
- *SingMOS-Pro*

The examples are five-page IEEE two-column camera-ready papers. The current
paper is a 13-page LNCS draft. Their margins, type size, column count, and page
density should not be copied into the INSAI version. The transferable lessons
are information hierarchy, evidence depth, visual pacing, and result
presentation.

## What each example does professionally

| Paper | Strongest content choice | Strongest layout choice | Important weakness |
|---|---|---|---|
| Cocktail-Party | Defines a memorable real-world task and reports one concrete headline result | Places a real recording setup on page 2 and a compact results table on page 4 | Narrow baseline set, no uncertainty analysis, and limited error analysis |
| SSEU-Bench | Maps two precise literature gaps to benchmark design, several baselines, SNR stress tests, and a mitigation | Uses an overview figure on page 2, a dense main-results table, and a multi-panel ablation | Very compressed presentation; the synthetic mixture setting limits external validity |
| SingMOS-Pro | Establishes credibility through dataset scale, annotator protocol, quality control, splits, domain shift, and many baselines | Visualizes corpus composition before presenting the benchmark results | Several plots and tables are difficult to read; the title itself contains a grammar error, and uncertainty is limited |

These papers look professional because the reader can answer four questions
quickly: what is missing, what was built, how it was tested, and what the main
number is. They are not flawless models. Their two-column density sometimes
hurts readability, and their statistical treatment is generally weaker than
the clustered analysis in the current manuscript.

## Current manuscript: strongest aspects

1. The title, abstract, and introduction now define a narrow and defensible
   problem: unsupported user-facing claims after an explicit tool failure.
2. The full-factorial design, deterministic simulator, frozen protocol,
   provider-neutral harness, and public audit artifacts are more reproducible
   than the supplied examples.
3. Clustered confidence intervals, paired tests, multiplicity control, and
   explicit resampling units give the quantitative claims a stronger
   statistical foundation.
4. The main figures are clean, accessible, and easier to read than several
   plots in the examples.
5. The paper reports a memorable result: false success falls from 32.0% to
   1.3%, while usefulness rises from 69.8% to 98.3%.

## Content gaps

### 1. Measurement validity is the largest reviewer vulnerability

All primary and secondary behavioral outcomes are model-judge labels. The
judge shares a vendor lineage with one tested model, and the structured
evidence-contract response can reveal its condition even when the condition
name is hidden. Verbatim spans and schema validation improve auditability but
do not establish label validity.

The supplied papers either use objective task labels or invest heavily in
human annotation and quality control. Without human validation, this paper
can support a strong model-judge benchmark result, but not a strong claim
about the true prevalence of deceptive or fabricated responses.

For a rapid preprint, retain the limitation and call the rates
“model-judge estimates.” For stronger peer review, a blinded human audit is
the highest-value new evidence.

### 2. The paper shows that the evidence contract works, but not why

The intervention combines four semantic requirements with a rigid response
format. There is no component ablation, neutral-schema control, or
format-only control. The discussion correctly says the bundle was evaluated,
but its mechanism language is still stronger than the design can prove.

A reviewer can reasonably ask whether the gain comes from evidence-state
reasoning, from easier-to-judge headings, from additional instruction length,
or from simple format compliance. Until an ablation is run, use
“consistent with” rather than causal language such as “explains why.”

### 3. External validity is narrower than the examples

The 100 tasks are English, synthetic, one-step, and presented through a
normalized textual tool trace. No native function-calling protocol, live
multi-turn agent, partial success, autonomous retry, or real document/tool
failure is tested. This control is a strength for causal isolation, but it
also means the benchmark is diagnostic rather than representative of deployed
agent prevalence.

The strongest future extension is a small, preregistered transfer set using
native tool protocols or recorded real failures. For the current paper, make
the diagnostic-versus-deployment boundary visible in the abstract,
introduction, and conclusion.

### 4. The utility claim needs a successful-task control

Usefulness and over-refusal are measured only after blocked tasks. This shows
that the contract improves recovery under failure. It does not show that the
contract preserves utility when tools succeed. The current phrase “without
sacrificing usefulness” should therefore be scoped to blocked tasks.

### 5. The main evidence is fragmented across prose and figures

The examples provide a dense primary-results table that readers can inspect
and cite. The current manuscript has design, configuration, example, and cost
tables, but no single table containing the principal outcomes across the three
conditions.

A compact table should report false success, fabrication, disclosure,
recovery, usefulness, and over-refusal, with confidence intervals for the two
primary outcomes. The figures should remain, but the table should be the
numeric source of record.

### 6. Error analysis is too thin

The stale-data observation and one forced-choice response are useful, but they
do not explain the residual failures. A professional benchmark paper should
show at least one taxonomy of:

- false-success versus fabrication-only failures;
- residual evidence-contract failures;
- model-specific instruction failures;
- failure category by pressure interaction; and
- judge uncertainty or repair frequency.

Most of this can be produced from existing outputs without new API calls.

### 7. Related-work coverage is correct but visually and bibliographically thin

The closest-work table reduces neighboring benchmarks to check marks and does
not show dataset size, setting, native versus simulated tools, public
artifacts, human validation, or intervention evaluation. The current
bibliography has 15 entries, versus 28, 47, and 48 in the supplied examples.
Reference count is not a quality metric, but the contrast reflects a thinner
map of the surrounding field.

## Layout gaps

### 1. The first explanatory figure appears on page 8

This is the clearest presentation gap. All three examples establish their
benchmark visually on page 2 or 3. The current reader crosses the introduction,
related work, benchmark design, execution, annotation, and statistics before
seeing a figure.

Add one early overview figure:

`user request -> deterministic failed-tool trace -> prompt condition -> model response -> evidence-grounded labels`

The same figure can show the four evidence-contract fields. It would make the
paper feel like a benchmark paper immediately.

### 2. There is no visual characterization of benchmark coverage

The balanced 5-by-5 task design is described in prose and tables, but the
reader never sees representative tasks or the coverage structure. A compact
matrix with one example per failure category and pressure type would make the
100-task design tangible.

### 3. Visual pacing is sparse, not unprofessional

The manuscript has about 4,200 words, comparable to the supplied papers
(roughly 3,700--4,500), but spreads them over 13 LNCS pages rather than five
IEEE pages. The paper is not unusually verbose by word count. It looks airy
because of the venue format and because the first seven pages contain only
text and tables.

Do not imitate the examples' 9-point, two-column compression. Improve pacing
with an early overview figure and a main-results table.

### 4. The submission still visibly looks like a draft

“Affiliation omitted in this submission draft” is an obvious placeholder.
The generated PDF also has empty title and author metadata. These details are
minor scientifically but matter immediately to a professional reader.

### 5. The closest-work table is too schematic

The table is clean, but its binary check marks make the comparison appear
author-defined. Replace or expand it with factual dimensions and sizes. Keep
the table compact enough to remain readable in LNCS format.

## Critical scorecard

| Dimension | Current assessment | Main reason |
|---|---:|---|
| Problem and gap | 4.5 / 5 | Narrow, consequential, and easy to state |
| Experimental control | 4.5 / 5 | Balanced deterministic design and frozen protocol |
| Measurement validity | 2.5 / 5 | No human validation and a detectable structured condition |
| Intervention explanation | 3.0 / 5 | Strong effect, but no component or format ablation |
| Statistical analysis | 4.5 / 5 | Better uncertainty and paired analysis than the examples |
| External validity | 2.5 / 5 | Synthetic one-step traces without native tools |
| Reproducibility | 4.8 / 5 | Public, auditable, and executable artifacts |
| Figure quality | 4.2 / 5 | Clean result figures |
| Visual storytelling | 2.8 / 5 | First figure arrives on page 8 |
| Submission finish | 3.0 / 5 | Affiliation placeholder and empty PDF metadata |

## Recommended order of work

### Fast publication pass, no new experiment

1. Add an early benchmark/evidence-contract overview figure.
2. Add one compact primary-results table from the frozen analysis.
3. Scope the utility claim to blocked tasks and soften mechanism claims.
4. Expand the closest-work table with factual benchmark dimensions.
5. Add a short residual-error analysis using existing outputs.
6. Replace the affiliation placeholder and set PDF title/author metadata.

### Stronger peer-review pass, requires new evidence

1. Human-validate a blinded stratified sample.
2. Run evidence-contract component and format controls.
3. Add successful-tool controls.
4. Add a small native-tool or recorded-real-failure transfer set.

## Bottom line

The manuscript already reads like a serious reproducible benchmark paper and
is statistically stronger than the supplied examples. It does not yet match
their empirical credibility or visual immediacy. The most visible layout fix
is an overview figure before the methods become dense. The most important
scientific fix is independent label validation; the most important causal fix
is an intervention ablation. A rapid arXiv release can proceed without those
new experiments only if the claims stay explicitly scoped to model-judge
estimates on synthetic blocked tasks.
