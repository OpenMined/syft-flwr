import json
import os
import random
import shutil
import warnings
from pathlib import Path

import faiss
import numpy as np
import torch
from loguru import logger
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from typing_extensions import List, Optional, Tuple, Union

warnings.filterwarnings("ignore", category=DeprecationWarning)


SOURCE_DATA_PATH = Path(__file__).parent.parent / "data" / "corpus"
assert SOURCE_DATA_PATH.exists(), f"Source data path {SOURCE_DATA_PATH} does not exist"
CORPUS_NAME = os.getenv("CORPUS_NAME", "statpearls")
CHUNK_DIR = SOURCE_DATA_PATH / CORPUS_NAME / "chunk"
assert CHUNK_DIR.exists(), f"Chunk directory {CHUNK_DIR} does not exist"
PROCESSED_DATA_PATH = Path(__file__).parent / "processed_data"

MOCK_DIR = PROCESSED_DATA_PATH / CORPUS_NAME / "mock"
PRIVATE_DIR = PROCESSED_DATA_PATH / CORPUS_NAME / "private"
MOCK_RATIO = 0.1  # 10% of the chunks will be used for mock
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
BATCH_SIZE = 32


logger.info(f"Corpus name: {CORPUS_NAME}")
logger.info(f"Source data path: {SOURCE_DATA_PATH}")
logger.info(f"Chunk directory: {CHUNK_DIR}")
logger.info(f"Output directory: {PROCESSED_DATA_PATH}")


def main():
    mock_chunk_dir, private_chunk_dir = _create_mock_private_dirs()
    _copy_chunks_to_mock_and_private(mock_chunk_dir, private_chunk_dir)

    logger.info(
        "Building FAISS indices for mock and private data for corpus {CORPUS_NAME}..."
    )

    # Build indices sequentially to avoid MPS device conflicts
    try:
        # Build mock index
        logger.info("Building mock index for corpus {CORPUS_NAME}...")
        _build_faiss_index(
            data_dir=mock_chunk_dir,
            output_dir=MOCK_DIR,
            embedding_model=EMBEDDING_MODEL,
            embedding_dimension=EMBEDDING_DIM,
            batch_size=BATCH_SIZE,
        )
        logger.success("Successfully built FAISS indices for mock data")

        # Build private index
        logger.info("Building private index for corpus {CORPUS_NAME}...")
        _build_faiss_index(
            data_dir=private_chunk_dir,
            output_dir=PRIVATE_DIR,
            embedding_model=EMBEDDING_MODEL,
            embedding_dimension=EMBEDDING_DIM,
            batch_size=BATCH_SIZE,
        )
        logger.success("Successfully built FAISS indices for private data")

    except Exception as e:
        logger.error(f"Error building indices: {e}")
        raise

    logger.success(f"Both FAISS indices built successfully for corpus {CORPUS_NAME}!")


def _create_mock_private_dirs() -> Tuple[Path, Path]:
    mock_chunk_dir = MOCK_DIR / "chunk"
    private_chunk_dir = PRIVATE_DIR / "chunk"

    if mock_chunk_dir.exists():
        shutil.rmtree(mock_chunk_dir)
    if private_chunk_dir.exists():
        shutil.rmtree(private_chunk_dir)

    mock_chunk_dir.mkdir(exist_ok=True, parents=True)
    private_chunk_dir.mkdir(exist_ok=True, parents=True)

    return mock_chunk_dir, private_chunk_dir


def _copy_chunks_to_mock_and_private(
    mock_chunk_dir: Path, private_chunk_dir: Path
) -> None:
    jsonl_files = list(CHUNK_DIR.glob("*.jsonl"))
    logger.info(f"There are {len(jsonl_files)} chunk files in total for {CORPUS_NAME}")
    random.shuffle(jsonl_files)
    split_idx = int(len(jsonl_files) * MOCK_RATIO)
    mock_files = jsonl_files[:split_idx]
    private_files = jsonl_files[split_idx:]

    logger.info(f"Copying {len(mock_files)} mock files for {CORPUS_NAME}...")
    for f in mock_files:
        shutil.copy2(f, mock_chunk_dir / f.name)

    logger.info(f"Copying {len(private_files)} private files for {CORPUS_NAME}...")
    for f in private_files:
        shutil.copy2(f, private_chunk_dir / f.name)

    # Verify the copy
    mock_count = len(list(mock_chunk_dir.glob("*.jsonl")))
    private_count = len(list(private_chunk_dir.glob("*.jsonl")))
    logger.info(
        f"Verified: {mock_count} files in mock dir, {private_count} files in private dir"
    )


