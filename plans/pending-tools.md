# Pending Tool Implementations

## ✅ Vision / Computer Use — SHIPPED (Phase 16, pre-existing)
`devagent/tools/vision_tools.py` fully implemented:
- `read_image` — reads any image file, encodes as base64, passes via `IMAGE_SENTINEL`
- `take_screenshot` — auto-registered when `mss` or `Pillow.ImageGrab` is available
- Both tools strip images for providers without vision support (Ollama, Gemini)
- Tests in `tests/test_phase16.py`

## ✅ Jupyter Notebook tools — SHIPPED (Phase 33)
`notebook_read`, `notebook_edit`, `notebook_run` fully implemented in
`devagent/tools/notebook_tools.py`; auto-registered when `nbformat` is
importable (in `[notebooks]` optional dep group). 14 tests in
`tests/test_notebook_tools.py`. `warnings.catch_warnings` suppresses
nbformat's `MissingIDFieldWarning` on older-format notebooks.
