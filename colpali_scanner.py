import base64
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import matplotlib.pyplot as plt
import numpy as np
import requests
from PIL import Image
from qdrant_client import QdrantClient, models
from transformers import AutoProcessor

# --- Environment Configurations ---
COLPALI_MODEL = "TomoroAI/tomoro-colqwen3-embed-4b"
EMBEDDING_DIM = 320  # ColQwen3 output dimension

QDRANT_HOST = os.environ.get("QDRANT_HOST", "10.0.10.65")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
COLLECTION_NAME = "invoice_colpali"

EMBED_BASE_URL = os.environ.get("EMBED_BASE_URL", "http://10.0.10.51:8000")
EMBED_IMAGE_MULTIVECTOR_URL = f"{EMBED_BASE_URL}/embed-image/v1/multivector-embeddings"

RECREATE_COLLECTION = True
QDRANT_UPSERT_BATCH_SIZE = 4

ROOT_DIR = Path(__file__).resolve().parent
INVOICE_PATH = ROOT_DIR / "invoice.png"


def _is_http_url(image_source: str) -> bool:
    parsed = urlparse(image_source)
    return parsed.scheme in {"http", "https"}


def _convert_image_to_base64(image_source: str) -> str:
    """Load an image from a URL or local path and return base64 bytes."""
    if _is_http_url(image_source):
        response = requests.get(image_source, timeout=30)
        response.raise_for_status()
        image_bytes = response.content
    else:
        parsed = urlparse(image_source)
        file_path = unquote(parsed.path) if parsed.scheme == "file" else image_source
        file_path = str(Path(file_path).resolve())
        with open(file_path, "rb") as image_file:
            image_bytes = image_file.read()
    return base64.b64encode(image_bytes).decode("utf-8")


def embed_colpali(
    data_images: list[str],
    data_texts: list[str],
    model_name: str = COLPALI_MODEL,
    batch_size: int = 8,
) -> list[list[list[float]]]:
    """Return per-input token embeddings ordered as [images…, texts…]."""
    base64_images = [_convert_image_to_base64(path) for path in data_images]
    data_inputs = base64_images + data_texts
    embeddings: list[list[list[float]]] = []

    for start in range(0, len(data_inputs), batch_size):
        batch = data_inputs[start : start + batch_size]
        response = requests.post(
            EMBED_IMAGE_MULTIVECTOR_URL,
            json={"model": model_name, "input_type": "auto", "input": batch},
            timeout=120,
        )
        response.raise_for_status()
        batch_embeddings = [item["embedding"] for item in response.json()["data"]]
        embeddings.extend(batch_embeddings)
        print(f"Embedded items {start}–{start + len(batch) - 1}")

    return embeddings


def embed_colpali_pages(page_paths: list[str]) -> list[list[list[float]]]:
    return embed_colpali(page_paths, [])


def embed_colpali_query(query: str) -> list[list[float]]:
    return embed_colpali([], [query])[0]


# --- MaxSim late-interaction similarity metrics ---

def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.clip(norms, 1e-12, None)


def maxsim_similarity_matrix(
    query_vectors: list[list[float]],
    page_vectors: list[list[float]],
) -> np.ndarray:
    """Cosine similarity matrix with shape (n_query_tokens, n_page_tokens)."""
    q = _l2_normalize(np.asarray(query_vectors, dtype=np.float32))
    d = _l2_normalize(np.asarray(page_vectors, dtype=np.float32))
    return q @ d.T


def maxsim_score(sim_matrix: np.ndarray) -> float:
    """Sum over query tokens of their best patch match (ColPali MaxSim)."""
    return float(sim_matrix.max(axis=1).sum())


# --- Visual patch layout & Visualization preparation ---

def _visual_patch_layout(image: Image.Image, processor: AutoProcessor) -> tuple[np.ndarray, int, int]:
    """Return image-token mask and patch grid size (cols, rows) for ColQwen3."""
    batch = processor.process_images(images=[image])
    image_mask = processor.get_image_mask(batch)[0].cpu().numpy().astype(bool)
    merge_size = (
        processor.image_processor.merge_size
        or processor.image_processor.spatial_merge_size
    )
    n_patches_x, n_patches_y = processor.get_n_patches(image.size, merge_size)
    return image_mask, n_patches_x, n_patches_y


def prepare_maxsim_visualization(
    image_path: str,
    query_vectors: list[list[float]],
    page_vectors: list[list[float]],
    processor: AutoProcessor,
) -> dict:
    """Build overlay + patch-grid data for a query/page pair."""
    image = Image.open(image_path).convert("RGB")
    image_mask, n_patches_x, n_patches_y = _visual_patch_layout(image, processor)

    n_visual = int(image_mask.sum())
    expected = n_patches_x * n_patches_y
    if n_visual != expected:
        raise ValueError(
            f"Expected {expected} visual patches ({n_patches_x}×{n_patches_y}), got {n_visual}"
        )

    visual_vectors = np.asarray(page_vectors, dtype=np.float32)[image_mask]
    sim = maxsim_similarity_matrix(query_vectors, visual_vectors.tolist())
    score = maxsim_score(sim)
    patch_scores = sim.max(axis=0)
    heatmap = patch_scores.reshape(n_patches_y, n_patches_x)

    return {
        "image": image,
        "heatmap": heatmap,
        "score": score,
        "token_argmax": sim.argmax(axis=1),
        "n_patches_x": n_patches_x,
        "n_patches_y": n_patches_y,
        "n_visual": n_visual,
        "n_prompt_tokens": len(page_vectors) - n_visual,
    }


