#!/usr/bin/env python3
"""Render publication-quality paper figures from the frozen analysis tables."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
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
    "nvidia.nemotron-super-3-120b": "Nemotron Super 3",
    "us.openai.gpt-5.6-terra": "GPT-5.6 Terra",
}
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
            "results/confirmatory-20260910-v1/"
            "analysis-model-judge/rates.csv"
        ),
        help="Frozen analysis rates CSV.",
    )
    parser.add_argument(
        "--comparisons",
        default=(
            "results/confirmatory-20260910-v1/"
            "analysis-model-judge/comparisons.csv"
        ),
        help="Frozen paired-comparison CSV.",
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
            "svg.hashsalt": "failure-transparent-agents-v0.2.0",
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
    ax.text(
        0,
        1,
        label,
        transform=label_transform,
        ha="left",
        va="bottom",
        fontsize=8.4,
        fontweight="bold",
        color=INK,
        visible=False,
    )
    ax.text(
        0,
        1,
        f"{label}   {title}",
        transform=label_transform,
        ha="left",
        va="bottom",
        fontsize=8.4,
        fontweight="bold",
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
    raw_pdf_path = output_dir / f".{stem}.raw.pdf"
    fig.savefig(raw_pdf_path, facecolor="white", transparent=False)

    ghostscript = shutil.which("gs")
    if ghostscript:
        subprocess.run(
            [
                ghostscript,
                "-q",
                "-dSAFER",
                "-dBATCH",
                "-dNOPAUSE",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                "-dAutoRotatePages=/None",
                "-dPDFSETTINGS=/prepress",
                f"-sOutputFile={pdf_path}",
                str(raw_pdf_path),
            ],
            check=True,
        )
        raw_pdf_path.unlink()
    else:
        raw_pdf_path.replace(pdf_path)

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
    """Render the controlled experiment and its factorial structure."""

    fig, ax = plt.subplots(figsize=(PAPER_WIDTH_IN, 2.42))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def card(
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        facecolor: str,
        edgecolor: str = HAIRLINE,
        linewidth: float = 0.85,
        radius: float = 0.012,
    ) -> FancyBboxPatch:
        patch = FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle=f"round,pad=0.006,rounding_size={radius}",
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
        label: str | None = None,
    ) -> None:
        ax.add_patch(
            FancyArrowPatch(
                start,
                end,
                arrowstyle="-|>",
                mutation_scale=9,
                linewidth=0.95,
                color=MUTED,
                shrinkA=2,
                shrinkB=2,
            )
        )
        if label:
            ax.text(
                (start[0] + end[0]) / 2,
                start[1] + 0.055,
                label,
                ha="center",
                va="bottom",
                fontsize=6.2,
                color=MUTED,
            )

    def stage_header(
        x: float,
        y: float,
        number: str,
        title: str,
        *,
        accent: str = MUTED,
    ) -> None:
        ax.text(
            x,
            y,
            number,
            ha="center",
            va="center",
            fontsize=7.2,
            fontweight="bold",
            color=accent,
        )
        ax.text(
            x + 0.021,
            y,
            title,
            ha="left",
            va="center",
            fontsize=8.1,
            fontweight="bold",
            color=INK,
        )

    card(
        0.018,
        0.20,
        0.185,
        0.66,
        facecolor="#F7F8FA",
        edgecolor="none",
    )
    stage_header(0.043, 0.790, "1", "Scenario bank")
    ax.text(
        0.110,
        0.630,
        "100 scenarios",
        ha="center",
        va="center",
        fontsize=10.0,
        fontweight="bold",
        color=INK,
    )
    ax.text(
        0.110,
        0.415,
        "5 failure types · 5 pressure strata",
        ha="center",
        va="center",
        fontsize=5.8,
        color=MUTED,
    )

    card(
        0.244,
        0.20,
        0.182,
        0.66,
        facecolor="#F9FAFB",
        edgecolor="none",
    )
    stage_header(0.269, 0.790, "2", "Fixed failure trace")
    ax.add_patch(plt.Circle((0.280, 0.590), 0.009, facecolor=WARM, edgecolor="none"))
    ax.text(
        0.300,
        0.590,
        "failed evidence",
        ha="left",
        va="center",
        fontsize=7.2,
        fontweight="bold",
        color=WARM,
    )
    ax.add_patch(
        plt.Circle(
            (0.270, 0.440),
            0.009,
            facecolor=COLORS["evidence_contract"],
            edgecolor="none",
        )
    )
    ax.text(
        0.345,
        0.440,
        "partial help is valid",
        ha="center",
        va="center",
        fontsize=7.0,
        fontweight="bold",
        color=COLORS["evidence_contract"],
    )
    ax.text(
        0.335,
        0.285,
        "same trace in every arm",
        ha="center",
        va="center",
        fontsize=6.5,
        color=MUTED,
    )

    card(
        0.466,
        0.14,
        0.287,
        0.76,
        facecolor="#FBFCFD",
        edgecolor="none",
    )
    stage_header(
        0.491,
        0.830,
        "3",
        "Factorial response collection",
        accent=COLORS["transparency"],
    )
    ax.text(
        0.610,
        0.700,
        "3 prompts × 3 models × 2 runs",
        ha="center",
        va="center",
        fontsize=9.0,
        fontweight="bold",
        color=INK,
    )
    prompt_specs = (
        ("Baseline", "baseline"),
        ("Transparency instruction", "transparency"),
        ("Evidence contract", "evidence_contract"),
    )
    for index, (label, condition) in enumerate(prompt_specs):
        y = 0.555 - index * 0.116
        card(
            0.492,
            y - 0.037,
            0.236,
            0.074,
            facecolor=LIGHT_COLORS[condition],
            edgecolor=COLORS[condition],
            linewidth=0.9 if condition == "evidence_contract" else 0.75,
            radius=0.009,
        )
        ax.text(
            0.610,
            y,
            label,
            ha="center",
            va="center",
            fontsize=6.8,
            fontweight="bold" if condition == "evidence_contract" else "normal",
            color=COLORS[condition],
        )
    ax.text(
        0.610,
        0.245,
        "OpenAI · Anthropic · NVIDIA/open-weight",
        ha="center",
        va="center",
        fontsize=6.3,
        color=MUTED,
    )

    card(
        0.794,
        0.20,
        0.188,
        0.66,
        facecolor="#F7F8FA",
        edgecolor="none",
    )
    stage_header(
        0.819,
        0.790,
        "4",
        "Blinded scoring",
        accent=COLORS["evidence_contract"],
    )
    ax.text(
        0.888,
        0.590,
        "5 response metrics",
        ha="center",
        va="center",
        fontsize=8.5,
        fontweight="bold",
        color=INK,
    )
    ax.text(
        0.872,
        0.430,
        "false success is primary",
        ha="center",
        va="center",
        fontsize=6.6,
        color=WARM,
    )
    ax.text(
        0.904,
        0.290,
        "95% clustered intervals",
        ha="center",
        va="center",
        fontsize=6.2,
        color=MUTED,
    )

    arrow((0.203, 0.525), (0.244, 0.525))
    arrow((0.426, 0.525), (0.466, 0.525))
    arrow((0.753, 0.525), (0.794, 0.525))

    card(
        0.350,
        0.015,
        0.300,
        0.085,
        facecolor=INK,
        edgecolor=INK,
        linewidth=0,
        radius=0.015,
    )
    ax.text(
        0.500,
        0.057,
        "100 × 3 × 3 × 2 = 1,800 responses",
        ha="center",
        va="center",
        fontsize=7.3,
        fontweight="bold",
        color="white",
    )

    fig.subplots_adjust(left=0.004, right=0.996, top=0.985, bottom=0.01)
    save_figure(fig, output_dir, "figure0_benchmark_overview")


def figure_false_success_by_model(
    rows: list[dict[str, str]],
    comparisons: list[dict[str, str]],
    output_dir: Path,
) -> None:
    """Show absolute rates and paired mitigation effects by model."""

    selected = select(rows, scope="model", metric="false_success")
    lookup = {
        (row["model"], row["condition"]): row
        for row in selected
    }
    effect_lookup = {
        (row["scope_value"], row["intervention_condition"]): row
        for row in comparisons
        if row["scope"] == "model" and row["metric"] == "false_success"
    }
    models = (
        "us.openai.gpt-5.6-terra",
        "claude-sonnet-5",
        "nvidia.nemotron-super-3-120b",
    )
    offsets = {"baseline": 0.20, "transparency": 0.0, "evidence_contract": -0.20}

    fig = plt.figure(figsize=(PAPER_WIDTH_IN, 3.10))
    grid = fig.add_gridspec(
        1,
        2,
        width_ratios=[1.16, 1.0],
        wspace=0.34,
    )
    rate_ax = fig.add_subplot(grid[0, 0])
    effect_ax = fig.add_subplot(grid[0, 1])
    y_positions = list(range(len(models)))

    rate_ax.axvspan(
        0,
        5,
        facecolor=LIGHT_COLORS["evidence_contract"],
        zorder=0,
    )
    rate_ax.axvline(
        5,
        color=COLORS["evidence_contract"],
        linewidth=0.8,
        linestyle=(0, (2, 2)),
    )
    for y in (0.5, 1.5):
        rate_ax.axhline(y, color="#F0F2F5", linewidth=0.8, zorder=0)
        effect_ax.axhline(y, color="#F0F2F5", linewidth=0.8, zorder=0)

    for condition in CONDITIONS:
        xs: list[float] = []
        lows: list[float] = []
        highs: list[float] = []
        ys: list[float] = []
        for index, model in enumerate(models):
            row = lookup[(model, condition)]
            value = as_percent(row["rate"])
            low = as_percent(row["ci_low"])
            high = as_percent(row["ci_high"])
            xs.append(value)
            lows.append(value - low)
            highs.append(high - value)
            ys.append(index + offsets[condition])
        rate_ax.errorbar(
            xs,
            ys,
            xerr=[lows, highs],
            fmt=MARKERS[condition],
            markersize=6.4,
            capsize=2.8,
            elinewidth=1.25,
            linewidth=0,
            color=COLORS[condition],
            markeredgecolor="white",
            markeredgewidth=0.7,
            label=CONDITION_LABELS[condition],
            zorder=3,
        )

    for condition in ("transparency", "evidence_contract"):
        xs = []
        lows = []
        highs = []
        ys = []
        for index, model in enumerate(models):
            row = effect_lookup[(model, condition)]
            reduction = -as_percent(row["absolute_difference"])
            ci_low = -as_percent(row["absolute_difference_ci_high"])
            ci_high = -as_percent(row["absolute_difference_ci_low"])
            xs.append(reduction)
            lows.append(reduction - ci_low)
            highs.append(ci_high - reduction)
            ys.append(index + offsets[condition])
        effect_ax.errorbar(
            xs,
            ys,
            xerr=[lows, highs],
            fmt=MARKERS[condition],
            markersize=6.4,
            capsize=2.8,
            elinewidth=1.25,
            linewidth=0,
            color=COLORS[condition],
            markeredgecolor="white",
            markeredgewidth=0.7,
            zorder=3,
        )

    rate_ax.set_yticks(y_positions, [MODEL_LABELS[model] for model in models])
    rate_ax.set_ylim(2.5, -0.55)
    rate_ax.set_xlim(-1.0, 50)
    rate_ax.xaxis.set_major_locator(MultipleLocator(10))
    rate_ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    rate_ax.set_xlabel("Observed false-success rate")
    panel_header(rate_ax, "a", "Absolute risk")
    style_axis(rate_ax, grid_axis="x")

    effect_ax.axvline(0, color=MUTED, linewidth=0.9)
    effect_ax.set_yticks([])
    effect_ax.set_ylim(2.5, -0.55)
    effect_ax.set_xlim(0, 50)
    effect_ax.xaxis.set_major_locator(MultipleLocator(10))
    effect_ax.xaxis.set_major_formatter(
        mpl.ticker.FuncFormatter(lambda value, _: f"{value:.0f} pp")
    )
    effect_ax.set_xlabel("Reduction versus baseline (higher is better)")
    panel_header(effect_ax, "b", "Paired mitigation effect")
    style_axis(effect_ax, grid_axis="x", hide_left=True)
    effect_ax.yaxis.set_major_locator(mpl.ticker.NullLocator())
    effect_ax.yaxis.set_minor_locator(mpl.ticker.NullLocator())
    effect_ax.tick_params(
        axis="y",
        which="both",
        left=False,
        right=False,
        labelleft=False,
        length=0,
    )
    for tick in (*effect_ax.yaxis.majorTicks, *effect_ax.yaxis.minorTicks):
        tick.set_visible(False)

    add_condition_legend(
        fig,
        loc="lower left",
        bbox_to_anchor=(0.032, 0.902),
    )
    fig.text(
        0.985,
        0.944,
        "n = 200 per cell · scenario-clustered 95% CI",
        ha="right",
        va="bottom",
        fontsize=6.6,
        color=MUTED,
    )
    fig.subplots_adjust(left=0.155, right=0.985, top=0.78, bottom=0.18)
    save_figure(
        fig,
        output_dir,
        "figure1_false_success_by_model",
        panel_axes=[rate_ax, effect_ax],
        panel_ids=["a", "b"],
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
    refusal.set_xlim(-0.05, 2.15)
    refusal.xaxis.set_major_locator(MultipleLocator(0.5))
    refusal.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=1))
    refusal.set_xlabel("Over-refusal rate")
    panel_header(refusal, "c", "Cost of the intervention")
    style_axis(refusal, grid_axis="x", hide_left=True)

    add_condition_legend(
        fig,
        loc="upper left",
        bbox_to_anchor=(0.085, 0.995),
    )
    fig.text(
        0.985,
        0.985,
        "n = 600 per condition · scenario-clustered 95% CI",
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
        "neutral",
        "expected_answer",
        "urgency",
    )
    fig, axes = plt.subplots(
        1,
        3,
        figsize=(PAPER_WIDTH_IN, 3.02),
        sharex=True,
        sharey=True,
        gridspec_kw={"wspace": 0.12},
    )
    panel_ids = ("a", "b", "c")

    for panel_id, condition, ax in zip(panel_ids, CONDITIONS, axes):
        ax.axhspan(-0.48, 1.48, facecolor=WARM_LIGHT, edgecolor="none", zorder=0)
        ax.axvspan(0, 5, facecolor=LIGHT_COLORS["evidence_contract"], zorder=0)
        ax.axvline(
            5,
            color=COLORS["evidence_contract"],
            linewidth=0.7,
            linestyle=(0, (2, 2)),
            zorder=1,
        )
        for index, pressure in enumerate(pressures):
            row = lookup[(pressure, condition)]
            value = as_percent(row["rate"])
            low = as_percent(row["ci_low"])
            high = as_percent(row["ci_high"])
            ax.errorbar(
                [value],
                [index],
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
        ax.set_xlim(-3, 105)
        ax.xaxis.set_major_locator(MultipleLocator(25))
        ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
        panel_header(ax, panel_id, CONDITION_LABELS[condition])
        style_axis(ax, grid_axis="x")

    axes[0].set_yticks(
        range(len(pressures)),
        [PRESSURE_LABELS[item] for item in pressures],
    )
    axes[1].tick_params(labelleft=False)
    axes[2].tick_params(labelleft=False)
    fig.supxlabel(
        "False-success rate (lower is better)",
        x=0.58,
        y=0.045,
        fontsize=7.8,
        color=INK,
    )
    fig.text(
        0.985,
        0.975,
        "n = 120 per pressure × condition · scenario-clustered 95% CI",
        ha="right",
        va="top",
        fontsize=6.3,
        color=MUTED,
    )
    fig.subplots_adjust(left=0.165, right=0.985, top=0.79, bottom=0.19)

    save_figure(
        fig,
        output_dir,
        "figure3_pressure_ablation",
        panel_axes=list(axes),
        panel_ids=list(panel_ids),
    )


def main() -> int:
    args = parse_args()
    rates_path = Path(args.rates)
    comparisons_path = Path(args.comparisons)
    output_dir = Path(args.output_dir)
    configure_style()
    rows = load_rates(rates_path)
    comparisons = load_rates(comparisons_path)
    if args.only in (None, "overview"):
        figure_benchmark_overview(output_dir)
    if args.only in (None, "figure1"):
        figure_false_success_by_model(rows, comparisons, output_dir)
    if args.only in (None, "figure2"):
        figure_transparency_and_utility(rows, output_dir)
    if args.only in (None, "figure3"):
        figure_pressure_ablation(rows, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
