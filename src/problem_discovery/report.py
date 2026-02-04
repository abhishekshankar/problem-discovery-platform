from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(output_dir: Path, run_id: str, payload: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"run_{run_id}.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


def write_html(output_dir: Path, run_id: str, payload: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"run_{run_id}.html"
    rows = []
    for idx, cluster in enumerate(payload.get("top_opportunities", []), start=1):
        rows.append(
            f"<tr><td>{idx}</td><td>{cluster.get('cluster_name')}</td>"
            f"<td>{cluster.get('scores', {}).get('final_score')}</td>"
            f"<td>{cluster.get('description')}</td></tr>"
        )
    table = "".join(rows)
    html = f"""
    <html>
    <head><title>Problem Discovery Run {run_id}</title></head>
    <body>
      <h1>Problem Discovery Run</h1>
      <p>Niche: {payload.get('niche')}</p>
      <p>Run ID: {run_id}</p>
      <h2>Top Opportunities</h2>
      <table border=\"1\" cellspacing=\"0\" cellpadding=\"6\">
        <tr><th>#</th><th>Cluster</th><th>Score</th><th>Description</th></tr>
        {table}
      </table>
    </body>
    </html>
    """
    with path.open("w", encoding="utf-8") as handle:
        handle.write(html)
    return path
