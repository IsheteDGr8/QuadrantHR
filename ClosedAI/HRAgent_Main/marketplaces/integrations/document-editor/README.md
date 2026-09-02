# Document Editor

Fills PDF forms, overlays text on flat PDFs, and reads/validates/diffs
Office documents (DOCX/XLSX/PPTX) -- without converting the document to a
different format first. Built on [`office-oxide-mcp`](https://github.com/Aimino-Tech/opendocswork-mcp)
(binary name `office-oxide-mcp`, repo name `opendocswork-mcp`).

## Why this one

Evaluated against the alternatives found (`formfill-mcp`, `pdfnative-mcp`,
`docx-mcp`, `document-edit-mcp`) — see the selection discussion in
`agent_docs/Todo.md`. No major-vendor-official PDF-form-filling MCP exists
(unlike `azure-ai-search`/`cosmos-db`, which have real Microsoft-official
options). `office-oxide-mcp` was the best capability match for this
project's actual documents: it's the only candidate that handles both real
AcroForm filling *and* flat-PDF text overlay *and* Office format reading in
one tool, and had the most GitHub stars (157) among the candidates found.

**License note:** GPL-3.0 (see `LICENSE-upstream`). Run as an external
subprocess over stdio, same as any other MCP server here — not linked into
this repo's own code, so this doesn't impose GPL terms on the rest of the
project (same reasoning as shelling out to `git` or `ffmpeg`), but it's
worth being aware of if this ever gets redistributed as a bundled binary.

## Installation (one-time, not automatic)

Unlike every other integration in this marketplace, `office-oxide-mcp` is
**not published to any package registry** (no npm, PyPI, or crates.io
package) — it must be built from source once:

```bash
cargo install --git https://github.com/Aimino-Tech/opendocswork-mcp
```

This installs the binary to `~/.cargo/bin/office-oxide-mcp`. If Rust/cargo
isn't installed, get it from <https://rustup.rs> first. `server/run.sh`
looks for the binary at `~/.cargo/bin/office-oxide-mcp` by default;
override with `OFFICE_OXIDE_MCP_BIN` if it's installed elsewhere.

## Tools (verified against this project's real documents)

Tested directly against `i9_form.pdf`, `employee_nda.pdf`,
`code_of_conduct_acknowledgment.docx`, and `emergency_contact_form.docx`
(from the `onboarding-forms` container in the `closedaidevstg` Azure
Storage account -- see `agent_docs/Todo.md` for how these were discovered).

| Tool | Verified against | Result |
|---|---|---|
| `office_list_pdf_fields` | `i9_form.pdf` | Correctly lists all 133 real AcroForm fields. |
| `office_fill_pdf_form` | `i9_form.pdf` | Filled name/date fields; `office_validate` passed 6/6 checks after; refilled values confirmed via `office_list_pdf_fields`; page count and rest of document unchanged. |
| `office_overlay_pdf_text` | `employee_nda.pdf` (no AcroForm fields -- flat PDF) | Inserted extractable (not rasterized) text at a specified page/x/y; verified via `pypdf` that the rest of the document's text (2415 chars on page 1) was byte-identical to the original and page count (4) was unchanged. **Note:** the `page` parameter is 1-indexed in practice even though its JSON schema says `"minimum": 0` -- passing `page: 3` landed the text on the 3rd page, not the 4th. Confirm placement with `office_analyze_pdf_layout` or a diff before relying on a specific page. |
| `office_analyze_pdf_layout` | `employee_nda.pdf` | **Known limitation:** garbled/undecoded text in the returned layout for this specific file (likely a font-encoding edge case in the Rust PDF parser) even though the same file's text extracts cleanly via `pypdf`. Layout/position data may still be usable, but don't trust the `text` field from this tool for this kind of PDF -- read the document with another tool first if you need to know what it says. |
| `office_read` | both `.docx` files | Extracts paragraphs and table structure from DOCX. |
| `office_list_docx_fields` | `emergency_contact_form.docx` | Detects empty table cells (Employee Name, ID, Department, etc.). |
| `office_fill_docx_form` | `emergency_contact_form.docx` | Fills table-cell fields; saves filled copy under `outputs/`. |
| `office_list_docx_fields` | `code_of_conduct_acknowledgment.docx` | Detects inline signature/name/date lines. |
| `office_fill_docx_form` | `code_of_conduct_acknowledgment.docx` | Fills Employee Name, Signature, and Date lines. |
| `office_template_detect` / `office_template_fill` | DOCX with `{placeholder}` tokens | Mail-merge style templates only (not table-based HR forms). |

## Where the real documents live

The `documents` container in Cosmos DB (`closedai-db`) holds *metadata* records
pointing at `blob://<container>/<blob-name>` references — the real files are
in the `closedaidevstg` Azure Storage account, containers `onboarding-forms`
(the actual fillable forms), `generated-reports`, and `policy-documents`.
This MCP operates on **local file paths only** — it has no Azure Blob
Storage client. Getting a blob onto local disk (and, if needed, uploading
the result back) is a separate step this plugin doesn't cover; for testing,
the two PDFs above were staged directly into `HRAgent_Main/workspace/documents/onboarding-forms/`.
