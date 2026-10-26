"""Isolated CPU BGE-M3/Chroma worker. JSON only on stdout, no model/API secrets."""

import hashlib
import json
import math
import sys
from contextlib import redirect_stdout
from importlib.metadata import version
from pathlib import Path


def hybrid_search(payload):
    import torch
    import chromadb
    from FlagEmbedding import BGEM3FlagModel

    torch.set_num_threads(2)
    model_path = Path(payload["model_path"]).resolve()
    model = BGEM3FlagModel(str(model_path), devices="cpu", use_fp16=False,
                          batch_size=1, return_dense=True, return_sparse=True,
                          query_max_length=512, passage_max_length=512)
    client = chromadb.PersistentClient(path=payload["index_path"])
    collection = client.get_or_create_collection("bge-m3-chunks-v1", metadata={"hnsw:space": "cosine"})
    chunks = payload["chunks"]
    ids = [chunk["chunk_id"] for chunk in chunks]
    # Query only the caller's validated corpus; stale rows can never become evidence.
    current = collection.get(ids=ids, include=["metadatas"]) if ids else {"ids": [], "metadatas": []}
    existing = dict(zip(current["ids"], current["metadatas"], strict=True))
    revision = payload["revision"]
    def fingerprint(chunk):
        raw = json.dumps([revision, 512, chunk], sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
    fresh = [chunk for chunk in chunks if existing.get(chunk["chunk_id"], {}).get("fingerprint") != fingerprint(chunk)]
    if fresh:
        encoded = model.encode([chunk["text"] for chunk in fresh], batch_size=1, max_length=512,
                               return_dense=True, return_sparse=True, return_colbert_vecs=False)
        dense = encoded["dense_vecs"].tolist()
        sparse = [{str(token): float(weight) for token, weight in weights.items()}
                  for weights in encoded["lexical_weights"]]
        collection.upsert(ids=[chunk["chunk_id"] for chunk in fresh], embeddings=dense,
                          documents=[chunk["text"] for chunk in fresh], metadatas=[{
                              "fingerprint": fingerprint(chunk), "paper_id": chunk["paper_id"],
                              "sparse": json.dumps(weights), "revision": revision}
                              for chunk, weights in zip(fresh, sparse, strict=True)])
    encoded_query = model.encode([payload["question"]], batch_size=1, max_length=512,
                                 return_dense=True, return_sparse=True, return_colbert_vecs=False)
    queried = collection.query(query_embeddings=encoded_query["dense_vecs"].tolist(), n_results=len(ids),
                               ids=ids, include=["distances"])
    dense = {cid: 1 - float(distance) for cid, distance in zip(queried["ids"][0], queried["distances"][0], strict=True)}
    stored = collection.get(ids=ids, include=["metadatas"])
    qweights = encoded_query["lexical_weights"][0]
    sparse = {}
    for cid, metadata in zip(stored["ids"], stored["metadatas"], strict=True):
        weights = json.loads(metadata["sparse"])
        sparse[cid] = sum(float(weight) * weights.get(str(token), 0) for token, weight in qweights.items())
    if any(not math.isfinite(value) for value in [*dense.values(), *sparse.values()]):
        raise ValueError("nonfinite encoding")
    return {"dense": dense, "sparse": sparse, "indexed_chunks": len(ids),
            "updated_chunks": len(fresh), "stored_vectors": collection.count(), "revision": revision,
            "dimension": len(encoded_query["dense_vecs"][0]),
            "versions": {name: version(name) for name in ("chromadb", "FlagEmbedding", "torch", "transformers")}}


def paper_embeddings(payload):
    import torch
    from FlagEmbedding import BGEM3FlagModel
    torch.set_num_threads(2)
    model = BGEM3FlagModel(str(Path(payload["model_path"]).resolve()), devices="cpu", use_fp16=False,
                          batch_size=1, return_dense=True, return_sparse=False, passage_max_length=512)
    vectors = {}
    for paper in payload["papers"]:
        encoded = model.encode(paper["texts"], batch_size=1, max_length=512,
            return_dense=True, return_sparse=False, return_colbert_vecs=False)["dense_vecs"]
        vector = encoded.mean(axis=0)
        vector = vector / float(torch.linalg.vector_norm(torch.tensor(vector)))
        vectors[paper["id"]] = vector.tolist()
    return {"vectors": vectors, "versions": {name: version(name) for name in ("FlagEmbedding", "torch", "transformers")}}


if __name__ == "__main__":
    try:
        payload = json.loads(sys.stdin.read())
        with redirect_stdout(sys.stderr):
            result = paper_embeddings(payload) if payload.get("operation") == "paper_embeddings" else hybrid_search(payload)
        print(json.dumps(result, allow_nan=False))
    except Exception as error:
        # No exception strings, URLs or environment values cross the API boundary.
        print(json.dumps({"worker_error": type(error).__name__}))
        sys.exit(1)
