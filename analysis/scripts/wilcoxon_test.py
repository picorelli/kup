#!/usr/bin/env python3
"""
Script para executar teste de Wilcoxon pareado entre estratégias.
"""

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def load_experiment_summary(summary_file: str) -> pd.DataFrame:
    """Carrega sumário de experimentos."""
    return pd.read_csv(summary_file)


def wilcoxon_test(reactive: np.ndarray, predictive: np.ndarray, metric_name: str) -> dict:
    """Executa teste de Wilcoxon pareado."""
    if len(reactive) != len(predictive):
        print(f"  ⚠️  Tamanhos diferentes: reactive={len(reactive)}, predictive={len(predictive)}")
        min_len = min(len(reactive), len(predictive))
        reactive = reactive[:min_len]
        predictive = predictive[:min_len]
    
    if len(reactive) < 5:
        print(f"  ⚠️  Amostras insuficientes para {metric_name}: n={len(reactive)}")
        return {
            "metric": metric_name,
            "n": len(reactive),
            "statistic": np.nan,
            "p_value": np.nan,
            "significant": False,
            "reactive_mean": np.mean(reactive),
            "predictive_mean": np.mean(predictive),
            "difference": np.mean(predictive) - np.mean(reactive),
            "improvement_pct": np.nan,
        }
    
    try:
        statistic, p_value = stats.wilcoxon(reactive, predictive)
    except Exception as e:
        print(f"  ⚠️  Erro no teste para {metric_name}: {e}")
        return {
            "metric": metric_name,
            "n": len(reactive),
            "statistic": np.nan,
            "p_value": np.nan,
            "significant": False,
            "reactive_mean": np.mean(reactive),
            "predictive_mean": np.mean(predictive),
            "difference": np.mean(predictive) - np.mean(reactive),
            "improvement_pct": np.nan,
        }
    
    reactive_mean = np.mean(reactive)
    predictive_mean = np.mean(predictive)
    difference = predictive_mean - reactive_mean
    
    # Calcula melhoria percentual
    if reactive_mean != 0:
        improvement_pct = ((reactive_mean - predictive_mean) / reactive_mean) * 100
    else:
        improvement_pct = 0
    
    return {
        "metric": metric_name,
        "n": len(reactive),
        "statistic": statistic,
        "p_value": p_value,
        "significant": p_value < 0.05,
        "reactive_mean": reactive_mean,
        "predictive_mean": predictive_mean,
        "difference": difference,
        "improvement_pct": improvement_pct,
    }


def compare_strategies(df: pd.DataFrame, scenario: str = None) -> list:
    """Compara estratégias para um cenário específico."""
    if scenario:
        df = df[df["scenario"] == scenario]
    
    reactive_data = df[df["strategy"] == "reactive"]
    predictive_data = df[df["strategy"] == "predictive"]
    
    if len(reactive_data) == 0 or len(predictive_data) == 0:
        print(f"  ⚠️  Dados insuficientes para comparação")
        return []
    
    # Métricas a comparar (alinhadas com colunas produzidas por calculate_metrics.py)
    metrics_to_compare = [
        "latency_p95",
        "latency_p99",
        "latency_mean",
        "error_rate",
        "availability",
        "cpu_total_mean",
        "replicas_total_mean",
    ]
    
    results = []
    
    for metric in metrics_to_compare:
        if metric not in reactive_data.columns or metric not in predictive_data.columns:
            continue
        
        reactive_values = reactive_data[metric].dropna().values
        predictive_values = predictive_data[metric].dropna().values
        
        if len(reactive_values) == 0 or len(predictive_values) == 0:
            continue
        
        result = wilcoxon_test(reactive_values, predictive_values, metric)
        result["scenario"] = scenario or "all"
        results.append(result)
    
    return results


def run_analysis(summary_file: str, output: str):
    """Executa análise estatística completa."""
    print("📊 Análise Estatística - Teste de Wilcoxon Pareado")
    print("=" * 60)
    
    df = load_experiment_summary(summary_file)
    
    print(f"\n📂 Dados carregados: {len(df)} experimentos")
    print(f"   Estratégias: {df['strategy'].unique()}")
    print(f"   Cenários: {df['scenario'].unique()}")
    
    all_results = []
    
    # Análise por cenário
    for scenario in df["scenario"].unique():
        print(f"\n{'─' * 60}")
        print(f"📈 Cenário: {scenario.upper()}")
        print(f"{'─' * 60}")
        
        results = compare_strategies(df, scenario)
        all_results.extend(results)
        
        for result in results:
            significance = "✅ SIGNIFICATIVO" if result["significant"] else "❌ Não significativo"
            improvement = f"{result['improvement_pct']:.1f}%" if not np.isnan(result['improvement_pct']) else "N/A"
            
            print(f"\n  📊 {result['metric']}:")
            print(f"     Reativo (média): {result['reactive_mean']:.4f}")
            print(f"     Preditivo (média): {result['predictive_mean']:.4f}")
            print(f"     p-value: {result['p_value']:.4f}")
            print(f"     Improvement: {improvement}")
            print(f"     {significance}")
    
    # Análise global
    print(f"\n{'═' * 60}")
    print("📈 ANÁLISE GLOBAL (todos os cenários)")
    print(f"{'═' * 60}")
    
    global_results = compare_strategies(df)
    all_results.extend(global_results)
    
    for result in global_results:
        significance = "✅ SIGNIFICATIVO" if result["significant"] else "❌ Não significativo"
        improvement = f"{result['improvement_pct']:.1f}%" if not np.isnan(result['improvement_pct']) else "N/A"
        
        print(f"\n  📊 {result['metric']}:")
        print(f"     Reativo (média): {result['reactive_mean']:.4f}")
        print(f"     Preditivo (média): {result['predictive_mean']:.4f}")
        print(f"     p-value: {result['p_value']:.4f}")
        print(f"     Improvement: {improvement}")
        print(f"     {significance}")
    
    # Save results
    results_df = pd.DataFrame(all_results)
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    results_df.to_csv(output, index=False)
    
    print(f"\n{'═' * 60}")
    print(f"Results saved to: {output}")
    
    # Final summary
    significant_count = sum(1 for r in all_results if r.get("significant", False))
    total_count = len(all_results)
    
    print(f"\nSummary:")
    print(f"   Total comparisons: {total_count}")
    print(f"   Significant (p < 0.05): {significant_count}")
    print(f"   Significance rate: {significant_count/total_count*100:.1f}%" if total_count > 0 else "   N/A")


def main():
    parser = argparse.ArgumentParser(description="Run Wilcoxon test")
    parser.add_argument("--summary", required=True, help="CSV file with experiment summary")
    parser.add_argument("--output", default="wilcoxon_results.csv", help="Output CSV file")
    
    args = parser.parse_args()
    
    run_analysis(args.summary, args.output)


if __name__ == "__main__":
    main()
