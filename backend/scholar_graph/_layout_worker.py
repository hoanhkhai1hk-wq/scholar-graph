"""Private local layout-model worker. No paper material leaves this process."""
import contextlib
import json
import sys


def detect(source, pages):
    import numpy as np
    import pypdfium2 as pdfium
    from paddleocr import LayoutDetection
    model = LayoutDetection(model_name='PP-DocLayout-S', device='cpu', cpu_threads=4, enable_mkldnn=False)
    document = pdfium.PdfDocument(source)
    results = []
    try:
        for number in pages:
            page = document[number - 1]
            bitmap = page.render(scale=min(1.4, (8_000_000 / max(1, page.get_width()*page.get_height())) ** .5))
            image = bitmap.to_pil().convert('RGB')
            try:
                value = list(model.predict(np.asarray(image)[:, :, ::-1].copy(), batch_size=1))[0]
                boxes = []
                for row in value['boxes']:
                    if float(row['score']) < .5:
                        continue
                    x0, y0, x1, y1 = map(float, row['coordinate'])
                    box = [max(0, min(1, x0/image.width)), max(0, min(1, y0/image.height)),
                           max(0, min(1, x1/image.width)), max(0, min(1, y1/image.height))]
                    if box[2] > box[0] and box[3] > box[1]:
                        boxes.append({'label': str(row['label']), 'score': float(row['score']), 'bbox': box})
                results.append({'page_number': number, 'regions': boxes})
            finally:
                image.close(); bitmap.close(); page.close()
    finally:
        document.close()
    return results


if __name__ == '__main__':
    try:
        with contextlib.redirect_stdout(sys.stderr):
            result = detect(sys.argv[1], json.loads(sys.argv[2]))
        sys.stdout.write(json.dumps(result, allow_nan=False))
    except Exception:
        sys.stdout.write('{"error":"local_layout_failed"}')
        raise SystemExit(1)
