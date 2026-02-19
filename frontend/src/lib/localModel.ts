/**
 * Local Live2D Model Loader
 * 
 * Handles loading Live2D models from local files by converting them to Blob URLs.
 * Rewrites relative paths in model3.json so all assets (moc3, textures, physics, etc.)
 * are served via Blob URLs.
 */

// Track created blob URLs for cleanup
const blobUrls: string[] = [];

export function cleanupBlobUrls(): void {
  blobUrls.forEach((url) => URL.revokeObjectURL(url));
  blobUrls.length = 0;
}

/**
 * Find .model3.json in a FileList from webkitdirectory input
 */
export function findModelFileInFileList(files: FileList): File | null {
  for (let i = 0; i < files.length; i++) {
    if (files[i].name.endsWith('.model3.json')) {
      return files[i];
    }
  }
  return null;
}

/**
 * Find .model3.json in dropped items (files or directory entries)
 */
export async function findModelFromDrop(dataTransfer: DataTransfer): Promise<{ modelFile: File; allFiles: Map<string, File> } | null> {
  const allFiles = new Map<string, File>();
  let modelFile: File | null = null;

  // Try using webkitGetAsEntry for directory support
  const items = dataTransfer.items;
  if (items && items.length > 0 && items[0].webkitGetAsEntry) {
    const entries: FileSystemEntry[] = [];
    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry();
      if (entry) entries.push(entry);
    }

    for (const entry of entries) {
      await collectFiles(entry, '', allFiles);
    }

    for (const [relativePath, file] of allFiles) {
      if (relativePath.endsWith('.model3.json')) {
        modelFile = file;
        break;
      }
    }
  } else {
    // Fallback: direct file drop
    const files = dataTransfer.files;
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      allFiles.set(f.name, f);
      if (f.name.endsWith('.model3.json')) {
        modelFile = f;
      }
    }
  }

  if (!modelFile) return null;
  return { modelFile, allFiles };
}

async function collectFiles(entry: FileSystemEntry, basePath: string, files: Map<string, File>): Promise<void> {
  if (entry.isFile) {
    const fileEntry = entry as FileSystemFileEntry;
    const file = await new Promise<File>((resolve, reject) => {
      fileEntry.file(resolve, reject);
    });
    const relativePath = basePath ? `${basePath}/${entry.name}` : entry.name;
    files.set(relativePath, file);
  } else if (entry.isDirectory) {
    const dirEntry = entry as FileSystemDirectoryEntry;
    const reader = dirEntry.createReader();
    const entries = await new Promise<FileSystemEntry[]>((resolve, reject) => {
      reader.readEntries(resolve, reject);
    });
    const dirPath = basePath ? `${basePath}/${entry.name}` : entry.name;
    for (const child of entries) {
      await collectFiles(child, dirPath, files);
    }
  }
}

/**
 * Load a local model from File objects (browser environment).
 * Rewrites all relative paths in model3.json to blob URLs.
 * Returns a blob URL pointing to the rewritten model3.json.
 */
export async function loadLocalModelFromFiles(modelFile: File, allFiles: Map<string, File>): Promise<string> {
  // NOTE: Do NOT call cleanupBlobUrls() here — the previous blob URLs may still be
  // in use by a Live2D model that hasn't been destroyed yet. Cleanup is done lazily:
  // old URLs are revoked only when the component unmounts or a new model finishes loading.

  const modelJson = JSON.parse(await modelFile.text());

  // Determine model directory prefix from the model file's path in allFiles
  let modelDir = '';
  for (const [path] of allFiles) {
    if (path.endsWith(modelFile.name)) {
      const idx = path.lastIndexOf('/');
      if (idx >= 0) modelDir = path.substring(0, idx);
      break;
    }
  }

  // Create blob URLs for all non-json files
  const blobUrlMap = new Map<string, string>();
  for (const [relativePath, file] of allFiles) {
    if (relativePath.endsWith('.model3.json')) continue;
    const blobUrl = URL.createObjectURL(file);
    blobUrls.push(blobUrl);
    // Store relative to model directory
    const relToModel = modelDir && relativePath.startsWith(modelDir + '/')
      ? relativePath.substring(modelDir.length + 1)
      : relativePath;
    blobUrlMap.set(relToModel, blobUrl);
  }

  // Rewrite paths in model3.json
  rewriteModelPaths(modelJson, blobUrlMap);

  // Create blob URL for the rewritten model3.json
  const modelBlob = new Blob([JSON.stringify(modelJson)], { type: 'application/json' });
  const modelBlobUrl = URL.createObjectURL(modelBlob);
  blobUrls.push(modelBlobUrl);

  return modelBlobUrl;
}

/**
 * Load a local model via Electron IPC.
 * Reads model3.json, resolves all referenced files, creates blob URLs.
 */
