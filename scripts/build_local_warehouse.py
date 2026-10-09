from __future__ import annotations

import json
from pathlib import Path

from restaurant_ops.warehouse import build_local_warehouse, run_quality_checks


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    result = build_local_warehouse(root)
    result["quality"] = run_quality_checks(root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

