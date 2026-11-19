import os
import ezdxf


def export_bom_to_dxf(bom_items: list, output_path: str) -> str:
    """Exports staged BOM steel members and takeoff dimensions into an AutoCAD / .dxf file."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    for layer_name, color_id in [("BM_STEEL", 3), ("BM_DIMS", 4), ("BM_TEXT", 7)]:
        if layer_name not in doc.layers:
            doc.layers.add(name=layer_name, color=color_id)

    y_cursor = 0.0
    for idx, item in enumerate(bom_items, start=1):
        model = str(item.get("model") or item.get("designation") or f"MEMBER-{idx}")
        qty = int(float(item.get("qty", 1) or 1))
        length_ft = float(item.get("length_ft") or item.get("length") or 10.0)
        length_in = max(12.0, length_ft * 12.0)

        # Draw scaled member centerline & flange profile box in inches
        msp.add_lwpolyline(
            [(0.0, y_cursor), (length_in, y_cursor), (length_in, y_cursor + 8.0), (0.0, y_cursor + 8.0)],
            close=True,
            dxfattribs={"layer": "BM_STEEL"},
        )
        msp.add_text(
            f"#{idx}: (x{qty}) {model} - {length_ft:.2f} ft",
            dxfattribs={"layer": "BM_TEXT", "height": 4.5, "insert": (0.0, y_cursor + 11.0)},
        )
        y_cursor -= 32.0

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc.saveas(output_path)
    return output_path
