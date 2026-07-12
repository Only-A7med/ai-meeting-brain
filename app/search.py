import math
import re
from collections import defaultdict

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "so", "of", "in", "on",
    "at", "to", "for", "with", "by", "from", "as", "is", "are", "was", "were",
    "be", "been", "it", "its", "this", "that", "these", "those", "we", "our",
    "you", "your", "i", "me", "my", "he", "she", "they", "them", "their",
    "will", "would", "can", "could", "should", "do", "does", "did", "have",
    "has", "had", "not", "no", "yes", "what", "which", "who", "when", "where",
    "how", "why", "all", "any", "some", "there", "here", "about", "into",
    "up", "down", "out", "over", "just", "also", "than", "too", "very",
    "s", "t", "ll", "ve", "re", "d", "m",
}


def tokenize(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]


class BM25Index:
    def __init__(self, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.docs = {}
        self.doc_len = {}
        self.postings = defaultdict(dict)
        self.total_len = 0
        self.avg_len = 0.0

    def add(self, doc_id, text):
        tokens = tokenize(text)
        self.docs[doc_id] = text
        self.doc_len[doc_id] = len(tokens)
        counts = defaultdict(int)
        for t in tokens:
            counts[t] += 1
        for t, c in counts.items():
            self.postings[t][doc_id] = c
        self.total_len += len(tokens)
        self.avg_len = self.total_len / len(self.doc_len)

    def search(self, query, k=10):
        terms = tokenize(query)
        n = len(self.docs)
        if not terms or not n:
            return []
        scores = defaultdict(float)
        for term in terms:
            posting = self.postings.get(term)
            if not posting:
                continue
            idf = math.log(1 + (n - len(posting) + 0.5) / (len(posting) + 0.5))
            for doc_id, tf in posting.items():
                dl = self.doc_len[doc_id]
                denom = tf + self.k1 * (1 - self.b + self.b * dl / (self.avg_len or 1))
                scores[doc_id] += idf * tf * (self.k1 + 1) / denom
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return ranked[:k]
