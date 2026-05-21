from __future__ import annotations

from typing import Any

from memory.memory_store import MemoryStore


class MarkdownReportGenerator:
    def generate(self, memory: MemoryStore, dataset_name: str = "") -> str:
        analysis = memory.analysis
        session = memory.session
        dataset = memory.dataset
        if analysis is None or not analysis.steps:
            return "# Analysis Report\n\nNo analysis steps recorded yet.\n"

        lines = [
            "# Data Analysis Report",
            "",
            "## 1. 分析目标",
            analysis.goal or session.last_resolved_query or "N/A",
            "",
            "## 2. 数据集概览",
            f"- Dataset: {dataset_name or (dataset.dataset_id if dataset else 'unknown')}",
            f"- Source: {dataset.source_type if dataset else 'csv'}",
            f"- Tables: {', '.join(dataset.tables) if dataset else 'N/A'}",
            "",
            "## 3. 使用字段",
        ]
        if dataset:
            lines.append(f"- Metrics: {', '.join(dataset.common_metrics)}")
            lines.append(f"- Dimensions: {', '.join(dataset.common_dimensions)}")
            lines.append(f"- Time columns: {', '.join(dataset.common_time_columns)}")
        lines.extend(["", "## 4. 分析步骤"])

        for step in analysis.steps:
            lines.extend([
                "",
                f"### Step {step['step_id']}: {step['question']}",
                "",
                "**SQL:**",
                "```sql",
                step["sql"],
                "```",
                "",
                "**结果摘要:**",
                f"- Row count: {step['summary'].get('row_count', 'N/A')}",
            ])
            if step.get("insights"):
                lines.append(f"- Insights: {'; '.join(step['insights'])}")

        lines.extend(["", "## 5. 主要发现"])
        for finding in analysis.main_findings:
            lines.append(f"- {finding}")

        lines.extend(["", "## 6. 限制与不确定性"])
        for limitation in analysis.limitations:
            lines.append(f"- {limitation}")

        lines.extend(["", "## 7. 下一步建议"])
        suggestions = analysis.follow_up_suggestions or [
            "继续按其他维度拆分分析",
            "检查数据质量",
        ]
        for suggestion in suggestions:
            lines.append(f"- {suggestion}")

        return "\n".join(lines) + "\n"


class ReportBuilder:
    def __init__(self) -> None:
        self.generator = MarkdownReportGenerator()

    def build(self, memory: MemoryStore, dataset_name: str = "") -> str:
        return self.generator.generate(memory, dataset_name)


class ExportManager:
    def __init__(self, reports_dir: str = "reports") -> None:
        from pathlib import Path
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def export_markdown(self, content: str, filename: str) -> str:
        path = self.reports_dir / filename
        path.write_text(content, encoding="utf-8")
        return str(path)
