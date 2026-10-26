"""Private inference process. Stdout is JSON only; the parent discards dependency logs."""

import contextlib
import json
import sys


def mineru_text(path):
    from mineru.parser import parse
    return parse(path, tier="flash", ocr_mode="txt", image_analysis=False).to_dict()


def paddle_engine(language):
    from paddleocr import PaddleOCR
    return PaddleOCR(lang=language, ocr_version="PP-OCRv5", device="cpu", cpu_threads=4,
                       text_detection_model_name="PP-OCRv5_mobile_det",
                       text_recognition_model_name=("en_PP-OCRv5_mobile_rec" if language == "en" else "PP-OCRv5_mobile_rec"),
                       text_recognition_batch_size=8,
                       use_doc_orientation_classify=False, use_doc_unwarping=False,
                       use_textline_orientation=False, enable_mkldnn=False)


def paddle_text(path, language, pages):
    import numpy as np
    import pypdfium2 as pdfium
    engine = paddle_engine(language)
    document = pdfium.PdfDocument(path)
    result_pages = []
    try:
        for index in pages:
            page = document[index]
            bitmap = page.render(scale=2)
            image = None
            try:
                image = bitmap.to_pil().convert("RGB")
                width, height = image.size
                records = list(engine.predict(np.asarray(image)[:, :, ::-1].copy()))
                blocks = []
                for result in records:
                    for text, score, poly in zip(result["rec_texts"], result["rec_scores"], result["rec_polys"], strict=True):
                        if score < 0.5 or not text.strip():
                            continue
                        xs, ys = [float(p[0]) for p in poly], [float(p[1]) for p in poly]
                        bbox = [max(0, min(xs) / width), max(0, min(ys) / height),
                                min(1, max(xs) / width), min(1, max(ys) / height)]
                        blocks.append({"type": "text", "index": len(blocks), "bbox": bbox,
                                       "content": [{"type": "text", "content": text.strip()}]})
                result_pages.append({"page_idx": index, "blocks": blocks})
            finally:
                if image is not None:
                    image.close()
                bitmap.close()
                page.close()
    finally:
        document.close()
    return {"pages": result_pages}


if __name__ == "__main__":
    try:
        with contextlib.redirect_stdout(sys.stderr):
            path, mode, language, pages = sys.argv[1:]
            value = mineru_text(path) if mode == "mineru" else paddle_text(path, language, json.loads(pages))
        sys.stdout.write(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except Exception:
        # Exception strings from third-party providers may contain credentials or request URLs.
        sys.stdout.write('{"error":"local_engine_failed"}')
        raise SystemExit(1)
