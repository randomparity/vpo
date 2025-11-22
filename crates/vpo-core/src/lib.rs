use pyo3::prelude::*;

mod discovery;
mod hasher;

/// Returns the version of the vpo-core library.
#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

/// A Python module implemented in Rust.
#[pymodule]
#[pyo3(name = "_core")]
fn vpo_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(discovery::discover_videos, m)?)?;
    m.add_function(wrap_pyfunction!(hasher::hash_files, m)?)?;
    Ok(())
}
