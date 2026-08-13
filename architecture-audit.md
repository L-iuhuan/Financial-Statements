# Architecture Audit

_Generated: 2026-08-13T13:28:02Z — mode: `quick` — scope: `['.']`_

## Executive summary

This codebase totals **24418 LOC** across languages: `html` `json` `python` `toml` .

Frameworks detected: _(none detected)_
Runtime topology: _(none detected)_
Verdict counts: **Correct: 2** · **Partial: 0** · **Incorrect: 0** · candidate: 0


---

## Macro-architecture

### Monolith — `Correct` (conf 0.4, sev `none`)

- **Scope**: `.`
- **Confirming signals**: `one_dockerfile` `no_services_dir` - **Disproving signals**: `many_entrypoints` - **Violations**: `Isolation` `Anti-pattern proximity` - **Recommendation**: Keep the single deployable; revisit if any module starts owning an independent release cadence.

**Evidence**

- `Dockerfile*` — 0 Dockerfile(s)


---

## Layering


---

## Component (meso) patterns

### Service Layer — `Correct` (conf 0.5, sev `none`)

- **Scope**: `2 *Service classes`
- **Confirming**: `service_class_names` `imported_by_interface_layer` - **Disproving**: _(none)_- **Recommendation**: Maintain the current service-layer boundary and transactional scope.

- `src\fsa\services\validation_service.py`:30-46 — ValidationService orchestrates RuleRegistry + RuleRunner; no file/GUI access
- `src\fsa\gui\pages\import_page.py`:32 — interface layer consumes the service via fsa.services.validation_service import


---

## Micro patterns

_(no micro findings)_
---

## Anti-patterns

_(no anti-patterns detected)_
---

## Cross-cutting concerns

This section summarizes how recurring concerns are handled across the codebase. They are reported here because they typically span layers/services and are easiest to evaluate as one block.

- **Logging**: see `signals_confirming` on individual findings; check for centralised log formatter / correlation IDs.
- **Auth**: gateway / BFF responsibility; check that domain code does not perform auth.
- **Config**: presence of `config/` or `settings.py` / `application.yml`; check no secrets in tree.
- **Error handling**: consistent error type? exception → HTTP mapping only at the interface boundary?
- **Transactions**: where are transaction boundaries declared? Service layer or repository?

(Detailed sub-findings will appear under the relevant pattern's evidence above.)

---

## Risk matrix

| Finding | Severity | Likelihood | Impact |
|---|---|---|---|
_(no risks above noise floor)_
---

## Recommendations (ordered)


---

## Appendix — Inventory

- Total LOC: **24418**
- Languages: `html` `json` `python` `toml` - Frameworks: _(none)_- Entrypoints: `scripts\generate_logo.py` `scripts\ux_shots.py` `scripts\validate_real_data.py` `scripts\verify_agent.py` `scripts\verify_diagnosis.py` `scripts\verify_export.py` `scripts\verify_ollama.py` `scripts\verify_pdf_import.py` `scripts\verify_sce.py` `scripts\verify_theme.py` `scripts\verify_update.py` `scripts\verify_w3.py` `src\fsa\__main__.py` - Runtime: 
## Appendix — Tooling

- Mode: `quick`
- ripgrep available: `False`
- networkx available: `True`
- Degradations: `tokei not installed; using naive line count` `ripgrep (rg) not installed; pattern detection will be slower` 
## Appendix — Subtrees

- `demo` (module)
- `docs` (module)
- `resources` (module)
- `scripts` (module)
- `src\fsa` (bounded_context)
- `src\fsa.egg-info` (bounded_context)
- `tests` (module)
