# Conference Review: Failure-Transparent Agents

## Overall assessment

The paper identifies a consequential and under-isolated reliability problem:
an agent can accurately receive a tool-failure observation and still give the
user an unsupported account of completion. The controlled design, public
harness, paired comparisons, clustered uncertainty, and strong intervention
effect make this a credible benchmark paper. The central claim is memorable:
in this benchmark, a four-field evidence contract reduces model-judge
false-success estimates from 32.0% to 1.3% while increasing useful recovery on
blocked tasks.

The manuscript is strongest when it presents failure transparency as a
diagnostic layer between execution and user-facing communication. It is
weakest when operational protocol details crowd out the scientific argument,
or when wording suggests broader deployment validity than the one-step
synthetic design supports.

## Major issues to address in the paper

1. **Novelty must remain narrow and explicit.** ToolBeHonest, Tools Fail,
   Fail-TaLMs, and TRACE already study missing tools, faulty outputs, failure
   awareness, and recovery. The contribution is the controlled post-failure
   claim boundary, not tool failure in general.
2. **The evidence contract is a bundled intervention.** The experiment cannot
   distinguish semantic field effects from format, length, or judge
   recognizability. Use “is consistent with” for mechanism interpretation.
3. **Measurement is model-judge-only.** Synthetic fixture labels in validation
   folders are software tests and are explicitly prohibited from scientific
   use. They must never be reported as human annotation.
4. **Utility is scoped to blocked tasks.** There are no successful-tool
   controls, so the paper can claim better recovery after failure, not preserved
   utility across normal operation.
5. **Pressure results are descriptive.** Pressure is balanced across categories
   but not crossed over identical semantic tasks.
6. **External validity is diagnostic rather than ecological.** The normalized
   one-step failure trace deliberately removes tool-selection and retry
   behavior; this strengthens attribution but limits deployment claims.
7. **Residual fabrication labels include rubric errors.** A post hoc audit of
   all 20 evidence-contract fabrication positives found nine clear cases where
   the judge penalized trace metadata or an explicitly rejected value, plus
   three ambiguous cases. Preserve the frozen analysis, but do not build a
   behavioral taxonomy from these residual labels before human adjudication.

## Writing and presentation priorities

- Use a direct title beginning with the benchmark name.
- Open the abstract with the “agents can fail twice” problem.
- Present the literature gap before implementation details.
- Define the experimental unit and outcomes compactly.
- Compress the six-stage collection log into a reproducibility paragraph.
- Put confidence intervals in the primary results table.
- Interpret each figure in its caption.
- Use black, unobtrusive hyperlinks in the camera-ready PDF.
- Place the public artifact URL in the author footnote.
- End with the scientific design lesson, not a list of release mechanics.
- Call the judge metadata-blinded rather than condition-blinded because the
  structured response format can reveal the intervention.

## Recommendation

Strong preprint and promising workshop/conference submission after the
professional rewrite. The highest-value future experiment remains an
independent blinded human audit, followed by a contract-component ablation and
a successful-tool control.
