"""Tests for rewriting `ImageSeries.external_file` paths relative to the written NWB file."""

import pytest
from pynwb import NWBHDF5IO, read_nwb
from pynwb.image import ImageSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv import ConverterPipe
from neuroconv.tools.nwb_helpers import configure_and_write_nwbfile, get_module
from neuroconv.tools.testing.mock_interfaces import MockExternalVideoInterface


def external_image_series(name: str, external_file: list[str]) -> ImageSeries:
    return ImageSeries(
        name=name,
        external_file=external_file,
        format="external",
        starting_frame=[0] * len(external_file),
        rate=30.0,
        num_samples=10,
        unit="n.a.",
    )


def test_absolute_path_under_the_output_directory(tmp_path):
    nwbfile = mock_NWBFile()
    nwbfile.add_acquisition(external_image_series(name="Video", external_file=[str(tmp_path / "videos" / "a.avi")]))

    nwbfile_path = tmp_path / "test.nwb"
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path, backend="hdf5")

    assert list(read_nwb(nwbfile_path).acquisition["Video"].external_file) == ["videos/a.avi"]


def test_absolute_path_outside_the_output_directory(tmp_path):
    nwbfile = mock_NWBFile()
    nwbfile.add_acquisition(external_image_series(name="Video", external_file=[str(tmp_path / "videos" / "a.avi")]))

    nwbfile_path = tmp_path / "output" / "nwb" / "test.nwb"
    nwbfile_path.parent.mkdir(parents=True)
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path, backend="hdf5")

    assert list(read_nwb(nwbfile_path).acquisition["Video"].external_file) == ["../../videos/a.avi"]


def test_working_directory_relative_path_is_rebased_onto_the_output_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    nwbfile = mock_NWBFile()
    nwbfile.add_acquisition(external_image_series(name="Video", external_file=["videos/a.avi"]))

    nwbfile_path = tmp_path / "output" / "test.nwb"
    nwbfile_path.parent.mkdir()
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path, backend="hdf5")

    assert list(read_nwb(nwbfile_path).acquisition["Video"].external_file) == ["../videos/a.avi"]


def test_url_is_left_untouched(tmp_path):
    url = "https://example.org/videos/a.avi"
    nwbfile = mock_NWBFile()
    nwbfile.add_acquisition(external_image_series(name="Video", external_file=[url]))

    nwbfile_path = tmp_path / "test.nwb"
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path, backend="hdf5")

    assert list(read_nwb(nwbfile_path).acquisition["Video"].external_file) == [url]


def test_file_without_image_series_is_written_unchanged(tmp_path):
    nwbfile = mock_NWBFile()

    nwbfile_path = tmp_path / "test.nwb"
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path, backend="hdf5")

    assert read_nwb(nwbfile_path).acquisition == {}


def test_every_image_series_is_rewritten(tmp_path):
    nwbfile = mock_NWBFile()
    nwbfile.add_acquisition(
        external_image_series(
            name="Acquired", external_file=[str(tmp_path / "videos" / "a.avi"), str(tmp_path / "videos" / "b.avi")]
        )
    )
    behavior_module = get_module(nwbfile=nwbfile, name="behavior", description="Behavior data.")
    behavior_module.add(external_image_series(name="Processed", external_file=[str(tmp_path / "videos" / "c.avi")]))

    nwbfile_path = tmp_path / "test.nwb"
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=nwbfile_path, backend="hdf5")

    written = read_nwb(nwbfile_path)
    assert list(written.acquisition["Acquired"].external_file) == ["videos/a.avi", "videos/b.avi"]
    assert list(written.processing["behavior"]["Processed"].external_file) == ["videos/c.avi"]


def test_export_keeps_the_paths_of_the_source_file(tmp_path):
    source_path = tmp_path / "source.nwb"
    nwbfile = mock_NWBFile()
    nwbfile.add_acquisition(external_image_series(name="Video", external_file=[str(tmp_path / "videos" / "a.avi")]))
    configure_and_write_nwbfile(nwbfile=nwbfile, nwbfile_path=source_path, backend="hdf5")

    export_path = tmp_path / "exported" / "export.nwb"
    export_path.parent.mkdir()
    with NWBHDF5IO(source_path, mode="r") as io:
        configure_and_write_nwbfile(nwbfile=io.read(), nwbfile_path=export_path, backend="hdf5")

    assert list(read_nwb(export_path).acquisition["Video"].external_file) == ["videos/a.avi"]


@pytest.mark.parametrize("through_converter", [False, True], ids=["interface", "converter"])
def test_append_rewrites_the_added_image_series(tmp_path, through_converter):
    nwbfile_path = tmp_path / "test.nwb"
    first = MockExternalVideoInterface(file_paths=[str(tmp_path / "videos" / "a.avi")], metadata_key="first")
    second = MockExternalVideoInterface(file_paths=[str(tmp_path / "videos" / "b.avi")], metadata_key="second")
    if through_converter:
        first, second = ConverterPipe([first]), ConverterPipe([second])

    first.run_conversion(nwbfile_path=nwbfile_path, backend="hdf5")
    second.run_conversion(nwbfile_path=nwbfile_path, append_on_disk_nwbfile=True)

    written = read_nwb(nwbfile_path)
    assert list(written.acquisition["Video a"].external_file) == ["videos/a.avi"]
    assert list(written.acquisition["Video b"].external_file) == ["videos/b.avi"]


def test_interface_paths_survive_a_conversion(tmp_path):
    """The interface hands its own `file_paths` list to the series, and a second conversion must still see them."""
    interface = MockExternalVideoInterface(file_paths=[str(tmp_path / "videos" / "a.avi")])

    first_path = tmp_path / "first" / "test.nwb"
    second_path = tmp_path / "second" / "nested" / "test.nwb"
    first_path.parent.mkdir()
    second_path.parent.mkdir(parents=True)
    interface.run_conversion(nwbfile_path=first_path, backend="hdf5")
    interface.run_conversion(nwbfile_path=second_path, backend="hdf5")

    assert list(read_nwb(first_path).acquisition["Video a"].external_file) == ["../videos/a.avi"]
    assert list(read_nwb(second_path).acquisition["Video a"].external_file) == ["../../videos/a.avi"]