def _build_faiss_index(
    data_dir: Union[str, Path],
    output_dir: Union[str, Path] = None,
    embedding_model: str = "all-MiniLM-L6-v2",
    embedding_dimension: int = 384,
    batch_size: int = 32,
    num_chunks: Optional[int] = None,
    device: Optional[str] = None,
) -> None:
    """
    Build a FAISS index from JSONL chunk files.

    Parameters:
    -----------
    data_dir : str or Path
        Directory containing JSONL chunk files
    output_dir : str or Path, optional
        Directory to save the FAISS index and doc IDs. If None, uses data_dir
    embedding_model : str
        Name of the sentence transformer model to use
    embedding_dimension : int
        Dimension of the embeddings
    batch_size : int
        Batch size for encoding documents
    num_chunks : int, optional
        Number of chunk files to process (for testing). If None, processes all files
    device : str, optional
        Device to use ('cuda', 'mps', 'cpu'). If None, auto-detects best available
    """
    # Convert paths to Path objects
    data_dir = Path(data_dir)

    # Define output paths
    index_path = output_dir / "faiss.index"
    doc_ids_path = output_dir / "all_doc_ids.npy"

    # Clean up existing index files
    for path in [index_path, doc_ids_path]:
        if path.exists():
            path.unlink()

    device = _detect_device()

    # Initialize the embedding model
    emb_model = SentenceTransformer(embedding_model, device=device)

    # Get JSONL files
    all_files: List[Path] = list(data_dir.glob("*.jsonl"))
    if num_chunks:
        all_files = all_files[:num_chunks]

    logger.info(
        f"Building FAISS index for {data_dir} with {len(all_files)} chunk files..."
    )

    # Collect all embeddings and document IDs
    all_embeddings: List[np.ndarray] = []
    all_doc_ids: List[str] = []

    # Process each JSONL file
    for filepath in tqdm(all_files):
        _process_jsonl_file(
            filepath=filepath,
            emb_model=emb_model,
            batch_size=batch_size,
            all_embeddings=all_embeddings,
            all_doc_ids=all_doc_ids,
        )

    # Build and save FAISS index
    _build_and_save_index(
        all_embeddings=all_embeddings,
        all_doc_ids=all_doc_ids,
        embedding_dimension=embedding_dimension,
        index_path=index_path,
        doc_ids_path=doc_ids_path,
    )


def _detect_device(force_cpu: bool = False) -> str:
    """Detect the best device to use."""
    if force_cpu:
        device = "cpu"
    else:
        device = "cpu"
        if torch.cuda.is_available():
            device = "cuda"
        elif torch.backends.mps.is_available():
            device = "mps"
    logger.info(f"Using device: {device}")
    return device


def _process_jsonl_file(
    filepath: Path,
    emb_model: SentenceTransformer,
    batch_size: int,
    all_embeddings: List[np.ndarray],
    all_doc_ids: List[str],
) -> None:
    """Process a single JSONL file and extract embeddings."""
    batch_content: List[str] = []
    batch_ids: List[str] = []

    with open(filepath, "r", encoding="utf-8") as infile:
        for line in infile:
            doc = json.loads(line)
            doc_id = doc.get("id", "")
            content = doc.get("content", "")

            batch_ids.append(doc_id)
            batch_content.append(content)

            # Process batch when it reaches the specified size
            if len(batch_ids) > batch_size:
                _encode_and_store_batch(
                    emb_model, batch_content, batch_ids, all_embeddings, all_doc_ids
                )
                batch_content, batch_ids = [], []

        # Process remaining batch
        if batch_content:
            _encode_and_store_batch(
                emb_model, batch_content, batch_ids, all_embeddings, all_doc_ids
            )


def _encode_and_store_batch(
    emb_model: SentenceTransformer,
    batch_content: List[str],
    batch_ids: List[str],
    all_embeddings: List[np.ndarray],
    all_doc_ids: List[str],
) -> None:
    """Encode a batch of documents and store embeddings."""
    batch_embeddings = emb_model.encode(batch_content, convert_to_numpy=True)
    all_embeddings.extend(batch_embeddings)
    all_doc_ids.extend(batch_ids)


def _build_and_save_index(
    all_embeddings: List[np.ndarray],
    all_doc_ids: List[str],
    embedding_dimension: int,
    index_path: Path,
    doc_ids_path: Path,
) -> None:
    """Build FAISS index from embeddings and save to disk."""
    # Filter embeddings by dimension
    filtered_embeddings = [
        emb
        for emb in all_embeddings
        if emb is not None and emb.shape == (embedding_dimension,)
    ]

    # Convert to float32 numpy array
    embeddings = np.array(filtered_embeddings, dtype=np.float32)
    d = embeddings.shape[1]

    logger.info(
        f"Building FAISS index with {len(embeddings)} embeddings of dimension {d}"
    )

    # Create FAISS index with IVF
    quantizer = faiss.IndexFlatL2(d)
    nlist = int(np.sqrt(len(embeddings)))  # Number of clusters
    index = faiss.IndexIVFFlat(quantizer, d, nlist, faiss.METRIC_L2)

    # Train and populate index
    index.train(embeddings)
    index.add(embeddings)

    # Save to disk
    faiss.write_index(index, str(index_path))
    np.save(str(doc_ids_path), np.array(all_doc_ids))

    logger.info(f"FAISS index saved to: {index_path}")
    logger.info(f"Document IDs saved to: {doc_ids_path}")


if __name__ == "__main__":
    main()
