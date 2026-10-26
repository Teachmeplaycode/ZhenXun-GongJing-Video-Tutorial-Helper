# Browser OCR assets

Browser OCR runs in a dedicated Worker using WebAssembly on one CPU thread. Models and runtime are served from this site; runtime inference never needs a third-party CDN. No model download occurs in server mode.

`npm run dev` and `npm run build` copy pinned npm-package assets into this directory using `scripts/prepare-ocr-assets.mjs`. The generated files are deliberately ignored: the npm lockfile and generated SHA-256 manifest identify their exact contents. Production deploys must include the resulting `dist/ocr` directory.

- Chinese PP-OCRv4 detector, recognizer, and `ppocr_keys_v1.txt`: `@gutenye/ocr-models` **1.4.2**, derived from [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR), Apache-2.0. See `LICENSE-PaddleOCR.txt`.
- ONNX Runtime Web **1.20.1**: [Microsoft ONNX Runtime](https://github.com/microsoft/onnxruntime), MIT. See `LICENSE-ONNXRuntime.txt`.
- OCR preprocessing/core: `@gutenye/ocr-common` **1.4.9**, [Guten OCR](https://github.com/gutenye/ocr), MIT. Its contour helper is adapted in `src/lib/ocrContours.js` to release OpenCV matrices between frames.
- OpenCV.js **4.9.0-release.3**: [OpenCV](https://opencv.org/), Apache-2.0. The packaged JS embeds its own WASM and is loaded only as part of the OCR Worker.

Models are cached with the browser Cache API when available. Cache/storage denial falls back to ordinary same-origin downloads. Browsers lacking Worker, WebAssembly or OffscreenCanvas report an unsupported-device state; hybrid processing continues on the server.
