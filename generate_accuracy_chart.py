import os
import json
import numpy as np
import matplotlib.pyplot as plt

def generate_accuracy_chart(metrics, best_model, output_path):
    # Sort metrics by accuracy descending
    metrics_sorted = sorted(metrics, key=lambda x: x.get("accuracy", 0), reverse=True)
    models = [m["model"] for m in metrics_sorted]
    accuracies = [m["accuracy"] * 100 for m in metrics_sorted]

    # Use default light background style for matplotlib
    plt.style.use('default')
    fig, ax = plt.subplots(figsize=(8, 4.5))

    # Use bright accent blue for best model, dark gray for other models
    colors = ['#3b82f6' if m == best_model else '#475569' for m in models]
    bars = ax.barh(models, accuracies, color=colors, height=0.55, edgecolor='none')
    
    ax.invert_yaxis()
    ax.set_xlim(85, 101)
    ax.set_title("Model Accuracy Comparison", fontsize=14, fontweight='bold', pad=20, color='#0f172a')
    ax.set_xlabel("Accuracy (%)", fontsize=11, color='#334155', labelpad=10)
    
    # Tick parameters with dark color for labels
    ax.tick_params(axis='both', colors='#334155', labelsize=10)
    
    for spine in ['top', 'right', 'bottom', 'left']:
        ax.spines[spine].set_visible(False)
        
    ax.xaxis.grid(True, linestyle='--', alpha=0.2, color='#94a3b8')
    ax.set_axisbelow(True)

    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + 0.3,
            bar.get_y() + bar.get_height() / 2,
            f"{width:.3f}%",
            ha='left',
            va='center',
            color='#0f172a',
            fontweight='bold',
            fontsize=9.5
        )

    plt.tight_layout()
    plt.savefig(output_path, dpi=160, transparent=True)
    plt.close()
    print(f"Generated accuracy chart at {output_path}")

def generate_metrics_chart(metrics, output_path):
    # Sort by model name or f1 score to keep consistent layout
    metrics_sorted = sorted(metrics, key=lambda x: x.get("f1", 0), reverse=True)
    
    models = [m["model"] for m in metrics_sorted]
    precisions = [m.get("precision", m.get("precision_score", 0)) * 100 for m in metrics_sorted]
    recalls = [m.get("recall", m.get("recall_score", 0)) * 100 for m in metrics_sorted]
    f1s = [m.get("f1", m.get("f1_score", 0)) * 100 for m in metrics_sorted]

    plt.style.use('default')
    fig, ax = plt.subplots(figsize=(9, 5.5))

    y = np.arange(len(models))
    height = 0.22

    # Draw grouped bars
    rects1 = ax.barh(y - height, precisions, height, label='Precision', color='#3b82f6', edgecolor='none')
    rects2 = ax.barh(y, recalls, height, label='Recall', color='#10b981', edgecolor='none')
    rects3 = ax.barh(y + height, f1s, height, label='F1-Score', color='#8b5cf6', edgecolor='none')

    ax.invert_yaxis()
    ax.set_yticks(y)
    ax.set_yticklabels(models, fontsize=10.5, color='#0f172a')
    ax.set_xlim(60, 103)
    
    ax.set_title("Precision, Recall & F1-Score Comparison", fontsize=14, fontweight='bold', pad=22, color='#0f172a')
    ax.set_xlabel("Score (%)", fontsize=11, color='#334155', labelpad=10)
    
    # Tick parameters with dark color for labels
    ax.tick_params(axis='both', colors='#334155', labelsize=10)
    
    ax.legend(facecolor='#ffffff', edgecolor='#cbd5e1', labelcolor='#0f172a', loc='lower left')

    for spine in ['top', 'right', 'bottom', 'left']:
        ax.spines[spine].set_visible(False)
        
    ax.xaxis.grid(True, linestyle='--', alpha=0.2, color='#94a3b8')
    ax.set_axisbelow(True)

    # Helper function to place text on bars
    def add_labels(rects):
        for rect in rects:
            width = rect.get_width()
            ax.text(
                width + 0.5,
                rect.get_y() + rect.get_height() / 2,
                f"{width:.1f}%",
                ha='left',
                va='center',
                color='#0f172a',
                fontsize=8.5
            )

    add_labels(rects1)
    add_labels(rects2)
    add_labels(rects3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=160, transparent=True)
    plt.close()
    print(f"Generated metrics comparison chart at {output_path}")

def main():
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    summary_path = os.path.join(workspace_dir, "reports", "model_training_summary.json")
    
    acc_output = os.path.join(workspace_dir, "visualizations", "model_accuracy_comparison.png")
    metrics_output = os.path.join(workspace_dir, "visualizations", "model_metrics_comparison.png")

    if not os.path.exists(summary_path):
        print(f"Error: {summary_path} not found.")
        return

    with open(summary_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    metrics = data.get("metrics", [])
    best_model = data.get("best_model", "")

    if not metrics:
        print("Error: No model metrics found in training summary.")
        return

    generate_accuracy_chart(metrics, best_model, acc_output)
    generate_metrics_chart(metrics, metrics_output)

if __name__ == "__main__":
    main()
