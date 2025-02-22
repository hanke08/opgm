import binascii
import pytest
import random
from unittest.mock import patch

from panda import Panda
from panda.python.spi import PandaSpiNackResponse

pytestmark = [
  pytest.mark.test_panda_types((Panda.HW_TYPE_TRES, ))
]

class TestSpi:
  def _ping(self, mocker, panda):
    # should work with no retries
    spy = mocker.spy(panda._handle, '_wait_for_ack')
    panda.health()
    assert spy.call_count == 2
    mocker.stop(spy)

  @pytest.mark.expected_logs(2)
  def test_protocol_version(self, p):
    for bootstub in (False, True):
      p.reset(enter_bootstub=bootstub)
      v = p._handle.get_protocol_version()

      uid = binascii.hexlify(v[:12]).decode()
      assert uid == p.get_uid()

      hwtype = v[12]
      assert hwtype == ord(p.get_type())

      bstub = v[13]
      assert bstub == (0xEE if bootstub else 0xCC)

      assert v[14:] == b"\x01"

  def test_all_comm_types(self, mocker, p):
    spy = mocker.spy(p._handle, '_wait_for_ack')

    # controlRead + controlWrite
    p.health()
    p.can_clear(0)
    assert spy.call_count == 2*2

    # bulkRead + bulkWrite
    p.can_recv()
    p.can_send(0x123, b"somedata", 0)
    assert spy.call_count == 2*4

  def test_bad_header(self, mocker, p):
    with patch('panda.python.spi.SYNC', return_value=0):
      with pytest.raises(PandaSpiNackResponse):
        p._handle.controlRead(Panda.REQUEST_IN, 0xd2, 0, 0, p.HEALTH_STRUCT.size, timeout=50)
    self._ping(mocker, p)

  def test_bad_checksum(self, mocker, p):
    cnt = p.health()['spi_checksum_error_count']
    with patch('panda.python.spi.PandaSpiHandle._calc_checksum', return_value=0):
      with pytest.raises(PandaSpiNackResponse):
        p._handle.controlRead(Panda.REQUEST_IN, 0xd2, 0, 0, p.HEALTH_STRUCT.size, timeout=50)
    self._ping(mocker, p)
    assert (p.health()['spi_checksum_error_count'] - cnt) > 0

  def test_non_existent_endpoint(self, mocker, p):
    for _ in range(10):
      ep = random.randint(4, 20)
      with pytest.raises(PandaSpiNackResponse):
        p._handle.bulkRead(ep, random.randint(1, 1000), timeout=35)

      self._ping(mocker, p)

      with pytest.raises(PandaSpiNackResponse):
        p._handle.bulkWrite(ep, b"abc", timeout=35)

      self._ping(mocker, p)
