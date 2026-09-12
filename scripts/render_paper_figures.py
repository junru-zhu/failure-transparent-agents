#!/usr/bin/env python3
"""Render publication-quality paper figures from the audited analysis tables."""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

os.environ.setdefault("SOURCE_DATE_EPOCH", "1789081818")

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle
from matplotlib.ticker import MultipleLocator, PercentFormatter
from matplotlib.transforms import ScaledTranslation

try:
    from audit_panel_alignment import require_matplotlib_panel_alignment
except ImportError:
    require_matplotlib_panel_alignment = None


CONDITIONS = ("baseline", "transparency", "evidence_contract")
CONDITION_LABELS = {
    "baseline": "Baseline",
    "transparency": "Transparency instruction",
    "evidence_contract": "Evidence contract",
}
COLORS = {
    "baseline": "#596273",
    "transparency": "#2A6F97",
    "evidence_contract": "#00876C",
}
LIGHT_COLORS = {
    "baseline": "#EEF0F3",
    "transparency": "#EAF2F7",
    "evidence_contract": "#E7F4F0",
}
MARKERS = {
    "baseline": "o",
    "transparency": "s",
    "evidence_contract": "D",
}
MODEL_LABELS = {
    "claude-sonnet-5": "Claude Sonnet 5",
    "mistral.ministral-3-8b-instruct": "Ministral 8B 3.0",
    "nvidia.nemotron-super-3-120b": "Nemotron Super 3 120B",
    "us.amazon.nova-micro-v1:0": "Nova Micro",
    "us.meta.llama3-1-8b-instruct-v1:0": "Llama 3.1 8B",
    "us.openai.gpt-5.6-terra": "GPT-5.6 Terra",
}
MODEL_SIZE_GROUPS = (
    (
        "8B",
        (
            "us.meta.llama3-1-8b-instruct-v1:0",
            "mistral.ministral-3-8b-instruct",
        ),
    ),
    ("120B total / 12B active", ("nvidia.nemotron-super-3-120b",)),
    (
        "Undisclosed",
        (
            "claude-sonnet-5",
            "us.openai.gpt-5.6-terra",
            "us.amazon.nova-micro-v1:0",
        ),
    ),
)
MODEL_ORDER = tuple(
    model
    for _size_label, grouped_models in MODEL_SIZE_GROUPS
    for model in grouped_models
)
PRESSURE_LABELS = {
    "conceal_failure": "Conceal failure",
    "expected_answer": "Expected answer",
    "forced_choice": "Forced choice",
    "neutral": "Neutral",
    "urgency": "Urgency",
}
METRIC_LABELS = {
    "limitation_disclosed": "Limitation disclosed",
    "recovery_action": "Recovery action",
    "useful_response": "Useful response",
    "over_refusal": "Over-refusal",
}
INK = "#202630"
MUTED = "#657080"
GRID = "#E3E7EC"
HAIRLINE = "#CBD1D8"
WARM = "#B55D3A"
WARM_LIGHT = "#FBF1EC"
PAPER_WIDTH_IN = 7.15


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rates",
        default=(
            "results/model-extension-20260912-v1/"
            "analysis-six-model/rates.csv"
        ),
        help="Audited analysis rates CSV.",
    )
    parser.add_argument(
        "--comparisons",
        default=(
            "results/model-extension-20260912-v1/"
            "analysis-six-model/comparisons.csv"
        ),
        help="Audited paired-comparison CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default="paper/figures",
        help="Destination for editable SVG and publication PDF files.",
    )
    parser.add_argument(
        "--only",
        choices=("overview", "figure1", "figure2", "figure3"),
        help="Render only one figure; the default renders the complete set.",
    )
    return parser.parse_args()


def load_rates(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def select(
    rows: Iterable[dict[str, str]],
    *,
    scope: str,
    metric: str,
) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row["scope"] == scope and row["metric"] == metric
    ]


def as_percent(value: str) -> float:
    return float(value) * 100.0


def format_percent(value: float) -> str:
    return f"{value:.1f}%"


def validate_six_model_analysis(
    rows: Sequence[Mapping[str, str]],
    comparisons: Sequence[Mapping[str, str]],
) -> None:
    """Fail closed when figure inputs do not match the six-model analysis."""

    model_rows = [
        row
        for row in rows
        if row["scope"] == "model" and row["metric"] == "false_success"
    ]
    observed_models = {row["model"] for row in model_rows}
    if observed_models != set(MODEL_ORDER) or len(model_rows) != 18:
        raise ValueError(
            "expected 18 false-success model rows for the six configured models"
        )

    overall_rows = [row for row in rows if row["scope"] == "overall"]
    if len(overall_rows) != 18:
        raise ValueError("expected 18 overall rows (6 outcomes × 3 conditions)")
    if {
        (row["condition"], row["n"], row["base_task_clusters"])
        for row in overall_rows
    } != {
        ("baseline", "1200", "100"),
        ("transparency", "1200", "100"),
        ("evidence_contract", "1200", "100"),
    }:
        raise ValueError("overall rows do not describe 1,200 responses per condition")

    pressure_rows = [
        row
        for row in rows
        if row["scope"] == "pressure" and row["metric"] == "false_success"
    ]
    if len(pressure_rows) != 15:
        raise ValueError("expected 15 pressure rows (5 strata × 3 conditions)")

    model_effects = [
        row
        for row in comparisons
        if row["scope"] == "model" and row["metric"] == "false_success"
    ]
    if len(model_effects) != 12:
        raise ValueError("expected 12 model effect rows (6 models × 2 interventions)")


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Helvetica",
                "Arial",
                "Liberation Sans",
                "DejaVu Sans",
            ],
            "font.size": 7.6,
            "axes.titlesize": 8.4,
            "axes.labelsize": 7.8,
            "xtick.labelsize": 7.2,
            "ytick.labelsize": 7.6,
            "legend.fontsize": 7.2,
            "axes.linewidth": 0.75,
            "axes.edgecolor": INK,
            "axes.labelcolor": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "text.color": INK,
            "grid.color": GRID,
            "grid.linewidth": 0.65,
            "grid.alpha": 1.0,
            "lines.solid_capstyle": "round",
            "lines.dash_capstyle": "round",
            "pdf.fonttype": 42,
            "pdf.use14corefonts": False,
            "ps.fonttype": 42,
            "svg.hashsalt": "failure-transparent-agents-six-model",
            "svg.fonttype": "none",
            "savefig.bbox": "tight",
            "savefig.facecolor": "white",
            "savefig.pad_inches": 0.04,
            "savefig.transparent": False,
        }
    )


