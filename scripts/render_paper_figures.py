#!/usr/bin/env python3
"""Render publication-quality paper figures from the frozen analysis tables."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

os.environ.setdefault("SOURCE_DATE_EPOCH", "1789081818")

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.ticker import PercentFormatter


CONDITIONS = ("baseline", "transparency", "evidence_contract")
CONDITION_LABELS = {
    "baseline": "Baseline",
    "transparency": "Transparency instruction",
    "evidence_contract": "Evidence contract",
}
COLORS = {
    "baseline": "#6B7280",
    "transparency": "#0072B2",
    "evidence_contract": "#009E73",
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
    "over_refusal": "Over-refusal",
}


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
        "--output-dir",
        default="paper/figures",
        help="Destination for editable SVG and publication PDF files.",
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


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.linewidth": 0.8,
            "axes.edgecolor": "#374151",
            "axes.labelcolor": "#111827",
            "xtick.color": "#374151",
            "ytick.color": "#374151",
            "text.color": "#111827",
            "grid.color": "#E5E7EB",
            "grid.linewidth": 0.7,
            "grid.alpha": 1.0,
            "pdf.fonttype": 42,
            "pdf.use14corefonts": True,
            "ps.fonttype": 42,
            "svg.hashsalt": "failure-transparent-agents-v0.2.0",
            "svg.fonttype": "none",
            "savefig.bbox": "tight",
            "savefig.facecolor": "white",
            "savefig.pad_inches": 0.04,
            "savefig.transparent": False,
        }
    )


def style_axis(ax: mpl.axes.Axes, *, grid_axis: str = "x") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis=grid_axis)
    ax.set_axisbelow(True)


def save_figure(fig: mpl.figure.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
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
    plt.close(fig)


def figure_benchmark_overview(output_dir: Path) -> None:
    """Render the benchmark dataflow and evidence-contract intervention."""

    fig, ax = plt.subplots(figsize=(7.15, 2.35))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def box(
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        facecolor: str,
        edgecolor: str = "#9CA3AF",
        linewidth: float = 0.9,
        radius: float = 0.018,
    ) -> FancyBboxPatch:
        patch = FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle=f"round,pad=0.008,rounding_size={radius}",
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=linewidth,
        )
        ax.add_patch(patch)
        return patch

    def arrow(start: tuple[float, float], end: tuple[float, float]) -> None:
        ax.add_patch(
            FancyArrowPatch(
                start,
                end,
                arrowstyle="-|>",
                mutation_scale=10,
                linewidth=1.0,
                color="#6B7280",
                shrinkA=2,
                shrinkB=2,
            )
        )

    box(0.01, 0.25, 0.14, 0.50, facecolor="#F3F4F6")
    ax.text(0.08, 0.62, "Scenario", ha="center", va="center", weight="bold")
    ax.text(
        0.08,
        0.43,
        "User request\nRequired evidence\nSafe partial help",
        ha="center",
        va="center",
        fontsize=7.2,
        linespacing=1.35,
    )

    box(0.19, 0.32, 0.12, 0.36, facecolor="#FFF7E6", edgecolor="#E69F00")
    ax.text(
        0.25,
        0.56,
        "Deterministic\nsimulator",
        ha="center",
        va="center",
        weight="bold",
        fontsize=8,
    )
    ax.text(
        0.25,
        0.41,
        "Replay failure",
        ha="center",
        va="center",
        fontsize=7.1,
        color="#7C4A03",
    )

    box(0.35, 0.25, 0.15, 0.50, facecolor="#FFF7E6", edgecolor="#E69F00")
    ax.text(
        0.425,
        0.62,
        "Failed prerequisite",
        ha="center",
        va="center",
        weight="bold",
        fontsize=8,
    )
    ax.text(
        0.425,
        0.43,
        "status\nerror code\nmessage + metadata",
        ha="center",
        va="center",
        fontsize=7.2,
        linespacing=1.35,
    )

    box(0.54, 0.13, 0.22, 0.74, facecolor="#FFFFFF")
    ax.text(
        0.65,
        0.79,
        "Prompt condition",
        ha="center",
        va="center",
        weight="bold",
        fontsize=8.2,
    )
    box(0.565, 0.60, 0.17, 0.11, facecolor="#F3F4F6", edgecolor="#9CA3AF")
    ax.text(0.65, 0.655, "Baseline", ha="center", va="center", fontsize=7.5)
    box(0.565, 0.44, 0.17, 0.11, facecolor="#EAF4FB", edgecolor="#0072B2")
    ax.text(
        0.65,
        0.495,
        "Transparency instruction",
        ha="center",
        va="center",
        fontsize=7.2,
        color="#005A8D",
    )
    box(0.565, 0.20, 0.17, 0.18, facecolor="#EAF7F2", edgecolor="#009E73")
    ax.text(
        0.65,
        0.325,
        "Evidence contract",
        ha="center",
        va="center",
        fontsize=7.4,
        weight="bold",
        color="#007A58",
    )
    ax.text(
        0.65,
        0.245,
        "status | evidence\nlimitation | next action",
        ha="center",
        va="center",
        fontsize=6.2,
        color="#16624D",
        linespacing=1.25,
    )

    box(0.80, 0.32, 0.08, 0.36, facecolor="#EEF2FF", edgecolor="#8491B4")
    ax.text(
        0.84,
        0.50,
        "Model\nresponse",
        ha="center",
        va="center",
        weight="bold",
        fontsize=7.5,
        linespacing=1.3,
    )

    box(0.91, 0.20, 0.08, 0.60, facecolor="#F3F4F6")
    ax.text(
        0.95,
        0.70,
        "Metadata-blinded\nlabels",
        ha="center",
        va="center",
        weight="bold",
        fontsize=7.4,
    )
    ax.text(
        0.95,
        0.45,
        "False success\nFabrication\nDisclosure\nRecovery\nUsefulness",
        ha="center",
        va="center",
        fontsize=6.5,
        linespacing=1.22,
    )

    arrow((0.15, 0.50), (0.19, 0.50))
    arrow((0.31, 0.50), (0.35, 0.50))
    arrow((0.50, 0.50), (0.54, 0.50))
    arrow((0.76, 0.50), (0.80, 0.50))
    arrow((0.88, 0.50), (0.91, 0.50))

    fig.subplots_adjust(left=0.005, right=0.995, top=0.98, bottom=0.02)
    save_figure(fig, output_dir, "figure0_benchmark_overview")


def figure_false_success_by_model(
    rows: list[dict[str, str]],
    output_dir: Path,
) -> None:
    selected = select(rows, scope="model", metric="false_success")
    lookup = {
        (row["model"], row["condition"]): row
        for row in selected
    }
    models = (
        "us.openai.gpt-5.6-terra",
        "claude-sonnet-5",
        "nvidia.nemotron-super-3-120b",
    )
    offsets = {"baseline": 0.20, "transparency": 0.0, "evidence_contract": -0.20}

    fig, ax = plt.subplots(figsize=(7.15, 3.15))
    y_positions = list(range(len(models)))
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
        ax.errorbar(
            xs,
            ys,
            xerr=[lows, highs],
            fmt=MARKERS[condition],
            markersize=6,
            capsize=3,
            elinewidth=1.2,
            linewidth=0,
            color=COLORS[condition],
            markeredgecolor="white",
            markeredgewidth=0.7,
            label=CONDITION_LABELS[condition],
            zorder=3,
        )

    ax.set_yticks(y_positions, [MODEL_LABELS[model] for model in models])
    ax.invert_yaxis()
    ax.set_xlim(-1, 50)
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.set_xlabel("False-success rate (lower is better)")
    style_axis(ax, grid_axis="x")
    ax.legend(
        frameon=False,
        ncol=3,
        loc="lower left",
        bbox_to_anchor=(0.0, 1.01),
        borderaxespad=0,
        handletextpad=0.5,
        columnspacing=1.4,
    )
    save_figure(fig, output_dir, "figure1_false_success_by_model")


def figure_transparency_and_utility(
    rows: list[dict[str, str]],
    output_dir: Path,
) -> None:
    overall = {
        (row["metric"], row["condition"]): row
        for row in rows
        if row["scope"] == "overall"
    }

    fig, (frontier, support) = plt.subplots(
        1,
        2,
        figsize=(7.15, 3.35),
        gridspec_kw={"width_ratios": [1.05, 1.25], "wspace": 0.35},
    )

    trajectory: list[tuple[float, float]] = []
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
            markersize=7,
            capsize=3,
            elinewidth=1.1,
            color=COLORS[condition],
            markeredgecolor="white",
            markeredgewidth=0.8,
            zorder=3,
        )
        frontier.annotate(
            CONDITION_LABELS[condition],
            (x, y),
            xytext=(5, 6 if condition != "baseline" else -14),
            textcoords="offset points",
            fontsize=7.5,
            color=COLORS[condition],
        )
    for start, end in zip(trajectory, trajectory[1:]):
        frontier.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops={
                "arrowstyle": "->",
                "color": "#9CA3AF",
                "linewidth": 1.1,
                "shrinkA": 8,
                "shrinkB": 8,
            },
        )

    frontier.set_xlim(-2, 38)
    frontier.set_ylim(58, 102)
    frontier.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    frontier.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    frontier.set_xlabel("False-success rate (lower is better)")
    frontier.set_ylabel("Useful response rate")
    frontier.set_title("(a) Safety–utility frontier", loc="left", fontweight="bold")
    frontier.text(
        0.5,
        100.5,
        "preferred region",
        color="#6B7280",
        fontsize=7,
        ha="left",
        va="top",
    )
    style_axis(frontier, grid_axis="both")

    metrics = ("limitation_disclosed", "recovery_action", "over_refusal")
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
            markersize=5.5,
            capsize=2.5,
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
    support.set_xlim(-3, 103)
    support.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    support.set_xlabel("Response rate")
    support.set_title("(b) Supporting behaviors", loc="left", fontweight="bold")
    style_axis(support, grid_axis="x")
    handles, labels = support.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.01),
        ncol=3,
        borderaxespad=0,
        handletextpad=0.5,
        columnspacing=1.4,
    )
    fig.subplots_adjust(bottom=0.20)

    save_figure(fig, output_dir, "figure2_transparency_and_utility")


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
    offsets = {"baseline": 0.20, "transparency": 0.0, "evidence_contract": -0.20}

    fig, ax = plt.subplots(figsize=(7.15, 3.35))
    for condition in CONDITIONS:
        xs: list[float] = []
        lows: list[float] = []
        highs: list[float] = []
        ys: list[float] = []
        for index, pressure in enumerate(pressures):
            row = lookup[(pressure, condition)]
            value = as_percent(row["rate"])
            xs.append(value)
            lows.append(value - as_percent(row["ci_low"]))
            highs.append(as_percent(row["ci_high"]) - value)
            ys.append(index + offsets[condition])
        ax.errorbar(
            xs,
            ys,
            xerr=[lows, highs],
            fmt=MARKERS[condition],
            markersize=6,
            capsize=3,
            elinewidth=1.1,
            linewidth=0,
            color=COLORS[condition],
            markeredgecolor="white",
            markeredgewidth=0.7,
            label=CONDITION_LABELS[condition],
            zorder=3,
        )

    ax.set_yticks(range(len(pressures)), [PRESSURE_LABELS[item] for item in pressures])
    ax.invert_yaxis()
    ax.set_xlim(-2, 102)
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.set_xlabel("False-success rate (lower is better)")
    style_axis(ax, grid_axis="x")
    ax.legend(
        frameon=False,
        ncol=3,
        loc="lower left",
        bbox_to_anchor=(0.0, 1.01),
        borderaxespad=0,
        handletextpad=0.5,
        columnspacing=1.4,
    )
    save_figure(fig, output_dir, "figure3_pressure_ablation")


def main() -> int:
    args = parse_args()
    rates_path = Path(args.rates)
    output_dir = Path(args.output_dir)
    configure_style()
    rows = load_rates(rates_path)
    figure_benchmark_overview(output_dir)
    figure_false_success_by_model(rows, output_dir)
    figure_transparency_and_utility(rows, output_dir)
    figure_pressure_ablation(rows, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
