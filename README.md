# vision-framework-ocr-mcp

MCP server for OCR on macOS using Apple's Vision framework APIs.

- Main OCR API: `VNRecognizeTextRequest`
- Local processing only: no external OCR API calls

## Why This Exists

This project exposes macOS Vision OCR through MCP tools so agents can extract
text from local images in a structured way.

## Tools

- `ocr_image`: OCR one image and return structured JSON.
- `ocr_batch`: OCR many images and return aggregate output with errors.
- `ocr_text`: OCR one image and return plain text.
- `compile_helper`: compile the Swift helper for faster execution.

## Requirements

- macOS (Vision framework is Apple platform API)
- Xcode command line tools (`xcrun`, `swift`, `swiftc`)
- Python 3.11+

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run (stdio)

```bash
source .venv/bin/activate
python server.py
```

## MCP Config Example

```json
{
  "mcpServers": {
    "vision-framework-ocr": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["/absolute/path/to/server.py"]
    }
  }
}
```

## Key Parameters (`ocr_image` / `ocr_batch` / `ocr_text`)

- `path` or `paths`: input image file path(s)
- `languages`: OCR languages, default `ja-JP,en-US`
- `recognition_level`: `accurate` or `fast`
- `language_correction`: enable language correction
- `sort_reading_order`: sort lines top-to-bottom then left-to-right
- `min_confidence`: filter lines below this confidence (`0.0` to `1.0`)

## Performance

By default, the server runs `vision_ocr.swift` via `xcrun swift`.
For better throughput, call `compile_helper` once and use `.build/vision_ocr`.

## Privacy

OCR runs locally on your macOS machine.
Images are not uploaded by this server.

## Legal

This is an independent open-source project and is not affiliated with or
endorsed by Apple Inc.

Apple, macOS, and Vision are trademarks of Apple Inc.