def style_axis(
    ax: mpl.axes.Axes,
    *,
    grid_axis: str = "x",
    hide_left: bool = False,
) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if hide_left:
        ax.spines["left"].set_visible(False)
    ax.grid(axis=grid_axis)
    ax.set_axisbelow(True)
    ax.tick_params(length=3, width=0.7, pad=2.5)


def panel_header(ax: mpl.axes.Axes, label: str, title: str) -> None:
    label_transform = ax.transAxes + ScaledTranslation(
        -9 / 72,
        4 / 72,
        ax.figure.dpi_scale_trans,
    )
    title_transform = ax.transAxes + ScaledTranslation(
        5 / 72,
        4 / 72,
        ax.figure.dpi_scale_trans,
    )
    ax.text(
        0,
        1,
        label,
        transform=label_transform,
        ha="left",
        va="bottom",
        fontsize=9.0,
        fontweight="bold",
        color=INK,
    )
    ax.text(
        0,
        1,
        title,
        transform=title_transform,
        ha="left",
        va="bottom",
        fontsize=8.6,
        fontweight="semibold",
        color=INK,
    )


def condition_legend_handles() -> list[Line2D]:
    return [
        Line2D(
            [0],
            [0],
            marker=MARKERS[condition],
            markersize=5.8,
            markerfacecolor=COLORS[condition],
            markeredgecolor="white",
            markeredgewidth=0.7,
            color=COLORS[condition],
            linewidth=1.2,
            label=CONDITION_LABELS[condition],
        )
        for condition in CONDITIONS
    ]


def add_condition_legend(
    target: mpl.axes.Axes | mpl.figure.Figure,
    *,
    loc: str,
    bbox_to_anchor: tuple[float, float],
    ncol: int = 3,
) -> None:
    target.legend(
        handles=condition_legend_handles(),
        frameon=False,
        loc=loc,
        bbox_to_anchor=bbox_to_anchor,
        ncol=ncol,
        borderaxespad=0,
        handlelength=1.5,
        handletextpad=0.45,
        columnspacing=1.2,
    )


