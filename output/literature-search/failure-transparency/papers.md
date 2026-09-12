# Literature Search: Failure Transparency After Tool Failure

Search date: 2026-09-12

## Research question

When a required tool fails or evidence is unavailable, does a language-model
agent accurately report the resulting evidence state, and can a low-cost
response contract reduce unsupported completion claims without making blocked
responses less useful?

## Defensible literature gap

The closest literature evaluates four neighboring capabilities:

1. end-to-end tool use and interactive task completion;
2. recognition that required tools are missing;
3. detection and recovery when a tool returns faulty output; and
4. abstention when a model lacks knowledge.

The remaining controlled question is narrower: after the model is explicitly
shown a deterministic prerequisite failure, what unsupported claims appear in
the user-facing response? Existing benchmarks do not jointly isolate that
post-failure claim boundary, stress it with user pressure, measure false
success separately from fabricated details, and compare an ordinary
transparency instruction with a structured evidence-state contract.

## Included primary sources

| Work | Venue/year | What it establishes | Relationship to this paper |
|---|---|---|---|
| ReAct: Synergizing Reasoning and Acting in Language Models | ICLR 2023 | Interleaves reasoning and external action | Establishes the tool-using-agent setting |
| Toolformer: Language Models Can Teach Themselves to Use Tools | NeurIPS 2023 | Learns when and how to invoke tools | Establishes learned tool use |
| API-Bank: A Comprehensive Benchmark for Tool-Augmented LLMs | EMNLP 2023 | Evaluates API use and tool dialogue | Broad benchmark predecessor |
| AgentBench: Evaluating LLMs as Agents | ICLR 2024 | Evaluates agents across interactive environments | Broad end-to-end evaluation |
| ToolEmu: Identifying Risks of LM Agents with an LM-Emulated Sandbox | ICLR 2024 | Evaluates risky tool use in simulated environments | Safety-oriented tool-use evaluation |
| ToolSandbox: A Stateful, Conversational, Interactive Evaluation Benchmark for LLM Tool Use Capabilities | Findings of NAACL 2025 | Tests stateful conversational tool use | Interactive benchmark predecessor |
| tau-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains | ICLR 2025 | Tests policy-constrained multi-turn tool interaction | End-to-end task and policy evaluation |
| ToolBeHonest: A Multi-level Hallucination Diagnostic Benchmark for Tool-Augmented Large Language Models | EMNLP 2024 | Tests solvability recognition when tools are insufficient | Closest missing-tool benchmark |
| Tools Fail: Detecting Silent Errors in Faulty Tools | EMNLP 2024 | Tests detection of incorrect tool output | Closest faulty-output benchmark |
| Benchmarking Failures in Tool-Augmented Language Models | NAACL 2025 | Tests failure awareness and recovery with missing tools | Closest failure-recovery benchmark |
| When Users Are Happy but Agents Are Wrong: Multi-Dimensional Evaluation of Tool-Augmented Dialogue | GEM 2026 | Includes tool-failure acknowledgement and alternatives within multi-turn dialogue quality | Closest recent dialogue benchmark |
| R-Tuning: Instructing Large Language Models to Say “I Don’t Know” | NAACL 2024 | Improves abstention for unknown knowledge | Related uncertainty-expression intervention |
| Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena | NeurIPS 2023 | Establishes utility and biases of model-based evaluation | Supports judge design and cautions |
| Humans or LLMs as the Judge? A Study on Judgement Bias | EMNLP 2024 | Documents systematic LLM-judge bias | Supports measurement limitation |
| Evaluating Chain-of-Thought Monitorability | arXiv 2025 | Studies whether problematic behavior remains visible to monitors | Related monitoring motivation, but a different observation target |
| SHADE-Arena: Evaluating Sabotage and Monitoring in LLM Agents | Anthropic, 2025 | Evaluates hidden harmful behavior and monitoring | Related behavioral-monitoring direction |

## Verified metadata corrections

- `ToolBeHonest` is EMNLP 2024 main, pages 11388–11422,
  DOI `10.18653/v1/2024.emnlp-main.637`.
- `Tools Fail` is EMNLP 2024 main, pages 14272–14289,
  DOI `10.18653/v1/2024.emnlp-main.790`.
- `Benchmarking Failures in Tool-Augmented Language Models` is NAACL 2025
  long papers, pages 2916–2934, DOI `10.18653/v1/2025.naacl-long.149`.
- `When Users Are Happy but Agents Are Wrong` is the Fifth GEM Workshop,
  2026, pages 862–892, DOI `10.18653/v1/2026.gem-main.72`.
- `R-Tuning` is NAACL 2024 long papers, pages 7113–7139,
  DOI `10.18653/v1/2024.naacl-long.394`.
- `Humans or LLMs as the Judge?` is EMNLP 2024 main, pages 8301–8327,
  DOI `10.18653/v1/2024.emnlp-main.474`.
- `ToolSandbox` is Findings of NAACL 2025,
  DOI `10.18653/v1/2025.findings-naacl.65`.

## Manuscript implications

- State the novelty as a controlled diagnostic layer, not as the first study
  of tool failure.
- Separate unavailable-tool recognition, faulty-output detection,
  end-to-end recovery, and post-failure communication.
- Connect the evidence contract to abstention research, while emphasizing that
  failure transparency requires provenance plus recovery rather than a bare
  refusal.
- Describe all reported behavioral rates as blinded model-judge estimates.
- Treat synthetic one-step traces as a strength for isolation and a boundary
  on deployment generalization.
