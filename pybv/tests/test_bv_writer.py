# -*- coding: utf-8 -*-
"""BrainVision Writer tests."""

# Authors: Phillip Alday <phillip.alday@unisa.edu.au>
#          Chris Holdgraf <choldgraf@berkeley.edu>
#          Stefan Appelhoff <stefan.appelhoff@mailbox.org>
#          Tristan Stenner <stenner@med-psych.uni-kiel.de>
#          Clemens Brunner <clemens.brunner@gmail.com>
#          Richard Höchenberger <richard.hoechenberger@gmail.com>
#
# License: BSD (3-clause)

from datetime import datetime, timezone

import mne
import numpy as np
import pytest
from mne.utils import requires_version
from numpy.testing import assert_allclose, assert_array_equal

from pybv.io import (SUPPORTED_FORMATS, SUPPORTED_VOLTAGE_SCALINGS,
                     _check_data_in_range, _chk_fmt, _scale_data_to_unit,
                     _write_bveeg_file, _write_vhdr_file, write_brainvision)

# create testing data
fname = 'pybv'
rng = np.random.RandomState(1337)
n_chans = 10
ch_names = [f'ch_{i}' for i in range(n_chans)]
sfreq = 1000
n_seconds = 5
n_times = n_seconds * sfreq
event_times = np.arange(1, 5)
events = np.column_stack([event_times * sfreq, [1, 1, 2, 2]])
# scale random data to reasonable EEG signal magnitude in V
data = rng.randn(n_chans, n_times) * 10 * 1e-6


@pytest.mark.parametrize(
    "events_errormsg",
    [([], 'events must be an ndarray of shape'),
     (rng.randn(10, 20, 30), 'events must be an ndarray of shape'),
     (rng.randn(10, 4), 'events must be an ndarray of shape'),
     (np.array([i for i in "abcd"]).reshape(2, -1), 'events must be an ndarray of shape'),  # noqa: E501
     (events, ''),
     (None, '')
     ])
def test_bv_writer_events(tmpdir, events_errormsg):
    """Test that all event options work without throwing an error."""
    kwargs = dict(data=data, sfreq=sfreq, ch_names=ch_names,
                  fname_base=fname, folder_out=tmpdir)

    ev, errormsg = events_errormsg
    if errormsg:
        with pytest.raises(ValueError, match=errormsg):
            write_brainvision(**kwargs, events=ev)
    else:
        write_brainvision(**kwargs, events=ev)


def test_kw_only_args(tmpdir):
    """Test that keyword only arguments are allowed."""
    msg = r'write_brainvision\(\) takes 0 positional arguments'
    with pytest.raises(TypeError, match=msg):
        write_brainvision(data, sfreq, ch_names, fname, folder_out=tmpdir)


def test_bv_writer_inputs(tmpdir):
    """Test channels, sfreq=sfreq, and resolution."""
    with pytest.raises(ValueError, match='Number of channels in data'):
        write_brainvision(data=data[1:, :], sfreq=sfreq, ch_names=ch_names,
                          fname_base=fname, folder_out=tmpdir)
    with pytest.raises(ValueError, match='Channel names must be unique'):
        write_brainvision(data=data[0:2, :], sfreq=sfreq, ch_names=['b', 'b'],
                          fname_base=fname, folder_out=tmpdir)
    with pytest.raises(ValueError, match='sfreq must be one of '):
        write_brainvision(data=data, sfreq='100', ch_names=ch_names,
                          fname_base=fname, folder_out=tmpdir)
    with pytest.raises(ValueError, match='Resolution should be numeric, is'):
        write_brainvision(data=data, sfreq=sfreq, ch_names=ch_names,
                          fname_base=fname, folder_out=tmpdir, resolution='y')
    with pytest.raises(ValueError, match='Resolution should be > 0'):
        write_brainvision(data=data, sfreq=sfreq, ch_names=ch_names,
                          fname_base=fname, folder_out=tmpdir, resolution=0)
    with pytest.raises(ValueError, match='Resolution should be one or n_chan'):
        write_brainvision(data=data, sfreq=sfreq, ch_names=ch_names,
                          fname_base=fname, folder_out=tmpdir,
                          resolution=np.arange(n_chans-1))


def test_bv_bad_format(tmpdir):
    """Test that bad formats throw an error."""
    vhdr_fname = tmpdir / fname + ".vhdr"
    vmrk_fname = tmpdir / fname + ".vmrk"
    eeg_fname = tmpdir / fname + ".eeg"

    with pytest.raises(ValueError, match='Orientation bad not supported'):
        _write_vhdr_file(vhdr_fname, vmrk_fname, eeg_fname, data=data,
                         sfreq=sfreq, ch_names=ch_names, orientation='bad',
                         format="binary_float32", resolution=1e-6,
                         units=["V"] * n_chans)
    with pytest.raises(ValueError, match='Data format bad not supported'):
        _write_vhdr_file(vhdr_fname, vmrk_fname, eeg_fname, data=data,
                         sfreq=sfreq, ch_names=ch_names,
                         orientation='multiplexed', format="bad",
                         resolution=1e-6,
                         units=["V"] * n_chans)
    with pytest.raises(ValueError, match='Orientation bad not supported'):
        _write_bveeg_file(eeg_fname, data=data, orientation='bad',
                          format="bad", resolution=1e-6,
                          units=["µV"] * n_chans)
    with pytest.raises(ValueError, match='Data format bad not supported'):
        _write_bveeg_file(eeg_fname, data=data, orientation='multiplexed',
                          format="bad", resolution=1e-6,
                          units=["µV"] * n_chans)


