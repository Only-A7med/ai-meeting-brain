from app.search import BM25Index, tokenize


def test_tokenize_lowercases_and_drops_stopwords():
    assert tokenize("The QUICK brown fox, and the dog!") == ["quick", "brown", "fox", "dog"]
    assert tokenize("I'll finish it by June 26.") == ["finish", "june", "26"]


def test_search_ranks_by_relevance():
    idx = BM25Index()
    idx.add("d1", "azure migration for the reporting stack")
    idx.add("d2", "quarterly budget review with finance")
    idx.add("d3", "azure azure azure everywhere in this cloud plan")
    results = idx.search("azure")
    assert [doc_id for doc_id, _ in results] == ["d3", "d1"]
    assert results[0][1] > results[1][1]


def test_multi_term_query_prefers_doc_with_both():
    idx = BM25Index()
    idx.add("d1", "consent portal designs for the launch")
    idx.add("d2", "consent model changes from legal")
    idx.add("d3", "portal deployment checklist")
    top_id, _ = idx.search("consent portal")[0]
    assert top_id == "d1"


def test_search_empty_and_unknown():
    idx = BM25Index()
    assert idx.search("anything") == []
    idx.add("d1", "hello world meeting")
    assert idx.search("") == []
    assert idx.search("nonexistent") == []


def test_search_k_limit():
    idx = BM25Index()
    for i in range(10):
        idx.add(f"d{i}", "azure cloud spend")
    assert len(idx.search("azure", k=3)) == 3


def test_avg_len_tracks_additions():
    idx = BM25Index()
    idx.add("a", "alpha beta gamma delta")
    idx.add("b", "alpha beta")
    assert idx.avg_len == 3.0
