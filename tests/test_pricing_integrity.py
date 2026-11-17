import json
import os


def test_pricing_integrity():
    required_files = [
        "matrix.json",
        "shop_safeguards.json",
        "steel_matrix.json",
        "project_ledger.json",
        os.path.join("config", "connection_presets.json"),
    ]
    for rf in required_files:
        assert os.path.exists(rf), f"Missing required data file: {rf}"
        with open(rf, "r", encoding="utf-8-sig") as f:
            json.load(f)

    with open("shop_safeguards.json", "r", encoding="utf-8-sig") as f:
        sg = json.load(f)
    assert sg["base_labor_rate"] > 0 and sg["labor_markup"] >= 1.0

    with open(os.path.join("config", "connection_presets.json"), "r", encoding="utf-8-sig") as f:
        cp = json.load(f)
    assert len(cp["presets"]) >= 5


if __name__ == "__main__":
    test_pricing_integrity()
    print("[PASS] All 5 pricing & Advance Steel JSON databases verified.")