def plot_page_overlay(viz: dict, title: str, output_path: str) -> None:
    """Save the page image with overlaid heatmap to disk."""
    image = viz["image"]
    fig, ax = plt.subplots(figsize=(8, 10))
    ax.imshow(image)
    ax.imshow(
        viz["heatmap"],
        cmap="hot",
        alpha=0.45,
        interpolation="bilinear",
        extent=(0, image.width, image.height, 0),
    )
    ax.set_title(f"{title}\nMaxSim overlay (score={viz['score']:.2f})")
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Saved overlay heatmap plot to {output_path}")


def plot_heatmap_scale(viz: dict, title: str, output_path: str) -> None:
    """Save the patch-grid heatmap with colorbar to disk."""
    fig, ax = plt.subplots(figsize=(6, 8))
    im = ax.imshow(viz["heatmap"], cmap="hot", interpolation="nearest")
    ax.set_title(f"{title}\nPatch grid {viz['n_patches_x']}×{viz['n_patches_y']}")
    ax.axis("off")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("MaxSim patch score")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Saved patch-grid heatmap to {output_path}")


def main():
    if not INVOICE_PATH.exists():
        print(f"Error: Invoice file not found at {INVOICE_PATH}")
        return

    print(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}...")
    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    if RECREATE_COLLECTION and qdrant.collection_exists(COLLECTION_NAME):
        print(f"Deleting existing Qdrant collection '{COLLECTION_NAME}'...")
        qdrant.delete_collection(COLLECTION_NAME)

    if not qdrant.collection_exists(COLLECTION_NAME):
        print(f"Creating Qdrant collection '{COLLECTION_NAME}' with MaxSim...")
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=EMBEDDING_DIM,
                distance=models.Distance.COSINE,
                multivector_config=models.MultiVectorConfig(
                    comparator=models.MultiVectorComparator.MAX_SIM,
                ),
            ),
        )

    print(f"Generating ColPali multivector embedding for {INVOICE_PATH.name}...")
    invoice_embeddings = embed_colpali_pages([str(INVOICE_PATH)])
    invoice_embedding = invoice_embeddings[0]
    print(
        f"Generated embedding matrix: {len(invoice_embedding)} tokens × "
        f"{len(invoice_embedding[0])} dims"
    )

    point = models.PointStruct(
        id=1,
        vector=invoice_embedding,
        payload={
            "source_file": INVOICE_PATH.name,
            "image_path": str(INVOICE_PATH),
            "model": COLPALI_MODEL,
            "num_tokens": len(invoice_embedding),
        },
    )

    print(f"Indexing point in collection '{COLLECTION_NAME}'...")
    qdrant.upsert(collection_name=COLLECTION_NAME, points=[point])
    print("Point successfully indexed.")

    # Load processor once for query metadata mapping
    print(f"Loading ColQwen3 processor from {COLPALI_MODEL}...")
    colqwen_processor = AutoProcessor.from_pretrained(
        COLPALI_MODEL,
        trust_remote_code=True,
        max_num_visual_tokens=1280,
    )

    test_queries = [
        "What is the total due on this invoice?",
        "Who is this invoice billed to?",
        "What are the tasks listed in the items table?",
        "What is the routing number and account number?",
    ]

    print("\n--- Running Semantic Queries ---")
    for q_idx, query_str in enumerate(test_queries, 1):
        print(f"\nQuery #{q_idx}: '{query_str}'")
        query_embedding = embed_colpali_query(query_str)
        print(f"Query embedded: {len(query_embedding)} tokens")

        # Query Qdrant
        search_results = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            limit=1,
            with_payload=True,
        ).points

        if not search_results:
            print("No matching points found in collection.")
            continue

        hit = search_results[0]
        print(
            f"Best match found: {hit.payload['source_file']} "
            f"(MaxSim score = {hit.score:.3f})"
        )

        # Generate visualizations
        safe_query_name = re.sub(r"[^\w\s-]", "", query_str.lower()).strip().replace(" ", "_")
        overlay_output_path = str(ROOT_DIR / f"invoice_overlay_{safe_query_name}.png")
        heatmap_output_path = str(ROOT_DIR / f"invoice_heatmap_{safe_query_name}.png")

        print("Preparing similarity heatmap visualization...")
        viz = prepare_maxsim_visualization(
            image_path=str(INVOICE_PATH),
            query_vectors=query_embedding,
            page_vectors=invoice_embedding,
            processor=colqwen_processor,
        )

        plot_page_overlay(viz, f"Query: {query_str}", overlay_output_path)
        plot_heatmap_scale(viz, f"Query: {query_str}", heatmap_output_path)


if __name__ == "__main__":
    main()
