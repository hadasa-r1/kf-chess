import os


class AssetResolver:
    """Translates game tokens/states into sprite frame paths.

    Mirrors the adapter pattern already used in board/loaders.py: game logic
    tokens (e.g. "wK", "idle") stay untouched everywhere else, and only this
    class knows how they map onto the actual asset folder layout on disk.
    Callers that need to handle mismatched real folder/state names pass
    explicit `folder_map`/`state_map` overrides; without them, `resolve_frames`
    falls back to using the token/state itself as the folder name.
    """

    def __init__(self, pieces_dir, folder_map=None, state_map=None):
        self._pieces_dir = pieces_dir
        self._folder_map = folder_map or {}
        self._state_map = state_map or {}

    def resolve_frames(self, token, state):
        folder = self._folder_map.get(token, token)
        state_name = self._state_map.get(state, state)
        directory = f"{self._pieces_dir}/{folder}/{state_name}"

        if not os.path.isdir(directory):
            raise FileNotFoundError(f"Sprite folder not found: {directory}")

        frames = sorted(
            os.path.join(directory, name)
            for name in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, name))
        )
        if not frames:
            raise FileNotFoundError(f"No sprite frames found in: {directory}")

        return frames
