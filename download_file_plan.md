# Plan: Enhance Web Fetching with `download_file` Tool

**Goal:** Create a robust mechanism for the agent to fetch arbitrary content (HTML, images, binaries, datasets) from a URL and make it available for subsequent processing without overwhelming the LLM context.

**Approach:** Introduce a new tool, `download_file`, that downloads content from a URL directly to the local filesystem and returns metadata about the downloaded file, including its path.

**Tool Details: `download_file`**

*   **Purpose:** Download content from a URL to a local file.
*   **Input Parameters:**
    *   `url` (string, required): URL of the resource.
    *   `output_dir` (string, optional, default: `data/downloads/`): Directory to save the file (relative to workspace root).
    *   `filename` (string, optional): Specific filename to use. If omitted, the tool will attempt to derive it.
*   **Process:**
    1.  Validate inputs (URL format, directory path if provided).
    2.  Ensure the target `output_dir` exists, creating it if necessary.
    3.  Fetch URL content using `requests` with `stream=True`.
    4.  Determine an appropriate local filename (checking `Content-Disposition` header, parsing URL, using provided `filename`). Implement logic to handle potential filename conflicts (e.g., appending a number or timestamp).
    5.  Save the raw response content (bytes) to the determined file path within the `output_dir`.
    6.  Return a `ToolResult` containing metadata:
        *   `local_path` (string): Relative path to the downloaded file (e.g., `data/downloads/image.jpg`).
        *   `original_url` (string): The source URL.
        *   `content_type` (string): The `Content-Type` reported by the server.
        *   `file_size` (integer): Size of the downloaded file in bytes.
        *   `status` (string): Success or error message.
*   **Benefits:**
    *   Handles diverse content types (binary, text, large files).
    *   Keeps large data out of the LLM context.
    *   Decouples fetching from processing, allowing flexible workflows using other tools (`read_file`, image tools, data tools).

**Workflow Diagram:**

```mermaid
graph TD
    subgraph Agent Interaction
        A[Agent identifies need to fetch content from URL] --> B{Call download_file};
        B -- url, [output_dir], [filename] --> C(download_file Execution);
        C -- ToolResult (local_path, metadata) --> D[Agent receives file path & info];
        D --> E{Decide next action based on task & metadata};
    end

    subgraph download_file Execution
        C --> F[Validate URL & Params];
        F --> G[Ensure output_dir exists];
        G --> H[HTTP GET Request (stream=True)];
        H --> I[Check Response Status];
        I --> J[Determine Filename (Header/URL/Input)];
        J --> K[Handle Filename Conflicts];
        K --> L[Stream Response to Local File];
        L --> M[Gather Metadata (path, type, size)];
        M --> C;
    end

    subgraph Subsequent Processing
        E -- If text/code & needs reading --> P1(Call read_file(local_path));
        E -- If image & needs analysis --> P2(Call image_tool(local_path));
        E -- If data & needs processing --> P3(Call data_tool(local_path));
        E -- If just needs reference --> P4(Use local_path in reports/summaries);
    end