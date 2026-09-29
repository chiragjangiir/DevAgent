# Pending Tool Implementations

## Vision / Computer Use
`devagent/tools/vision_tools.py` exists but `screenshot()` is a no-op (`pass`).
Plan:
- Use `mss` or `Pillow` + `pyautogui` to capture a screen region
- Encode as base64 PNG
- Pass to LLM via the `image` content block (Anthropic / OpenAI vision APIs)
- Add `click(x, y)`, `type_text(text)`, `scroll(direction)` using `pyautogui`
- Gate behind a `[vision]` optional dependency group

## Jupyter Notebook tools
Not present. Plan:
- `notebook_read(path)` — read `.ipynb`, return cells as formatted text
- `notebook_edit(path, cell_index, new_source)` — patch a cell and save
- Use `nbformat` library (add as optional dep)
- Register in `build_registry()` alongside file tools
