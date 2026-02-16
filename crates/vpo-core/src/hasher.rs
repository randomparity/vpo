// False positive with PyO3's PyResult type alias
#![allow(clippy::useless_conversion)]

use pyo3::prelude::*;
use pyo3::types::PyDict;
use rayon::prelude::*;
use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::time::Instant;
use xxhash_rust::xxh64::xxh64;

const CHUNK_SIZE: usize = 65536; // 64KB
const PROGRESS_BATCH_SIZE: usize = 100; // Report progress every N files

/// Hash result for a single file.
#[derive(Clone)]
pub struct FileHash {
    pub path: String,
    pub hash: Option<String>,
    pub error: Option<String>,
}

impl<'py> IntoPyObject<'py> for FileHash {
    type Target = PyDict;
    type Output = Bound<'py, PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = PyDict::new(py);
        dict.set_item("path", self.path)?;
        dict.set_item("hash", self.hash)?;
        dict.set_item("error", self.error)?;
        Ok(dict)
    }
}

/// Compute a partial hash of a file using xxHash64.
///
/// For files >= 128KB: hash first 64KB + last 64KB + file size
/// For smaller files: hash the entire file
///
/// Returns hash in format: xxh64:<first_hash>:<last_hash>:<size>
fn compute_file_hash(path: &str) -> Result<String, String> {
    let mut file = File::open(path).map_err(|e| e.to_string())?;
    let metadata = file.metadata().map_err(|e| e.to_string())?;
    let size = metadata.len();

    if size < (CHUNK_SIZE * 2) as u64 {
        // Small file: hash entire content
        // Note: We repeat the hash twice (first_hash:last_hash) even for small files
        // to maintain a consistent format with large files, simplifying parsing.
        let mut buffer = Vec::new();
        file.read_to_end(&mut buffer).map_err(|e| e.to_string())?;
        let hash = xxh64(&buffer, 0);
        Ok(format!("xxh64:{:016x}:{:016x}:{}", hash, hash, size))
    } else {
        // Large file: hash first and last chunks
        let mut first_chunk = vec![0u8; CHUNK_SIZE];
        file.read_exact(&mut first_chunk)
            .map_err(|e| e.to_string())?;
        let first_hash = xxh64(&first_chunk, 0);

        let mut last_chunk = vec![0u8; CHUNK_SIZE];
        file.seek(SeekFrom::End(-(CHUNK_SIZE as i64)))
            .map_err(|e| e.to_string())?;
        file.read_exact(&mut last_chunk)
            .map_err(|e| e.to_string())?;
        let last_hash = xxh64(&last_chunk, 0);

        Ok(format!(
            "xxh64:{:016x}:{:016x}:{}",
            first_hash, last_hash, size
        ))
    }
}

/// Hash multiple files in parallel.
///
/// Args:
///     paths: List of file paths to hash
///     progress_callback: Optional callback called with (processed, total, files_per_sec)
///         as files are hashed
///
/// Returns:
///     List of dicts with path, hash (or None), and error (or None) for each file
#[pyfunction]
#[pyo3(signature = (paths, progress_callback = None))]
pub fn hash_files(
    py: Python<'_>,
    paths: Vec<String>,
    progress_callback: Option<Py<PyAny>>,
) -> PyResult<Vec<FileHash>> {
    let total = paths.len();

    if let Some(ref cb) = progress_callback {
        // Use batched processing to allow progress callbacks between batches
        let mut results: Vec<FileHash> = Vec::with_capacity(total);
        let mut processed: usize = 0;
        let start_time = Instant::now();

        for chunk in paths.chunks(PROGRESS_BATCH_SIZE) {
            // Check for Ctrl+C before each batch
            py.check_signals()?;

            // Release GIL during parallel hashing
            let chunk_results: Vec<FileHash> = py.detach(|| {
                chunk
                    .par_iter()
                    .map(|path| match compute_file_hash(path) {
                        Ok(hash) => FileHash {
                            path: path.clone(),
                            hash: Some(hash),
                            error: None,
                        },
                        Err(e) => FileHash {
                            path: path.clone(),
                            hash: None,
                            error: Some(e),
                        },
                    })
                    .collect()
            });

            processed += chunk_results.len();
            results.extend(chunk_results);

            // Call progress callback (holding GIL)
            let elapsed = start_time.elapsed().as_secs_f64();
            let rate = if elapsed > 0.0 {
                processed as f64 / elapsed
            } else {
                0.0
            };
            cb.call1(py, (processed, total, rate))?;
        }

        Ok(results)
    } else {
        // No callback - use batched processing to allow signal checking
        let mut results: Vec<FileHash> = Vec::with_capacity(total);

        for chunk in paths.chunks(PROGRESS_BATCH_SIZE) {
            // Check for Ctrl+C before each batch
            py.check_signals()?;

            // Release GIL during parallel hashing
            let chunk_results: Vec<FileHash> = py.detach(|| {
                chunk
                    .par_iter()
                    .map(|path| match compute_file_hash(path) {
                        Ok(hash) => FileHash {
                            path: path.clone(),
                            hash: Some(hash),
                            error: None,
                        },
                        Err(e) => FileHash {
                            path: path.clone(),
                            hash: None,
                            error: Some(e),
                        },
                    })
                    .collect()
            });

            results.extend(chunk_results);
        }

        Ok(results)
    }
}

// Note: Unit tests for hash_files require Python linking at test time.
// These are tested via Python integration tests in tests/unit/test_scanner_*.py
// which run through the maturin-built extension.
