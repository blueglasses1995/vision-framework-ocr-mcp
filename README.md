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

## Run Standalone (stdio)

```bash
source .venv/bin/activate
python server.py
```

## MCP Setup (User-Level)

These examples configure MCP at user scope, not project scope.

Before configuring any client, decide your absolute paths:

- `PYTHON_PATH`: `/absolute/path/to/vision-framework-ocr-mcp/.venv/bin/python`
- `SERVER_PATH`: `/absolute/path/to/vision-framework-ocr-mcp/server.py`

### Codex (`~/.codex/config.toml`)

1. Open `~/.codex/config.toml`.
2. Add this block:

```toml
[mcp_servers.vision-framework-ocr]
command = "/absolute/path/to/vision-framework-ocr-mcp/.venv/bin/python"
args = ["/absolute/path/to/vision-framework-ocr-mcp/server.py"]
```

3. Restart Codex app or start a new Codex session.

### Claude Code CLI (`~/.claude.json`)

1. Open `~/.claude.json`.
2. Add this object under top-level `mcpServers`:

```json
{
  "mcpServers": {
    "vision-framework-ocr": {
      "command": "/absolute/path/to/vision-framework-ocr-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/vision-framework-ocr-mcp/server.py"]
    }
  }
}
```

3. Restart Claude Code CLI.

Note:
- If `mcpServers` already exists, merge this entry into the existing object.
- Do not overwrite other existing MCP servers.

### Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`)

1. Open `~/Library/Application Support/Claude/claude_desktop_config.json`.
2. Add this object under top-level `mcpServers`:

```json
{
  "mcpServers": {
    "vision-framework-ocr": {
      "command": "/absolute/path/to/vision-framework-ocr-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/vision-framework-ocr-mcp/server.py"]
    }
  }
}
```

3. Completely quit and relaunch Claude Desktop.

Note:
- If `mcpServers` already exists, merge this entry into the existing object.
- Do not overwrite other existing MCP servers.

## Verify

After restart, confirm `vision-framework-ocr` appears in your MCP server list.
Then call any tool such as:

- `ocr_image`
- `ocr_text`
- `ocr_batch`
- `compile_helper`

## Path Tips

- Use absolute paths.
- Paths with spaces or non-ASCII characters are supported.
- In JSON/TOML, keep the full path as one string value.

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
