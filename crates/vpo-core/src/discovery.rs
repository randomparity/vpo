use pyo3::prelude::*;
use pyo3::types::PyDict;
use rayon::prelude::*;
use std::collections::HashSet;
use std::path::PathBuf;
use walkdir::WalkDir;

/// Discovered file information returned to Python.
#[derive(Clone)]
pub struct DiscoveredFile {
    pub path: String,
    pub size: u64,
    pub modified: f64,
}

impl IntoPy<PyObject> for DiscoveredFile {
    fn into_py(self, py: Python<'_>) -> PyObject {
        let dict = PyDict::new_bound(py);
        dict.set_item("path", self.path).unwrap();
        dict.set_item("size", self.size).unwrap();
        dict.set_item("modified", self.modified).unwrap();
        dict.into()
    }
}

/// Recursively discover video files in a directory.
///
/// Args:
///     root_path: The root directory to scan
///     extensions: List of file extensions to match (e.g., ["mkv", "mp4"])
///     follow_symlinks: Whether to follow symbolic links
///
/// Returns:
///     List of dicts with path, size, and modified timestamp for each file
#[pyfunction]
#[pyo3(signature = (root_path, extensions, follow_symlinks = false))]
pub fn discover_videos(
    root_path: &str,
    extensions: Vec<String>,
    follow_symlinks: bool,
) -> PyResult<Vec<DiscoveredFile>> {
    let extensions: HashSet<String> = extensions.into_iter().map(|e| e.to_lowercase()).collect();
    let root = PathBuf::from(root_path);

    // Check if root exists
    if !root.exists() {
        return Err(PyErr::new::<pyo3::exceptions::PyFileNotFoundError, _>(
            format!("Directory not found: {}", root_path),
        ));
    }

    if !root.is_dir() {
        return Err(PyErr::new::<pyo3::exceptions::PyNotADirectoryError, _>(
            format!("Not a directory: {}", root_path),
        ));
    }

    // Track visited directories to detect symlink cycles
    let visited: std::sync::Mutex<HashSet<PathBuf>> = std::sync::Mutex::new(HashSet::new());

    let walker = WalkDir::new(&root).follow_links(follow_symlinks);

    // Collect all entries first
    let entries: Vec<_> = walker
        .into_iter()
        .filter_entry(|e| {
            // Skip hidden directories
            if e.file_type().is_dir() {
                if let Some(name) = e.file_name().to_str() {
                    if name.starts_with('.') && e.depth() > 0 {
                        return false;
                    }
                }
            }

            // Symlink cycle detection
            if follow_symlinks && e.file_type().is_dir() {
                if let Ok(canonical) = e.path().canonicalize() {
                    let mut visited_guard = visited.lock().unwrap();
                    if visited_guard.contains(&canonical) {
                        return false; // Skip cycle
                    }
                    visited_guard.insert(canonical);
                }
            }

            true
        })
        .filter_map(|e| e.ok())
        .collect();

    // Process files in parallel
    let files: Vec<DiscoveredFile> = entries
        .par_iter()
        .filter_map(|entry| {
            if !entry.file_type().is_file() {
                return None;
            }

            let path = entry.path();
            let extension = path
                .extension()
                .and_then(|e| e.to_str())
                .map(|e| e.to_lowercase())?;

            if !extensions.contains(&extension) {
                return None;
            }

            let metadata = entry.metadata().ok()?;
            let modified = metadata
                .modified()
                .ok()
                .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                .map(|d| d.as_secs_f64())
                .unwrap_or(0.0);

            Some(DiscoveredFile {
                path: path.to_string_lossy().to_string(),
                size: metadata.len(),
                modified,
            })
        })
        .collect();

    Ok(files)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::{self, File};
    use tempfile::tempdir;

    #[test]
    fn test_discover_videos_empty_dir() {
        let dir = tempdir().unwrap();
        let result = discover_videos(dir.path().to_str().unwrap(), vec!["mkv".to_string()], false);
        assert!(result.is_ok());
        assert!(result.unwrap().is_empty());
    }

    #[test]
    fn test_discover_videos_with_files() {
        let dir = tempdir().unwrap();
        File::create(dir.path().join("video.mkv")).unwrap();
        File::create(dir.path().join("video.mp4")).unwrap();
        File::create(dir.path().join("text.txt")).unwrap();

        let result = discover_videos(
            dir.path().to_str().unwrap(),
            vec!["mkv".to_string(), "mp4".to_string()],
            false,
        );
        assert!(result.is_ok());
        let files = result.unwrap();
        assert_eq!(files.len(), 2);
    }

    #[test]
    fn test_discover_videos_nested() {
        let dir = tempdir().unwrap();
        fs::create_dir(dir.path().join("nested")).unwrap();
        File::create(dir.path().join("nested/deep.mkv")).unwrap();

        let result = discover_videos(dir.path().to_str().unwrap(), vec!["mkv".to_string()], false);
        assert!(result.is_ok());
        let files = result.unwrap();
        assert_eq!(files.len(), 1);
    }

    #[test]
    fn test_discover_videos_skips_hidden() {
        let dir = tempdir().unwrap();
        fs::create_dir(dir.path().join(".hidden")).unwrap();
        File::create(dir.path().join(".hidden/video.mkv")).unwrap();
        File::create(dir.path().join("visible.mkv")).unwrap();

        let result = discover_videos(dir.path().to_str().unwrap(), vec!["mkv".to_string()], false);
        assert!(result.is_ok());
        let files = result.unwrap();
        assert_eq!(files.len(), 1);
        assert!(files[0].path.contains("visible"));
    }

    #[test]
    fn test_discover_videos_not_found() {
        let result = discover_videos("/nonexistent/path", vec!["mkv".to_string()], false);
        assert!(result.is_err());
    }
}
