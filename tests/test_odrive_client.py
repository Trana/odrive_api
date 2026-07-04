from types import SimpleNamespace

from odrive_api.odrive_client import GET_VERSION_PAYLOAD_SIZE, ODriveClient


class ResponseBus:
    def __init__(self) -> None:
        self.pending = []
        self.sent = []

    def message_factory(self, **fields):
        return SimpleNamespace(**fields)

    def send(self, message) -> None:
        self.sent.append(message)
        self.pending.append(
            SimpleNamespace(
                arbitration_id=message.arbitration_id,
                is_remote_frame=False,
                data=bytes(range(GET_VERSION_PAYLOAD_SIZE)),
            )
        )

    def recv(self, timeout=None):
        if self.pending:
            return self.pending.pop(0)
        return None


def test_measure_response_time_sends_get_version_remote_frame():
    bus = ResponseBus()
    client = ODriveClient(bus, {}, {})

    samples = client.measure_response_time(43, sample_count=2, interval_s=0, timeout_s=0.01)

    assert len(samples) == 2
    assert all(sample is not None for sample in samples)
    assert len(bus.sent) == 2
    request = bus.sent[0]
    assert request.arbitration_id == (43 << 5)
    assert request.is_remote_frame is True
    assert request.dlc == GET_VERSION_PAYLOAD_SIZE
