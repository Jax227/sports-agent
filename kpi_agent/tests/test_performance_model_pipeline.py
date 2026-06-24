"""Test the full Literature → Performance Model pipeline."""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("ENTREZ_EMAIL", "test@example.com")

print("=" * 60)
print("Testing Performance Model Pipeline")
print("=" * 60)

# ── Test 1: Imports ──
print("\n1. Testing imports...")
from app.performance_model.taxonomy import (
    CATEGORIES, classify_term, get_canonical_name, get_category_name_cn
)
print(f"   Categories: {len(CATEGORIES)}")
print(f"   classify_term('vo2max'): {classify_term('vo2max')}")
print(f"   classify_term('running economy'): {classify_term('running economy')}")
print(f"   classify_term('injury risk'): {classify_term('injury risk')}")
print(f"   classify_term('pacing strategy'): {classify_term('pacing strategy')}")
print(f"   classify_term('reaction time'): {classify_term('reaction time')}")
print(f"   classify_term('caffeine'): {classify_term('caffeine')}")
print(f"   classify_term('stride length'): {classify_term('stride length')}")
print(f"   classify_term('scoring system'): {classify_term('scoring system')}")
print(f"   classify_term('unknown term xyz'): {classify_term('unknown term xyz')}")
print(f"   get_canonical_name('maximal oxygen uptake'): {get_canonical_name('maximal oxygen uptake')}")
print(f"   get_canonical_name('VO2max'): {get_canonical_name('VO2max')}")
print("   Taxonomy: OK")

from app.performance_model.batch_loader import (
    load_literature_batch, get_cached_queries, LiteratureDocument,
)
print("   Batch loader: OK")

from app.performance_model.extractor import (
    extract_determinant_candidates_from_batch,
    extract_determinant_candidates_from_document,
    DeterminantCandidate,
)
print("   Extractor: OK")

from app.performance_model.merger import (
    merge_determinant_candidates, standardize_all_names,
)
print("   Merger: OK")

from app.performance_model.builder import (
    build_performance_model_from_candidates,
)
print("   Builder: OK")

from app.performance_model.evidence_linker import (
    create_evidence_links, build_evidence_report,
)
print("   Evidence linker: OK")

from app.performance_model.pipeline import run_full_pipeline
print("   Pipeline: OK")

print("\n   All imports OK!")

# ── Test 2: Load literature from cache ──
print("\n2. Testing batch loader...")
docs = load_literature_batch(limit=20, include_fulltext=False)
print(f"   Loaded {len(docs)} documents")
if docs:
    d = docs[0]
    print(f"   First doc: {d.title[:100]}")
    print(f"   Has abstract: {bool(d.abstract)}")
    print(f"   Year: {d.year}, DOI: {d.doi}")

# ── Test 3: Extract from single document ──
if docs:
    print("\n3. Testing single-document extraction...")
    cands = extract_determinant_candidates_from_document(
        docs[0], include_fulltext=False, use_keybert=False, use_yake=False
    )
    print(f"   Extracted {len(cands)} candidates (dictionary + regex only)")
    if cands:
        for c in cands[:5]:
            print(f"   - {c.canonical_name} ({c.category_key}): conf={c.confidence_score:.2f}")

# ── Test 4: Run full pipeline ──
print("\n4. Testing full pipeline...")
result = run_full_pipeline(
    limit=20,
    include_fulltext=False,
    use_keybert=False,
    use_yake=False,
    min_confidence=0.1,
)
print(f"   Documents loaded: {result['documents_loaded']}")
print(f"   Raw candidates: {result['candidates_extracted']}")
print(f"   Merged candidates: {result['candidates_merged']}")
print(f"   Filtered candidates: {result['candidates_filtered']}")
print(f"   Evidence links: {result['evidence_links']}")

# Show category distribution
model_tree = result.get("model_tree", {})
print("\n   Category distribution:")
for cat in model_tree.get("categories", []):
    if cat["candidate_count"] > 0:
        print(f"   - {cat['name_cn']}: {cat['candidate_count']} candidates, {cat['total_evidence_count']} evidence")

# Show top candidates
if result["candidates"]:
    print("\n   Top 10 candidates:")
    for c in result["candidates"][:10]:
        print(f"   - {c['canonical_name']} [{c['category_key']}] "
              f"ev={len(c['source_literature_ids'])} "
              f"conf={c['confidence_score']:.2f} "
              f"str={c['evidence_strength_score']:.2f}")

# Show evidence report excerpt
report = result.get("evidence_report", "")
report_lines = report.split("\n")
print(f"\n   Evidence report: {len(report_lines)} lines")

# ── Test 5: Export formats ──
print("\n5. Testing exports...")
# JSON export
import json as _json
json_str = _json.dumps({
    "model_tree": model_tree,
    "candidates": result["candidates"],
}, ensure_ascii=False)
print(f"   JSON: {len(json_str)} chars")

# Markdown
md = result.get("evidence_report", "")
print(f"   Markdown: {len(md)} chars")

# CSV
import csv, io
csv_buf = io.StringIO()
writer = csv.writer(csv_buf)
writer.writerow(["canonical_name", "category", "evidence_count", "confidence"])
for c in result["candidates"]:
    writer.writerow([c["canonical_name"], c["category_key"],
                      len(c["source_literature_ids"]), c["confidence_score"]])
print(f"   CSV: {csv_buf.getvalue()[:200]}...")

print("\n" + "=" * 60)
print("All pipeline tests passed!")
print("=" * 60)