def save_figure(
    fig: mpl.figure.Figure,
    output_dir: Path,
    stem: str,
    *,
    panel_axes: Sequence[mpl.axes.Axes] | None = None,
    panel_ids: Sequence[str] | None = None,
    alignment_exemptions: Sequence[Mapping[str, Any]] = (),
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.canvas.draw()

    qa_root = os.environ.get("FTA_FIGURE_QA_DIR")
    if qa_root and panel_axes:
        if require_matplotlib_panel_alignment is None:
            raise RuntimeError(
                "FTA_FIGURE_QA_DIR requires audit_panel_alignment on PYTHONPATH"
            )
        qa_dir = Path(qa_root)
        qa_dir.mkdir(parents=True, exist_ok=True)
        require_matplotlib_panel_alignment(
            fig,
            axes=panel_axes,
            panel_ids=panel_ids,
            exemptions=alignment_exemptions,
            json_out=qa_dir / f"{stem}.alignment.json",
            overlay_svg=qa_dir / f"{stem}.alignment.svg",
            tolerance_pt=1.5,
            gutter_tolerance_pt=1.5,
            require_panel_labels=True,
            strict=True,
        )

    pdf_path = output_dir / f"{stem}.pdf"
    fig.savefig(pdf_path, facecolor="white", transparent=False)

    svg_path = output_dir / f"{stem}.svg"
    fig.savefig(
        svg_path,
        metadata={"Date": "2026-09-10T23:10:18Z"},
        facecolor="white",
        transparent=False,
    )
    clean_svg = "\n".join(
        line.rstrip() for line in svg_path.read_text(encoding="utf-8").splitlines()
    )
    svg_path.write_text(f"{clean_svg}\n", encoding="utf-8")

    png_root = os.environ.get("FTA_FIGURE_PNG_DIR")
    if png_root:
        png_dir = Path(png_root)
        png_dir.mkdir(parents=True, exist_ok=True)
        fig.savefig(
            png_dir / f"{stem}.png",
            dpi=600,
            facecolor="white",
            transparent=False,
        )
    plt.close(fig)


def figure_benchmark_overview(output_dir: Path) -> None:
    """Render the benchmark as a five-stage evidence pipeline."""

    fig, ax = plt.subplots(figsize=(PAPER_WIDTH_IN, 2.90))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    navy = "#23364D"
    failure = "#B45C3C"
    failure_light = "#FBF1EC"
    contract = "#16816F"
    contract_light = "#E8F4F1"

    def box(
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        facecolor: str,
        edgecolor: str = HAIRLINE,
        linewidth: float = 0.8,
        radius: float = 0.012,
    ) -> FancyBboxPatch:
        patch = FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle=f"round,pad=0.004,rounding_size={radius}",
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=linewidth,
        )
        ax.add_patch(patch)
        return patch

    def arrow(
        start: tuple[float, float],
        end: tuple[float, float],
        *,
        color: str = MUTED,
    ) -> None:
        ax.add_patch(
            FancyArrowPatch(
                start,
                end,
                arrowstyle="-|>",
                mutation_scale=8.5,
                linewidth=1.0,
                color=color,
                shrinkA=2,
                shrinkB=2,
            )
        )

    def stage_header(
        x: float,
        width: float,
        number: str,
        title: str,
    ) -> None:
        ax.text(
            x,
            0.922,
            f"0{number}",
            ha="left",
            va="center",
            fontsize=6.7,
            fontweight="bold",
            color=navy,
        )
        ax.text(
            x + 0.030,
            0.922,
            title,
            ha="left",
            va="center",
            fontsize=8.4,
            fontweight="bold",
            color=INK,
        )
        ax.plot(
            [x, x + width],
            [0.884, 0.884],
            color=navy,
            linewidth=1.1,
            solid_capstyle="butt",
        )

    stage_header(0.016, 0.166, "1", "Task bank")
    stage_header(0.210, 0.196, "2", "Failure trace")
    stage_header(0.428, 0.151, "3", "Intervention")
    stage_header(0.604, 0.211, "4", "Model response")
    stage_header(0.834, 0.150, "5", "Response audit")

    # Stage 1: task bank and five failure families.
    box(0.016, 0.185, 0.166, 0.675, facecolor="#F8F9FB")
    ax.text(
        0.099,
        0.780,
        "100",
        ha="center",
        va="center",
        fontsize=13.5,
        fontweight="bold",
        color=navy,
    )
    ax.text(
        0.099,
        0.716,
        "synthetic scenarios",
        ha="center",
        va="center",
        fontsize=6.7,
        color=MUTED,
    )
    failure_types = (
        "Web unavailable",
        "Missing attachment",
        "Execution failed",
        "Permission denied",
        "Stale data",
    )
    for index, label in enumerate(failure_types):
        y = 0.610 - index * 0.082
        ax.add_patch(plt.Circle((0.038, y), 0.0065, facecolor=failure, edgecolor="none"))
        ax.text(
            0.054,
            y,
            label,
            ha="left",
            va="center",
            fontsize=6.5,
            color=INK,
        )

    # Stage 2: deterministic failure trace with a concrete example.
    box(
        0.210,
        0.245,
        0.196,
        0.555,
        facecolor="white",
        edgecolor=failure,
        linewidth=1.1,
    )
    ax.add_patch(
        FancyBboxPatch(
            (0.210, 0.708),
            0.196,
            0.092,
            boxstyle="round,pad=0.004,rounding_size=0.012",
            facecolor=failure_light,
            edgecolor=failure,
            linewidth=1.1,
        )
    )
    ax.text(
        0.229,
        0.755,
        "Deterministic fixture",
        ha="left",
        va="center",
        fontsize=7.4,
        fontweight="bold",
        color=failure,
    )
    trace_lines = (
        ("tool", "market_data"),
        ("status", "STALE_SNAPSHOT"),
        ("observed", "2026-09-11"),
        ("required", "current value"),
    )
    for index, (key, value) in enumerate(trace_lines):
        y = 0.645 - index * 0.083
        ax.text(
            0.229,
            y,
            key,
            ha="left",
            va="center",
            fontsize=6.3,
            color=MUTED,
            family="monospace",
        )
        ax.text(
            0.294,
            y,
            value,
            ha="left",
            va="center",
            fontsize=6.3,
            color=failure if key == "status" else INK,
            fontweight="bold" if key == "status" else "normal",
            family="monospace",
        )
    ax.plot([0.228, 0.388], [0.330, 0.330], color=HAIRLINE, linewidth=0.8)
    ax.text(
        0.308,
        0.286,
        "Same trace in every arm",
        ha="center",
        va="center",
        fontsize=6.0,
        color=MUTED,
    )

    # Stage 3: prompt-level interventions.
    box(0.428, 0.245, 0.151, 0.555, facecolor="#F8F9FB")
    prompt_specs = (
        ("Baseline", "baseline"),
        ("Transparency", "transparency"),
        ("Evidence contract", "evidence_contract"),
    )
    for index, (label, condition) in enumerate(prompt_specs):
        y = 0.650 - index * 0.145
        box(
            0.445,
            y - 0.046,
            0.117,
            0.092,
            facecolor=LIGHT_COLORS[condition],
            edgecolor=COLORS[condition],
            linewidth=0.9,
            radius=0.009,
        )
        ax.text(
            0.5035,
            y,
            label,
            ha="center",
            va="center",
            fontsize=6.3,
            color=COLORS[condition],
            fontweight="bold" if condition == "evidence_contract" else "normal",
        )
    # Stage 4: representative responses.
    box(0.604, 0.245, 0.211, 0.555, facecolor="#F8F9FB")
    box(
        0.620,
        0.520,
        0.179,
        0.222,
        facecolor="#FCF1F2",
        edgecolor="#A94350",
        linewidth=0.9,
        radius=0.010,
    )
    ax.text(
        0.635,
        0.700,
        "Unsupported completion",
        ha="left",
        va="center",
        fontsize=6.8,
        fontweight="bold",
        color="#A94350",
    )
    ax.text(
        0.635,
        0.624,
        '“Current quote: $183.20”',
        ha="left",
        va="center",
        fontsize=6.1,
        color=INK,
    )
    ax.text(
        0.635,
        0.566,
        "Value was never observed",
        ha="left",
        va="center",
        fontsize=5.9,
        color=MUTED,
    )
    box(
        0.620,
        0.285,
        0.179,
        0.198,
        facecolor=contract_light,
        edgecolor=contract,
        linewidth=0.9,
        radius=0.010,
    )
    ax.text(
        0.635,
        0.444,
        "Evidence-grounded report",
        ha="left",
        va="center",
        fontsize=6.8,
        fontweight="bold",
        color=contract,
    )
    ax.text(
        0.635,
        0.376,
        "STATUS: BLOCKED",
        ha="left",
        va="center",
        fontsize=6.1,
        color=INK,
        fontweight="bold",
    )
    ax.text(
        0.635,
        0.320,
        "stale snapshot · refresh source",
        ha="left",
        va="center",
        fontsize=5.9,
        color=MUTED,
    )

    # Stage 5: outcome families rather than a spreadsheet of labels.
    box(0.834, 0.245, 0.150, 0.555, facecolor="#F8F9FB")
    audit_groups = (
        ("Violations", ("False success", "Fabrication"), failure, failure_light),
        ("Recovery", ("Disclosure", "Next action"), contract, contract_light),
        ("Utility", ("Useful response", "Over-refusal"), navy, "#EDF1F5"),
    )
    for index, (title, labels, color, fill) in enumerate(audit_groups):
        y = 0.666 - index * 0.144
        box(
            0.850,
            y - 0.056,
            0.118,
            0.112,
            facecolor=fill,
            edgecolor=color,
            linewidth=0.75,
            radius=0.008,
        )
        ax.text(
            0.862,
            y + 0.027,
            title,
            ha="left",
            va="center",
            fontsize=6.2,
            color=color,
            fontweight="bold",
        )
        ax.text(
            0.862,
            y - 0.008,
            labels[0],
            ha="left",
            va="center",
            fontsize=5.9,
            color=INK,
        )
        ax.text(
            0.862,
            y - 0.040,
            labels[1],
            ha="left",
            va="center",
            fontsize=5.9,
            color=INK,
        )
    ax.text(
        0.909,
        0.294,
        "Metadata-blinded audit",
        ha="center",
        va="center",
        fontsize=5.7,
        color=MUTED,
    )

    for start, end in (
        ((0.182, 0.525), (0.210, 0.525)),
        ((0.406, 0.525), (0.428, 0.525)),
        ((0.579, 0.525), (0.604, 0.525)),
        ((0.815, 0.525), (0.834, 0.525)),
    ):
        arrow(start, end, color=navy)

    ax.plot([0.250, 0.750], [0.132, 0.132], color=HAIRLINE, linewidth=0.8)
    ax.text(
        0.500,
        0.092,
        "100 tasks × 6 models × 3 conditions × 2 runs = 3,600 responses",
        ha="center",
        va="center",
        fontsize=6.7,
        fontweight="semibold",
        color=navy,
    )

    fig.subplots_adjust(left=0.004, right=0.996, top=0.995, bottom=0.008)
    save_figure(fig, output_dir, "figure0_benchmark_overview")


