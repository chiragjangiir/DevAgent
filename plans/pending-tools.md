# Pending Tool Implementations

## Vision / Computer Use
`devagent/tools/vision_tools.py` exists but `screenshot()` is a no-op (`pass`).
Plan:
- Use `mss` or `Pillow` + `pyautogui` to capture a screen region
- Encode as base64 PNG
- Pass to LLM via the `image` content block (Anthropic / OpenAI vision APIs)
- Add `click(x, y)`, `type_text(text)`, `scroll(direction)` using `pyautogui`
- Gate behind a `[vision]` optional dependency group

## ✅ Jupyter Notebook tools — SHIPPED (Phase 33)
`notebook_read`, `notebook_edit`, `notebook_run` fully implemented in
`devagent/tools/notebook_tools.py`; auto-registered when `nbformat` is
importable (in `[notebooks]` optional dep group). 14 tests in
`tests/test_notebook_tools.py`. `warnings.catch_warnings` suppresses
nbformat's `MissingIDFieldWarning` on older-format notebooks.