@pytest.mark.parametrize("meas_date,match",
                         [(1, '`meas_date` must be of type str, datetime'),
                          ('', 'Got a str for `meas_date`, but it was'),
                          ('1973', 'Got a str for `meas_date`, but it was')])
def test_bad_meas_date(tmpdir, meas_date, match):
    """Test that bad measurement dates raise errors."""
    with pytest.raises(ValueError, match=match):
        write_brainvision(data=data, sfreq=sfreq, ch_names=ch_names,
                          fname_base=fname, folder_out=tmpdir,
                          meas_date=meas_date)


@requires_version("mne", min_version="0.22")
@pytest.mark.parametrize("ch_names_tricky",
                         [[ch + ' f o o' for ch in ch_names],
                          [ch + ',foo' for ch in ch_names],
                          ]
                         )
def test_comma_in_ch_name(tmpdir, ch_names_tricky):
    """Test that writing channel names with special characters works."""
    # write and read data to BV format
    write_brainvision(data=data, sfreq=sfreq, ch_names=ch_names_tricky,
                      fname_base=fname, folder_out=tmpdir)
    vhdr_fname = tmpdir / fname + '.vhdr'
    raw_written = mne.io.read_raw_brainvision(vhdr_fname=vhdr_fname,
                                              preload=True)

    assert ch_names_tricky == raw_written.ch_names  # channels

    assert_allclose(data, raw_written._data)  # data round-trip


@pytest.mark.parametrize("meas_date",
                         [('20000101120000000000'),
                          (datetime(2000, 1, 1, 12, 0, 0, 0))])
def test_write_read_cycle(tmpdir, meas_date):
    """Test that a write/read cycle produces identical data."""
    # First fail writing due to wrong unit
    unsupported_unit = "rV"
    with pytest.warns(UserWarning, match='Encountered unsupported '
                                         'non-voltage unit'):
        write_brainvision(data=data, sfreq=sfreq, ch_names=ch_names,
                          fname_base=fname, folder_out=tmpdir,
                          unit=unsupported_unit)

    # write and read data to BV format
    # ensure that greek small letter mu gets converted to micro sign
    with pytest.warns(UserWarning, match="Encountered small Greek letter mu"):
        write_brainvision(data=data, sfreq=sfreq, ch_names=ch_names,
                          fname_base=fname, folder_out=tmpdir, events=events,
                          resolution=np.power(10., -np.arange(10)),
                          unit='μV', meas_date=meas_date)
    vhdr_fname = tmpdir / fname + '.vhdr'
    raw_written = mne.io.read_raw_brainvision(vhdr_fname=vhdr_fname,
                                              preload=True)
    # delete the first annotation because it's just marking a new segment
    raw_written.annotations.delete(0)
    # convert our annotations to events
    events_written, event_id = mne.events_from_annotations(raw_written)

    # sfreq
    assert sfreq == raw_written.info['sfreq']

    # event timing should be exactly the same
    assert_array_equal(events[:, 0], events_written[:, 0])
    assert_array_equal(events[:, 1], events_written[:, 2])

    assert len(event_id) == 2  # there should be two unique event types

    assert_allclose(data, raw_written._data)  # data round-trip

    assert_array_equal(ch_names, raw_written.ch_names)  # channels

    # measurement dates must match
    assert raw_written.info['meas_date'] == datetime(2000, 1, 1, 12, 0, 0, 0,
                                                     tzinfo=timezone.utc)


resolutions = np.logspace(0, -9, 10)
resolutions = np.hstack((resolutions, [np.pi, 0.5, 0.27e-6, 13]))