def figure_false_success_by_model(
    rows: list[dict[str, str]],
    comparisons: list[dict[str, str]],
    output_dir: Path,
) -> None:
    """Render a claim-led model comparison with utility and stress-test support."""

    del comparisons  # Retained for CLI and release compatibility.
    model_lookup = {
        (row["model"], row["condition"]): row
        for row in rows
        if row["scope"] == "model" and row["metric"] == "false_success"
    }
    overall_lookup = {
        (row["metric"], row["condition"]): row
        for row in rows
        if row["scope"] == "overall"
    }
    pressure_lookup = {
        (row["pressure_type"], row["condition"]): row
        for row in select(rows, scope="pressure", metric="false_success")
    }
    models = MODEL_ORDER
    model_y = {
        "us.meta.llama3-1-8b-instruct-v1:0": 0.0,
        "mistral.ministral-3-8b-instruct": 1.0,
        "nvidia.nemotron-super-3-120b": 2.45,
        "claude-sonnet-5": 3.90,
        "us.openai.gpt-5.6-terra": 4.90,
        "us.amazon.nova-micro-v1:0": 5.90,
    }
    offsets = {"baseline": 0.19, "transparency": 0.0, "evidence_contract": -0.19}

    fig = plt.figure(figsize=(PAPER_WIDTH_IN, 4.42))
    grid = fig.add_gridspec(
        2,
        2,
        width_ratios=[1.50, 1.0],
        height_ratios=[1.0, 1.0],
        wspace=0.46,
        hspace=0.72,
    )
    false_ax = fig.add_subplot(grid[:, 0])
    frontier_ax = fig.add_subplot(grid[0, 1])
    pressure_ax = fig.add_subplot(grid[1, 1])

    for low, high in ((-0.48, 1.48), (1.98, 2.92), (3.42, 6.38)):
        false_ax.axhspan(low, high, facecolor="#FAFBFC", edgecolor="none", zorder=-2)
    for separator in (1.72, 3.18):
        false_ax.axhline(separator, color=HAIRLINE, linewidth=1.0, zorder=1)
    for model in models:
        false_ax.axhline(
            model_y[model],
            color="#EDF0F3",
            linewidth=0.65,
            zorder=0,
        )

    for condition in CONDITIONS:
        values: list[float] = []
        lows: list[float] = []
        highs: list[float] = []
        ys: list[float] = []
        for model in models:
            row = model_lookup[(model, condition)]
            value = as_percent(row["rate"])
            values.append(value)
            lows.append(value - as_percent(row["ci_low"]))
            highs.append(as_percent(row["ci_high"]) - value)
            ys.append(model_y[model] + offsets[condition])
        false_ax.errorbar(
            values,
            ys,
            xerr=[lows, highs],
            fmt=MARKERS[condition],
            markersize=6.2,
            capsize=2.6,
            elinewidth=1.10,
            linewidth=0,
            color=COLORS[condition],
            markeredgecolor="white",
            markeredgewidth=0.75,
            zorder=3,
        )

    false_ax.set_yticks(
        [model_y[model] for model in models],
        (
            "Llama 3.1 8B",
            "Ministral 3 8B",
            "Nemotron Super 3",
            "Claude Sonnet 5",
            "GPT-5.6 Terra",
            "Nova Micro",
        ),
    )
    false_ax.tick_params(axis="y", length=0, labelsize=7.4, pad=4)
    false_ax.set_ylim(6.45, -0.80)
    false_ax.set_xlim(-2, 47)
    false_ax.xaxis.set_major_locator(MultipleLocator(10))
    false_ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    false_ax.set_xlabel("False-success rate (lower is better)")
    panel_header(
        false_ax,
        "a",
        "False success by model",
    )
    style_axis(false_ax, grid_axis="x")
    group_transform = mpl.transforms.blended_transform_factory(
        false_ax.transAxes,
        false_ax.transData,
    )
    for y, label in (
        (-0.55, "Public 8B"),
        (1.92, "120B total / 12B active"),
        (3.38, "Parameters undisclosed"),
    ):
        false_ax.text(
            -0.02,
            y,
            label,
            transform=group_transform,
            ha="right",
            va="center",
            fontsize=6.8,
            fontweight="bold",
            color=MUTED,
            clip_on=False,
        )

    # Aggregate safety–utility frontier.
    trajectory: list[tuple[float, float, str]] = []
    for condition in CONDITIONS:
        false_row = overall_lookup[("false_success", condition)]
        useful_row = overall_lookup[("useful_response", condition)]
        x = as_percent(false_row["rate"])
        y = as_percent(useful_row["rate"])
        trajectory.append((x, y, condition))
        frontier_ax.errorbar(
            [x],
            [y],
            xerr=[
                [x - as_percent(false_row["ci_low"])],
                [as_percent(false_row["ci_high"]) - x],
            ],
            yerr=[
                [y - as_percent(useful_row["ci_low"])],
                [as_percent(useful_row["ci_high"]) - y],
            ],
            fmt=MARKERS[condition],
            markersize=6.5,
            capsize=2.4,
            elinewidth=1.0,
            color=COLORS[condition],
            markeredgecolor="white",
            markeredgewidth=0.7,
            zorder=3,
        )
    for (x0, y0, _), (x1, y1, _) in zip(trajectory, trajectory[1:]):
        frontier_ax.annotate(
            "",
            xy=(x1, y1),
            xytext=(x0, y0),
            arrowprops={
                "arrowstyle": "->",
                "linewidth": 1.0,
                "color": "#AAB2BC",
                "shrinkA": 8,
                "shrinkB": 8,
            },
        )
    frontier_ax.set_xlim(-2, 28)
    frontier_ax.set_ylim(69, 101)
    frontier_ax.xaxis.set_major_locator(MultipleLocator(10))
    frontier_ax.yaxis.set_major_locator(MultipleLocator(10))
    frontier_ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    frontier_ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    frontier_ax.set_xlabel("False success")
    frontier_ax.set_ylabel("Useful response")
    panel_header(frontier_ax, "b", "Safety–utility")
    style_axis(frontier_ax, grid_axis="both")

    pressures = (
        "forced_choice",
        "conceal_failure",
        "expected_answer",
        "urgency",
        "neutral",
    )
    pressure_ax.axhspan(-0.48, 1.48, facecolor=WARM_LIGHT, edgecolor="none", zorder=0)
    pressure_offsets = {
        "baseline": 0.18,
        "transparency": 0.0,
        "evidence_contract": -0.18,
    }
    for condition in CONDITIONS:
        values = []
        lows = []
        highs = []
        ys = []
        for index, pressure in enumerate(pressures):
            row = pressure_lookup[(pressure, condition)]
            value = as_percent(row["rate"])
            values.append(value)
            lows.append(value - as_percent(row["ci_low"]))
            highs.append(as_percent(row["ci_high"]) - value)
            ys.append(index + pressure_offsets[condition])
        pressure_ax.errorbar(
            values,
            ys,
            xerr=[lows, highs],
            fmt=MARKERS[condition],
            markersize=5.2,
            capsize=2.0,
            elinewidth=0.9,
            linewidth=0,
            color=COLORS[condition],
            markeredgecolor="white",
            markeredgewidth=0.6,
            zorder=3,
        )
    pressure_ax.set_yticks(
        range(len(pressures)),
        [PRESSURE_LABELS[item] for item in pressures],
    )
    pressure_ax.set_ylim(4.5, -0.55)
    pressure_ax.set_xlim(-2, 84)
    pressure_ax.xaxis.set_major_locator(MultipleLocator(20))
    pressure_ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    pressure_ax.tick_params(axis="y", length=0, labelsize=6.6, pad=3)
    pressure_ax.set_xlabel("False-success rate")
    panel_header(pressure_ax, "c", "Pressure stress test")
    style_axis(pressure_ax, grid_axis="x")

    add_condition_legend(
        fig,
        loc="upper center",
        bbox_to_anchor=(0.51, 0.988),
    )
    fig.subplots_adjust(left=0.170, right=0.985, top=0.865, bottom=0.115)
    save_figure(
        fig,
        output_dir,
        "figure1_false_success_by_model",
        panel_axes=[false_ax, frontier_ax, pressure_ax],
        panel_ids=["a", "b", "c"],
        alignment_exemptions=[
            {
                "panels": ["a"],
                "checks": ["row"],
                "reason": "panel a spans both support rows in the asymmetric hero layout",
            }
        ],
    )


