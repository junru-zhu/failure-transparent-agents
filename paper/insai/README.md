# INSAI / Springer CCIS Paper Variant

This directory contains the INSAI-oriented proceedings version of the paper.
It uses Springer's `llncs` class because the accepted INSAI 2025 papers were
published in the Communications in Computer and Information Science series.

Build from the repository root:

```bash
make insai-paper PYTHON=.venv/bin/python
qpdf --check paper/insai/main.pdf
```

The adaptation follows the visible conventions of the accepted proceedings:

- Springer LNCS/CCIS page geometry and typography;
- running title and running author;
- abstract followed by keywords;
- numbered sections and subsections;
- table captions above tables and figure captions below figures;
- compact numbered references; and
- a full-paper length comparable to the accepted 2025 papers.

The public INSAI 2026 site did not expose a complete author-guideline package
when this variant was prepared. Before submission, verify the exact track,
page limit, anonymity policy, copyright form, and submission-system metadata.
The current source identifies the author as an independent researcher; replace
that line if a formal institutional affiliation should be listed.
