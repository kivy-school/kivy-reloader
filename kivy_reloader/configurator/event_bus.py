class _EventBus:
    def __init__(self):
        self._listeners = {}
        self._cards = {}

    def on(self, event, fn):
        self._listeners.setdefault(event, []).append(fn)

    def off(self, event, fn):
        listeners = self._listeners.get(event, [])
        if fn in listeners:
            listeners.remove(fn)

    def emit(self, event, **kwargs):
        for fn in list(self._listeners.get(event, [])):
            fn(**kwargs)

    def register_card(self, name, instance):
        self._cards[name] = instance
        self.emit('card_registered', name=name)

    def get_cards(self):
        return dict(self._cards)


EventBus = _EventBus()