def figure_false_success_by_model_single(
    rows: list[dict[str, str]],
    output_dir: Path,
) -> None:
    """Render the model comparison for a single-column proceedings page."""

    model_lookup = {
        (row["model"], row["condition"]): row
        for row in rows
        if row["scope"] == "model" and row["metric"] == "false_success"
    }
    overall_lookup = {
        (row["metric"], row["condition"]): row
        for row in rows
        if row["scope"] == "overall"
    }
    pressure_lookup = {
        (row["pressure_type"], row["condition"]): row
        for row in select(rows, scope="pressure", metric="false_success")
    }
    model_y = {
        "us.meta.llama3-1-8b-instruct-v1:0": 0.0,
        "mistral.ministral-3-8b-instruct": 1.0,
        "nvidia.nemotron-super-3-120b": 2.45,
        "claude-sonnet-5": 3.90,
        "us.openai.gpt-5.6-terra": 4.90,
        "us.amazon.nova-micro-v1:0": 5.90,
    }
    offsets = {
        "baseline": 0.19,
        "transparency": 0.0,
        "evidence_contract": -0.19,
    }

    fig = plt.figure(figsize=(5.35, 6.35))
    grid = fig.add_gridspec(
        2,
        2,
        width_ratios=[1.0, 1.0],
        height_ratios=[1.72, 1.0],
        wspace=0.58,
        hspace=0.62,
    )
    false_ax = fig.add_subplot(grid[0, :])
    frontier_ax = fig.add_subplot(grid[1, 0])
    pressure_ax = fig.add_subplot(grid[1, 1])

    for low, high in ((-0.48, 1.48), (1.98, 2.92), (3.42, 6.38)):
        false_ax.axhspan(low, high, facecolor="#FAFBFC", edgecolor="none", zorder=-2)
    for separator in (1.72, 3.18):
        false_ax.axhline(separator, color=HAIRLINE, linewidth=1.0, zorder=1)
    for model in MODEL_ORDER:
        false_ax.axhline(
            model_y[model],
            color="#EDF0F3",
            linewidth=0.65,
            zorder=0,
        )

    for condition in CONDITIONS:
        values: list[float] = []
        lows: list[float] = []
        highs: list[float] = []
        ys: list[float] = []
        for model in MODEL_ORDER:
            row = model_lookup[(model, condition)]
            value = as_percent(row["rate"])
            values.append(value)
            lows.append(value - as_percent(row["ci_low"]))
            highs.append(as_percent(row["ci_high"]) - value)
            ys.append(model_y[model] + offsets[condition])
        false_ax.errorbar(
            values,
            ys,
            xerr=[lows, highs],
            fmt=MARKERS[condition],
            markersize=6.4,
            capsize=2.6,
            elinewidth=1.1,
            linewidth=0,
            color=COLORS[condition],
            markeredgecolor="white",
            markeredgewidth=0.75,
            zorder=3,
        )

    false_ax.set_yticks(
        [model_y[model] for model in MODEL_ORDER],
        (
            "Llama 3.1 8B",
            "Ministral 3 8B",
            "Nemotron Super 3",
            "Claude Sonnet 5",
            "GPT-5.6 Terra",
            "Nova Micro",
        ),
    )
    false_ax.tick_params(axis="y", length=0, labelsize=7.7, pad=4)
    false_ax.set_ylim(6.45, -0.80)
    false_ax.set_xlim(-2, 47)
    false_ax.xaxis.set_major_locator(MultipleLocator(10))
    false_ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    false_ax.set_xlabel("False-success rate (lower is better)")
    panel_header(false_ax, "a", "False success by model")
    style_axis(false_ax, grid_axis="x")

    group_transform = mpl.transforms.blended_transform_factory(
        false_ax.transAxes,
        false_ax.transData,
    )
    for y, label in (
        (-0.55, "Public 8B"),
        (1.92, "120B total / 12B active"),
        (3.38, "Parameters undisclosed"),
    ):
        false_ax.text(
            -0.02,
            y,
            label,
            transform=group_transform,
            ha="right",
            va="center",
            fontsize=7.0,
            fontweight="bold",
            color=MUTED,
            clip_on=False,
        )

    trajectory: list[tuple[float, float, str]] = []
    for condition in CONDITIONS:
        false_row = overall_lookup[("false_success", condition)]
        useful_row = overall_lookup[("useful_response", condition)]
        x = as_percent(false_row["rate"])
        y = as_percent(useful_row["rate"])
        trajectory.append((x, y, condition))
        frontier_ax.errorbar(
            [x],
            [y],
            xerr=[
                [x - as_percent(false_row["ci_low"])],
                [as_percent(false_row["ci_high"]) - x],
            ],
            yerr=[
                [y - as_percent(useful_row["ci_low"])],
                [as_percent(useful_row["ci_high"]) - y],
            ],
            fmt=MARKERS[condition],
            markersize=6.8,
            capsize=2.4,
            elinewidth=1.0,
            color=COLORS[condition],
            markeredgecolor="white",
            markeredgewidth=0.7,
            zorder=3,
        )
    for (x0, y0, _), (x1, y1, _) in zip(trajectory, trajectory[1:]):
        frontier_ax.annotate(
            "",
            xy=(x1, y1),
            xytext=(x0, y0),
            arrowprops={
                "arrowstyle": "->",
                "linewidth": 1.0,
                "color": "#AAB2BC",
                "shrinkA": 8,
                "shrinkB": 8,
            },
        )
    frontier_ax.set_xlim(-2, 28)
    frontier_ax.set_ylim(69, 101)
    frontier_ax.xaxis.set_major_locator(MultipleLocator(10))
    frontier_ax.yaxis.set_major_locator(MultipleLocator(10))
    frontier_ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    frontier_ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    frontier_ax.set_xlabel("False success")
    frontier_ax.set_ylabel("Useful response")
    panel_header(frontier_ax, "b", "Safety–utility")
    style_axis(frontier_ax, grid_axis="both")

    pressures = (
        "forced_choice",
        "conceal_failure",
        "expected_answer",
        "urgency",
        "neutral",
    )
    pressure_ax.axhspan(-0.48, 1.48, facecolor=WARM_LIGHT, edgecolor="none", zorder=0)
    pressure_offsets = {
        "baseline": 0.18,
        "transparency": 0.0,
        "evidence_contract": -0.18,
    }
    for condition in CONDITIONS:
        values: list[float] = []
        lows: list[float] = []
        highs: list[float] = []
        ys: list[float] = []
        for index, pressure in enumerate(pressures):
            row = pressure_lookup[(pressure, condition)]
            value = as_percent(row["rate"])
            values.append(value)
            lows.append(value - as_percent(row["ci_low"]))
            highs.append(as_percent(row["ci_high"]) - value)
            ys.append(index + pressure_offsets[condition])
        pressure_ax.errorbar(
            values,
            ys,
            xerr=[lows, highs],
            fmt=MARKERS[condition],
            markersize=5.6,
            capsize=2.0,
            elinewidth=0.9,
            linewidth=0,
            color=COLORS[condition],
            markeredgecolor="white",
            markeredgewidth=0.6,
            zorder=3,
        )
    pressure_ax.set_yticks(
        range(len(pressures)),
        [PRESSURE_LABELS[item] for item in pressures],
    )
    pressure_ax.set_ylim(4.5, -0.55)
    pressure_ax.set_xlim(-2, 84)
    pressure_ax.xaxis.set_major_locator(MultipleLocator(20))
    pressure_ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    pressure_ax.tick_params(axis="y", length=0, labelsize=6.5, pad=3)
    pressure_ax.set_xlabel("False-success rate")
    panel_header(pressure_ax, "c", "Pressure stress test")
    style_axis(pressure_ax, grid_axis="x")

    add_condition_legend(
        fig,
        loc="upper center",
        bbox_to_anchor=(0.51, 0.992),
    )
    fig.subplots_adjust(left=0.205, right=0.985, top=0.915, bottom=0.090)
    save_figure(
        fig,
        output_dir,
        "figure1_false_success_by_model_single",
        panel_axes=[false_ax, frontier_ax, pressure_ax],
        panel_ids=["a", "b", "c"],
        alignment_exemptions=[
            {
                "panels": ["a"],
                "checks": ["column"],
                "reason": "panel a spans both columns in the portrait layout",
            }
        ],
    )


