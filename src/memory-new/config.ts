import path from "node:path";
import os from "node:os";

/**
 * Michael's simplified embedding configuration
 * (Much simpler than Moltbot's full config)
 */
export interface MemoryEmbeddingConfig {
  provider: "openai" | "local" | "gemini" | "auto";
  model: string;
  fallback: "openai" | "gemini" | "local" | "none";
  remote?: {
    baseUrl?: string;
    apiKey?: string;
    headers?: Record<string, string>;
  };
  local?: {
    modelPath?: string;
    modelCacheDir?: string;
  };
}

export interface MemorySearchConfig {
  // Embedding configuration (top level for MemoryIndexManager)
  provider: "openai" | "local" | "gemini" | "auto";
  model: string;
  fallback: "openai" | "gemini" | "local" | "none";
  remote?: {
    baseUrl?: string;
    apiKey?: string;
    headers?: Record<string, string>;
    batch?: {
      enabled: boolean;
      wait: boolean;
      concurrency: number;
      pollIntervalMs: number;
      timeoutMs: number;
      timeoutMinutes?: number;
    };
  };
  local?: {
    modelPath?: string;
    modelCacheDir?: string;
  };

  // Additional settings needed by MemoryIndexManager
  sources: Array<"memory">; // Michael: only "memory" source

  cache: {
    enabled: boolean;
    maxEntries?: number;
  };

  query: {
    minScore: number;
    maxResults: number;
    hybrid: {
      enabled: boolean;
      vectorWeight: number;
      textWeight: number;
      candidateMultiplier: number;
    };
  };

  store: {
    path: string; // Database path
    vector: {
      enabled: boolean;
      extensionPath?: string;
    };
  };

  sync: {
    watch: boolean;
    watchDebounceMs: number;
    onSearch: boolean;
    onSessionStart: boolean;
    intervalMinutes?: number;
    sessions?: {
      bytesThreshold: number;
      messagesThreshold: number;
      deltaBytes: number;
      deltaMessages: number;
    };
  };

  chunking: {
    tokens: number;
    overlap: number;
  };
}

/**
 * Minimal config interface needed by MemoryIndexManager
 * (Replaces Moltbot's complex MoltbotConfig)
 */
export interface MichaelMemoryConfig {
  memory: {
    search: MemorySearchConfig;
  };
}

/**
 * Resolve ~ and relative paths to absolute paths
 * (Ported from Moltbot utils.ts)
 */
export function resolveUserPath(input: string): string {
  const trimmed = input.trim();
  if (!trimmed) return trimmed;
  if (trimmed.startsWith("~")) {
    const expanded = trimmed.replace(/^~(?=$|[\\/])/, os.homedir());
    return path.resolve(expanded);
  }
  return path.resolve(trimmed);
}

/**
 * Load embedding config from environment variables
 * (Simplified for Michael)
 */
export function loadMemoryConfig(dataDir?: string): MichaelMemoryConfig {
  const validProviders = ["openai", "local", "gemini"] as const;
  type ValidProvider = typeof validProviders[number];

  const rawProvider = process.env.EMBEDDING_PROVIDER || "local";
  if (!validProviders.includes(rawProvider as ValidProvider)) {
    throw new Error(
      `Invalid EMBEDDING_PROVIDER: "${rawProvider}". Valid values: ${validProviders.join(", ")}`
    );
  }
  const provider = rawProvider as ValidProvider;

  const baseDataDir = dataDir || process.env.DATA_DIR || "./data";

  let model: string;
  let remote: MemorySearchConfig["remote"];
  let local: MemorySearchConfig["local"];

  if (provider === "openai") {
    model = "text-embedding-3-small";
    remote = {
      apiKey: process.env.OPENAI_API_KEY,
      batch: {
        enabled: true,
        wait: true,
        concurrency: 4,
        pollIntervalMs: 5000,
        timeoutMs: 600000 // 10 minutes
      }
    };
  } else if (provider === "gemini") {
    model = "text-embedding-004";
    remote = {
      apiKey: process.env.GOOGLE_API_KEY,
      batch: {
        enabled: true,
        wait: true,
        concurrency: 4,
        pollIntervalMs: 5000,
        timeoutMs: 600000
      }
    };
  } else {
    // local
    model = process.env.LOCAL_MODEL_PATH || "hf:ggml-org/embeddinggemma-300M-GGUF/embeddinggemma-300M-Q8_0.gguf";
    local = {
      modelPath: process.env.LOCAL_MODEL_PATH,
      modelCacheDir: process.env.LOCAL_MODEL_CACHE_DIR || path.join(baseDataDir, "models")
    };
  }

  return {
    memory: {
      search: {
        // === Embedding Configuration ===
        // Provider set from EMBEDDING_PROVIDER env var (default: "local")
        provider,
        // Model depends on provider:
        //   - openai: "text-embedding-3-small"
        //   - gemini: "text-embedding-004"
        //   - local: gguf model path from LOCAL_MODEL_PATH env or default HuggingFace model
        model,
        // "none" - don't fallback to another provider if primary fails
        fallback: "none",
        remote,
        local,

        // === Michael Specific Settings ===
        // Only index "memory" source (messages from conversations)
        // Moltbot also supports "sessions" but Michael doesn't need it
        sources: ["memory"],

        // === Embedding Cache ===
        cache: {
          enabled: true,       // Cache embeddings to avoid re-computation
          maxEntries: 10000    // Max cached embeddings (LRU eviction after this limit)
        },

        // === Search Query Settings ===
        query: {
          minScore: 0.0,       // Minimum similarity score (0.0 = return all results)
          maxResults: 10,      // Maximum results to return per search
          hybrid: {
            enabled: true,     // Combine vector similarity + FTS5 keyword search
            vectorWeight: 0.7, // 70% weight to semantic similarity
            textWeight: 0.3,   // 30% weight to keyword match (BM25)
            candidateMultiplier: 3 // Fetch 3x candidates before re-ranking
          }
        },

        // === Storage Settings ===
        store: {
          path: path.join(baseDataDir, "memory-index.db"), // Separate DB for embeddings
          vector: {
            enabled: true      // Enable sqlite-vec extension for vector search
          }
        },

        // === Sync Settings ===
        sync: {
          watch: false,         // Don't watch memory files for changes (manual sync only)
          watchDebounceMs: 2000, // Debounce time if watch is enabled
          onSearch: true,       // Auto-sync before each search query
          onSessionStart: false, // Michael has no session concept
          intervalMinutes: undefined // No periodic background sync
        },

        // === Text Chunking Settings ===
        chunking: {
          tokens: 512,  // Target chunk size in tokens
          overlap: 50   // Overlap between chunks for context continuity
        }
      }
    }
  };
}
