class PieceSprites:
    def __init__(self, asset_resolver, cell_size):
        self._resolver = asset_resolver
        self._cell_size = cell_size
        self._cache = {}

    def get(self, token, state):
        key = (token, state)
        if key not in self._cache:
            paths = self._resolver.resolve_frames(token, state)
            from UI.img import Img
            self._cache[key] = [
                Img().read(path, size=(self._cell_size, self._cell_size))
                for path in paths
            ]
        return self._cache[key]