export async function loadLocalModelFromElectron(modelFilePath: string): Promise<string> {
  // NOTE: Do NOT call cleanupBlobUrls() here — see loadLocalModelFromFiles comment.

  const api = (window as any).electronAPI;

  // Read model3.json
  const result = await api.readModelFile(modelFilePath);
  if (!result.success || !result.data) throw new Error(result.error || 'Failed to read model file');

  const modelJson = JSON.parse(atob(result.data));

  // Get directory of model file
  const modelDir = modelFilePath.substring(0, modelFilePath.lastIndexOf('/'));

  // Collect all referenced file paths from model3.json
  const referencedPaths = extractReferencedPaths(modelJson);

  // Read each file and create blob URLs
  const blobUrlMap = new Map<string, string>();
  for (const relPath of referencedPaths) {
    const absPath = `${modelDir}/${relPath}`;
    const fileResult = await api.readModelFile(absPath);
    if (fileResult.success && fileResult.data) {
      const binary = atob(fileResult.data);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const blob = new Blob([bytes], { type: fileResult.mime || 'application/octet-stream' });
      const blobUrl = URL.createObjectURL(blob);
      blobUrls.push(blobUrl);
      blobUrlMap.set(relPath, blobUrl);
    }
  }

  // Rewrite paths
  rewriteModelPaths(modelJson, blobUrlMap);

  const modelBlob = new Blob([JSON.stringify(modelJson)], { type: 'application/json' });
  const modelBlobUrl = URL.createObjectURL(modelBlob);
  blobUrls.push(modelBlobUrl);

  return modelBlobUrl;
}

/**
 * Extract all referenced file paths from a model3.json structure
 */
function extractReferencedPaths(json: any): string[] {
  const paths: string[] = [];

  // Moc
  if (json.FileReferences?.Moc) paths.push(json.FileReferences.Moc);

  // Textures
  if (Array.isArray(json.FileReferences?.Textures)) {
    paths.push(...json.FileReferences.Textures);
  }

  // Physics
  if (json.FileReferences?.Physics) paths.push(json.FileReferences.Physics);

  // Pose
  if (json.FileReferences?.Pose) paths.push(json.FileReferences.Pose);

  // UserData
  if (json.FileReferences?.UserData) paths.push(json.FileReferences.UserData);

  // DisplayInfo
  if (json.FileReferences?.DisplayInfo) paths.push(json.FileReferences.DisplayInfo);

  // Expressions
  if (Array.isArray(json.FileReferences?.Expressions)) {
    for (const expr of json.FileReferences.Expressions) {
      if (expr.File) paths.push(expr.File);
    }
  }

  // Motions
  if (json.FileReferences?.Motions) {
    for (const group of Object.values(json.FileReferences.Motions) as any[]) {
      if (Array.isArray(group)) {
        for (const motion of group) {
          if (motion.File) paths.push(motion.File);
          if (motion.Sound) paths.push(motion.Sound);
        }
      }
    }
  }

  return paths.filter(Boolean);
}

/**
 * Rewrite file paths in model3.json to blob URLs
 */
function rewriteModelPaths(json: any, blobUrlMap: Map<string, string>): void {
  const rewrite = (p: string) => {
    // Try exact match first
    const exact = blobUrlMap.get(p);
    if (exact) return exact;
    // Try without leading ./
    const normalized = p.replace(/^\.\//, '');
    const norm = blobUrlMap.get(normalized);
    if (norm) return norm;
    // Try all entries for a suffix match (handles varying directory prefixes)
    for (const [key, url] of blobUrlMap) {
      if (key.endsWith('/' + normalized) || key === normalized) return url;
    }
    // Return original (may cause issues if library tries relative resolution on blob: base)
    return p;
  };

  if (json.FileReferences?.Moc) json.FileReferences.Moc = rewrite(json.FileReferences.Moc);

  if (Array.isArray(json.FileReferences?.Textures)) {
    json.FileReferences.Textures = json.FileReferences.Textures.map(rewrite);
  }

  if (json.FileReferences?.Physics) json.FileReferences.Physics = rewrite(json.FileReferences.Physics);
  if (json.FileReferences?.Pose) json.FileReferences.Pose = rewrite(json.FileReferences.Pose);
  if (json.FileReferences?.UserData) json.FileReferences.UserData = rewrite(json.FileReferences.UserData);
  if (json.FileReferences?.DisplayInfo) json.FileReferences.DisplayInfo = rewrite(json.FileReferences.DisplayInfo);

  if (Array.isArray(json.FileReferences?.Expressions)) {
    for (const expr of json.FileReferences.Expressions) {
      if (expr.File) expr.File = rewrite(expr.File);
    }
  }

  if (json.FileReferences?.Motions) {
    for (const group of Object.values(json.FileReferences.Motions) as any[]) {
      if (Array.isArray(group)) {
        for (const motion of group) {
          if (motion.File) motion.File = rewrite(motion.File);
          if (motion.Sound) motion.Sound = rewrite(motion.Sound);
        }
      }
    }
  }
}
