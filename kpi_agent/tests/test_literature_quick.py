"""Quick test of all literature module imports and connector status."""
import sys
import os
from pathlib import Path

# Add kpi_agent directory to path so 'app' is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("ENTREZ_EMAIL", "test@example.com")

from app.literature.schema import LiteratureResult, ExtractionResult, EvidenceMatrix
print("Schema: OK")

from app.literature.connectors.registry import ConnectorRegistry
print("Registry: OK")

# Check connector status
status = ConnectorRegistry.check_status()
for s in status:
    name = s["name"]
    available = s["available"]
    msg = s["message"][:80]
    print(f"  {name}: available={available}, msg={msg}")

from app.literature.dedup import deduplicate_results
print("Dedup: OK")

from app.literature.cache import LiteratureCache
print("Cache: OK")

from app.literature.fulltext import enrich_fulltext_links
print("Fulltext: OK")

from app.literature.ranking import hybrid_rerank, BM25Ranker
print("Ranking: OK")

from app.literature.extraction import free_extract_evidence, batch_extract
print("Extraction: OK")

from app.literature.matrix import generate_evidence_matrix
print("Matrix: OK")

print("\nAll imports OK!")

# Quick test of search_all_sources with a simple query
print("\n--- Testing search_all_sources ---")
from app.literature.connectors.registry import search_all_sources

result = search_all_sources("running economy elite runners", sources=["europe_pmc"], limit_per_source=5)
print(f"Europe PMC results: {result['source_counts']}")
print(f"Errors: {result['errors']}")
print(f"Total raw results: {len(result['results'])}")

if result['results']:
    r = result['results'][0]
    print(f"First result: {r.title[:100]}")
    print(f"  Authors: {r.authors[:3]}")
    print(f"  Year: {r.year}")
    print(f"  DOI: {r.doi}")
    print(f"  PMID: {r.pmid}")

# Test dedup
dedup = deduplicate_results(result['results'])
print(f"\nDedup: {dedup['before_count']} -> {dedup['after_count']} (removed {dedup['duplicates_removed']})")

# Test ranking
ranked = hybrid_rerank("running economy elite runners", dedup['results'])
if ranked:
    print(f"Top result: {ranked[0].title[:100]}, score={ranked[0].final_score}")
    print(f"  Explanation: {ranked[0].ranking_explanation}")

# Test extraction
if ranked:
    ext = free_extract_evidence(ranked[0])
    print(f"\nExtraction: sport={ext.sport}, pop={ext.population_level}, n={ext.sample_size}")
    print(f"  Perf vars: {ext.performance_variables[:5]}")
    print(f"  Interventions: {ext.interventions[:5]}")
    print(f"  KPI candidates: {[k['name'] for k in ext.kpi_implications[:5]]}")
    print(f"  Confidence: {ext.confidence}")

# Test cache
cache = LiteratureCache()
ck = LiteratureCache.make_cache_key("test running", ["europe_pmc"])
print(f"\nCache key: {ck}")
cached = cache.get_cached_query(ck)
print(f"Cached query: {cached}")

print("\n=== All tests passed! ===")
