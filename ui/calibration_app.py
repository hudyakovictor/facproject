"""
calibration_app.py v3.3
Gradio UI для калибровки анализа кожи по фото за один день, 9 ракурсов.

Запуск на M1:
1. Сначала запусти stage1 extraction:
   python run_calibration.py --input /path/to/calibration_photos --output /path/to/run

2. Потом запусти калибровку UI:
   pip install gradio
   python ui/calibration_app.py --stage1 /path/to/run/stage1

Или без Gradio — CLI:
   python ui/calibration_app.py --stage1 /path/to/run/stage1 --no_gradio
"""
import os
import sys
import argparse
import json
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ui.calibration_core import CalibrationEngine


def launch_gradio(args):
    try:
        import gradio as gr
    except ImportError:
        print("Gradio not installed, run: pip install gradio")
        return False

    engine = CalibrationEngine(uv_size=args.uv_size)

    def calibrate_fn(stage1_dir):
        if not stage1_dir or not os.path.exists(stage1_dir):
            return "Path not exists", None

        profile = engine.calibrate_from_stage1(stage1_dir)

        # Save
        tmp_out = Path(stage1_dir) / "_calibration_profile.json"
        engine.save_profile(profile, str(tmp_out))

        # Format summary
        v = profile.get('verdict', {})
        summary = f"""
### Verdict: {v.get('confidence', 'N/A')} — Same person: {v.get('same_person', 'N/A')}

{v.get('message', '')}

**Poses found:** {', '.join(profile.get('poses_found', []))}
**Total images:** {profile.get('total_images', 0)}

**Variability (same-person baseline):**
- Laplacian var std: {profile.get('variability', {}).get('laplacian_var_std', 0):.2f}
- LBP entropy std: {profile.get('variability', {}).get('lbp_entropy_std', 0):.4f}

**Calibrated thresholds:**
{json.dumps(profile.get('thresholds', {}), indent=2)}

**Cross-pose validation:**
{json.dumps({k: v for k, v in list(profile.get('cross_pose_validation', {}).items())[:5]}, indent=2)}
"""

        with open(tmp_out, 'r') as f:
            profile_json = f.read()

        return summary, profile_json, str(tmp_out)

    with gr.Blocks(title="Forensic Face Calibration - Same Person Same Day") as demo:
        gr.Markdown("""
# Forensic Face Calibration UI v3.3
### Калибровка по stage1-выделенным фото за один день

**Инструкция:**
1. Запусти `run_calibration.py --input /path/to/photos --output /path/to/run`
2. Укажи путь к stage1 output ниже (`/path/to/run/stage1`)
3. Система проанализирует UV-геометрию + image-текстуру кожи
4. Пороги калибруются под same-person вариативность

**Архитектура v3.3:**
- UV-пространство: Frangi ridges + skan skeleton (геометрия морщин)
- Image-пространство: LBP/GLCM/Gabor (текстура пор)
- Два пространства объединены в единый forensic report
        """)

        inp_path = gr.Textbox(label="Path to stage1 output directory", placeholder="/path/to/run/stage1")
        btn = gr.Button("Run Calibration")

        out_summary = gr.Markdown(label="Summary")
        out_json = gr.Code(label="Calibration Profile JSON", language="json")
        out_path = gr.Textbox(label="Saved profile path")

        btn.click(fn=calibrate_fn, inputs=[inp_path], outputs=[out_summary, out_json, out_path])

    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)
    return True


def launch_cli(args):
    engine = CalibrationEngine(uv_size=args.uv_size)
    profile = engine.calibrate_from_stage1(args.stage1)
    out_path = args.out or os.path.join(args.stage1, "calibration_profile.json")
    engine.save_profile(profile, out_path)
    print("\n=== VERDICT ===")
    print(json.dumps(profile.get('verdict', {}), indent=2, ensure_ascii=False))
    print(f"\nFull profile saved to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Forensic Calibration UI v3.3")
    parser.add_argument('--stage1', type=str, help='Path to stage1 output directory')
    parser.add_argument('--uv_size', type=int, default=1000, help='UV atlas size')
    parser.add_argument('--out', type=str, default=None)
    parser.add_argument('--no_gradio', action='store_true', help='Force CLI mode')

    args = parser.parse_args()

    if args.stage1:
        launch_cli(args)
    else:
        if not args.no_gradio:
            ok = launch_gradio(args)
            if not ok:
                print("Gradio not available. Use --stage1 /path/to/stage1 for CLI mode.")
        else:
            print("Provide --stage1 for CLI mode")
