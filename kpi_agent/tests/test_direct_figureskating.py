"""Direct test of full generate_model pipeline for figure skating."""
import sys
import os
from pathlib import Path

# Setup path BEFORE any other imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "sports_science_agent"))

os.environ.setdefault("PUBMED_EMAIL", "test@example.com")

print("Testing full generate_model pipeline for figure skating...")
print()

# Test 1: search_evidence directly
print("=== Test 1: search_evidence ===")
from app.agent.evidence_model_generator import search_evidence, build_search_queries, _resolve_sport_terms

terms = _resolve_sport_terms("花样滑冰")
print(f"Resolved terms: {terms}")

queries = build_search_queries("花样滑冰")
for qtype, q in queries.items():
    print(f"\n{qtype}:")
    print(f"  {q[:250]}")

results = search_evidence("花样滑冰", "", max_results_per_query=8)
print(f"\nSearch summary: {results['summary']}")
for qtype, papers in results['results'].items():
    print(f"\n{qtype}: {len(papers)} papers")
    for p in papers[:3]:
        title = p.get('title', '')[:100]
        pmid = p.get('pmid', '')
        year = p.get('year', '')
        print(f"  PMID {pmid} [{year}]: {title}")

# Test 2: generate_model
print()
print("=== Test 2: generate_model ===")
from app.agent.evidence_model_generator import generate_model

model = generate_model("花样滑冰", "", use_llm=False, max_results_per_query=8)
print(f"Sport name: {model.get('sport_name')}")
print(f"Resolved: {model.get('sport_name_resolved')}")
print(f"Translation note: {model.get('translation_note')}")
print(f"Search summary: {model.get('search_summary')}")
print(f"Evidence sources: {len(model.get('evidence_sources', []))}")
print(f"Extraction method: {model.get('extraction_method')}")
print(f"Model summary: {model.get('model_summary')}")

# Print categories and determinants
print("\nCategories extracted:")
for cat_name, cat_data in model.get('categories', {}).items():
    dets = cat_data.get('determinants', [])
    if dets:
        print(f"  {cat_name} ({len(dets)}):")
        for d in dets[:5]:
            print(f"    - {d['name']} (evidence: {d.get('evidence_level', '?')}, mentions: {d.get('mention_count', '?')})")
    else:
        print(f"  {cat_name}: (empty)")

print(f"\nKPIs: {len(model.get('kpis', []))}")
print(f"Interventions: {len(model.get('interventions', []))}")

# Print empty categories with reasons
print("\nEmpty categories:")
for ec in model.get('empty_categories', []):
    print(f"  {ec['category']}: {ec['reason']}")

# Print all evidence source titles
print("\nAll evidence sources:")
es = model.get('evidence_sources', [])
for i, s in enumerate(es):
    print(f"  {i+1}. [{s.get('year', '?')}] {s.get('title', '')[:120]}")
    print(f"     source_type: {s.get('source_type', '?')}")

# Print paper-determinant map summary
pmap = model.get('paper_determinant_map', [])
matched = [p for p in pmap if p.get('match_count', 0) > 0]
print(f"\nPaper-determinant mapping: {len(matched)}/{len(pmap)} papers matched to determinants")
for p in pmap[:5]:
    m = p.get('match_count', 0)
    dets = p.get('matched_determinants', [])
    print(f"  [{p.get('year', '?')}] matches={m}: {[d['determinant'] for d in dets]}")