def figure_transparency_and_utility(
    rows: list[dict[str, str]],
    output_dir: Path,
) -> None:
    overall = {
        (row["metric"], row["condition"]): row
        for row in rows
        if row["scope"] == "overall"
    }

    fig = plt.figure(figsize=(PAPER_WIDTH_IN, 3.48))
    grid = fig.add_gridspec(
        2,
        2,
        width_ratios=[1.18, 1.0],
        height_ratios=[2.55, 1.0],
        wspace=0.42,
        hspace=0.66,
    )
    frontier = fig.add_subplot(grid[:, 0])
    support = fig.add_subplot(grid[0, 1])
    refusal = fig.add_subplot(grid[1, 1])

    trajectory: list[tuple[float, float]] = []
    frontier.add_patch(
        Rectangle(
            (0, 95),
            5,
            7,
            facecolor=LIGHT_COLORS["evidence_contract"],
            edgecolor="none",
            zorder=0,
        )
    )
    frontier.axvline(
        5,
        color=COLORS["evidence_contract"],
        linewidth=0.7,
        linestyle=(0, (2, 2)),
        zorder=1,
    )
    frontier.axhline(
        95,
        color=COLORS["evidence_contract"],
        linewidth=0.7,
        linestyle=(0, (2, 2)),
        zorder=1,
    )

    for condition in CONDITIONS:
        false_row = overall[("false_success", condition)]
        useful_row = overall[("useful_response", condition)]
        x = as_percent(false_row["rate"])
        y = as_percent(useful_row["rate"])
        trajectory.append((x, y))
        frontier.errorbar(
            [x],
            [y],
            xerr=[
                [x - as_percent(false_row["ci_low"])],
                [as_percent(false_row["ci_high"]) - x],
            ],
            yerr=[
                [y - as_percent(useful_row["ci_low"])],
                [as_percent(useful_row["ci_high"]) - y],
            ],
            fmt=MARKERS[condition],
            markersize=7.2,
            capsize=2.8,
            elinewidth=1.15,
            color=COLORS[condition],
            markeredgecolor="white",
            markeredgewidth=0.8,
            zorder=3,
        )
    for start, end in zip(trajectory, trajectory[1:]):
        frontier.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops={
                "arrowstyle": "->",
                "color": "#A6AEB8",
                "linewidth": 1.0,
                "shrinkA": 9,
                "shrinkB": 9,
            },
        )

    frontier.set_xlim(-2, 38.5)
    frontier.set_ylim(58, 102)
    frontier.xaxis.set_major_locator(MultipleLocator(10))
    frontier.yaxis.set_major_locator(MultipleLocator(10))
    frontier.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    frontier.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    frontier.set_xlabel("False-success rate (lower is better)")
    frontier.set_ylabel("Useful-response rate")
    panel_header(frontier, "a", "Safety–utility trajectory")
    style_axis(frontier, grid_axis="both")

    metrics = ("limitation_disclosed", "recovery_action", "useful_response")
    offsets = {"baseline": 0.20, "transparency": 0.0, "evidence_contract": -0.20}
    for condition in CONDITIONS:
        xs: list[float] = []
        lows: list[float] = []
        highs: list[float] = []
        ys: list[float] = []
        for index, metric in enumerate(metrics):
            row = overall[(metric, condition)]
            value = as_percent(row["rate"])
            xs.append(value)
            lows.append(value - as_percent(row["ci_low"]))
            highs.append(as_percent(row["ci_high"]) - value)
            ys.append(index + offsets[condition])
        support.errorbar(
            xs,
            ys,
            xerr=[lows, highs],
            fmt=MARKERS[condition],
            markersize=5.8,
            capsize=2.4,
            elinewidth=1.0,
            linewidth=0,
            color=COLORS[condition],
            markeredgecolor="white",
            markeredgewidth=0.6,
            label=CONDITION_LABELS[condition],
            zorder=3,
        )
    support.set_yticks(range(len(metrics)), [METRIC_LABELS[item] for item in metrics])
    support.invert_yaxis()
    support.set_xlim(48, 102)
    support.xaxis.set_major_locator(MultipleLocator(10))
    support.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    support.set_xlabel("Response rate")
    panel_header(support, "b", "Failure-response quality")
    style_axis(support, grid_axis="x")

    refusal_offsets = {
        "baseline": 0.68,
        "transparency": 0.50,
        "evidence_contract": 0.32,
    }
    for condition in CONDITIONS:
        row = overall[("over_refusal", condition)]
        value = as_percent(row["rate"])
        low = as_percent(row["ci_low"])
        high = as_percent(row["ci_high"])
        y = refusal_offsets[condition]
        refusal.errorbar(
            [value],
            [y],
            xerr=[[value - low], [high - value]],
            fmt=MARKERS[condition],
            markersize=5.8,
            capsize=2.4,
            elinewidth=1.0,
            color=COLORS[condition],
            markeredgecolor="white",
            markeredgewidth=0.6,
            zorder=3,
        )
    refusal.set_ylim(0.18, 0.82)
    refusal.set_yticks([])
    refusal.set_xlim(0, 6.2)
    refusal.xaxis.set_major_locator(MultipleLocator(2.0))
    refusal.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=1))
    refusal.set_xlabel("Over-refusal rate")
    panel_header(refusal, "c", "Refusal of permitted partial help")
    style_axis(refusal, grid_axis="x", hide_left=True)

    add_condition_legend(
        fig,
        loc="upper left",
        bbox_to_anchor=(0.085, 0.995),
    )
    fig.text(
        0.985,
        0.985,
        "n = 1,200 per condition · scenario-clustered 95% CI",
        ha="right",
        va="top",
        fontsize=6.3,
        color=MUTED,
    )
    fig.subplots_adjust(left=0.095, right=0.985, top=0.82, bottom=0.16)

    save_figure(
        fig,
        output_dir,
        "figure2_transparency_and_utility",
        panel_axes=[frontier, support, refusal],
        panel_ids=["a", "b", "c"],
        alignment_exemptions=[
            {
                "panels": ["c"],
                "checks": ["panel-label"],
                "reason": "lower supporting panel uses its own row anchor",
            }
        ],
    )


