from kivy_reloader.send_app_to_phone import build_usb_targets


def test_usb_targets_use_unique_host_ports_for_each_device():
    devices = [
        {
            'serial': 'phone-1',
            'model': 'same_model',
            'transport': 'usb',
        },
        {
            'serial': 'phone-2',
            'model': 'same_model',
            'transport': 'usb',
        },
    ]
    calls = []

    def forward(host_port, serial, remote_port):
        calls.append((host_port, serial, remote_port))
        return 0

    targets = build_usb_targets(
        devices,
        remote_port=8050,
        host_ip='127.0.0.1',
        forward=forward,
    )

    assert targets == [
        ('127.0.0.1', 8050, 'phone-1', 'same_model'),
        ('127.0.0.1', 8051, 'phone-2', 'same_model'),
    ]
    assert calls == [
        (8050, 'phone-1', 8050),
        (8051, 'phone-2', 8050),
    ]


def test_usb_targets_skip_devices_when_forwarding_fails():
    devices = [
        {'serial': 'phone-1', 'model': 'model-1', 'transport': 'usb'},
        {'serial': 'phone-2', 'model': 'model-2', 'transport': 'usb'},
    ]

    def forward(host_port, serial, remote_port):
        return 1 if serial == 'phone-1' else 0

    targets = build_usb_targets(
        devices,
        remote_port=8050,
        host_ip='127.0.0.1',
        forward=forward,
    )

    assert targets == [('127.0.0.1', 8051, 'phone-2', 'model-2')]
