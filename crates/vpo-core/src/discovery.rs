// False positive with PyO3's PyResult type alias
#![allow(clippy::useless_conversion)]

use pyo3::prelude::*;
use pyo3::types::PyDict;
use rayon::prelude::*;
use std::collections::HashSet;
use std::path::PathBuf;
use std::time::Instant;
use walkdir::WalkDir;

/// Discovered file information returned to Python.
#[derive(Clone)]
pub struct DiscoveredFile {
    pub path: String,
    pub size: u64,
    pub modified: f64,
}

impl<'py> IntoPyObject<'py> for DiscoveredFile {
    type Target = PyDict;
    type Output = Bound<'py, PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = PyDict::new(py);
        dict.set_item("path", self.path)?;
        dict.set_item("size", self.size)?;
        dict.set_item("modified", self.modified)?;
        Ok(dict)
    }
}

/// Recursively discover video files in a directory.
///
/// Args:
///     root_path: The root directory to scan
///     extensions: List of file extensions to match (e.g., ["mkv", "mp4"])
///     follow_symlinks: Whether to follow symbolic links
///     progress_callback: Optional callback called with (files_found, files_per_sec) as files
///         are discovered.
///
/// Returns:
///     List of dicts with path, size, and modified timestamp for each file
#[pyfunction]
#[pyo3(signature = (root_path, extensions, follow_symlinks = false, progress_callback = None))]
pub fn discover_videos(
    py: Python<'_>,
    root_path: &str,
    extensions: Vec<String>,
    follow_symlinks: bool,
    progress_callback: Option<PyObject>,
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

    // Note: walkdir silently skips directories/files that cannot be read due to
    // permission errors. This is intentional - we want to scan what we can access
    // rather than failing the entire scan on permission issues.
    let walker = WalkDir::new(&root).follow_links(follow_symlinks);

    // Collect all entries first, reporting progress during the sequential walk
    let mut entries: Vec<_> = Vec::new();
    let mut files_found: usize = 0;
    let mut last_reported: usize = 0;
    let start_time = Instant::now();

    for e in walker
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
        .flatten()
    {
        // Count files (not directories) with matching extensions
        if e.file_type().is_file() {
            if let Some(ext) = e.path().extension().and_then(|x| x.to_str()) {
                if extensions.contains(&ext.to_lowercase()) {
                    files_found += 1;

                    // Report progress and check for signals every 100 files
                    if files_found - last_reported >= 100 {
                        // Check for Ctrl+C (raises KeyboardInterrupt if signaled)
                        py.check_signals()?;

                        if let Some(ref cb) = progress_callback {
                            let elapsed = start_time.elapsed().as_secs_f64();
                            let rate = if elapsed > 0.0 {
                                files_found as f64 / elapsed
                            } else {
                                0.0
                            };
                            cb.call1(py, (files_found, rate))?;
                        }
                        last_reported = files_found;
                    }
                }
            }
        }
        entries.push(e);
    }

    // Final progress callback
    if let Some(ref cb) = progress_callback {
        if files_found != last_reported {
            let elapsed = start_time.elapsed().as_secs_f64();
            let rate = if elapsed > 0.0 {
                files_found as f64 / elapsed
            } else {
                0.0
            };
            cb.call1(py, (files_found, rate))?;
        }
    }

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

// Note: Unit tests for discover_videos require Python linking at test time.
// These are tested via Python integration tests in tests/unit/test_scanner_*.py
// which run through the maturin-built extension.
