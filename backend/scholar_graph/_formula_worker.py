"""Local image-to-LaTeX inference; no paper material is sent to a provider."""
import contextlib
import json
from pathlib import Path
import sys


def recognize(source, manifest, model_dir):
    import numpy as np
    import pypdfium2 as pdfium
    from paddleocr import FormulaRecognition
    model = FormulaRecognition(model_name='PP-FormulaNet-S', model_dir=model_dir,
                               device='cpu', cpu_threads=4, enable_mkldnn=False)
    regions = json.loads(Path(manifest).read_text(encoding='utf-8'))
    document = pdfium.PdfDocument(source)
    results = []
    try:
        for region in regions:
            page = document[region['page_number']-1]
            bitmap = page.render(scale=2.5)
            image = bitmap.to_pil().convert('RGB')
            crop = None
            try:
                x0,y0,x1,y1 = region['bbox']
                # Layout boxes can omit small terminal subscripts/punctuation.
                # Keep additional horizontal context without capturing the next text line.
                crop = image.crop((max(0,round((x0-.025)*image.width)), max(0,round((y0-.005)*image.height)),
                                   min(image.width,round((x1+.025)*image.width)), min(image.height,round((y1+.005)*image.height))))
                values = list(model.predict(np.asarray(crop)[:,:,::-1].copy(), batch_size=1))
                if len(values) != 1: raise ValueError('Invalid formula result count')
                results.append({'region_id':region['region_id'], 'latex':str(values[0]['rec_formula'])})
            finally:
                if crop is not None: crop.close()
                image.close(); bitmap.close(); page.close()
    finally:
        document.close()
    return results


if __name__ == '__main__':
    try:
        with contextlib.redirect_stdout(sys.stderr):
            value = recognize(*sys.argv[1:])
        sys.stdout.write(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except Exception:
        sys.stdout.write('{"error":"local_formula_recognition_failed"}')
        raise SystemExit(1)
