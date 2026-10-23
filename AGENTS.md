# Project Rules

1. The main project specification is the file `Техническое задание.doc` in the project root. It is the primary document for starting all work. Convert and read it via Python (available on this machine).
2. The file `Дополнение к ТЗ.docx` contains a significantly extended version of the specification, organized into sections. Consult it only when the main specification lacks information or when questions arise. Start with Section 9, which contains a project summary. If Section 9 is insufficient, consult the other sections — they elaborate on each aspect in greater detail. Which section to pick next depends on the specific question that needs to be clarified for the user's current task.
3. Ignore diagrams from the specification. Work only from the text assignments. If a diagram is needed — build our own or skip it.
4. Even if the specification is deeply elaborated: when inconsistencies, errors, or a better idea are found — explicitly report them to the user and wait for their decision. Do not act on your own.
5. The 1C LSP tooling requires the `lsp-skill-server` process (C:\Users\vladi\AppData\Local\1c-tools\x86_64-pc-windows-msvc\lsp-skill-server.exe) to be running whenever working on this project; its web UI is at http://127.0.0.1:4000. Start it before 1C-related work. It is not needed for non-1C projects.
6. After starting opencode (and after any LSP project restart), verify that the project's **«Корневой путь BSL»** (`root_path`) points at this repository, not at the tool installation directory. The wrapper resets it to `C:\Users\vladi\AppData\Local\1c-tools\bsl-language-server` on start, and indexing then crawls at 0% forever.
   - Check: `(Invoke-WebRequest http://127.0.0.1:4000/api/projects -UseBasicParsing).Content` — `root_path` must be `D:\Projects\1C_prj\7 семестр\Kursovaya`; the response must show `"status":"ready"` and `"percentage":100`.
   - Fix: open http://127.0.0.1:4000, open the project card, set «Корневой путь BSL» to `D:\Projects\1C_prj\7 семестр\Kursovaya` (do not touch «Корневой путь всего проекта»), save, then Stop → Start.
   - Healthy server proves itself: diagnostics over all 34 form modules return findings in about a second. A broken one answers `Проект еще не готов. Текущий статус: остановлен.`
   - Registration lives in `C:\Users\vladi\AppData\Local\Infostart\LspSkill\data\data.db` (16 KB) — keep a copy; restoring it brings the correct path back. Do not delete and re-create the project card: re-creation is what writes the default path.
7. **1C crash dumps are the primary diagnostic signal.** Whenever an `1cv8.exe` run hangs, produces no report where one was expected, or fails in a way you cannot observe (modal dialog, silent hang), do all of the following before retrying:
   - Look in the project root for files matching `Ошибка_*.zip`.
   - Pick the one with the **newest `LastWriteTime`** — do not guess from the file name alone.
   - Unpack it to a temp directory and read `report.json`; the failure text is in `errorInfo.applicationErrorInfo.errors` (each entry: `[context, flags, message, detail]`, and the message names the metadata object, the BSL line and the reason).
   - A dump whose timestamp is within roughly 10 minutes of now is conclusive evidence of the failure that just happened — treat it as the actual error, not as noise, and do not retry the same operation without changing something.
   - **A missing dump does not prove the run succeeded** — a compile error, a hang on a lock, or a killed process may leave nothing behind. Absence only means this signal is unavailable.
   - Before retrying any 1C command, make sure no `1cv8*` process is left running; kill leftovers, then fix the root cause.
8. **Static check before loading a configuration.** Run `1c-lsp-diagnostics` over every modified `.bsl` and fix all `severity = 1` findings before `LoadConfigFromFiles`. Runtime-only defects still get through, but this catches the recurring ones (reserved names such as `Выполнить`, `Дата` used as a constructor without arguments, `НачатьТранзакцию`, non-existent types such as `СравнениеЗначений`).

# Spec clarifications (confirmed by the customer)

1. The infobase is intentionally a file infobase. Client-server deployment is out of scope: a separate task that requires a paid license.
