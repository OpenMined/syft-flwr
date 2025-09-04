# Roadmap

## V1: Pre-chunked documents, Index database available
Current flow:
```
Query → Retrieve from pre-built index → Return results
```


The current implementation makes several assumptions that may not hold in a production federated learning environment:

### 1. **Data is Pre-chunked**
- Assumes data owners have already processed their raw documents into JSONL chunks
- No guidance on chunking strategies or parameters
- Missing standardization across different data owners

### 2. **Data is Harmonized**
- Assumes all data follows the same schema/format
- No validation or transformation pipeline
- Could lead to incompatible data across federation

### 3. **FAISS Indices Pre-built**
- Assumes indices are already created before any federated job
- No mechanism for on-demand index generation
- Indices may become stale over time

### 4. **Static Corpus**
- No mechanism for data owners to update/add new documents
- Cannot handle evolving document collections
- Missing versioning and change tracking


## V2: Raw data harmonization, chunking and indexing as job submission

### 1. **Data Preparation Pipeline**

**Required Flow for Dataset Processing:**
```
Raw Documents → Chunking → Harmonization → Indexing
```

**Key Requirements:**
- Each data owner should be able to process their own documents
- Need standardized chunking strategy (size, overlap, etc.) via job submission
- Need schema validation/harmonization
- Support for multiple document formats (PDF, TXT, HTML, etc.)

### 2. **Dynamic Index Building**

- Data owners should build indices locally when they approve the job
- Indices should update when new data is added
- Support for incremental indexing
- Automatic reindexing on significant changes

### 3. **Privacy & Access Control**

- Data owners decide what to share (public/private split)
- Granular permissions (which clients can query what)
- Audit logs of who queried what
- Encrypted indices for sensitive data

### 4. **Overall Job Submission Flow**

**Data Processing Flow:**
```
1. Job Request
2. Data Owner Approval
3. Local Index Building/Update (if needed)
4. Data Owners Sends Dataset Processing Succeeed Signals
```

Then, RAG Query Flow:
```
1. Job Request
2. Data Owner Approval
3. Data Owner Sends Relevant Documents / Vectors
4. Secure Retrieval
5. Aggregated Results
```

## Proposed Architecture Improvements

### 1. **Data Onboarding Flow**

**Implementation Steps:**
- Data owner uploads raw documents to SyftBox
- Review and approve data chunking and index building job
- Local processing pipeline (chunk → embed → index)
- Metadata registration with network
- Automatic quality validation?

### 2. **Query Flow**

**Features:**
- Client submits RAG query as RDS job
- Data owners approve/reject based on query content
- Local retrieval happens on approved nodes
- Results aggregated from approved nodes

### Optional: **Dynamic Updates**

- Watch for new documents in SyftBox data dir
- Incremental index updates
- Version control for indices
- Rollback capabilities for corrupted indices

## V3: MCP Integration

### MCP-Enhanced Job Flows

#### **Data Processing Job via MCP**
```
1. MCP Client calls submit_data_processing_job(documents, chunk_config)
2. Job distributed to relevant nodes via RDS
3. Data owners receive approval request through their MCP tools
4. Data owners call approve_job(job_id, conditions) via their MCP interface
5. Processing begins, status available via check_processing_status(job_id)
6. Completion notification sent to original MCP client
```

#### **Federated Query via MCP**
```
1. MCP Client calls submit_federated_query(query, scope, privacy_level)
2. Privacy impact automatically assessed via get_privacy_metrics()
3. Query routed to relevant nodes based on dataset discovery
4. Node owners review via list_pending_approvals() and approve_job()
5. Query execution across approved nodes
6. Results aggregated and returned via get_query_results()
```

### Universal Client Support

**Any MCP-compatible application can now use FedRAG:**
- **AI Assistants**: Claude, ChatGPT (via MCP), Copilot
- **IDEs**: VSCode, Cursor, Zed with MCP extensions
- **Research Tools**: Jupyter, R Studio, Observable
- **Business Apps**: Custom enterprise applications
- **No-Code Platforms**: Zapier, Make.com (if they add MCP support)

### Benefits of V3 MCP Integration

1. **Zero Integration Friction**: Any MCP client works immediately
2. **Ecosystem Network Effects**: Every new MCP tool/client expands FedRAG's reach
3. **Standardized Experience**: Consistent interface across all applications
4. **AI-Native**: Built for AI assistant interactions from ground up
5. **Future-Proof**: Automatically compatible with new MCP developments
