"""Concurrent TESScut requests must not share Astroquery's timestamped ZIP."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from threading import Barrier
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import survivor_packets as S


class PixelFile:
    def __init__(self, path):
        self.path = Path(path)
        self.payload = self.path.read_text()

    def create_threshold_mask(self, **kwargs):
        return np.ones((2, 2), dtype=bool)

    def estimate_centroids(self, **kwargs):
        return np.zeros(1), np.zeros(1)


def coordinate(ra):
    return SimpleNamespace(ra=SimpleNamespace(deg=ra), dec=SimpleNamespace(deg=-40.0))


def filename(ra, sector=60):
    return f"tess-s{sector:04d}-1-1_{ra:.6f}_-40.000000_{S.CUTOUT_PX}x{S.CUTOUT_PX}_astrocut.fits"


def test_same_second_downloads_are_isolated(tmp_path, monkeypatch):
    from astroquery.mast import Tesscut
    monkeypatch.setenv("LIGHTKURVE_CACHE", str(tmp_path))
    barrier = Barrier(2)
    directories = []

    def download(*, coordinates, sector, path, **kwargs):
        directory = Path(path)
        directories.append(directory)
        payload = str(coordinates.ra.deg)
        archive = directory / "tesscut_same_second.zip"
        archive.write_text(payload)
        barrier.wait(timeout=5)
        assert archive.read_text() == payload
        fits = directory / filename(coordinates.ra.deg, sector)
        fits.write_text(payload)
        return {"Local Path": [str(fits)]}

    monkeypatch.setattr(Tesscut, "download_cutouts", download)
    lk = SimpleNamespace(TessTargetPixelFile=PixelFile)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda ra: S._tesscut_tpf(lk, coordinate(ra), 60, []), (10., 20.)))
    assert [result.payload for result in results] == ["10.0", "20.0"]
    assert len(set(directories)) == 2
    assert all(result.path.parent == tmp_path / "tesscut" for result in results)
    assert all(not directory.exists() for directory in directories)


@pytest.mark.parametrize("wrong_request", ["target", "directory"])
def test_foreign_download_is_rejected(tmp_path, monkeypatch, wrong_request):
    from astroquery.mast import Tesscut
    monkeypatch.setenv("LIGHTKURVE_CACHE", str(tmp_path))

    def download(*, path, **kwargs):
        destination = Path(path) / filename(20.) if wrong_request == "target" else tmp_path / filename(10.)
        destination.write_text("foreign")
        return {"Local Path": [str(destination)]}

    monkeypatch.setattr(Tesscut, "download_cutouts", download)
    with pytest.raises(ValueError, match="different target/sector"):
        S._tesscut_tpf(SimpleNamespace(TessTargetPixelFile=PixelFile), coordinate(10.), 60, [])
    assert not list((tmp_path / "tesscut").glob("*.fits"))


def test_existing_cache_name_is_reused(tmp_path, monkeypatch):
    from astroquery.mast import Tesscut
    monkeypatch.setenv("LIGHTKURVE_CACHE", str(tmp_path))
    cache = tmp_path / "tesscut"
    cache.mkdir()
    old = cache / filename(10.)
    old.write_text("legacy cutout")

    def unexpected_download(**kwargs):
        pytest.fail("A cached cutout must not be downloaded again")

    monkeypatch.setattr(Tesscut, "download_cutouts", unexpected_download)
    result = S._tesscut_tpf(SimpleNamespace(TessTargetPixelFile=PixelFile), coordinate(10.), 60, [])
    assert result.path == old and result.payload == "legacy cutout"
