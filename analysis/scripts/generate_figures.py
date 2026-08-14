#!/usr/bin/env python3
"""
Generate the TCC figures (fig1..fig6) from the aggregated results CSV.

Usage:
  python generate_figures.py \
      --summary output/preliminary_results.csv \
      --output-dir experiments/results/figures
"""

import argparse
import os

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


SCENARIOS = ["low", "medium", "high"]
SCENARIO_LABELS = {
    "low": "Baixa (50 RPS)",
    "medium": "Média (200 RPS)",
    "high": "Alta (1.000 RPS)",
}
STRATEGIES = ["reactive", "predictive"]
STRATEGY_LABELS = {"reactive": "Reativo", "predictive": "Preditivo"}
STRATEGY_COLORS = {"reactive": "#4477CC", "predictive": "#E8802C"}

BAR_WIDTH = 0.38


def _style() -> None:
    plt.rcParams.update({
        "figure.dpi": 200,
        "font.size": 13,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def _scenarios_present(df: pd.DataFrame) -> list:
    return [s for s in SCENARIOS if s in set(df["scenario"])]


def grouped_bar(df: pd.DataFrame, column: str, ylabel: str, out_path: str,
                show_error: bool = True) -> None:
    """Grouped bar chart: one group per scenario, one bar per strategy."""
    scenarios = _scenarios_present(df)
    fig, ax = plt.subplots(figsize=(11, 6.8))

    for offset, strategy in zip((-BAR_WIDTH / 2, BAR_WIDTH / 2), STRATEGIES):
        means, errors = [], []
        for scenario in scenarios:
            values = df[(df["strategy"] == strategy)
                        & (df["scenario"] == scenario)][column].dropna()
            means.append(values.mean() if not values.empty else 0.0)
            errors.append(values.std() if len(values) > 1 else 0.0)

        ax.bar(
            [i + offset for i in range(len(scenarios))],
            means,
            width=BAR_WIDTH,
            yerr=errors if show_error else None,
            capsize=5,
            label=STRATEGY_LABELS[strategy],
            color=STRATEGY_COLORS[strategy],
            edgecolor="black",
            linewidth=0.8,
        )

    ax.set_xticks(range(len(scenarios)))
    ax.set_xticklabels([SCENARIO_LABELS[s] for s in scenarios])
    ax.set_ylabel(ylabel)
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  wrote {out_path}")


def availability_bar(df: pd.DataFrame, out_path: str) -> None:
    """Availability needs a zoomed y-axis — percentages sit near 100%."""
    scenarios = _scenarios_present(df)
    values = df["availability"].dropna()
    if values.empty:
        return

    fig, ax = plt.subplots(figsize=(11, 6.8))
    for offset, strategy in zip((-BAR_WIDTH / 2, BAR_WIDTH / 2), STRATEGIES):
        means, errors = [], []
        for scenario in scenarios:
            subset = df[(df["strategy"] == strategy)
                        & (df["scenario"] == scenario)]["availability"].dropna()
            means.append(subset.mean() if not subset.empty else 0.0)
            errors.append(subset.std() if len(subset) > 1 else 0.0)

        ax.bar(
            [i + offset for i in range(len(scenarios))],
            means,
            width=BAR_WIDTH,
            yerr=errors,
            capsize=5,
            label=STRATEGY_LABELS[strategy],
            color=STRATEGY_COLORS[strategy],
            edgecolor="black",
            linewidth=0.8,
        )

    lower = max(0.0, values.min() - 0.4)
    ax.set_ylim(lower, 100.2)
    ax.set_xticks(range(len(scenarios)))
    ax.set_xticklabels([SCENARIO_LABELS[s] for s in scenarios])
    ax.set_ylabel("Disponibilidade (%)")
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  wrote {out_path}")


def boxplot_p95(df: pd.DataFrame, out_path: str) -> None:
    """One boxplot panel per scenario, comparing both strategies."""
    scenarios = _scenarios_present(df)
    fig, axes = plt.subplots(1, len(scenarios), figsize=(5.5 * len(scenarios), 6.5))
    if len(scenarios) == 1:
        axes = [axes]

    for ax, scenario in zip(axes, scenarios):
        data, labels, colors = [], [], []
        for strategy in STRATEGIES:
            values = df[(df["strategy"] == strategy)
                        & (df["scenario"] == scenario)]["latency_p95"].dropna()
            data.append(values.values)
            labels.append(STRATEGY_LABELS[strategy])
            colors.append(STRATEGY_COLORS[strategy])

        box = ax.boxplot(data, tick_labels=labels, patch_artist=True, widths=0.5)
        for patch, color in zip(box["boxes"], colors):
            patch.set_facecolor(color)
        for element in ("medians", "whiskers", "caps"):
            for line in box[element]:
                line.set_color("black")

        ax.set_title(SCENARIO_LABELS[scenario])

    axes[0].set_ylabel("Latência P95 (ms)")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  wrote {out_path}")


def variance_bar(df: pd.DataFrame, out_path: str) -> None:
    """Standard deviation of P95 per scenario/strategy (stability comparison)."""
    scenarios = _scenarios_present(df)
    fig, ax = plt.subplots(figsize=(11, 6.8))

    for offset, strategy in zip((-BAR_WIDTH / 2, BAR_WIDTH / 2), STRATEGIES):
        stds = []
        for scenario in scenarios:
            values = df[(df["strategy"] == strategy)
                        & (df["scenario"] == scenario)]["latency_p95"].dropna()
            stds.append(values.std() if len(values) > 1 else 0.0)

        ax.bar(
            [i + offset for i in range(len(scenarios))],
            stds,
            width=BAR_WIDTH,
            label=STRATEGY_LABELS[strategy],
            color=STRATEGY_COLORS[strategy],
            edgecolor="black",
            linewidth=0.8,
        )

    ax.set_xticks(range(len(scenarios)))
    ax.set_xticklabels([SCENARIO_LABELS[s] for s in scenarios])
    ax.set_ylabel("Desvio-padrão da Latência P95 (ms)")
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"  wrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate TCC figures from results CSV")
    parser.add_argument("--summary", required=True, help="Aggregated results CSV")
    parser.add_argument("--output-dir", required=True, help="Directory for the PNG figures")
    args = parser.parse_args()

    df = pd.read_csv(args.summary)
    os.makedirs(args.output_dir, exist_ok=True)
    _style()

    print(f"Generating figures from {args.summary}")
    grouped_bar(df, "latency_p95", "Latência P95 (ms)",
                os.path.join(args.output_dir, "fig1_latencia_p95.png"))
    grouped_bar(df, "latency_p99", "Latência P99 (ms)",
                os.path.join(args.output_dir, "fig2_latencia_p99.png"))
    availability_bar(df, os.path.join(args.output_dir, "fig3_disponibilidade.png"))
    grouped_bar(df, "cpu_total_mean", "CPU Média (cores)",
                os.path.join(args.output_dir, "fig4_cpu.png"))
    boxplot_p95(df, os.path.join(args.output_dir, "fig5_boxplot_p95.png"))
    variance_bar(df, os.path.join(args.output_dir, "fig6_variancia.png"))
    print("Done.")


if __name__ == "__main__":
    main()
