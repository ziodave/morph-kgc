# Compatibility Contract (V2)

## Scope
V2 must preserve user-visible behavior for supported YARRRML/RML/FNML scenarios covered by retained regression tests under `test/`.

## Initial Guarantees
- Package name remains `morph_kgc`.
- Public entry points reserved:
  - `materialize`
  - `materialize_oxigraph`
  - `materialize_set`
  - `materialize_kafka`
  - `translate_to_rml`
- CLI command remains `morph-kgc`.

## Performance Targets
- Establish baseline from legacy branch and require measurable improvements before release.

## Validation Gate
- No release until conformance + performance test gates are green.
