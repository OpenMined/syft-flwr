# Federated Retrieval Augmented Generation (FedRAG) for Privacy-Preserving Medical Question Answering
Medical knowledge is scattered across hospitals, research centers, and
healthcare systems worldwide, each guarding their data due to privacy regulations and
competitive concerns. Traditional AI systems require copying all this data to one
place, which is often impossible or illegal in healthcare. Federated RAG solves this
by letting AI systems search and learn from medical documents across multiple
institutions without moving or exposing the actual data. Each hospital keeps its
medical records and research private while still contributing to a shared AI that can
answer medical questions more accurately. This approach enables better medical AI
assistants that respect patient privacy and institutional boundaries—essential for
real-world healthcare deployment where data sharing faces strict legal and ethical
constraints.

## Overview
![overview](./images/fedmedragOverview.png)

## Installing Dependencies
### `uv` - a fast Python package manager
- macOS/Linux:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```
- Windows (PowerShell):
```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Alternative methods:
  - With pip: `pip install uv`
  - With Homebrew (macOS): `brew install uv`


After installation, you can use uv sync to install your project dependencies from the `pyproject.toml` file
```bash
uv sync
```
this will create a virtual python environment at `.venv`.


### `wget` and `git-lfs`
`wget` is used to download `.tar` files from the Web. `git-lfs` is used to download large files from the Hugging Face respository
- macOS
```
brew install wget
brew install git-lfs
```
- RHEL
```
yum install wget
yum install git-lfs
```
- Ubuntu/Debian
```
apt install wget
apt install git-lfs
```
- Windows: If you are on Windows, it is highly recommended to make use of WSL with Ubuntu to run your Flower apps. Then, you can install the packages using the above Ubuntu commands. Extra tip: with WSL you can also make use of the NVIDIA GPU in your Windows host.

- enable Git LFS in your Git environment (applicable for all systems)
```
git lfs install
```

## Download & Index Corpus

Run
```bash
./data/prepare.sh
```
to download the `Textbooks` and `StatPearls` corpora and create an index for each corpus using the *first 100 chunks (documents)*. The processed data will be downloaded under the `data/corpus` directory. The total required disk space for all the documents of `Textbooks` and `StatPearls` is around `3GBs`.

To download all corpora and create an index for all files, please run the following command:
```bash
./data/prepare.sh --datasets "pubmed" "statpearls" "textbooks" "wikipedia" --index_num_chunks 0
```
The total disk space for the all documents of all four corpora is around `120GBs`.

### Dataset explanations

#### Clients' datasets
- **PubMed (23.9M docs):** Biomedical literature database from the National Library of Medicine. Contains abstracts and citations from life science journals and online books covering medicine, biology, and related fields.

- **StatPearls (9.3k docs):** Medical reference library providing peer-reviewed medical articles. Used by healthcare professionals and students for clinical knowledge, covering topics like diseases, procedures, and pharmacology.

- **Textbooks (18 docs):** Medical textbooks collection, likely comprehensive educational texts covering various medical specialties and foundational medical knowledge.

- **Wikipedia (6.5M docs)**: The general encyclopedia, providing broad coverage of medical and scientific topics in accessible language, useful for general medical information retrieval

In this federated setup, these corpora are distributed across clients for decentralized document retrieval, with each client indexing portions of the data locally.

#### Server's evaluation datasets
For QA benchmarking, the example supports the following benchmark datasets: `PubMedQA`, `BioASQ`, `MMLU`, `MedQA`, `MedMCQA`. These are question-answer pairs used to test how well the system performs. They contain pre-made questions with correct answers.

#### How they work together
1. The system retrieves relevant documents from the corpora (`PubMed`, `StatPearls`, etc.) split among different clients
2. The server uses those documents to answer questions from the QA benchmarks
3. The server compares generated answers against the benchmark's correct answers to measure performance


## References
- https://syftbox.net
- https://github.com/adap/flower/tree/main/examples/fedrag