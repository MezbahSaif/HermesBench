# Paper A: Retrieval-Augmented Generation for Customer Support

We propose a retrieval-augmented generation (RAG) pipeline: a dense retriever
selects relevant documents from a support knowledge base, and a frozen large
language model generates answers conditioned on the retrieved passages. The
LLM weights are never updated. The approach requires no GPU training and
supports adding new documents at any time without retraining. The main
downsides are higher inference latency (retrieval plus generation) and
dependency on retrieval quality: if the retriever misses the right passage,
the answer is wrong even if the LLM is strong.

## Paper B: Fine-Tuning for Customer Support

We propose fine-tuning the LLM on historical support tickets paired with
accepted answers. The model learns the domain's terminology and style
directly, which yields lower latency at inference time (no retrieval step)
and fluent answers. The main downsides are the cost of preparing training
data and GPU training time, and the fact that the model cannot incorporate
new knowledge without retraining: knowledge is frozen at the training cut-off.
