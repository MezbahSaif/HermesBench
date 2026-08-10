# FastRetrieval: Dense Indexing with Cross-Encoder Reranking for FAQ Search

## Method

We propose a two-stage retrieval pipeline for enterprise FAQ search. The first
stage uses a dense vector index built with a sentence-transformer encoder to
recall the 50 nearest candidate passages for a query. The second stage
reranks those candidates with a cross-encoder that scores query-passage pairs
jointly, and returns the top 5. The cross-encoder adds a small latency cost
because it processes each pair independently.

## Results

On our internal enterprise FAQ benchmark, the pipeline improves retrieval
accuracy by approximately 17% over a BM25 baseline, and the two-stage design
is about 3.2x faster end-to-end than running the cross-encoder over the full
corpus. Accuracy was measured as the fraction of queries where the correct
answer passage appeared in the top 5.

## Limitation

The system was evaluated on a single dataset (internal FAQ logs from one
quarter), so generalization to other domains or languages is not yet
established.
