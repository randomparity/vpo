use pyo3::prelude::*;
use pyo3::types::PyDict;
use rayon::prelude::*;
use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use xxhash_rust::xxh64::xxh64;

const CHUNK_SIZE: usize = 65536; // 64KB

/// Hash result for a single file.
#[derive(Clone)]
pub struct FileHash {
    pub path: String,
    pub hash: Option<String>,
    pub error: Option<String>,
}

impl IntoPy<PyObject> for FileHash {
    fn into_py(self, py: Python<'_>) -> PyObject {
        let dict = PyDict::new_bound(py);
        dict.set_item("path", self.path).unwrap();
        dict.set_item("hash", self.hash).unwrap();
        dict.set_item("error", self.error).unwrap();
        dict.into()
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
///
/// Returns:
///     List of dicts with path, hash (or None), and error (or None) for each file
#[pyfunction]
pub fn hash_files(paths: Vec<String>) -> Vec<FileHash> {
    paths
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
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::tempdir;

    #[test]
    fn test_hash_small_file() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("small.bin");
        let mut file = File::create(&path).unwrap();
        file.write_all(b"hello world").unwrap();

        let result = hash_files(vec![path.to_string_lossy().to_string()]);
        assert_eq!(result.len(), 1);
        assert!(result[0].hash.is_some());
        assert!(result[0].error.is_none());
        assert!(result[0].hash.as_ref().unwrap().starts_with("xxh64:"));
    }

    #[test]
    fn test_hash_large_file() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("large.bin");
        let mut file = File::create(&path).unwrap();
        // Create a file larger than 128KB
        let data = vec![0u8; 200_000];
        file.write_all(&data).unwrap();

        let result = hash_files(vec![path.to_string_lossy().to_string()]);
        assert_eq!(result.len(), 1);
        assert!(result[0].hash.is_some());
        assert!(result[0].error.is_none());

        let hash = result[0].hash.as_ref().unwrap();
        assert!(hash.starts_with("xxh64:"));
        assert!(hash.ends_with(":200000"));
    }

    #[test]
    fn test_hash_nonexistent_file() {
        let result = hash_files(vec!["/nonexistent/file.bin".to_string()]);
        assert_eq!(result.len(), 1);
        assert!(result[0].hash.is_none());
        assert!(result[0].error.is_some());
    }

    #[test]
    fn test_hash_multiple_files() {
        let dir = tempdir().unwrap();
        let path1 = dir.path().join("file1.bin");
        let path2 = dir.path().join("file2.bin");
        File::create(&path1).unwrap().write_all(b"file1").unwrap();
        File::create(&path2).unwrap().write_all(b"file2").unwrap();

        let result = hash_files(vec![
            path1.to_string_lossy().to_string(),
            path2.to_string_lossy().to_string(),
        ]);
        assert_eq!(result.len(), 2);
        assert!(result.iter().all(|r| r.hash.is_some()));
    }
}