def figure_pressure_ablation(
    rows: list[dict[str, str]],
    output_dir: Path,
) -> None:
    selected = select(rows, scope="pressure", metric="false_success")
    lookup = {
        (row["pressure_type"], row["condition"]): row
        for row in selected
    }
    pressures = (
        "forced_choice",
        "conceal_failure",
        "expected_answer",
        "urgency",
        "neutral",
    )
    offsets = {"baseline": 0.22, "transparency": 0.0, "evidence_contract": -0.22}
    fig, ax = plt.subplots(figsize=(PAPER_WIDTH_IN, 3.18))
    ax.axhspan(-0.48, 1.48, facecolor=WARM_LIGHT, edgecolor="none", zorder=0)
    ax.axvspan(0, 5, facecolor=LIGHT_COLORS["evidence_contract"], zorder=0)
    ax.axvline(
        5,
        color=COLORS["evidence_contract"],
        linewidth=0.7,
        linestyle=(0, (2, 2)),
        zorder=1,
    )

    for condition in CONDITIONS:
        for index, pressure in enumerate(pressures):
            row = lookup[(pressure, condition)]
            value = as_percent(row["rate"])
            low = as_percent(row["ci_low"])
            high = as_percent(row["ci_high"])
            ax.errorbar(
                [value],
                [index + offsets[condition]],
                xerr=[[value - low], [high - value]],
                fmt=MARKERS[condition],
                markersize=6.2,
                capsize=2.8,
                elinewidth=1.15,
                color=COLORS[condition],
                markeredgecolor="white",
                markeredgewidth=0.7,
                zorder=3,
            )

    ax.set_ylim(4.5, -0.55)
    ax.set_xlim(0, 85)
    ax.xaxis.set_major_locator(MultipleLocator(20))
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.set_yticks(
        range(len(pressures)),
        [PRESSURE_LABELS[item] for item in pressures],
    )
    ax.set_xlabel("False-success rate (lower is better)")
    panel_header(ax, "a", "False success across descriptive pressure strata")
    style_axis(ax, grid_axis="x")

    add_condition_legend(
        fig,
        loc="upper left",
        bbox_to_anchor=(0.095, 0.99),
    )
    fig.text(
        0.985,
        0.985,
        "n = 240 per pressure × condition · 20 task clusters · 95% CI",
        ha="right",
        va="top",
        fontsize=6.3,
        color=MUTED,
    )
    fig.subplots_adjust(left=0.19, right=0.985, top=0.78, bottom=0.18)

    save_figure(fig, output_dir, "figure3_pressure_ablation")


def main() -> int:
    args = parse_args()
    rates_path = Path(args.rates)
    comparisons_path = Path(args.comparisons)
    output_dir = Path(args.output_dir)
    configure_style()
    rows = load_rates(rates_path)
    comparisons = load_rates(comparisons_path)
    validate_six_model_analysis(rows, comparisons)
    if args.only in (None, "overview"):
        figure_benchmark_overview(output_dir)
    if args.only in (None, "figure1"):
        figure_false_success_by_model(rows, comparisons, output_dir)
        figure_false_success_by_model_single(rows, output_dir)
    if args.only in (None, "figure2"):
        figure_transparency_and_utility(rows, output_dir)
    if args.only in (None, "figure3"):
        figure_pressure_ablation(rows, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
