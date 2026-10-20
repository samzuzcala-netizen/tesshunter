# Fitted-model archive storage

The scientific worker writes ordinary NPZ fitted-model archives. Completed archives may subsequently be wrapped in standard XZ compression. The original logical `.npz` reference then resolves to `.npz.xz`; decompression reproduces the complete original NPZ file byte for byte. `protocol/model_storage.py:open_model` reads either representation with NumPy. Standard XZ tools also restore the original container.

Every packed file has an immutable `results/model_storage/<candidate>.json` receipt binding the original NPZ SHA256, compressed SHA256, uncompressed size, compressed size and unchanged scientific case SHA256. The original redundant NPZ is removed only after decompression verification and durable receipt creation, and only inside the isolated P11.5 `c_models` directory. No historical data or scientific prediction is changed.

The prospective storage-only pilot on the largest completed timing archive saved 32.5% with byte-identical reconstruction. Alternative per-member LZMA and BZIP2 tests, including their costs, remain preserved. This is evidence packaging; neither model selection nor scientific thresholds depend on compression results. Packaging costs are reported separately from original scientific worker timings, and must be included in experiment expenditure.