@pytest.mark.parametrize("format", SUPPORTED_FORMATS.keys())
@pytest.mark.parametrize("resolution", resolutions)
@pytest.mark.parametrize("unit", SUPPORTED_VOLTAGE_SCALINGS)
def test_format_resolution_unit(tmpdir, format, resolution, unit):
    """Test different combinations of formats, resolutions, and units."""
    # Check whether this test will be numerically possible
    tmpdata = _scale_data_to_unit(data.copy(), [unit] * n_chans)
    tmpdata = tmpdata * np.atleast_2d((1 / resolution)).T
    _, dtype = _chk_fmt(format)
    data_will_fit = _check_data_in_range(tmpdata, dtype)

    kwargs = dict(data=data, sfreq=sfreq, ch_names=ch_names,
                  fname_base=fname, folder_out=tmpdir,
                  resolution=resolution, unit=unit,
                  fmt=format)

    if not data_will_fit:
        # End this test early
        match = f"can not be represented in '{format}' given"
        with pytest.raises(ValueError, match=match):
            write_brainvision(**kwargs)
        return

    write_brainvision(**kwargs)
    vhdr_fname = tmpdir / fname + '.vhdr'
    raw_written = mne.io.read_raw_brainvision(vhdr_fname=vhdr_fname,
                                              preload=True)

    # Check that the correct units were written in the BV file
    orig_units = [u for key, u in raw_written._orig_units.items()]
    assert len(set(orig_units)) == 1
    if unit is not None:
        assert orig_units[0] == unit.replace("u", "µ")

    # Check round trip of data: in binary_int16 format, the tolerance
    # is given by the lowest resolution
    if format == "binary_int16":
        absolute_tolerance = np.atleast_2d(resolution).min()
    else:
        absolute_tolerance = 0

    assert_allclose(data, raw_written.get_data(), atol=absolute_tolerance)


@pytest.mark.parametrize("sfreq", [100, 125, 128, 500, 512, 1000, 1024, 512.1])
def test_sampling_frequencies(tmpdir, sfreq):
    """Test different sampling frequencies."""
    # sampling frequency gets written as sampling interval
    write_brainvision(data=data, sfreq=sfreq, ch_names=ch_names,
                      fname_base=fname, folder_out=tmpdir)
    vhdr_fname = tmpdir / fname + '.vhdr'
    raw_written = mne.io.read_raw_brainvision(vhdr_fname=vhdr_fname,
                                              preload=True)
    assert_allclose(sfreq, raw_written.info['sfreq'])


@pytest.mark.parametrize("unit", SUPPORTED_VOLTAGE_SCALINGS)
def test_write_multiple_units(tmpdir, unit):
    """Test writing data with a list of units."""
    wrong_num_units = [unit]
    with pytest.raises(ValueError, match='Number of channels in unit'):
        write_brainvision(data=data, sfreq=sfreq, ch_names=ch_names,
                          fname_base=fname, folder_out=tmpdir,
                          unit=wrong_num_units)

    # write brain vision file
    vhdr_fname = tmpdir / fname + '.vhdr'
    write_brainvision(data=data, sfreq=sfreq, ch_names=ch_names,
                      fname_base=fname, folder_out=tmpdir,
                      unit=[unit] * n_chans)
    raw_written = mne.io.read_raw_brainvision(vhdr_fname=vhdr_fname,
                                              preload=True)

    # check round-trip works
    absolute_tolerance = 0
    assert_allclose(data, raw_written.get_data(), atol=absolute_tolerance)

    # Check that the correct units were written in the BV file
    orig_units = [u for key, u in raw_written._orig_units.items()]
    assert len(set(orig_units)) == 1
    assert orig_units[0] == unit.replace("u", "µ")

    # now write with different units across all channels
    other_unit = 'mV' if unit != 'mV' else 'V'
    units = [unit] * (n_chans // 2)
    units.extend([other_unit] * (n_chans // 2))

    # write file and read back in
    write_brainvision(data=data, sfreq=sfreq, ch_names=ch_names,
                      fname_base=fname, folder_out=tmpdir,
                      unit=units)
    raw_written = mne.io.read_raw_brainvision(vhdr_fname=vhdr_fname,
                                              preload=True)

    # Check that the correct units were written in the BV file
    orig_units = [u for key, u in raw_written._orig_units.items()]
    assert len(set(orig_units)) == 2
    assert all([orig_units[idx] == unit.replace("u", "µ")
                for idx in range(n_chans // 2)])
    assert all([orig_units[-idx] == other_unit.replace("u", "µ")
                for idx in range(1, n_chans // 2 + 1)])


def test_write_unsupported_units(tmpdir):
    """Test writing data with a list of possibly unsupported BV units."""
    unit = 'V'  # supported test unit
    units = [unit] * n_chans
    units[-1] = '°C'

    # write brain vision file
    vhdr_fname = tmpdir / (fname + '.vhdr')
    with pytest.warns(UserWarning, match='Encountered unsupported '
                                         'non-voltage unit'):
        write_brainvision(data=data, sfreq=sfreq, ch_names=ch_names,
                          fname_base=fname, folder_out=tmpdir,
                          unit=units)
    raw_written = mne.io.read_raw_brainvision(vhdr_fname=vhdr_fname,
                                              preload=True)

    # check round-trip works
    absolute_tolerance = 0
    assert_allclose(data, raw_written.get_data(), atol=absolute_tolerance)

    # Check that the correct units were written in the BV file
    orig_units = [u for key, u in raw_written._orig_units.items()]
    assert len(set(orig_units)) == 2
    assert all([orig_units[idx] == unit for idx in range(n_chans - 1)])
    assert orig_units[-1] == '°C'
